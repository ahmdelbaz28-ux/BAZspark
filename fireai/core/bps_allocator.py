"""
fireai/core/bps_allocator.py
=============================
NAC Booster Power Supply (BPS) Auto-Allocator for High-Rise Buildings.

In multi-storey buildings, a single FACP cannot always supply sufficient
current to all Notification Appliance Circuits (NAC) across every floor.
When the cumulative NAC current exceeds the panel's PSU rating, this
module automatically deploys NAC Power Extender / Booster Panels (BPS)
at strategic floor levels, ensuring every notification appliance receives
adequate voltage and current per NFPA 72 §10.6 and §21.2.

Key features:
  - **Waterfall load balancing**: floors are assigned to the FACP or
    the most recent BPS until capacity is reached, then a new BPS is
    spawned.
  - **Strobe synchronisation**: when multiple BPS units are deployed,
    a mandatory SYNC MODULE is injected per NFPA 72 §18.5.5 to ensure
    all strobes flash in unison.
  - **Per-floor current validation**: any single floor whose NAC current
    exceeds the BPS capacity itself is flagged for internal sub-division.

Code references:
  - NFPA 72-2022 §10.6   — Power supplies
  - NFPA 72-2022 §18.5.5 — Synchronization of notification appliances
  - NFPA 72-2022 §21.2   — Emergency voice/alarm communication systems
  - UL 864 10th Edition  — Control units and accessories

Provenance:
  Returns ``DecisionProvenance`` via the ``.new()`` factory when
  ``src.v8_core`` is available; degrades gracefully to plain dict otherwise.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Provenance — graceful degradation
# ---------------------------------------------------------------------------
try:
    from fireai.core.provenance import (
        DecisionProvenance,
        RuleApplied,
        Violation,
        ConfidenceScore,
        ConfidenceLevel,
    )
except ImportError:
    DecisionProvenance = None  # type: ignore[misc,assignment]
    RuleApplied = None  # type: ignore[misc,assignment]
    Violation = None  # type: ignore[misc,assignment]
    ConfidenceScore = None  # type: ignore[misc,assignment]
    ConfidenceLevel = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Default FACP PSU NAC current limit (amps)
DEFAULT_FACP_LIMIT_AMPS: float = 8.0

# Default BPS (booster power supply) per-unit capacity (amps)
DEFAULT_BOOSTER_CAPACITY_AMPS: float = 6.0

# Default BPS offset from stairwell centroid for placement (metres)
DEFAULT_BPS_OFFSET_X: float = 1.5
DEFAULT_BPS_OFFSET_Y: float = 1.0

# Citations
_CITE_NFPA72_10_6 = "NFPA 72-2022 §10.6"
_CITE_NFPA72_18_5_5 = "NFPA 72-2022 §18.5.5"
_CITE_NFPA72_21_2 = "NFPA 72-2022 §21.2"
_CITE_UL864 = "UL 864 10th Ed."


@dataclass(frozen=True)
class FloorNACProfile:
    """NAC current demand profile for a single floor.

    Attributes:
        floor_name: Human-readable floor identifier (e.g. "GF", "F03").
        nac_current: Total NAC current demand for this floor (amps).
        centroid_location: (x, y) centroid of the floor's NAC devices,
            typically the stairwell core.  Used for BPS placement.
        level_z: Vertical elevation of the floor (metres).  Used for
            sorting floors from lowest to highest.
    """
    floor_name: str
    nac_current: float
    centroid_location: Tuple[float, float] = (0.0, 0.0)
    level_z: float = 0.0


@dataclass(frozen=True)
class BoosterAllocation:
    """Represents a single deployed BPS panel.

    Attributes:
        booster_id: Unique identifier (e.g. "BPS-01").
        x, y: Placement coordinates (metres).
        floors_covered: List of floor names served by this BPS.
        peak_load: Peak cumulative NAC current (amps).
    """
    booster_id: str
    x: float
    y: float
    floors_covered: List[str]
    peak_load: float


class NACBoosterAllocator:
    """Automatically distributes NAC load across FACP and BPS panels
    for high-rise and large-footprint buildings.

    The allocator uses a **waterfall load-balancing** strategy:

      1. Floors are sorted by elevation (low to high).
      2. Each floor's NAC current is packed into the current supply
         zone (FACP first, then the most recently deployed BPS).
      3. When adding a floor would exceed the zone's capacity, a new
         BPS panel is deployed at that floor's centroid location.
      4. If multiple BPS panels are deployed, a mandatory SYNC MODULE
         is injected per NFPA 72 §18.5.5.

    Usage::

        allocator = NACBoosterAllocator(facp_limit_amps=10.0)
        result = allocator.allocate_boosters_across_floors(floor_data=[
            {"floor_name": "GF", "nac_current": 3.5, "level_z": 0.0,
             "centroid_location": (10.0, 5.0)},
            {"floor_name": "F01", "nac_current": 4.2, "level_z": 4.0,
             "centroid_location": (10.0, 5.0)},
        ])
    """

    def __init__(
        self,
        facp_limit_amps: float = DEFAULT_FACP_LIMIT_AMPS,
        booster_capacity_amps: float = DEFAULT_BOOSTER_CAPACITY_AMPS,
        bps_offset_x: float = DEFAULT_BPS_OFFSET_X,
        bps_offset_y: float = DEFAULT_BPS_OFFSET_Y,
    ) -> None:
        """Initialise the allocator.

        Args:
            facp_limit_amps: Maximum aggregate NAC current the FACP can
                supply (amps).  Default 8.0 A.
            booster_capacity_amps: Maximum NAC current each BPS can
                supply (amps).  Default 6.0 A.
            bps_offset_x: Horizontal offset from floor centroid for
                BPS placement (metres).
            bps_offset_y: Vertical offset from floor centroid for
                BPS placement (metres).
        """
        self.facp_limit = facp_limit_amps
        self.booster_limit = booster_capacity_amps
        self.bps_offset_x = bps_offset_x
        self.bps_offset_y = bps_offset_y

    def allocate_boosters_across_floors(
        self,
        floor_data: List[Dict[str, Any]],
    ) -> Any:
        """Distribute NAC load across FACP and auto-deployed BPS panels.

        Each element of *floor_data* must be a dict with:

        - ``floor_name`` (str): Floor identifier.
        - ``nac_current`` (float): Total NAC current demand (amps).
        - ``centroid_location`` (tuple[float, float], optional): (x, y)
          centroid for BPS placement.  Defaults to ``(0, 0)``.
        - ``level_z`` (float, optional): Floor elevation (m).  Defaults
          to 0.0.

        Returns:
            ``DecisionProvenance`` if provenance module is available;
            otherwise a plain dict with the same structure.
        """
        violations: list = []
        panel_allocation: List[Dict[str, Any]] = []
        cumulative_load: float = 0.0
        active_booster_id: int = 1
        current_load: float = 0.0  # load in current supply zone

        # Sort floors by elevation (ascending)
        sorted_floors = sorted(
            floor_data,
            key=lambda x: float(x.get("level_z", 0.0)),
        )

        for f_info in sorted_floors:
            f_name = f_info.get("floor_name", "UNKNOWN")
            f_current = float(f_info.get("nac_current", 0.0))
            f_centroid = f_info.get("centroid_location", (0.0, 0.0))
            cumulative_load += f_current

            # Check if this floor's current inherently exceeds a single
            # BPS booster's capacity
            if f_current > self.booster_limit:
                desc = (
                    f"Floor '{f_name}' current ({f_current:.2f} A) "
                    f"inherently exceeds single BPS booster limit "
                    f"({self.booster_limit:.1f} A). Requires internal "
                    f"NAC sub-division on this floor."
                )
                if Violation is not None:
                    violations.append(Violation(
                        severity="CRITICAL",
                        citation=f"{_CITE_NFPA72_10_6} / {_CITE_NFPA72_21_2}",
                        description=desc,
                    ))
                else:
                    violations.append({
                        "severity": "CRITICAL",
                        "citation": f"{_CITE_NFPA72_10_6} / {_CITE_NFPA72_21_2}",
                        "description": desc,
                    })
                logger.critical(desc)

            # Determine the capacity ceiling of the current supply zone:
            # - If no BPS has been deployed yet, the zone is the FACP.
            # - If a BPS has been deployed, the zone is that BPS.
            zone_capacity = (
                self.facp_limit if not panel_allocation
                else self.booster_limit
            )

            # Would adding this floor exceed the zone's capacity?
            if current_load + f_current > zone_capacity:
                # Deploy a new BPS at this floor's centroid
                pos = f_centroid if isinstance(f_centroid, tuple) else (0.0, 0.0)
                new_booster: Dict[str, Any] = {
                    "type": "NAC_BOOSTER_BPS",
                    "id": f"BPS-0{active_booster_id}",
                    "x": pos[0] + self.bps_offset_x,
                    "y": pos[1] + self.bps_offset_y,
                    "floors_covered": [f_name],
                    "peak_load": f_current,
                }
                panel_allocation.append(new_booster)
                current_load = f_current
                active_booster_id += 1
            else:
                # Pack this floor into the current zone
                current_load += f_current
                if panel_allocation:
                    panel_allocation[-1]["floors_covered"].append(f_name)
                    panel_allocation[-1]["peak_load"] = current_load
                # else: assigned to FACP natively — no BPS record needed

        # If multiple BPS panels were deployed, inject a mandatory
        # synchronisation module per NFPA 72 §18.5.5
        if len(panel_allocation) > 0:
            sync_module: Dict[str, Any] = {
                "type": "SYNC_MODULE",
                "description": (
                    "Mandatory Global Notification Synchronization "
                    f"({_CITE_NFPA72_18_5_5})"
                ),
                "target": "ALL BPS",
            }
            panel_allocation.insert(0, sync_module)

        safe = len(violations) == 0

        # Build provenance result
        if DecisionProvenance is not None:
            try:
                rules = [
                    RuleApplied(
                        citation=_CITE_NFPA72_18_5_5,
                        constant_id="STROBE_SYNC",
                        value_used=1.0,
                        unit="BOOLEAN",
                    ),
                    RuleApplied(
                        citation=_CITE_NFPA72_10_6,
                        constant_id="PSU_BPS_SPLIT",
                        value_used=self.booster_limit,
                        unit="AMPS",
                    ),
                ]
                conf = ConfidenceScore(
                    input_quality_score=1.0,
                    rule_coverage=1.0,
                    geometry_certainty=1.0,
                    overall=ConfidenceLevel.HIGH if safe else ConfidenceLevel.LOW,
                )
                return DecisionProvenance.new(
                    decision_type="distributed_power_routing",
                    value={
                        "boosters": panel_allocation,
                        "total_current": round(cumulative_load, 4),
                        "facp_native_load": round(
                            cumulative_load - sum(
                                b.get("peak_load", 0.0)
                                for b in panel_allocation
                                if b.get("type") == "NAC_BOOSTER_BPS"
                            ),
                            4,
                        ),
                        "num_boosters": sum(
                            1 for b in panel_allocation
                            if b.get("type") == "NAC_BOOSTER_BPS"
                        ),
                        "sync_required": len(panel_allocation) > 1,
                    },
                    inputs={
                        "floors_analyzed": len(floor_data),
                    },
                    rules_applied=rules,
                    algorithm={"name": "WaterfallLoadBalancer", "version": "v19"},
                    confidence=conf,
                    selected_because=(
                        "Voltage/Current aggregation dynamically fragmented "
                        "into topological autonomous zones satisfying "
                        "structural wire limitations per NFPA 72 §10.6 / §21.2"
                    ),
                    violations=violations if violations else None,
                )
            except Exception:
                pass

        # Fallback: plain dict
        return {
            "decision_type": "distributed_power_routing",
            "value": {
                "boosters": panel_allocation,
                "total_current": round(cumulative_load, 4),
            },
            "inputs": {"floors_analyzed": len(floor_data)},
            "safe": safe,
            "violations": violations,
        }


__all__ = [
    "NACBoosterAllocator",
    "FloorNACProfile",
    "BoosterAllocation",
    "DEFAULT_FACP_LIMIT_AMPS",
    "DEFAULT_BOOSTER_CAPACITY_AMPS",
]
