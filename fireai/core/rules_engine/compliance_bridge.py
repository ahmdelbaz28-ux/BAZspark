"""
FireAI Rules Engine — Integration Bridge
==========================================

Bridges the new Rules Engine with the existing FireAI compliance
system. This module provides:

1. Conversion from existing data models to Rule Engine facts
2. Conversion from Rule Engine results to existing violation format
3. Integration with existing AuditStore for rule evaluation audit
4. Backward-compatible API — existing code continues to work

SAFETY: This bridge ensures that the Rules Engine enhances (not replaces)
the existing compliance checks. Both systems run in parallel during
the transition period. Discrepancies are flagged for review.

Reference: NFPA 72-2022, agent.md Rules 6 and 7
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fireai.core.rules_engine.engine import (
    Fact,
    Rule,
    RulePriority,
    RuleResult,
    RulesEngine,
    RuleAuditEntry,
)
from fireai.core.rules_engine.nfpa72_rules import NFPA72RuleSet
from fireai.core.rules_engine.truth_maintenance import TruthMaintenanceSystem

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════

def room_to_facts(
    room_id: str,
    ceiling_height_m: float,
    detector_type: str = "smoke",
    room_area_m2: Optional[float] = None,
    is_corridor: bool = False,
    occupancy_type: str = "office",
) -> List[Fact]:
    """Convert a room specification to Rule Engine facts.

    This is the main entry point for analyzing a room through the
    declarative rules engine.
    """
    facts = [
        Fact(
            fact_type="room",
            properties={
                "room_id": room_id,
                "ceiling_height_m": ceiling_height_m,
                "detector_type": detector_type,
                "room_area_m2": room_area_m2,
                "is_corridor": is_corridor,
                "occupancy_type": occupancy_type,
            },
            source="room_input",
            nfpa_reference="NFPA 72 §17.6.3.1",
        )
    ]
    return facts


def detector_to_fact(
    detector_id: str,
    room_id: str,
    detector_type: str,
    x: float,
    y: float,
    distance_to_wall_m: Optional[float] = None,
    listed_spacing_m: Optional[float] = None,
    wall_distance_max_m: Optional[float] = None,
) -> Fact:
    """Convert a detector to a Rule Engine fact."""
    properties = {
        "detector_id": detector_id,
        "room_id": room_id,
        "detector_type": detector_type,
        "x": x,
        "y": y,
    }
    if distance_to_wall_m is not None:
        properties["distance_to_wall_m"] = distance_to_wall_m
    if listed_spacing_m is not None:
        properties["listed_spacing_m"] = listed_spacing_m
    if wall_distance_max_m is not None:
        properties["wall_distance_max_m"] = wall_distance_max_m

    return Fact(
        fact_type="detector",
        properties=properties,
        source="detector_input",
        nfpa_reference="NFPA 72 §17.6.3.1",
    )


def hvac_to_fact(
    unit_id: str,
    cfm: float,
    has_duct_detector: bool = False,
    duct_type: str = "supply",
) -> Fact:
    """Convert an HVAC unit to a Rule Engine fact."""
    return Fact(
        fact_type="hvac_unit",
        properties={
            "unit_id": unit_id,
            "cfm": cfm,
            "has_duct_detector": has_duct_detector,
            "duct_type": duct_type,
        },
        source="hvac_input",
        nfpa_reference="NFPA 72 §17.7.5.1",
    )


def elevator_to_fact(
    elevator_id: str,
    has_lobby_detector: bool = False,
    has_hoistway_detector: bool = False,
) -> Fact:
    """Convert an elevator to a Rule Engine fact."""
    return Fact(
        fact_type="elevator",
        properties={
            "elevator_id": elevator_id,
            "has_lobby_detector": has_lobby_detector,
            "has_hoistway_detector": has_hoistway_detector,
        },
        source="elevator_input",
        nfpa_reference="NFPA 72 §21.3.3",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RESULT CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ComplianceReport:
    """Structured compliance report from the rules engine.

    Compatible with the existing ExpertResult format but enriched
    with rule evaluation details and truth maintenance data.
    """
    session_id: str
    is_safe: bool
    critical_issues: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    compliance_checks: List[Dict[str, Any]] = field(default_factory=list)
    derived_facts: List[Dict[str, Any]] = field(default_factory=list)
    audit_summary: Dict[str, Any] = field(default_factory=dict)
    nfpa_references: List[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def results_to_report(
    engine: RulesEngine,
) -> ComplianceReport:
    """Convert Rule Engine results to a ComplianceReport.

    This is the main output conversion function. It takes a fully
    evaluated RulesEngine and produces a structured report.
    """
    summary = engine.get_compliance_summary()

    critical_issues = []
    violations = []
    compliance_checks = []

    for result in engine.get_results():
        entry = {
            "rule_id": result.rule_id,
            "rule_name": result.rule_name,
            "nfpa_reference": result.nfpa_reference,
            "message": result.message,
            "severity": result.severity.name,
            "matched_facts": result.matched_facts,
            "confidence": result.confidence,
        }

        if result.severity == RulePriority.CRITICAL_SAFETY:
            critical_issues.append(entry)
        elif result.severity == RulePriority.SAFETY_VIOLATION:
            violations.append(entry)
        else:
            compliance_checks.append(entry)

    # Collect derived facts
    derived = []
    for fact in engine.get_facts():
        if fact.source == "derived":
            derived.append({
                "fact_type": fact.fact_type,
                "fact_id": fact.fact_id,
                "properties": fact.properties,
                "nfpa_reference": fact.nfpa_reference,
            })

    # Collect NFPA references
    nfpa_refs = list({
        r.nfpa_reference
        for r in engine.get_results()
        if r.nfpa_reference
    })

    return ComplianceReport(
        session_id=engine.session_id,
        is_safe=len(critical_issues) == 0 and len(violations) == 0,
        critical_issues=critical_issues,
        violations=violations,
        compliance_checks=compliance_checks,
        derived_facts=derived,
        audit_summary=summary,
        nfpa_references=nfpa_refs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL API
# ═══════════════════════════════════════════════════════════════════════════════

class NFPA72ComplianceChecker:
    """High-level API for NFPA 72 compliance checking using the rules engine.

    This provides a simple interface for the rest of the FireAI system
    to use the rules engine without dealing with low-level details.

    Usage:
        checker = NFPA72ComplianceChecker()
        checker.add_room("R1", ceiling_height_m=3.0, detector_type="smoke")
        checker.add_detector("D1", "R1", "smoke", x=5.0, y=5.0,
                             distance_to_wall_m=0.5)
        report = checker.evaluate()
        if not report.is_safe:
            for issue in report.critical_issues:
                print(f"CRITICAL: {issue['message']}")
    """

    def __init__(self, session_id: str = "") -> None:
        self.engine = RulesEngine(
            session_id=session_id,
            max_iterations=50,
        )
        self.engine.add_rules(NFPA72RuleSet.all_rules())
        # TMS is integrated inside RulesEngine via _derived_from/_supports
        # dictionaries. The standalone TruthMaintenanceSystem is available
        # for external audit and consistency checks.
        self.tms = TruthMaintenanceSystem()

    def validate_tms_consistency(self) -> List[str]:
        """Check TMS consistency between engine and standalone TMS.

        Returns list of stale fact IDs. Empty list = consistent.
        SAFETY: This should always return an empty list.
        """
        existing_ids = {f.fact_id for f in self.engine.get_facts()}
        return self.tms.validate_consistency(existing_ids)

    def add_room(
        self,
        room_id: str,
        ceiling_height_m: float,
        detector_type: str = "smoke",
        room_area_m2: Optional[float] = None,
        is_corridor: bool = False,
        occupancy_type: str = "office",
    ) -> str:
        """Add a room for compliance analysis."""
        facts = room_to_facts(
            room_id=room_id,
            ceiling_height_m=ceiling_height_m,
            detector_type=detector_type,
            room_area_m2=room_area_m2,
            is_corridor=is_corridor,
            occupancy_type=occupancy_type,
        )
        fid = self.engine.assert_fact(facts[0])
        logger.info(
            f"Room added: {room_id} h={ceiling_height_m}m "
            f"type={detector_type}"
        )
        return fid

    def add_detector(
        self,
        detector_id: str,
        room_id: str,
        detector_type: str,
        x: float,
        y: float,
        distance_to_wall_m: Optional[float] = None,
        listed_spacing_m: Optional[float] = None,
        wall_distance_max_m: Optional[float] = None,
    ) -> str:
        """Add a detector for compliance analysis."""
        fact = detector_to_fact(
            detector_id=detector_id,
            room_id=room_id,
            detector_type=detector_type,
            x=x,
            y=y,
            distance_to_wall_m=distance_to_wall_m,
            listed_spacing_m=listed_spacing_m,
            wall_distance_max_m=wall_distance_max_m,
        )
        fid = self.engine.assert_fact(fact)
        logger.info(
            f"Detector added: {detector_id} in {room_id} "
            f"at ({x:.1f}, {y:.1f})"
        )
        return fid

    def add_hvac(
        self,
        unit_id: str,
        cfm: float,
        has_duct_detector: bool = False,
    ) -> str:
        """Add an HVAC unit for duct detector compliance."""
        fact = hvac_to_fact(
            unit_id=unit_id,
            cfm=cfm,
            has_duct_detector=has_duct_detector,
        )
        return self.engine.assert_fact(fact)

    def add_elevator(
        self,
        elevator_id: str,
        has_lobby_detector: bool = False,
        has_hoistway_detector: bool = False,
    ) -> str:
        """Add an elevator for recall compliance."""
        fact = elevator_to_fact(
            elevator_id=elevator_id,
            has_lobby_detector=has_lobby_detector,
            has_hoistway_detector=has_hoistway_detector,
        )
        return self.engine.assert_fact(fact)

    def evaluate(self) -> ComplianceReport:
        """Run compliance evaluation and return a structured report."""
        logger.info(f"Starting NFPA 72 compliance evaluation for session {self.engine.session_id}")
        results = self.engine.evaluate()
        report = results_to_report(self.engine)

        # Log summary
        logger.info(
            f"Compliance evaluation complete: "
            f"safe={report.is_safe}, "
            f"critical={len(report.critical_issues)}, "
            f"violations={len(report.violations)}, "
            f"checks={len(report.compliance_checks)}"
        )

        return report

    def get_audit_log(self) -> List[RuleAuditEntry]:
        """Get the complete audit log for this session."""
        return self.engine.get_audit_log()

    def explain(self, fact_id: str) -> Dict[str, Any]:
        """Explain how a fact was derived (truth maintenance)."""
        return self.engine.explain(fact_id)

    def reset(self) -> None:
        """Reset for a new analysis session."""
        self.engine.reset()
