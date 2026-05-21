"""
fireai/core/elevator_shunt_trip.py
===================================
Elevator Shunt-Trip Power Severance Auditor — CRITICAL LIFE-SAFETY MODULE.

When sprinklers are installed inside elevator hoistways or machine rooms,
NFPA 72 §21.4.1 and ASME A17.1 Rule 2.8.3.3 mandate that a dedicated heat
detector must be placed within 0.6 m (2 ft) of each sprinkler head, with a
temperature rating **at least 11.1 °C (20 °F) lower** than the sprinkler's
operating temperature.  This ensures the heat detector actuates BEFORE the
sprinkler discharges, triggering an immediate shunt-trip of the elevator's
main power breaker — preventing lethal electrocution of firefighters and
occupants from electrified water spray on live 480 V motor windings.

Code references:
  - NFPA 72-2022 §21.4.1  — Shunt trip requirement
  - NFPA 72-2022 §21.4.2  — Heat detector placement & rating
  - ASME A17.1 Rule 2.8.3.3 — Elevator safety
  - NFPA 13-2022           — Sprinkler requirements in elevator spaces

Provenance:
  Returns ``DecisionProvenance`` via the ``.new()`` factory when
  ``src.v8_core`` is available; degrades gracefully to plain dict otherwise.
"""
from __future__ import annotations

import hashlib
import math
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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

# The heat detector must actuate at least 20 °F (11.1 °C) BELOW the
# sprinkler's temperature rating per NFPA 72 §21.4.2.
SAFETY_GAP_C: float = 11.1

# Maximum permissible horizontal distance between a sprinkler head and its
# dedicated shunt-trip heat detector — 2 ft = 0.61 m per NFPA 72 §21.4.2.
MAX_HD_SPRINKLER_DISTANCE_M: float = 0.6

# Standard sprinkler temperature ratings (°C) per NFPA 13 Table 6.2.5.1
STANDARD_SPRINKLER_TEMPS_C: Dict[str, float] = {
    "ordinary": 68.3,       # 155 °F
    "intermediate": 93.3,   # 200 °F
    "high": 140.6,          # 286 °F
    "extra_high": 182.2,    # 360 °F
}

# Standard heat detector temperature ratings (°C) per UL 521
STANDARD_HD_TEMPS_C: Dict[str, float] = {
    "135F": 57.2,    # 135 °F — most common for shunt-trip
    "145F": 62.8,    # 145 °F
    "160F": 71.1,    # 160 °F
    "190F": 87.8,    # 190 °F
    "200F": 93.3,    # 200 °F
}

# Citations
_CITE_NFPA72_21_4_1 = "NFPA 72-2022 §21.4.1"
_CITE_NFPA72_21_4_2 = "NFPA 72-2022 §21.4.2"
_CITE_ASME_A17_1 = "ASME A17.1 Rule 2.8.3.3"


@dataclass(frozen=True)
class ShuntTripResult:
    """Structured result for a single sprinkler head's shunt-trip audit."""
    sprinkler_id: str
    room_id: str
    has_dedicated_hd: bool
    hd_distance_m: Optional[float]
    hd_temp_rating_C: Optional[float]
    required_hd_temp_C: float
    sprinkler_temp_C: float
    compliant: bool
    violation_description: Optional[str] = None


