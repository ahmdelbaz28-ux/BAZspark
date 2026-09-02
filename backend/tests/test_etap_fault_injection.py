"""backend/tests/test_etap_fault_injection.py — Fault Injection and Resilience Test Suite.

Mandated by BAZSPARK Phase 11 (P11-R5):
- Multi-format SSRF attack vector matrix.
- 10MB + 1 byte buffer overflow rejection.
- Circuit breaker state machine transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
- Hypothesis property-based testing for circuit breaker invariants.
- Backpressure and concurrency saturation (wire code 429).
- Timeout budget exhaustion.
- Disallowed command and malformed payload rejection (fail-closed).
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backend.core.etap_resilience_contracts import (
    BackpressurePolicy,
    BackpressureRejectionError,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerPolicy,
    CircuitBreakerState,
    IdempotencyKey,
    IdempotencyStore,
    ResilienceError,
    RetryPolicy,
    TimeoutBudgetExceededError,
)
from backend.core.etap_telemetry import default_etap_telemetry
from backend.integrations.etap_live_adapter import (
    EtapLiveAdapter,
    EtapSecurityViolation,
    reset_all_circuit_breakers,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_all_circuit_breakers()
    default_etap_telemetry.reset()


# -----------------------------------------------------------------------------
# 1. Multi-Format SSRF Attack Matrix
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malicious_host",
    [
        "127.0.0.1",
        "127.0.0.2",
        "127.1.2.3",
        "0.0.0.0",
        "10.0.0.1",
        "10.255.255.254",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.0.1",
        "192.168.1.254",
        "169.254.169.254",  # AWS/GCP/Azure instance metadata endpoint
        "localhost",
        "::1",
        "0x7f.1",
        "0177.0.0.1",
    ],
)
def test_ssrf_multi_format_attack_matrix_rejected_fail_closed(malicious_host: str) -> None:
    """Verify that all variants of private, loopback, and metadata targets are strictly rejected."""
    adapter = EtapLiveAdapter(host=malicious_host, port=18888)
    with pytest.raises(EtapSecurityViolation) as exc_info:
        adapter.test_connection_live()
    assert "SSRF Protection" in str(exc_info.value) or "not allowed" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 2. 10MB + 1 Byte Buffer Limit Rejection
# -----------------------------------------------------------------------------


def test_payload_exceeding_10mb_limit_rejected_fail_closed() -> None:
    """Verify that any payload exceeding MAX_READLINE_BYTES (10MB) is strictly rejected."""
    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888)

    # Construct payload that exceeds 10MB
    overflow_buses = [{"id": f"BUS-{i}", "kv": 13.8, "padding": "X" * 1000} for i in range(11000)]
    overflow_model = {"buses": overflow_buses}

    with pytest.raises(EtapSecurityViolation) as exc_info:
        adapter.export_project_live("proj_overflow", overflow_model)

    assert "exceeds mandatory 10MB limit" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 3. Circuit Breaker State Transitions
# -----------------------------------------------------------------------------


def test_circuit_breaker_full_lifecycle_transitions() -> None:
    """Verify complete CLOSED -> OPEN -> HALF_OPEN -> CLOSED state machine transitions."""
    policy = CircuitBreakerPolicy(failure_threshold=3, recovery_timeout_seconds=0.1, success_threshold=2)
    cb = CircuitBreaker(policy=policy, name="test_cb")

    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute() is True

    # 1st failure
    cb.record_failure(Exception("fail 1"))
    assert cb.state == CircuitBreakerState.CLOSED

    # 2nd failure
    cb.record_failure(Exception("fail 2"))
    assert cb.state == CircuitBreakerState.CLOSED

    # 3rd failure -> Trip to OPEN
    cb.record_failure(Exception("fail 3"))
    assert cb.state == CircuitBreakerState.OPEN

    # In OPEN state, can_execute must raise CircuitBreakerOpenError fail-closed
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        cb.can_execute()
    assert "is OPEN" in str(exc_info.value)

    # Wait for recovery timeout
    time.sleep(0.15)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # First success in HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Second success in HALF_OPEN -> Transitions back to CLOSED
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_failure_re_trips_immediately() -> None:
    """Verify that a failure in HALF_OPEN immediately re-trips the circuit to OPEN."""
    policy = CircuitBreakerPolicy(failure_threshold=2, recovery_timeout_seconds=0.1, success_threshold=2)
    cb = CircuitBreaker(policy=policy, name="test_cb_half_open_fail")

    cb.record_failure(Exception("f1"))
    cb.record_failure(Exception("f2"))
    assert cb.state == CircuitBreakerState.OPEN

    time.sleep(0.15)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Failure during trial probe in HALF_OPEN
    cb.record_failure(Exception("trial fail"))
    assert cb.state == CircuitBreakerState.OPEN


@given(
    st.lists(
        st.tuples(
            st.booleans(),  # True = success, False = failure
            st.floats(min_value=0.0, max_value=1.0),  # simulated time advance in seconds
        ),
        min_size=5,
        max_size=30,
    )
)
def test_circuit_breaker_property_invariants(operations: list[tuple[bool, float]]) -> None:
    """Property test: Circuit breaker state is always valid and respects fail-closed invariants."""
    policy = CircuitBreakerPolicy(failure_threshold=3, recovery_timeout_seconds=0.5, success_threshold=2)
    cb = CircuitBreaker(policy=policy, name="pbt_cb")

    current_sim_time = 1000.0
    with patch("time.monotonic", side_effect=lambda: current_sim_time):
        cb._last_state_change = current_sim_time

        for is_success, dt in operations:
            current_sim_time += dt

            current_state = cb.state
            assert current_state in {CircuitBreakerState.CLOSED, CircuitBreakerState.OPEN, CircuitBreakerState.HALF_OPEN}

            if current_state == CircuitBreakerState.OPEN:
                with pytest.raises(CircuitBreakerOpenError):
                    cb.can_execute()
            else:
                assert cb.can_execute() is True

            if is_success:
                cb.record_success()
            else:
                cb.record_failure(Exception("injected error"))


# -----------------------------------------------------------------------------
# 5. Backpressure and Concurrency Saturation (Wire 429)
# -----------------------------------------------------------------------------


def test_concurrency_limiter_backpressure_rejection() -> None:
    """Verify that exceeding concurrent license seats raises BackpressureRejectionError (HTTP 429)."""
    policy = BackpressurePolicy(max_concurrent_requests=1, acquire_timeout_seconds=0.05, rejection_status_code=429)
    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888, backpressure_policy=policy)

    # Acquire the single available slot
    with adapter.concurrency_limiter:
        # Second call must be rejected due to saturation
        adapter2 = EtapLiveAdapter(host="93.184.216.34", port=18888, backpressure_policy=policy)
        with pytest.raises(BackpressureRejectionError) as exc_info:
            adapter2.test_connection_live()

        assert exc_info.value.status_code == 429
        assert "Backpressure limit reached" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 6. Timeout Budget Exhaustion
# -----------------------------------------------------------------------------


def test_timeout_budget_exhaustion_raises_fail_closed() -> None:
    """Verify that exceeding the total timeout budget raises TimeoutBudgetExceededError fail-closed."""
    retry_pol = RetryPolicy(total_timeout_budget_seconds=0.001)  # 1ms budget
    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888, retry_policy=retry_pol)

    buses = [{"id": "BUS-1", "nominal_kv": 13.8, "p_mw": 1.0, "q_mvar": 0.2}]
    gen = [{"id": "GEN-1", "mw": 2.0, "mvar": 0.5}]

    # Sleep within calculation to guarantee budget exhaustion
    with patch("time.monotonic", side_effect=[100.0, 100.0, 105.0, 105.0]):
        with pytest.raises(TimeoutBudgetExceededError) as exc_info:
            adapter.calculate_live_load_flow(buses, [], gen)

        assert "exceeded total timeout budget" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 7. Disallowed Commands Rejection (Fail-Closed)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "disallowed_cmd",
    [
        "eval_remote_script",
        "drop_database",
        "exec_shell",
        "format_disk",
        "bypass_auth",
        "unknown_action",
    ],
)
def test_disallowed_commands_rejected_fail_closed(disallowed_cmd: str) -> None:
    """Verify that any bridge command outside the closed allow-list is rejected immediately."""
    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888)
    with pytest.raises(EtapSecurityViolation) as exc_info:
        adapter._validate_command_allowed(disallowed_cmd)
    assert "Disallowed ETAP bridge command" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 8. Idempotency Key Conflict Detection
# -----------------------------------------------------------------------------


def test_idempotency_key_payload_conflict_rejection() -> None:
    """Verify that reusing the same token with differing payloads raises ResilienceError."""
    store = IdempotencyStore()
    key1 = IdempotencyKey.generate({"action": "export", "id": 1}, token="fixed-token")
    key2 = IdempotencyKey.generate({"action": "export", "id": 2}, token="fixed-token")

    store.check_or_set(key1)
    with pytest.raises(ResilienceError) as exc_info:
        store.check_or_set(key2)

    assert "Idempotency conflict" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 9. RetryPolicy Backoff Delay & Jitter Invariants
# -----------------------------------------------------------------------------


def test_retry_policy_calculate_delay_invariants() -> None:
    """Verify RetryPolicy calculate_delay bounds, negative attempt handling, and jitter modes."""
    policy = RetryPolicy(
        initial_backoff_seconds=1.0,
        max_backoff_seconds=8.0,
        backoff_multiplier=2.0,
        jitter=True,
    )

    # Negative attempt returns 0.0
    assert policy.calculate_delay(-1) == 0.0
    assert policy.calculate_delay(-10) == 0.0

    # Without seed: result must be in [0.5 * capped, capped]
    for attempt in range(5):
        raw = 1.0 * (2.0**attempt)
        capped = min(raw, 8.0)
        delay = policy.calculate_delay(attempt)
        assert 0.5 * capped <= delay <= capped, f"Attempt {attempt} delay {delay} out of bounds"

    # With seed: must be strictly deterministic
    delay_seeded_1 = policy.calculate_delay(attempt=2, seed=42.0)
    delay_seeded_2 = policy.calculate_delay(attempt=2, seed=42.0)
    assert delay_seeded_1 == delay_seeded_2

    # Without jitter: exact exponential backoff capped at max
    no_jitter_policy = RetryPolicy(
        initial_backoff_seconds=1.0,
        max_backoff_seconds=8.0,
        backoff_multiplier=2.0,
        jitter=False,
    )
    assert no_jitter_policy.calculate_delay(0) == 1.0
    assert no_jitter_policy.calculate_delay(1) == 2.0
    assert no_jitter_policy.calculate_delay(2) == 4.0
    assert no_jitter_policy.calculate_delay(3) == 8.0
    assert no_jitter_policy.calculate_delay(10) == 8.0

    # Serialization
    d = policy.to_dict()
    assert d["initial_backoff_seconds"] == 1.0
    assert d["max_backoff_seconds"] == 8.0
    assert d["jitter"] is True

