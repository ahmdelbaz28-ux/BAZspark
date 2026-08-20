"""tests/test_named_pipe_circuit_breaker.py — Phase 4.0 Circuit Breaker Resilience Test Suite.

Verifies:
1. Circuit Breaker starts in CLOSED state.
2. Consecutive failures increment counter.
3. 3 consecutive failures trip state to OPEN.
4. Fast-fail rejection in OPEN state returning BRIDGE_PROCESS_UNRESPONSIVE without hanging or network/pipe attempts.
5. Transition to HALF_OPEN after cooldown expiry.
6. Recovery to CLOSED on successful probe.
7. Re-trip to OPEN on failed probe during HALF_OPEN.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from fireai.mcp_server.named_pipe_client import (
    CircuitState,
    NamedPipeCircuitBreaker,
    RevitNamedPipeClient,
)


class TestNamedPipeCircuitBreaker:
    """Test suite for NamedPipeCircuitBreaker state machine."""

    def test_initial_state_is_closed(self):
        cb = NamedPipeCircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.can_execute() is True

    def test_failures_trip_to_open_after_threshold(self):
        cb = NamedPipeCircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3
        assert cb.can_execute() is False

    def test_recovery_cooldown_to_half_open(self):
        cb = NamedPipeCircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

        # Wait for cooldown
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_resets_to_closed(self):
        cb = NamedPipeCircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.06)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.can_execute() is True

    def test_half_open_failure_trips_back_to_open(self):
        cb = NamedPipeCircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.06)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False


class TestRevitNamedPipeClientCircuitBreaker:
    """Test suite for RevitNamedPipeClient with Circuit Breaker."""

    def test_client_fast_fails_when_circuit_open(self):
        client = RevitNamedPipeClient(failure_threshold=2, recovery_timeout=1.0)
        # Force circuit open
        client.circuit_breaker.record_failure()
        client.circuit_breaker.record_failure()
        assert client.circuit_breaker.state == CircuitState.OPEN

        # Should fast-fail with BRIDGE_PROCESS_UNRESPONSIVE
        res = client.send_command({"action": "set_parameter", "element_id": "100", "parameter_name": "dia", "value": 25.0})
        assert res["status"] == "error"
        assert res["error_code"] == "BRIDGE_PROCESS_UNRESPONSIVE"
        assert res["circuit_state"] == "OPEN"
        assert res["consecutive_failures"] == 2

    def test_stats_include_circuit_breaker_info(self):
        client = RevitNamedPipeClient(failure_threshold=3)
        stats = client.get_stats()
        assert "circuit_breaker_state" in stats
        assert stats["circuit_breaker_state"] == "CLOSED"
        assert stats["consecutive_failures"] == 0
        assert stats["circuit_breaker_enabled"] is True
