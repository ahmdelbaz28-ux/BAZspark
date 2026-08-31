"""backend/tests/architecture/test_removal_gate.py — Removal Gate & Retirement Contract Verification.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 & Principle 11:
Verifies the retirement criteria mechanism for the legacy regex fallback planner:
  (intent-suite pass >= 95%) AND (LLM availability SLO >= 99.9% over rolling window)
"""

from __future__ import annotations

import pytest
from backend.core.planner_telemetry import (
    PlannerTelemetry,
    RETIREMENT_INTENT_PASS_RATE_MIN,
    RETIREMENT_LLM_AVAILABILITY_MIN,
)


def test_removal_gate_evaluation_eligible_when_both_criteria_met() -> None:
    """When Intent Suite pass rate >= 95% and LLM Availability >= 99.9%, retirement is eligible."""
    tel = PlannerTelemetry()
    tel.record_intent_suite_result(total_cases=100, passed_cases=98, pass_rate=0.98)

    # 1000 successful probes (100% availability)
    for _ in range(1000):
        tel.record_llm_probe(success=True)

    evaluation = tel.evaluate_retirement()
    assert evaluation.is_eligible_for_retirement is True
    assert evaluation.current_intent_pass_rate >= RETIREMENT_INTENT_PASS_RATE_MIN
    assert evaluation.current_llm_availability >= RETIREMENT_LLM_AVAILABILITY_MIN
    assert "READY FOR DECOMMISSION" in evaluation.status_summary


def test_removal_gate_evaluation_ineligible_when_pass_rate_below_threshold() -> None:
    """When Intent Suite pass rate < 95%, retirement remains ineligible (frozen fallback retained)."""
    tel = PlannerTelemetry()
    tel.record_intent_suite_result(total_cases=100, passed_cases=88, pass_rate=0.88)

    for _ in range(1000):
        tel.record_llm_probe(success=True)

    evaluation = tel.evaluate_retirement()
    assert evaluation.is_eligible_for_retirement is False
    assert "FROZEN COMPATIBILITY FALLBACK ACTIVE" in evaluation.status_summary


def test_removal_gate_evaluation_ineligible_when_availability_below_threshold() -> None:
    """When LLM Availability < 99.9%, retirement remains ineligible (frozen fallback retained)."""
    tel = PlannerTelemetry()
    tel.record_intent_suite_result(total_cases=100, passed_cases=99, pass_rate=0.99)

    # 950 successes, 50 failures -> 95% availability (<99.9%)
    for _ in range(950):
        tel.record_llm_probe(success=True)
    for _ in range(50):
        tel.record_llm_probe(success=False)

    evaluation = tel.evaluate_retirement()
    assert evaluation.is_eligible_for_retirement is False
    assert "FROZEN COMPATIBILITY FALLBACK ACTIVE" in evaluation.status_summary
