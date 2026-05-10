"""Compliance verification engine - orchestrates all rule checks."""

from core.compliance_engine.rule_registry import get_all_rules
from core.compliance_engine.compliance_checker import (
    check_detector_spacing,
    check_coverage,
    check_redundancy,
    check_egress,
    check_ceiling_height_adjustment,
    check_manual_call_points
)
from core.compliance_engine.audit_logger import AuditLog


def run_compliance_verification(rooms: list, devices: list, coverage: float, design_confidence: float) -> dict:
    audit = AuditLog()
    all_results = []

    # Check detector spacing
    spacing_result = check_detector_spacing(devices)
    all_results.append(spacing_result)
    audit.log(spacing_result["rule_id"], "PASS" if spacing_result["passed"] else "FAIL", spacing_result)

    # Check coverage
    coverage_result = check_coverage(coverage)
    all_results.append(coverage_result)
    audit.log(coverage_result["rule_id"], "PASS" if coverage_result["passed"] else "FAIL", coverage_result)

    # Check each room
    for room in rooms:
        room_devices = [d for d in devices if d.get("room_id") == room.get("id")]

        # Check redundancy
        redundancy_result = check_redundancy(room, room_devices)
        if redundancy_result.get("applicable", True):
            all_results.append(redundancy_result)
            audit.log(redundancy_result["rule_id"], "PASS" if redundancy_result["passed"] else "FAIL", redundancy_result)

        # Check egress
        egress_result = check_egress(room)
        all_results.append(egress_result)
        audit.log(egress_result["rule_id"], "PASS" if egress_result["passed"] else "FAIL", egress_result)

        # Check ceiling height
        height_result = check_ceiling_height_adjustment(room)
        all_results.append(height_result)
        audit.log(height_result["rule_id"], "PASS" if height_result["passed"] else "FAIL", height_result)

        # Check manual call points
        mcp_result = check_manual_call_points(room, room_devices)
        all_results.append(mcp_result)
        audit.log(mcp_result["rule_id"], "PASS" if mcp_result["passed"] else "FAIL", mcp_result)

    audit_summary = audit.summary()

    all_passed = audit_summary["failed"] == 0
    has_critical = audit_summary["critical_failures"] > 0

    if has_critical:
        overall = "REJECTED"
    elif not all_passed:
        overall = "CONDITIONAL_APPROVAL"
    else:
        overall = "APPROVED"

    return {
        "overall": overall,
        "all_passed": all_passed,
        "has_critical_failures": has_critical,
        "audit_summary": audit_summary,
        "rule_results": all_results,
        "rules_checked": len(all_results),
        "design_confidence": design_confidence,
        "traceable": True,
        "audit_log": audit.entries
    }