"""Compliance rule registry with NFPA/OSHA standards."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ComplianceRule:
    rule_id: str
    source: str
    version: str
    section: str
    severity: str
    category: str
    description: str
    rationale: str
    check_function: str
    auto_fixable: bool = False


RULE_REGISTRY = [
    ComplianceRule(
        rule_id="NFPA72-17.6.3-SPACING",
        source="NFPA 72",
        version="2022",
        section="17.6.3",
        severity="HIGH",
        category="detector_spacing",
        description="Maximum detector spacing shall not exceed 15 meters",
        rationale="Ensures smoke detection within acceptable time",
        check_function="check_detector_spacing",
        auto_fixable=True
    ),
    ComplianceRule(
        rule_id="NFPA72-17.6.3.1-COVERAGE",
        source="NFPA 72",
        version="2022",
        section="17.6.3.1",
        severity="CRITICAL",
        category="coverage",
        description="Detector coverage shall be at least 90% of room area",
        rationale="Guarantees no unprotected zones in the room",
        check_function="check_coverage",
        auto_fixable=True
    ),
    ComplianceRule(
        rule_id="NFPA72-17.7.1-REDUNDANCY",
        source="NFPA 72",
        version="2022",
        section="17.7.1",
        severity="HIGH",
        category="redundancy",
        description="Critical areas require overlapping detector coverage",
        rationale="Prevents single point of failure in high-risk rooms",
        check_function="check_redundancy",
        auto_fixable=True
    ),
    ComplianceRule(
        rule_id="OSHA-1910.36-EGRESS",
        source="OSHA 1910.36",
        version="2023",
        section="1910.36(d)",
        severity="CRITICAL",
        category="egress",
        description="Exit routes must be adequate for occupant load",
        rationale="Ensures safe evacuation during emergency",
        check_function="check_egress",
        auto_fixable=False
    ),
    ComplianceRule(
        rule_id="NFPA72-17.6.2-HEIGHT",
        source="NFPA 72",
        version="2022",
        section="17.6.2",
        severity="MEDIUM",
        category="ceiling_height",
        description="Detector placement adjusted for ceiling height",
        rationale="High ceilings affect smoke stratification",
        check_function="check_ceiling_height_adjustment",
        auto_fixable=True
    ),
    ComplianceRule(
        rule_id="NFPA72-17.14-MCP",
        source="NFPA 72",
        version="2022",
        section="17.14",
        severity="MEDIUM",
        category="manual_call_points",
        description="Manual call points required at exits and corridors",
        rationale="Allows manual activation of fire alarm",
        check_function="check_manual_call_points",
        auto_fixable=True
    ),
]


def get_rules_by_category(category: str) -> List[ComplianceRule]:
    return [r for r in RULE_REGISTRY if r.category == category]


def get_rules_by_severity(severity: str) -> List[ComplianceRule]:
    return [r for r in RULE_REGISTRY if r.severity == severity]


def get_all_rules() -> List[ComplianceRule]:
    return RULE_REGISTRY


def get_rule_by_id(rule_id: str) -> Optional[ComplianceRule]:
    for r in RULE_REGISTRY:
        if r.rule_id == rule_id:
            return r
    return None