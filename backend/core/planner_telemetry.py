"""backend/core/planner_telemetry.py — Autonomous Workflow Planner Telemetry & Retirement Tracking.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 and Principle 11:
- Captures usage, latency, success/failure, and fallback reasons for all planner invocations.
- Enforces the Regex Planner Retirement Contract:
    1. intent_suite_pass_rate >= 0.95 (95%)
    2. llm_availability_slo >= 0.999 (99.9% availability window)
- Non-preferred fallback usage is continuously tracked and auditable.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Minimum thresholds for retiring the legacy regex fallback planner
RETIREMENT_INTENT_PASS_RATE_MIN = 0.95
RETIREMENT_LLM_AVAILABILITY_MIN = 0.999
RETIREMENT_OBSERVATION_WINDOW_HOURS = 24.0


@dataclass
class PlannerInvocationRecord:
    """Record of an individual planner invocation."""

    invocation_id: str
    planner_type: str  # "generic" | "regex_fallback"
    intent_summary: str
    success: bool
    latency_ms: float
    fallback_reason: str | None = None
    step_count: int = 0
    project_id: str = ""
    error_message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetirementEvaluation:
    """Evaluation of the regex planner retirement conditions."""

    is_eligible_for_retirement: bool
    current_intent_pass_rate: float
    target_intent_pass_rate: float
    current_llm_availability: float
    target_llm_availability: float
    total_generic_invocations: int
    total_regex_fallback_invocations: int
    fallback_percentage: float
    observation_window_hours: float
    status_summary: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlannerTelemetry:
    """Thread-safe telemetry recorder and retirement tracker for autonomous planners."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[PlannerInvocationRecord] = []
        self._llm_probe_successes: int = 0
        self._llm_probe_failures: int = 0
        self._intent_suite_runs: list[dict[str, Any]] = []

    def record_invocation(
        self,
        *,
        invocation_id: str,
        planner_type: str,
        intent_summary: str,
        success: bool,
        latency_ms: float,
        fallback_reason: str | None = None,
        step_count: int = 0,
        project_id: str = "",
        error_message: str | None = None,
    ) -> PlannerInvocationRecord:
        """Record an invocation of either the generic planner or regex fallback."""
        rec = PlannerInvocationRecord(
            invocation_id=invocation_id,
            planner_type=planner_type,
            intent_summary=intent_summary,
            success=success,
            latency_ms=round(latency_ms, 2),
            fallback_reason=fallback_reason,
            step_count=step_count,
            project_id=project_id,
            error_message=error_message,
        )
        with self._lock:
            self._records.append(rec)
            # Bound in-memory log to newest 10,000 invocations
            if len(self._records) > 10000:
                self._records = self._records[-10000:]
        return rec

    def record_llm_probe(self, success: bool) -> None:
        """Record a live LLM availability probe result for SLO calculations."""
        with self._lock:
            if success:
                self._llm_probe_successes += 1
            else:
                self._llm_probe_failures += 1

    def record_intent_suite_result(
        self,
        *,
        total_cases: int,
        passed_cases: int,
        pass_rate: float,
        suite_name: str = "full_pipeline_intent_suite",
    ) -> None:
        """Record the latest Intent Suite execution pass rate."""
        with self._lock:
            self._intent_suite_runs.append(
                {
                    "suite_name": suite_name,
                    "total_cases": total_cases,
                    "passed_cases": passed_cases,
                    "pass_rate": pass_rate,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    def get_summary(self) -> dict[str, Any]:
        """Generate high-level telemetry metrics summary."""
        with self._lock:
            total = len(self._records)
            generic_records = [r for r in self._records if r.planner_type == "generic"]
            regex_records = [r for r in self._records if r.planner_type == "regex_fallback"]

            generic_count = len(generic_records)
            regex_count = len(regex_records)

            generic_success = sum(1 for r in generic_records if r.success)
            regex_success = sum(1 for r in regex_records if r.success)

            avg_generic_lat = (
                sum(r.latency_ms for r in generic_records) / generic_count
                if generic_count > 0
                else 0.0
            )
            avg_regex_lat = (
                sum(r.latency_ms for r in regex_records) / regex_count if regex_count > 0 else 0.0
            )

            fallback_reasons: dict[str, int] = {}
            for r in regex_records:
                reason = r.fallback_reason or "unknown"
                fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1

            total_probes = self._llm_probe_successes + self._llm_probe_failures
            llm_avail = (
                (self._llm_probe_successes / total_probes) if total_probes > 0 else 1.0
            )

            latest_intent_pass_rate = (
                self._intent_suite_runs[-1]["pass_rate"]
                if self._intent_suite_runs
                else 1.0
            )

            return {
                "total_invocations": total,
                "generic_planner": {
                    "count": generic_count,
                    "success_count": generic_success,
                    "pass_rate": round(generic_success / max(1, generic_count), 4)
                    if generic_count > 0
                    else 1.0,
                    "avg_latency_ms": round(avg_generic_lat, 2),
                },
                "regex_fallback": {
                    "count": regex_count,
                    "success_count": regex_success,
                    "pass_rate": round(regex_success / max(1, regex_count), 4)
                    if regex_count > 0
                    else 1.0,
                    "avg_latency_ms": round(avg_regex_lat, 2),
                    "fallback_reasons": fallback_reasons,
                },
                "fallback_percentage": round((regex_count / max(1, total)) * 100.0, 2),
                "llm_availability_slo": round(llm_avail, 4),
                "latest_intent_suite_pass_rate": round(latest_intent_pass_rate, 4),
            }

    def evaluate_retirement(self) -> RetirementEvaluation:
        """Evaluate whether the legacy regex fallback planner meets criteria for deletion."""
        summary = self.get_summary()
        current_pass_rate = summary["latest_intent_suite_pass_rate"]
        current_avail = summary["llm_availability_slo"]

        pass_rate_ok = current_pass_rate >= RETIREMENT_INTENT_PASS_RATE_MIN
        avail_ok = current_avail >= RETIREMENT_LLM_AVAILABILITY_MIN

        eligible = pass_rate_ok and avail_ok

        status_msg = (
            "READY FOR DECOMMISSION: Intent suite pass rate and LLM availability SLO conditions met."
            if eligible
            else f"FROZEN COMPATIBILITY FALLBACK ACTIVE: Pass Rate ({current_pass_rate*100:.1f}% >= {RETIREMENT_INTENT_PASS_RATE_MIN*100:.1f}%), "
            f"SLO Availability ({current_avail*100:.2f}% >= {RETIREMENT_LLM_AVAILABILITY_MIN*100:.2f}%)."
        )

        return RetirementEvaluation(
            is_eligible_for_retirement=eligible,
            current_intent_pass_rate=current_pass_rate,
            target_intent_pass_rate=RETIREMENT_INTENT_PASS_RATE_MIN,
            current_llm_availability=current_avail,
            target_llm_availability=RETIREMENT_LLM_AVAILABILITY_MIN,
            total_generic_invocations=summary["generic_planner"]["count"],
            total_regex_fallback_invocations=summary["regex_fallback"]["count"],
            fallback_percentage=summary["fallback_percentage"],
            observation_window_hours=RETIREMENT_OBSERVATION_WINDOW_HOURS,
            status_summary=status_msg,
        )

    def reset(self) -> None:
        """Reset telemetry for test isolation."""
        with self._lock:
            self._records.clear()
            self._llm_probe_successes = 0
            self._llm_probe_failures = 0
            self._intent_suite_runs.clear()


default_planner_telemetry = PlannerTelemetry()
