"""
fireai/core/seismic_joint_penalyer.py
======================================
Seismic / Building Expansion Joint Routing Penalty Engine.

In seismically active zones and large-footprint buildings, structural
engineers design expansion joints and seismic separation joints to
accommodate thermal movement and differential seismic displacement.
Rigid conduit (EMT, RMC, IMC) that crosses these joints without
flexible fittings will be sheared off during building movement,
severing fire alarm circuits precisely when they are needed most.

This module analyses A* routing paths against declared structural
joint lines and:

  1. **Detects crossings** — every path segment that intersects a
     seismic/expansion joint boundary.
  2. **Flags violations** — rigid conduit crossing a joint without
     a designated flexible transition fitting.
  3. **Injects FLEXIBLE_JUNCTION_TIE elements** — for each crossing,
     a mandatory flexible conduit transition is added to the
     AutoDrafting output and Bill of Quantities (BOQ).
  4. **Applies routing penalties** — path cost is increased at joint
     crossings to discourage gratuitous crossings.

Code references:
  - NFPA 70 (NEC) §300.4(D) — Protection against physical damage
  - NFPA 70 (NEC) §250.98   — Bonding for other enclosures
  - IBC 2021 §1705.18       — Seismic resistance testing
  - ASCE 7-22 §13.6.6       — Architectural, mechanical, electrical
    components & systems in seismic design category C and above

Provenance:
  Returns ``DecisionProvenance`` via the ``.new()`` factory when
  ``src.v8_core`` is available; degrades gracefully to plain dict otherwise.
"""
from __future__ import annotations

import hashlib
import logging
import math
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

# Minimum offset distance (m) from a joint crossing for the flexible
# conduit transition zone
FLEXIBLE_TRANSITION_LENGTH_M: float = 0.6

# Cost penalty applied to A* grid cells that coincide with a joint line
JOINT_CROSSING_COST_PENALTY: float = 5000.0

# Citations
_CITE_NEC_300_4D = "NEC §300.4(D)"
_CITE_NEC_250_98 = "NEC §250.98"
_CITE_IBC_1705_18 = "IBC 2021 §1705.18"
_CITE_ASCE_7 = "ASCE 7-22 §13.6.6"


@dataclass(frozen=True)
class StructuralJoint:
    """Represents a seismic or expansion joint as a line segment.

    Attributes:
        joint_id: Unique identifier (e.g. "SJ-01", "EJ-03").
        start: (x, y) start point of the joint line (metres).
        end: (x, y) end point of the joint line (metres).
        joint_type: Either ``"seismic"`` or ``"expansion"``.
        expected_displacement_mm: Expected displacement across the joint
            in millimetres.  Used to size the flexible conduit length.
    """
    joint_id: str
    start: Tuple[float, float]
    end: Tuple[float, float]
    joint_type: str = "seismic"
    expected_displacement_mm: float = 25.0


@dataclass(frozen=True)
class JointCrossing:
    """Records a single path crossing of a structural joint.

    Attributes:
        joint_id: The structural joint being crossed.
        crossing_point: (x, y) location of the intersection.
        path_segment_index: Index of the path segment that crosses.
        requires_flexible: Whether a flexible transition is required
            (always True for detected crossings).
    """
    joint_id: str
    crossing_point: Tuple[float, float]
    path_segment_index: int
    requires_flexible: bool = True


@dataclass(frozen=True)
class FlexibleJunctionTie:
    """Represents a required flexible conduit transition at a joint crossing.

    Attributes:
        joint_id: The structural joint at which the transition is required.
        location: (x, y) centre of the flexible transition zone.
        conduit_type: Type of flexible conduit (e.g. "FMC", "LFMC").
        length_m: Required length of the flexible conduit section.
    """
    joint_id: str
    location: Tuple[float, float]
    conduit_type: str = "LFMC"
    length_m: float = FLEXIBLE_TRANSITION_LENGTH_M


