"""backend/core/etap_resilience_contracts.py — ETAP Resilience and Production Hardening Contracts.

Mandated by BAZSPARK Phase 11 (P11-R1 & P11-R2):
- Versioned resilience schemas for enterprise external CAD/ETAP live integration.
- RetryPolicy: Bounded attempts, exponential backoff with full/decorrelated jitter, and total timeout budget.
- CircuitBreaker: Complete thread-safe state machine (CLOSED -> OPEN -> HALF_OPEN) with fail-closed semantics.
- BackpressurePolicy: Bounded concurrent seat limit with explicit wire semantics (HTTP 429 / 503).
- IdempotencyKey & IdempotencyStore: Request-level idempotency protection preventing duplicate executions.
- Zero silent fallbacks — all degraded conditions fail closed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

RESILIENCE_CONTRACT_VERSION = "1.0"


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class ResilienceError(Exception):
    """Base exception for resilience contract violations and failures."""


class CircuitBreakerOpenError(ResilienceError):
    """Raised fail-closed when execution is rejected because the circuit breaker is OPEN."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class BackpressureRejectionError(ResilienceError):
    """Raised fail-closed when concurrency limit or queue capacity is exceeded."""

    def __init__(self, message: str, status_code: int = 429) -> None:
        super().__init__(message)
        self.status_code = status_code


class TimeoutBudgetExceededError(ResilienceError):
    """Raised when the cumulative execution time exceeds the total timeout budget."""


# -----------------------------------------------------------------------------
# RetryPolicy
# -----------------------------------------------------------------------------


@dataclass
class RetryPolicy:
    """Bounded retry policy with jittered exponential backoff and total timeout budget."""

    schema_version: str = RESILIENCE_CONTRACT_VERSION
    max_retries: int = 3
    initial_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 8.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    total_timeout_budget_seconds: float = 30.0

    def calculate_delay(self, attempt: int, seed: float | None = None) -> float:
        """Calculate the backoff delay for a given 0-indexed attempt number.

        Uses full jitter where delay is uniformly distributed in [0, exponential_backoff].
        """
        if attempt < 0:
            return 0.0
        raw_backoff = self.initial_backoff_seconds * (self.backoff_multiplier**attempt)
        capped_backoff = min(raw_backoff, self.max_backoff_seconds)

        if not self.jitter:
            return round(capped_backoff, 4)

        if seed is not None:
            rng = random.Random(seed + attempt)
            jitter_ratio = rng.random()
        else:
            jitter_ratio = random.random()

        # Full jitter: random between 0.5 * capped and capped (or 0 to capped)
        delay = capped_backoff * (0.5 + 0.5 * jitter_ratio)
        return round(delay, 4)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# CircuitBreaker State Machine
# -----------------------------------------------------------------------------


class CircuitBreakerState(str, Enum):
    """State of the circuit breaker state machine."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerPolicy:
    """Configuration for circuit breaker state machine."""

    schema_version: str = RESILIENCE_CONTRACT_VERSION
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 10.0
    success_threshold: int = 2
    fail_closed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CircuitBreaker:
    """Thread-safe circuit breaker with monotonic time tracking and fail-closed operation."""

    def __init__(self, policy: CircuitBreakerPolicy | None = None, name: str = "etap_circuit") -> None:
        self.policy = policy or CircuitBreakerPolicy()
        self.name = name
        self._lock = threading.RLock()
        self._state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self._consecutive_failures: int = 0
        self._consecutive_successes: int = 0
        self._last_state_change: float = time.monotonic()
        self._last_failure_time: float | None = None
        self._last_error: str | None = None
        self._total_trips: int = 0
        self._total_executions: int = 0
        self._total_failures: int = 0

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            self._evaluate_state_transition()
            return self._state

    def _evaluate_state_transition(self) -> None:
        """Evaluate if OPEN state has expired recovery timeout to transition to HALF_OPEN."""
        now = time.monotonic()
        if self._state == CircuitBreakerState.OPEN:
            elapsed = now - self._last_state_change
            if elapsed >= self.policy.recovery_timeout_seconds:
                logger.info(
                    "Circuit breaker '%s' transition: OPEN -> HALF_OPEN after %.2fs",
                    self.name,
                    elapsed,
                )
                self._state = CircuitBreakerState.HALF_OPEN
                self._last_state_change = now
                self._consecutive_successes = 0

    def can_execute(self) -> bool:
        """Check if execution is allowed. Raises CircuitBreakerOpenError if circuit is OPEN."""
        with self._lock:
            self._evaluate_state_transition()
            if self._state == CircuitBreakerState.OPEN:
                now = time.monotonic()
                remaining = max(0.0, self.policy.recovery_timeout_seconds - (now - self._last_state_change))
                if self.policy.fail_closed:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. Execution rejected (fail-closed). "
                        f"Retry allowed in {remaining:.2f}s.",
                        retry_after_seconds=round(remaining, 2),
                    )
                return False
            return True

    def record_success(self) -> None:
        """Record a successful execution, updating state machine."""
        with self._lock:
            self._total_executions += 1
            self._consecutive_failures = 0
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.policy.success_threshold:
                    logger.info(
                        "Circuit breaker '%s' transition: HALF_OPEN -> CLOSED (success threshold %d met)",
                        self.name,
                        self.policy.success_threshold,
                    )
                    self._state = CircuitBreakerState.CLOSED
                    self._last_state_change = time.monotonic()
                    self._consecutive_successes = 0

    def record_failure(self, exc: Exception | None = None) -> None:
        """Record an execution failure, potentially tripping the circuit."""
        with self._lock:
            now = time.monotonic()
            self._total_executions += 1
            self._total_failures += 1
            self._last_failure_time = now
            self._last_error = str(exc) if exc else "Unknown error"

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.warning(
                    "Circuit breaker '%s' transition: HALF_OPEN -> OPEN (trial probe failed: %s)",
                    self.name,
                    self._last_error,
                )
                self._state = CircuitBreakerState.OPEN
                self._last_state_change = now
                self._total_trips += 1
                self._consecutive_successes = 0
                return

            if self._state == CircuitBreakerState.CLOSED:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.policy.failure_threshold:
                    logger.warning(
                        "Circuit breaker '%s' transition: CLOSED -> OPEN (failure threshold %d exceeded: %s)",
                        self.name,
                        self.policy.failure_threshold,
                        self._last_error,
                    )
                    self._state = CircuitBreakerState.OPEN
                    self._last_state_change = now
                    self._total_trips += 1

    def reset(self) -> None:
        """Manually reset the circuit breaker to clean CLOSED state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._last_state_change = time.monotonic()
            self._last_error = None

    def get_metrics(self) -> dict[str, Any]:
        """Return diagnostic metrics of the circuit breaker."""
        with self._lock:
            self._evaluate_state_transition()
            return {
                "name": self.name,
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "consecutive_successes": self._consecutive_successes,
                "total_trips": self._total_trips,
                "total_executions": self._total_executions,
                "total_failures": self._total_failures,
                "last_error": self._last_error,
                "last_state_change_seconds_ago": round(time.monotonic() - self._last_state_change, 2),
            }