class ElevatorShuntTripAuditor:
    """Audits elevator spaces for mandatory shunt-trip heat detector
    compliance per NFPA 72 §21.4.1 / ASME A17.1 Rule 2.8.3.3.

    The auditor examines every sprinkler located inside an elevator hoistway
    or machine room and verifies:

      1. A dedicated heat detector exists within 0.6 m of the sprinkler.
      2. The heat detector's temperature rating is at least 11.1 °C
         (20 °F) lower than the sprinkler's temperature rating.

    When both conditions are met, the auditor generates a logic injection
    (``SHUNT_TRIP_POWER_DELAY_0s``) for the Sequence of Operations matrix
    to sever the elevator's main power breaker instantaneously.

    Usage::

        auditor = ElevatorShuntTripAuditor()
        result = auditor.audit_hoistway_machine_room(
            sprinkler_locations=sprinklers,
            heat_detector_locations=heat_detectors,
            elevator_spaces=elevator_room_ids,
        )
    """

    def __init__(self, safety_gap_C: float = SAFETY_GAP_C) -> None:
        """Initialise the auditor.

        Args:
            safety_gap_C: Minimum temperature gap (°C) between the heat
                detector and sprinkler ratings.  Defaults to 11.1 °C
                (20 °F) per NFPA 72 §21.4.2.
        """
        self.safety_gap_C = safety_gap_C

    def audit_hoistway_machine_room(
        self,
        sprinkler_locations: List[Dict[str, Any]],
        heat_detector_locations: List[Dict[str, Any]],
        elevator_spaces: List[str],
    ) -> Any:
        """Audit all sprinklers in elevator spaces for shunt-trip compliance.

        Args:
            sprinkler_locations: Each dict must have:
                - ``device_id`` (str): Sprinkler identifier.
                - ``room_id`` (str): Room identifier.
                - ``x``, ``y`` (float): 2D coordinates (metres).
                - ``temp_rating_C`` (float, optional): Sprinkler temperature
                  rating in °C.  Defaults to 68.3 °C (ordinary, 155 °F).
            heat_detector_locations: Each dict must have:
                - ``device_id`` (str): Heat detector identifier.
                - ``room_id`` (str): Room identifier.
                - ``x``, ``y`` (float): 2D coordinates (metres).
                - ``temp_rating_C`` (float, optional): Heat detector rating
                  in °C.  Defaults to 57.2 °C (135 °F).
            elevator_spaces: List of room IDs that are elevator hoistways
                or machine rooms (e.g. ``["ELEV-MR-01", "ELEV-HW-01"]``).

        Returns:
            ``DecisionProvenance`` if provenance module is available;
            otherwise a plain dict with the same structure.
        """
        violations: list = []
        injections: list = []
        detailed_results: List[ShuntTripResult] = []

        for sprinkler in sprinkler_locations:
            room_id = sprinkler.get("room_id", "")
            # ASME A17.1 Rule 2.8.3.3 applies ONLY inside elevator spaces
            if room_id not in elevator_spaces:
                continue

            spk_id = sprinkler.get("device_id", "UNKNOWN-SPK")
            spk_x = float(sprinkler.get("x", 0.0))
            spk_y = float(sprinkler.get("y", 0.0))
            spk_temp = float(sprinkler.get("temp_rating_C", 68.3))
            required_hd_temp = round(spk_temp - self.safety_gap_C, 1)

            # Find the closest heat detector in the same elevator space
            hd_found = False
            best_hd = None
            best_dist = float("inf")

            for hd in heat_detector_locations:
                if hd.get("room_id", "") != room_id:
                    continue
                hd_x = float(hd.get("x", 0.0))
                hd_y = float(hd.get("y", 0.0))
                dist = math.hypot(spk_x - hd_x, spk_y - hd_y)
                if dist < best_dist:
                    best_dist = dist
                    best_hd = hd

            if best_hd is not None and best_dist <= MAX_HD_SPRINKLER_DISTANCE_M:
                hd_found = True
                hd_id = best_hd.get("device_id", "UNKNOWN-HD")
                hd_temp = float(best_hd.get("temp_rating_C", 57.2))

                if hd_temp > required_hd_temp:
                    # Heat detector fires TOO LATE — sprinkler will burst
                    # before power is severed
                    desc = (
                        f"Heat Detector '{hd_id}' rating ({hd_temp:.1f}°C) "
                        f"is too high! Must actuate before Sprinkler "
                        f"'{spk_id}' ({spk_temp:.1f}°C) to shunt-trip the "
                        f"elevator power. Required max HD rating: "
                        f"{required_hd_temp:.1f}°C."
                    )
                    if Violation is not None:
                        violations.append(Violation(
                            severity="CRITICAL",
                            citation=f"{_CITE_NFPA72_21_4_1} / {_CITE_ASME_A17_1}",
                            description=desc,
                        ))
                    else:
                        violations.append({
                            "severity": "CRITICAL",
                            "citation": f"{_CITE_NFPA72_21_4_1} / {_CITE_ASME_A17_1}",
                            "description": desc,
                        })
                    logger.critical(desc)
                    detailed_results.append(ShuntTripResult(
                        sprinkler_id=spk_id,
                        room_id=room_id,
                        has_dedicated_hd=True,
                        hd_distance_m=round(best_dist, 4),
                        hd_temp_rating_C=hd_temp,
                        required_hd_temp_C=round(required_hd_temp, 1),
                        sprinkler_temp_C=spk_temp,
                        compliant=False,
                        violation_description=desc,
                    ))
                else:
                    # Correct: HD will fire before sprinkler → inject
                    # shunt-trip logic into the cause-and-effect matrix
                    injections.append({
                        "input": hd_id,
                        "action": "SHUNT_TRIP_POWER_DELAY_0s",
                        "target": f"ELEVATOR_BREAKER_{room_id}",
                    })
                    detailed_results.append(ShuntTripResult(
                        sprinkler_id=spk_id,
                        room_id=room_id,
                        has_dedicated_hd=True,
                        hd_distance_m=round(best_dist, 4),
                        hd_temp_rating_C=hd_temp,
                        required_hd_temp_C=round(required_hd_temp, 1),
                        sprinkler_temp_C=spk_temp,
                        compliant=True,
                    ))
            else:
                # FATAL OMISSION: No heat detector within range
                desc = (
                    f"FATAL OMISSION: Sprinkler '{spk_id}' at "
                    f"({spk_x:.1f}, {spk_y:.1f}) in Elevator Space "
                    f"'{room_id}' lacks dedicated Shunt-Trip Heat Detector "
                    f"within {MAX_HD_SPRINKLER_DISTANCE_M} m. "
                    f"Water on 480 V motor windings will cause lethal "
                    f"electrocution."
                )
                if Violation is not None:
                    violations.append(Violation(
                        severity="CRITICAL",
                        citation=_CITE_NFPA72_21_4_1,
                        description=desc,
                    ))
                else:
                    violations.append({
                        "severity": "CRITICAL",
                        "citation": _CITE_NFPA72_21_4_1,
                        "description": desc,
                    })
                logger.critical(desc)
                detailed_results.append(ShuntTripResult(
                    sprinkler_id=spk_id,
                    room_id=room_id,
                    has_dedicated_hd=False,
                    hd_distance_m=round(best_dist, 4) if best_hd else None,
                    hd_temp_rating_C=None,
                    required_hd_temp_C=round(required_hd_temp, 1),
                    sprinkler_temp_C=spk_temp,
                    compliant=False,
                    violation_description=desc,
                ))

        # Count sprinklers inside elevator spaces
        sprinklers_in_shaft = sum(
            1 for s in sprinkler_locations
            if s.get("room_id", "") in elevator_spaces
        )

        safe = len(violations) == 0

        # Build provenance result
        if DecisionProvenance is not None:
            try:
                rules = [
                    RuleApplied(
                        citation=_CITE_NFPA72_21_4_1,
                        constant_id="SHUNT_TRIP",
                        value_used=self.safety_gap_C,
                        unit="Celsius",
                    ),
                    RuleApplied(
                        citation=_CITE_NFPA72_21_4_2,
                        constant_id="HD_SPRINKLER_MAX_DISTANCE",
                        value_used=MAX_HD_SPRINKLER_DISTANCE_M,
                        unit="metres",
                    ),
                ]
                conf = ConfidenceScore(
                    input_quality_score=1.0,
                    rule_coverage=1.0,
                    geometry_certainty=1.0,
                    overall=ConfidenceLevel.HIGH if safe else ConfidenceLevel.LOW,
                )
                return DecisionProvenance.new(
                    decision_type="elevator_shunt_trip",
                    value={
                        "logic_injections": injections,
                        "safe": safe,
                        "detailed_results": [
                            {
                                "sprinkler_id": r.sprinkler_id,
                                "room_id": r.room_id,
                                "has_dedicated_hd": r.has_dedicated_hd,
                                "hd_distance_m": r.hd_distance_m,
                                "hd_temp_rating_C": r.hd_temp_rating_C,
                                "required_hd_temp_C": r.required_hd_temp_C,
                                "sprinkler_temp_C": r.sprinkler_temp_C,
                                "compliant": r.compliant,
                                "violation_description": r.violation_description,
                            }
                            for r in detailed_results
                        ],
                    },
                    inputs={
                        "sprinklers_in_shaft": sprinklers_in_shaft,
                        "heat_detectors_total": len(heat_detector_locations),
                        "elevator_spaces": len(elevator_spaces),
                    },
                    rules_applied=rules,
                    algorithm={"name": "AsmeShuntSync", "version": "v19"},
                    confidence=conf,
                    selected_because=(
                        "Required power severing to avoid lethal shock "
                        "before suppression discharge in electro-mechanical "
                        "shaft/rooms per NFPA 72 §21.4.1 / ASME A17.1"
                    ),
                    violations=violations if violations else None,
                )
            except Exception:
                pass

        # Fallback: plain dict
        return {
            "decision_type": "elevator_shunt_trip",
            "value": {
                "logic_injections": injections,
                "safe": safe,
                "detailed_results": [
                    {
                        "sprinkler_id": r.sprinkler_id,
                        "room_id": r.room_id,
                        "has_dedicated_hd": r.has_dedicated_hd,
                        "hd_distance_m": r.hd_distance_m,
                        "hd_temp_rating_C": r.hd_temp_rating_C,
                        "required_hd_temp_C": r.required_hd_temp_C,
                        "sprinkler_temp_C": r.sprinkler_temp_C,
                        "compliant": r.compliant,
                        "violation_description": r.violation_description,
                    }
                    for r in detailed_results
                ],
            },
            "inputs": {
                "sprinklers_in_shaft": sprinklers_in_shaft,
                "heat_detectors_total": len(heat_detector_locations),
                "elevator_spaces": len(elevator_spaces),
            },
            "safe": safe,
            "violations": violations,
        }


__all__ = [
    "ElevatorShuntTripAuditor",
    "ShuntTripResult",
    "SAFETY_GAP_C",
    "MAX_HD_SPRINKLER_DISTANCE_M",
    "STANDARD_SPRINKLER_TEMPS_C",
    "STANDARD_HD_TEMPS_C",
]