def _segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float],
) -> Optional[Tuple[float, float]]:
    """Find the intersection point of two line segments.

    Uses the cross-product method.  Returns the (x, y) intersection
    point if the segments intersect, otherwise ``None``.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None  # Parallel or collinear

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return (round(ix, 4), round(iy, 4))

    return None


class SeismicJointPenalyer:
    """Detects and penalises fire-alarm routing paths that cross
    seismic or expansion joints without flexible conduit transitions.

    Usage::

        penalyer = SeismicJointPenalyer()
        result = penalyer.detect_structural_shearing(
            path=[(0,0), (5,0), (10,0), (15,0)],
            seismic_joints=[
                StructuralJoint("SJ-01", (10, -5), (10, 5), "seismic"),
            ],
        )
    """

    def __init__(
        self,
        crossing_cost_penalty: float = JOINT_CROSSING_COST_PENALTY,
        flexible_transition_length_m: float = FLEXIBLE_TRANSITION_LENGTH_M,
    ) -> None:
        """Initialise the penalyer.

        Args:
            crossing_cost_penalty: Cost penalty to apply at each joint
                crossing cell for A* routing.
            flexible_transition_length_m: Default length of the flexible
                conduit transition zone (metres).
        """
        self.crossing_cost_penalty = crossing_cost_penalty
        self.flexible_transition_length_m = flexible_transition_length_m

    def detect_structural_shearing(
        self,
        path: List[Tuple[float, float]],
        seismic_joints: List[StructuralJoint],
    ) -> Any:
        """Analyse a routing path for structural joint crossings.

        Each consecutive pair of points in *path* forms a line segment.
        Each *seismic_joints* entry defines a joint as a line segment.
        The module checks every path segment against every joint segment
        for intersections.

        Args:
            path: Ordered list of (x, y) waypoints forming the cable
                route (metres).
            seismic_joints: List of ``StructuralJoint`` objects defining
                the building's structural joints.

        Returns:
            ``DecisionProvenance`` if provenance module is available;
            otherwise a plain dict with the same structure.
        """
        violations: list = []
        crossings: List[JointCrossing] = []
        flexible_junctions: List[FlexibleJunctionTie] = []

        for seg_idx in range(len(path) - 1):
            p1 = path[seg_idx]
            p2 = path[seg_idx + 1]

            for joint in seismic_joints:
                intersection = _segments_intersect(
                    p1, p2, joint.start, joint.end,
                )
                if intersection is not None:
                    crossing = JointCrossing(
                        joint_id=joint.joint_id,
                        crossing_point=intersection,
                        path_segment_index=seg_idx,
                        requires_flexible=True,
                    )
                    crossings.append(crossing)

                    # Inject a flexible junction tie
                    # Flexible conduit length should accommodate the
                    # expected displacement (rule of thumb: 2× displacement)
                    flex_length = max(
                        self.flexible_transition_length_m,
                        (joint.expected_displacement_mm / 1000.0) * 2.0,
                    )
                    flexible_junctions.append(FlexibleJunctionTie(
                        joint_id=joint.joint_id,
                        location=intersection,
                        conduit_type="LFMC",
                        length_m=round(flex_length, 3),
                    ))

                    # Flag violation — rigid conduit across structural joint
                    desc = (
                        f"Fire-alarm cable path crosses "
                        f"{'seismic' if joint.joint_type == 'seismic' else 'expansion'} "
                        f"joint '{joint.joint_id}' at point "
                        f"({intersection[0]:.1f}, {intersection[1]:.1f}) "
                        f"without flexible conduit transition. "
                        f"Expected displacement: "
                        f"{joint.expected_displacement_mm:.0f} mm. "
                        f"Rigid EMT/RMC will shear during building movement, "
                        f"severing the circuit."
                    )
                    if Violation is not None:
                        violations.append(Violation(
                            severity="MAJOR",
                            citation=f"{_CITE_NEC_300_4D} / Structural Joint",
                            description=desc,
                        ))
                    else:
                        violations.append({
                            "severity": "MAJOR",
                            "citation": f"{_CITE_NEC_300_4D} / Structural Joint",
                            "description": desc,
                        })
                    logger.warning(desc)

        safe = len(violations) == 0

        # Build penalty grid cells (for integration with A* routing)
        penalty_cells: List[Dict[str, Any]] = []
        for joint in seismic_joints:
            # Rasterise the joint line onto a 0.25 m grid
            x1, y1 = joint.start
            x2, y2 = joint.end
            length = math.hypot(x2 - x1, y2 - y1)
            if length < 1e-6:
                continue
            steps = max(1, int(length / 0.25))
            for i in range(steps + 1):
                t = i / steps
                gx = round((x1 + t * (x2 - x1)) * 4) / 4  # snap to 0.25 m
                gy = round((y1 + t * (y2 - y1)) * 4) / 4
                penalty_cells.append({
                    "x": gx,
                    "y": gy,
                    "cost_penalty": self.crossing_cost_penalty,
                    "joint_id": joint.joint_id,
                })

        # Build provenance result
        if DecisionProvenance is not None:
            try:
                rules = [
                    RuleApplied(
                        citation=_CITE_NEC_300_4D,
                        constant_id="SEISMIC_JOINT_FLEXIBLE",
                        value_used=self.flexible_transition_length_m,
                        unit="metres",
                    ),
                    RuleApplied(
                        citation=_CITE_NEC_250_98,
                        constant_id="BONDING_JOINT",
                        value_used=1.0,
                        unit="BOOLEAN",
                    ),
                ]
                conf = ConfidenceScore(
                    input_quality_score=1.0,
                    rule_coverage=1.0,
                    geometry_certainty=1.0,
                    overall=ConfidenceLevel.HIGH if safe else ConfidenceLevel.LOW,
                )
                return DecisionProvenance.new(
                    decision_type="seismic_joint_routing",
                    value={
                        "crossings_detected": len(crossings),
                        "flexible_junctions": [
                            {
                                "joint_id": fj.joint_id,
                                "location": fj.location,
                                "conduit_type": fj.conduit_type,
                                "length_m": fj.length_m,
                            }
                            for fj in flexible_junctions
                        ],
                        "penalty_grid_cells": penalty_cells,
                        "safe": safe,
                    },
                    inputs={
                        "path_points": len(path),
                        "structural_joints": len(seismic_joints),
                    },
                    rules_applied=rules,
                    algorithm={"name": "StructuralShearDetector", "version": "v19"},
                    confidence=conf,
                    selected_because=(
                        "Fire-alarm circuits crossing structural joints "
                        "must use flexible conduit transitions to prevent "
                        "circuit shearing during seismic or thermal "
                        f"movement per {_CITE_NEC_300_4D}"
                    ),
                    violations=violations if violations else None,
                )
            except Exception:
                pass

        # Fallback: plain dict
        return {
            "decision_type": "seismic_joint_routing",
            "value": {
                "crossings_detected": len(crossings),
                "flexible_junctions": [
                    {
                        "joint_id": fj.joint_id,
                        "location": fj.location,
                        "conduit_type": fj.conduit_type,
                        "length_m": fj.length_m,
                    }
                    for fj in flexible_junctions
                ],
                "safe": safe,
            },
            "inputs": {
                "path_points": len(path),
                "structural_joints": len(seismic_joints),
            },
            "safe": safe,
            "violations": violations,
        }


__all__ = [
    "SeismicJointPenalyer",
    "StructuralJoint",
    "JointCrossing",
    "FlexibleJunctionTie",
    "JOINT_CROSSING_COST_PENALTY",
    "FLEXIBLE_TRANSITION_LENGTH_M",
    "_segments_intersect",
]