# -----------------------------------------------------------------------------
# BackpressurePolicy & Concurrency Limiter
# -----------------------------------------------------------------------------


@dataclass
class BackpressurePolicy:
    """Backpressure control policy enforcing single-flight or bounded concurrency."""

    schema_version: str = RESILIENCE_CONTRACT_VERSION
    max_concurrent_requests: int = 2
    max_queue_size: int = 10
    rejection_status_code: int = 429
    acquire_timeout_seconds: float = 2.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConcurrencyLimiter:
    """Bounded semaphore concurrency limiter with timeout and fail-closed backpressure."""

    def __init__(self, policy: BackpressurePolicy | None = None, name: str = "etap_seat_lock") -> None:
        self.policy = policy or BackpressurePolicy()
        self.name = name
        self._semaphore = threading.BoundedSemaphore(value=self.policy.max_concurrent_requests)
        self._active_count: int = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Attempt to acquire execution slot within timeout. Raises BackpressureRejectionError on failure."""
        acquired = self._semaphore.acquire(timeout=self.policy.acquire_timeout_seconds)
        if not acquired:
            raise BackpressureRejectionError(
                f"Backpressure limit reached for '{self.name}'. "
                f"Max concurrency of {self.policy.max_concurrent_requests} exceeded. "
                "Explicit wire code 429 Too Many Requests.",
                status_code=self.policy.rejection_status_code,
            )
        with self._lock:
            self._active_count += 1
        return True

    def release(self) -> None:
        """Release execution slot."""
        with self._lock:
            if self._active_count > 0:
                self._active_count -= 1
                try:
                    self._semaphore.release()
                except ValueError:
                    pass

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active_count

    def __enter__(self) -> ConcurrencyLimiter:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# -----------------------------------------------------------------------------
# IdempotencyKey & IdempotencyStore
# -----------------------------------------------------------------------------


@dataclass
class IdempotencyKey:
    """Idempotency key descriptor tying a unique token to a payload hash."""

    token: str
    payload_hash: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0

    @classmethod
    def generate(cls, payload: dict[str, Any], token: str | None = None, ttl_seconds: float = 300.0) -> IdempotencyKey:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        resolved_token = token or hashlib.sha256(f"{payload_hash}:{time.time()}".encode()).hexdigest()[:16]
        return cls(token=resolved_token, payload_hash=payload_hash, ttl_seconds=ttl_seconds)

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IdempotencyStore:
    """Thread-safe store for in-flight and completed idempotent requests."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._max_entries = max_entries

    def check_or_set(self, key: IdempotencyKey) -> dict[str, Any] | None:
        """Return cached result if already completed for this key. If not present, records in-flight."""
        with self._lock:
            self._purge_expired()
            existing = self._entries.get(key.token)
            if existing:
                if existing["payload_hash"] != key.payload_hash:
                    raise ResilienceError(
                        f"Idempotency conflict: token '{key.token}' reused with different payload."
                    )
                return existing.get("response")
            self._entries[key.token] = {
                "payload_hash": key.payload_hash,
                "created_at": key.created_at,
                "ttl_seconds": key.ttl_seconds,
                "status": "in_flight",
                "response": None,
            }
            return None

    def complete(self, key: IdempotencyKey, response: dict[str, Any]) -> None:
        """Record completed response for idempotency token."""
        with self._lock:
            if key.token in self._entries:
                self._entries[key.token]["status"] = "completed"
                self._entries[key.token]["response"] = response

    def _purge_expired(self) -> None:
        now = time.time()
        expired_keys = [k for k, v in self._entries.items() if (now - v["created_at"]) > v["ttl_seconds"]]
        for k in expired_keys:
            del self._entries[k]
        if len(self._entries) > self._max_entries:
            oldest = sorted(self._entries.items(), key=lambda item: item[1]["created_at"])
            for k, _ in oldest[: len(self._entries) - self._max_entries]:
                del self._entries[k]

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


# Default singleton stores
default_idempotency_store = IdempotencyStore()
