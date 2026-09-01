"""backend/core/etap_telemetry.py — ETAP Telemetry and Governance Audit Integration.

Mandated by BAZSPARK Phase 11 (P11-R3):
- Structured telemetry events:
    etap.attempt, etap.resolve, etap.submit, etap.poll,
    etap.fetch, etap.verify, etap.circuit_open
- Correlation ID tracking across all life-cycle phases.
- Real-time SLO calculation: Success rate, P95 latency, ssrf_blocked count, circuit_opens count.
- Integrated with planner_telemetry and workspace governance audit logs.
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.core.planner_telemetry import default_planner_telemetry

logger = logging.getLogger(__name__)

# Mandatory event types
EVENT_ETAP_ATTEMPT = "etap.attempt"
EVENT_ETAP_RESOLVE = "etap.resolve"
EVENT_ETAP_SUBMIT = "etap.submit"
EVENT_ETAP_POLL = "etap.poll"
EVENT_ETAP_FETCH = "etap.fetch"
EVENT_ETAP_VERIFY = "etap.verify"
EVENT_ETAP_CIRCUIT_OPEN = "etap.circuit_open"

VALID_ETAP_EVENT_TYPES = {
    EVENT_ETAP_ATTEMPT,
    EVENT_ETAP_RESOLVE,
    EVENT_ETAP_SUBMIT,
    EVENT_ETAP_POLL,
    EVENT_ETAP_FETCH,
    EVENT_ETAP_VERIFY,
    EVENT_ETAP_CIRCUIT_OPEN,
}


@dataclass
class EtapTelemetryEvent:
    """Structured telemetry event record."""

    event_type: str
    correlation_id: str
    host: str
    port: int
    duration_ms: float = 0.0
    success: bool = True
    error_type: str | None = None
    error_message: str | None = None
    idempotency_key: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EtapTelemetryRecorder:
    """Thread-safe telemetry aggregator and SLO evaluator for live ETAP bridge."""

    def __init__(self, max_history: int = 5000) -> None:
        self._lock = threading.Lock()
        self._events: list[EtapTelemetryEvent] = []
        self._max_history = max_history
        self._ssrf_blocked_count: int = 0
        self._circuit_opens_count: int = 0
        self._backpressure_rejections_count: int = 0
        self._latencies_ms: list[float] = []

    def record_event(
        self,
        event_type: str,
        *,
        correlation_id: str | None = None,
        host: str = "unknown",
        port: int = 18888,
        duration_ms: float = 0.0,
        success: bool = True,
        error_type: str | None = None,
        error_message: str | None = None,
        idempotency_key: str | None = None,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EtapTelemetryEvent:
        """Record an ETAP telemetry event and update internal SLO tracking."""
        cid = correlation_id or f"etap-cor-{uuid.uuid4().hex[:12]}"
        evt = EtapTelemetryEvent(
            event_type=event_type,
            correlation_id=cid,
            host=host,
            port=port,
            duration_ms=round(duration_ms, 2),
            success=success,
            error_type=error_type,
            error_message=error_message,
            idempotency_key=idempotency_key,
            project_id=project_id,
            metadata=metadata or {},
        )

        with self._lock:
            self._events.append(evt)
            if len(self._events) > self._max_history:
                self._events = self._events[-self._max_history :]

            if duration_ms > 0:
                self._latencies_ms.append(duration_ms)
                if len(self._latencies_ms) > self._max_history:
                    self._latencies_ms = self._latencies_ms[-self._max_history :]

            if event_type == EVENT_ETAP_CIRCUIT_OPEN:
                self._circuit_opens_count += 1

            if error_type == "SSRFError" or (error_message and "SSRF" in error_message):
                self._ssrf_blocked_count += 1

            if error_type == "BackpressureRejectionError" or (error_message and "Backpressure" in error_message):
                self._backpressure_rejections_count += 1

        # Also bridge to default_planner_telemetry probe / audit if suitable
        try:
            if event_type in (EVENT_ETAP_VERIFY, EVENT_ETAP_SUBMIT):
                default_planner_telemetry.record_invocation(
                    invocation_id=cid,
                    planner_type="etap_live_bridge",
                    intent_summary=f"{event_type} on {host}:{port}",
                    success=success,
                    latency_ms=duration_ms,
                    fallback_reason=error_type,
                    step_count=1,
                    project_id=project_id or "",
                    error_message=error_message,
                )
        except Exception as exc:
            logger.debug("Failed to bridge ETAP telemetry to planner_telemetry: %s", exc)

        return evt

    def record_ssrf_blocked(self, host: str, correlation_id: str | None = None) -> None:
        """Record an explicit SSRF pre-resolution block."""
        self.record_event(
            EVENT_ETAP_RESOLVE,
            correlation_id=correlation_id,
            host=host,
            success=False,
            error_type="SSRFError",
            error_message=f"SSRF violation: Host '{host}' resolved to restricted IP.",
        )

    def record_circuit_trip(self, name: str, host: str, correlation_id: str | None = None) -> None:
        """Record a circuit breaker opening event."""
        self.record_event(
            EVENT_ETAP_CIRCUIT_OPEN,
            correlation_id=correlation_id,
            host=host,
            success=False,
            error_type="CircuitBreakerOpenError",
            error_message=f"Circuit breaker '{name}' opened for {host}",
        )

    def get_slo_metrics(self) -> dict[str, Any]:
        """Compute real-time SLO metrics: success rate, P95 latency, and security counters."""
        with self._lock:
            total_events = len(self._events)
            action_events = [e for e in self._events if e.event_type in (EVENT_ETAP_SUBMIT, EVENT_ETAP_VERIFY, EVENT_ETAP_ATTEMPT)]
            total_actions = len(action_events)
            successful_actions = sum(1 for e in action_events if e.success)

            success_rate = (successful_actions / total_actions) if total_actions > 0 else 1.0

            # Calculate p95 latency
            p95_latency = 0.0
            if self._latencies_ms:
                sorted_lat = sorted(self._latencies_ms)
                idx = math.ceil(0.95 * len(sorted_lat)) - 1
                p95_latency = round(sorted_lat[max(0, min(idx, len(sorted_lat) - 1))], 2)

            return {
                "total_events": total_events,
                "total_actions": total_actions,
                "successful_actions": successful_actions,
                "success_rate": round(success_rate, 4),
                "p95_latency_ms": p95_latency,
                "ssrf_blocked_count": self._ssrf_blocked_count,
                "circuit_opens_count": self._circuit_opens_count,
                "backpressure_rejections_count": self._backpressure_rejections_count,
            }

    def get_events(self, limit: int = 100, event_type: str | None = None) -> list[dict[str, Any]]:
        """Return the most recent telemetry events matching filter."""
        with self._lock:
            evts = self._events
            if event_type:
                evts = [e for e in evts if e.event_type == event_type]
            return [e.to_dict() for e in evts[-limit:]]

    def reset(self) -> None:
        """Reset telemetry storage for clean test isolation."""
        with self._lock:
            self._events.clear()
            self._latencies_ms.clear()
            self._ssrf_blocked_count = 0
            self._circuit_opens_count = 0
            self._backpressure_rejections_count = 0


# Default global telemetry recorder
default_etap_telemetry = EtapTelemetryRecorder()
