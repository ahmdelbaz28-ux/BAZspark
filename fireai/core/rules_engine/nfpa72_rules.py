"""
FireAI Rules Engine — NFPA 72 Declarative Rule Definitions
============================================================

Defines NFPA 72 fire alarm code compliance rules as declarative
Rule objects instead of scattered Python if/else logic.

BENEFITS:
1. Rules are auditable — every rule has an NFPA section reference
2. Rules are reviewable — an FPE can read the rules without reading code
3. Rules are maintainable — add/modify rules without touching engine code
4. Rules are traceable — every decision is logged with evidence
5. Rules are composable — join conditions detect cross-rule interactions

CURRENT COVERAGE (to be expanded incrementally):
- Ceiling height → spacing determination
- Spacing → coverage radius
- Coverage radius → detector count
- Wall distance requirements
- Dead air space constraints
- Duct detector requirements
- Elevator recall requirements
- Corridor-specific spacing

Reference: NFPA 72-2022 (National Fire Alarm and Signaling Code)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from fireai.core.rules_engine.engine import (
    Fact,
    Rule,
    RulePriority,
    RuleResult,
    RulesEngine,
)


# ═══════════════════════════════════════════════════════════════════════════════
# RULE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _spacing_for_ceiling_height(
    ceiling_height_m: float,
    detector_type: str,
) -> float:
    """Determine NFPA 72 listed spacing based on ceiling height.

    Reference: NFPA 72-2022 Table 17.6.3.1
    """
    if detector_type == "smoke":
        if ceiling_height_m <= 3.0:
            return 9.10   # 30 ft
        elif ceiling_height_m <= 3.9:
            return 8.20   # 27 ft
        elif ceiling_height_m <= 4.9:
            return 7.30   # 24 ft
        elif ceiling_height_m <= 6.1:
            return 6.40   # 21 ft
        elif ceiling_height_m <= 7.6:
            return 5.50   # 18 ft
        elif ceiling_height_m <= 9.1:
            return 4.60   # 15 ft
        elif ceiling_height_m <= 10.7:
            return 3.70   # 12 ft
        elif ceiling_height_m <= 12.2:
            return 3.00   # 10 ft
        else:
            return 3.00   # Conservative — AHJ review required
    elif detector_type == "heat":
        if ceiling_height_m <= 3.0:
            return 6.10   # 20 ft
        elif ceiling_height_m <= 3.9:
            return 5.50   # 18 ft
        elif ceiling_height_m <= 4.9:
            return 4.90   # 16 ft
        elif ceiling_height_m <= 6.1:
            return 4.30   # 14 ft
        elif ceiling_height_m <= 7.6:
            return 3.70   # 12 ft
        elif ceiling_height_m <= 9.1:
            return 3.00   # 10 ft
        else:
            return 3.00   # Conservative — AHJ review required
    else:
        return 9.10  # Default to smoke spacing


def _coverage_radius(spacing_m: float) -> float:
    """R = 0.7 × S per NFPA 72 §17.7.4.2.3.1."""
    return 0.7 * spacing_m


def _wall_distance_max(spacing_m: float) -> float:
    """Maximum distance from wall = S/2 per NFPA 72 §17.6.3.1."""
    return spacing_m / 2.0


def _min_detectors_for_room(
    room_area_m2: float,
    coverage_radius_m: float,
) -> int:
    """Minimum detectors for a room based on coverage area.

    Each detector covers a circle of radius R.
    Conservative estimate: ceiling(area / (pi * R^2)).
    """
    if coverage_radius_m <= 0:
        return 1
    coverage_area = math.pi * coverage_radius_m ** 2
    return max(1, math.ceil(room_area_m2 / coverage_area))


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — CEILING HEIGHT & SPACING
# ═══════════════════════════════════════════════════════════════════════════════

RULE_CEILING_HEIGHT_SPACING = Rule(
    rule_id="NFPA72-001",
    rule_name="Ceiling Height Determines Detector Spacing",
    nfpa_reference="NFPA 72 §17.6.3.1, Table 17.6.3.1",
    priority=RulePriority.COMPLIANCE_CHECK,
    description=(
        "Detector listed spacing is reduced as ceiling height increases. "
        "Higher ceilings delay smoke/heat arrival, requiring tighter spacing."
    ),
    fact_type="room",
    condition=lambda f: (
        "ceiling_height_m" in f.properties
        and "detector_type" in f.properties
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-001",
            rule_name="Ceiling Height Determines Detector Spacing",
            nfpa_reference="NFPA 72 §17.6.3.1, Table 17.6.3.1",
            severity=RulePriority.COMPLIANCE_CHECK,
            message=(
                f"Room '{facts[0].properties.get('room_id', '?')}': "
                f"ceiling_height={facts[0].properties['ceiling_height_m']:.1f}m, "
                f"detector_type={facts[0].properties['detector_type']}, "
                f"listed_spacing={_spacing_for_ceiling_height(facts[0].properties['ceiling_height_m'], facts[0].properties['detector_type']):.2f}m"
            ),
            asserted_facts=[
                Fact(
                    fact_type="spacing",
                    properties={
                        "room_id": facts[0].properties.get("room_id", ""),
                        "detector_type": facts[0].properties["detector_type"],
                        "ceiling_height_m": facts[0].properties["ceiling_height_m"],
                        "listed_spacing_m": _spacing_for_ceiling_height(
                            facts[0].properties["ceiling_height_m"],
                            facts[0].properties["detector_type"],
                        ),
                        "coverage_radius_m": _coverage_radius(
                            _spacing_for_ceiling_height(
                                facts[0].properties["ceiling_height_m"],
                                facts[0].properties["detector_type"],
                            )
                        ),
                        "wall_distance_max_m": _wall_distance_max(
                            _spacing_for_ceiling_height(
                                facts[0].properties["ceiling_height_m"],
                                facts[0].properties["detector_type"],
                            )
                        ),
                    },
                    source="derived",
                    nfpa_reference="NFPA 72 §17.6.3.1",
                )
            ],
            matched_facts=[f.fact_id for f in facts],
        )
    ],
    derives_facts=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — COVERAGE RADIUS
# ═══════════════════════════════════════════════════════════════════════════════

RULE_COVERAGE_RADIUS = Rule(
    rule_id="NFPA72-002",
    rule_name="Coverage Radius = 0.7 × Spacing",
    nfpa_reference="NFPA 72 §17.7.4.2.3.1",
    priority=RulePriority.COMPLIANCE_CHECK,
    description=(
        "The coverage radius R = 0.7 × S, where S is the listed spacing. "
        "This ensures every point on the ceiling is within R of a detector."
    ),
    fact_type="spacing",
    condition=lambda f: "listed_spacing_m" in f.properties,
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-002",
            rule_name="Coverage Radius = 0.7 × Spacing",
            nfpa_reference="NFPA 72 §17.7.4.2.3.1",
            severity=RulePriority.COMPLIANCE_CHECK,
            message=(
                f"Room '{facts[0].properties.get('room_id', '?')}': "
                f"R = 0.7 × {facts[0].properties['listed_spacing_m']:.2f}m "
                f"= {_coverage_radius(facts[0].properties['listed_spacing_m']):.2f}m"
            ),
            asserted_facts=[
                Fact(
                    fact_type="coverage",
                    properties={
                        "room_id": facts[0].properties.get("room_id", ""),
                        "detector_type": facts[0].properties.get("detector_type", ""),
                        "R_m": _coverage_radius(
                            facts[0].properties["listed_spacing_m"]
                        ),
                        "S_m": facts[0].properties["listed_spacing_m"],
                    },
                    source="derived",
                    nfpa_reference="NFPA 72 §17.7.4.2.3.1",
                )
            ],
            matched_facts=[f.fact_id for f in facts],
        )
    ],
    derives_facts=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — CEILING HEIGHT EXCEEDS TABLE RANGE
# ═══════════════════════════════════════════════════════════════════════════════

RULE_CEILING_HEIGHT_EXCEEDS_TABLE = Rule(
    rule_id="NFPA72-003",
    rule_name="Ceiling Height Exceeds NFPA 72 Table Range",
    nfpa_reference="NFPA 72 §17.6.3.1, Table 17.6.3.1 Note",
    priority=RulePriority.CRITICAL_SAFETY,
    description=(
        "When ceiling height exceeds 12.2m (40ft), the NFPA 72 spacing "
        "table no longer applies. Engineering judgment and AHJ review "
        "are required. The system uses conservative 3.0m spacing but "
        "flags this for mandatory professional review."
    ),
    fact_type="room",
    condition=lambda f: (
        "ceiling_height_m" in f.properties
        and f.properties["ceiling_height_m"] > 12.2
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-003",
            rule_name="Ceiling Height Exceeds NFPA 72 Table Range",
            nfpa_reference="NFPA 72 §17.6.3.1, Table 17.6.3.1 Note",
            severity=RulePriority.CRITICAL_SAFETY,
            message=(
                f"CRITICAL: Room '{facts[0].properties.get('room_id', '?')}' "
                f"ceiling height {facts[0].properties['ceiling_height_m']:.1f}m "
                f"exceeds NFPA 72 Table 17.6.3.1 maximum (12.2m/40ft). "
                f"AHJ review is MANDATORY. Using conservative 3.0m spacing."
            ),
            asserted_facts=[
                Fact(
                    fact_type="safety_flag",
                    properties={
                        "room_id": facts[0].properties.get("room_id", ""),
                        "flag_type": "AHJ_REVIEW_REQUIRED",
                        "reason": "ceiling_height_exceeds_table",
                        "ceiling_height_m": facts[0].properties["ceiling_height_m"],
                    },
                    source="derived",
                    nfpa_reference="NFPA 72 §17.6.3.1",
                )
            ],
            matched_facts=[f.fact_id for f in facts],
        )
    ],
    derives_facts=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — DEAD AIR SPACE
# ═══════════════════════════════════════════════════════════════════════════════

RULE_DEAD_AIR_SPACE = Rule(
    rule_id="NFPA72-004",
    rule_name="Dead Air Space — Detector Too Close to Wall",
    nfpa_reference="NFPA 72 §17.6.3.1.1",
    priority=RulePriority.SAFETY_VIOLATION,
    description=(
        "Detectors must be at least 0.1m (4 inches) from the wall "
        "per NFPA 72 §17.6.3.1.1. Dead air space near walls prevents "
        "smoke from reaching the detector."
    ),
    fact_type="detector",
    condition=lambda f: (
        "distance_to_wall_m" in f.properties
        and f.properties["distance_to_wall_m"] < 0.1
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-004",
            rule_name="Dead Air Space — Detector Too Close to Wall",
            nfpa_reference="NFPA 72 §17.6.3.1.1",
            severity=RulePriority.SAFETY_VIOLATION,
            message=(
                f"VIOLATION: Detector '{facts[0].properties.get('detector_id', '?')}' "
                f"is {facts[0].properties['distance_to_wall_m']:.3f}m from wall "
                f"(minimum 0.1m per NFPA 72 §17.6.3.1.1). Dead air space "
                f"prevents smoke detection."
            ),
            matched_facts=[f.fact_id for f in facts],
        )
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — WALL DISTANCE
# ═══════════════════════════════════════════════════════════════════════════════

RULE_WALL_DISTANCE_EXCEEDED = Rule(
    rule_id="NFPA72-005",
    rule_name="Detector Too Far From Wall",
    nfpa_reference="NFPA 72 §17.6.3.1",
    priority=RulePriority.SAFETY_VIOLATION,
    description=(
        "No point on the ceiling shall be more than S/2 from the "
        "nearest detector. This means detectors must be within "
        "S/2 of all walls."
    ),
    fact_type="detector",
    condition=lambda f: (
        "distance_to_wall_m" in f.properties
        and "wall_distance_max_m" in f.properties
        and f.properties["distance_to_wall_m"] > f.properties["wall_distance_max_m"]
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-005",
            rule_name="Detector Too Far From Wall",
            nfpa_reference="NFPA 72 §17.6.3.1",
            severity=RulePriority.SAFETY_VIOLATION,
            message=(
                f"VIOLATION: Detector '{facts[0].properties.get('detector_id', '?')}' "
                f"is {facts[0].properties['distance_to_wall_m']:.2f}m from wall "
                f"(max {facts[0].properties['wall_distance_max_m']:.2f}m = S/2 "
                f"per NFPA 72 §17.6.3.1). Wall coverage gap detected."
            ),
            matched_facts=[f.fact_id for f in facts],
        )
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — DUCT DETECTOR REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════

RULE_DUCT_DETECTOR_REQUIRED = Rule(
    rule_id="NFPA72-006",
    rule_name="Duct Smoke Detector Required on Air Handler",
    nfpa_reference="NFPA 72 §17.7.5.1, §17.7.5.2",
    priority=RulePriority.SAFETY_VIOLATION,
    description=(
        "Smoke detectors shall be installed in air supply systems "
        "with a design capacity greater than 2000 CFM. For systems "
        "greater than 15000 CFM, detectors at both supply and return "
        "are required."
    ),
    fact_type="hvac_unit",
    condition=lambda f: (
        "cfm" in f.properties
        and f.properties["cfm"] > 2000
        and not f.properties.get("has_duct_detector", False)
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-006",
            rule_name="Duct Smoke Detector Required on Air Handler",
            nfpa_reference="NFPA 72 §17.7.5.1",
            severity=RulePriority.SAFETY_VIOLATION,
            message=(
                f"VIOLATION: HVAC unit '{facts[0].properties.get('unit_id', '?')}' "
                f"has {facts[0].properties['cfm']} CFM (> 2000 CFM threshold) "
                f"but no duct smoke detector. NFPA 72 §17.7.5.1 requires "
                f"smoke detection on air handlers > 2000 CFM."
                + (
                    " Supply AND return detectors required (> 15000 CFM)."
                    if facts[0].properties["cfm"] > 15000
                    else ""
                )
            ),
            asserted_facts=[
                Fact(
                    fact_type="required_device",
                    properties={
                        "location_id": facts[0].properties.get("unit_id", ""),
                        "device_type": "duct_smoke_detector",
                        "reason": "hvac_cfm_exceeds_2000",
                        "cfm": facts[0].properties["cfm"],
                        "needs_return_detector": facts[0].properties["cfm"] > 15000,
                    },
                    source="derived",
                    nfpa_reference="NFPA 72 §17.7.5.1",
                )
            ],
            matched_facts=[f.fact_id for f in facts],
        )
    ],
    derives_facts=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — ELEVATOR RECALL
# ═══════════════════════════════════════════════════════════════════════════════

RULE_ELEVATOR_RECALL = Rule(
    rule_id="NFPA72-007",
    rule_name="Elevator Recall Smoke Detector Required",
    nfpa_reference="NFPA 72 §21.3.3",
    priority=RulePriority.SAFETY_VIOLATION,
    description=(
        "Smoke detectors shall be installed in each elevator lobby "
        "and at the top of each elevator hoistway per NFPA 72 §21.3.3."
    ),
    fact_type="elevator",
    condition=lambda f: (
        f.properties.get("has_lobby_detector", False) is False
        or f.properties.get("has_hoistway_detector", False) is False
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-007",
            rule_name="Elevator Recall Smoke Detector Required",
            nfpa_reference="NFPA 72 §21.3.3",
            severity=RulePriority.SAFETY_VIOLATION,
            message=(
                f"VIOLATION: Elevator '{facts[0].properties.get('elevator_id', '?')}' "
                f"missing detectors — "
                f"lobby_detector={facts[0].properties.get('has_lobby_detector', False)}, "
                f"hoistway_detector={facts[0].properties.get('has_hoistway_detector', False)}. "
                f"NFPA 72 §21.3.3 requires both."
            ),
            matched_facts=[f.fact_id for f in facts],
        )
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — CORRIDOR SPACING
# ═══════════════════════════════════════════════════════════════════════════════

RULE_CORRIDOR_SPACING = Rule(
    rule_id="NFPA72-008",
    rule_name="Corridor Reduced Spacing for Narrow Spaces",
    nfpa_reference="NFPA 72 §17.7.3.1",
    priority=RulePriority.COMPLIANCE_CHECK,
    description=(
        "In corridors and narrow spaces, detector spacing along the "
        "corridor shall not exceed the listed spacing, and detectors "
        "shall be within half the listed spacing of the corridor end."
    ),
    fact_type="room",
    condition=lambda f: (
        "is_corridor" in f.properties
        and f.properties["is_corridor"] is True
    ),
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-008",
            rule_name="Corridor Reduced Spacing for Narrow Spaces",
            nfpa_reference="NFPA 72 §17.7.3.1",
            severity=RulePriority.COMPLIANCE_CHECK,
            message=(
                f"Room '{facts[0].properties.get('room_id', '?')}' is a corridor. "
                f"NFPA 72 §17.7.3.1 corridor spacing rules apply. "
                f"Detectors within S/2 of corridor ends required."
            ),
            asserted_facts=[
                Fact(
                    fact_type="corridor_flag",
                    properties={
                        "room_id": facts[0].properties.get("room_id", ""),
                        "applies_corridor_rules": True,
                    },
                    source="derived",
                    nfpa_reference="NFPA 72 §17.7.3.1",
                )
            ],
            matched_facts=[f.fact_id for f in facts],
        )
    ],
    derives_facts=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA 72 RULES — MINIMUM DETECTOR COUNT
# ═══════════════════════════════════════════════════════════════════════════════

def _action_min_detector_count(facts, engine):
    """Action for NFPA72-009: derives minimum detector count.

    Looks up room area from room facts in the engine when available,
    falls back to 1.0 (conservative minimum) when room area is unknown.
    """
    coverage_fact = facts[0]
    room_id = coverage_fact.properties.get("room_id", "")
    r_m = coverage_fact.properties["R_m"]

    # Try to find the room fact to get the actual room area
    room_area_m2 = 1.0  # Conservative fallback
    room_facts = engine.get_facts("room")
    for rf in room_facts:
        if rf.properties.get("room_id") == room_id and rf.properties.get("room_area_m2") is not None:
            room_area_m2 = rf.properties["room_area_m2"]
            break

    min_dets = _min_detectors_for_room(room_area_m2, r_m)

    return [
        RuleResult(
            rule_id="NFPA72-009",
            rule_name="Minimum Detector Count for Room Coverage",
            nfpa_reference="NFPA 72 §17.6.3.1, §17.7.4.2.3.1",
            severity=RulePriority.COMPLIANCE_CHECK,
            message=(
                f"Room '{room_id}': "
                f"R={r_m:.2f}m, "
                f"area={room_area_m2:.1f}m2, "
                f"minimum_detectors={min_dets}"
            ),
            asserted_facts=[
                Fact(
                    fact_type="detector_requirement",
                    properties={
                        "room_id": room_id,
                        "detector_type": coverage_fact.properties.get("detector_type", ""),
                        "coverage_radius_m": r_m,
                        "room_area_m2": room_area_m2,
                        "min_detectors": min_dets,
                        "area_source": "room_fact" if room_area_m2 != 1.0 else "fallback",
                    },
                    source="derived",
                    nfpa_reference="NFPA 72 §17.7.4.2.3.1",
                )
            ],
            matched_facts=[f.fact_id for f in facts],
        )
    ]


RULE_MINIMUM_DETECTOR_COUNT = Rule(
    rule_id="NFPA72-009",
    rule_name="Minimum Detector Count for Room Coverage",
    nfpa_reference="NFPA 72 §17.6.3.1, §17.7.4.2.3.1",
    priority=RulePriority.COMPLIANCE_CHECK,
    description=(
        "Derives the minimum number of detectors needed to achieve "
        "full coverage based on room area and coverage radius. "
        "When room area is available from the room fact, the exact "
        "minimum is computed; otherwise a conservative fallback of 1.0 "
        "is used, and the area_source field indicates this."
    ),
    fact_type="coverage",
    condition=lambda f: "R_m" in f.properties and "room_id" in f.properties,
    action=_action_min_detector_count,
    derives_facts=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# JOIN RULE — DETECTOR IN ROOM (cross-fact-type)
# ═══════════════════════════════════════════════════════════════════════════════

RULE_DETECTOR_SPACING_VIOLATION = Rule(
    rule_id="NFPA72-010",
    rule_name="Detector Spacing Exceeds Listed Spacing",
    nfpa_reference="NFPA 72 §17.6.3.1",
    priority=RulePriority.CRITICAL_SAFETY,
    description=(
        "The distance between two adjacent detectors of the same type "
        "shall not exceed the listed spacing S. This rule joins "
        "detector pairs to check inter-detector distance."
    ),
    fact_type="detector",
    condition=lambda f: (
        "x" in f.properties and "y" in f.properties
        and "listed_spacing_m" in f.properties
    ),
    join_conditions=[
        (
            "detector",
            "detector",
            lambda d1, d2: (
                d1.properties.get("room_id") == d2.properties.get("room_id")
                and d1.fact_id != d2.fact_id
                and "x" in d1.properties and "y" in d1.properties
                and "x" in d2.properties and "y" in d2.properties
                and math.hypot(
                    d1.properties["x"] - d2.properties["x"],
                    d1.properties["y"] - d2.properties["y"],
                ) > d1.properties.get("listed_spacing_m", float("inf"))
            ),
        )
    ],
    action=lambda facts, engine: [
        RuleResult(
            rule_id="NFPA72-010",
            rule_name="Detector Spacing Exceeds Listed Spacing",
            nfpa_reference="NFPA 72 §17.6.3.1",
            severity=RulePriority.CRITICAL_SAFETY,
            message=(
                f"CRITICAL: Detectors "
                f"'{facts[0].properties.get('detector_id', '?')}' and "
                f"'{facts[1].properties.get('detector_id', '?')}' in room "
                f"'{facts[0].properties.get('room_id', '?')}' are "
                f"{math.hypot(facts[0].properties['x'] - facts[1].properties['x'], facts[0].properties['y'] - facts[1].properties['y']):.2f}m "
                f"apart (max {facts[0].properties.get('listed_spacing_m', 0):.2f}m "
                f"per NFPA 72 §17.6.3.1). Coverage gap detected."
            ),
            matched_facts=[f.fact_id for f in facts],
        )
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# NFPA72RuleSet — Complete Rule Set
# ═══════════════════════════════════════════════════════════════════════════════

class NFPA72RuleSet:
    """Complete NFPA 72 rule set for the rules engine.

    Provides all NFPA 72 rules as a ready-to-use collection.
    Rules are ordered by priority for deterministic evaluation.

    Usage:
        engine = RulesEngine(session_id="room-001")
        engine.add_rules(NFPA72RuleSet.all_rules())
        engine.assert_fact(Fact(fact_type="room", properties={...}))
        results = engine.evaluate()
    """

    _ALL_RULES: List[Rule] = [
        # CRITICAL SAFETY (priority 0) — fires first
        RULE_CEILING_HEIGHT_EXCEEDS_TABLE,
        RULE_DETECTOR_SPACING_VIOLATION,
        # SAFETY VIOLATIONS (priority 10)
        RULE_DEAD_AIR_SPACE,
        RULE_WALL_DISTANCE_EXCEEDED,
        RULE_DUCT_DETECTOR_REQUIRED,
        RULE_ELEVATOR_RECALL,
        # COMPLIANCE CHECKS (priority 20)
        RULE_CEILING_HEIGHT_SPACING,
        RULE_COVERAGE_RADIUS,
        RULE_CORRIDOR_SPACING,
        RULE_MINIMUM_DETECTOR_COUNT,
    ]

    @classmethod
    def all_rules(cls) -> List[Rule]:
        """Get all NFPA 72 rules."""
        return list(cls._ALL_RULES)

    @classmethod
    def critical_safety_rules(cls) -> List[Rule]:
        """Get only CRITICAL_SAFETY priority rules."""
        return [
            r for r in cls._ALL_RULES
            if r.priority == RulePriority.CRITICAL_SAFETY
        ]

    @classmethod
    def rules_by_nfpa_section(cls, section: str) -> List[Rule]:
        """Get rules that reference a specific NFPA section."""
        return [
            r for r in cls._ALL_RULES
            if r.nfpa_reference and section in r.nfpa_reference
        ]

    @classmethod
    def summary(cls) -> List[Dict[str, Any]]:
        """Get a summary of all rules for documentation."""
        return [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "nfpa_reference": r.nfpa_reference,
                "priority": r.priority.name,
                "description": r.description,
                "fact_type": r.fact_type,
                "has_joins": bool(r.join_conditions),
                "derives_facts": r.derives_facts,
            }
            for r in cls._ALL_RULES
        ]
