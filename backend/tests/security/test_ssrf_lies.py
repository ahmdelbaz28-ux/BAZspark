"""Phase 4+++ — Truly honest self-critique: tests that expose the LIES
still in the previous "Honest Complete" claim.

LIE 1: "Defense is complete against slow-DNS DoS"
  REALITY: validate_host_for_user_input() calls _resolve_host() with NO
  timeout (line 338). A slow-DNS attacker hangs the Pydantic validator
  → hangs the entire request. The fix in resolve_to_safe_ip() did NOT
  cover the validator.

LIE 2: "Validator does DNS checks safely"
  REALITY: Pydantic validators should be pure (no network I/O). The
  validator's DNS check is (a) slow, (b) can hang, (c) redundant with
  the service layer, (d) creates TOCTOU. Architecturally wrong.

LIE 3: "Semaphore protects against DoS"
  REALITY: The semaphore is GLOBAL. 8 stuck lookups on host A blocks
  ALL lookups on host B. One attacker can DoS every ETAP integration
  for every user.

LIE 4: "Code is testable"
  REALITY: The global semaphore cannot be reset. A test that exhausts
  the semaphore (8 stuck lookups) pollutes all subsequent tests.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from backend.integrations._ssrf_guard import (
    SSRFError,
    resolve_to_safe_ip,
    validate_host_for_user_input,
)

# ─── LIE 1: Validator hangs on slow DNS ─────────────────────────────────────


def test_validator_does_not_hang_on_slow_dns(monkeypatch):
    """The validator calls _resolve_host() with NO timeout. A slow-DNS
    attacker can hang the validator (and thus the request) indefinitely.

    This test patches getaddrinfo to sleep 30s and asserts the validator
    returns within 2s (either accepts or rejects, but does NOT hang).
    """

    def slow_getaddrinfo(host, *args, **kwargs):
        time.sleep(30)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", slow_getaddrinfo)

    start = time.monotonic()
    # Should return (or raise) within 2 seconds, NOT hang for 30s
    try:
        validate_host_for_user_input("some-host.example.com")
    except SSRFError:
        pass  # rejection is fine — we just need it to be FAST
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, (
        f"Validator took {elapsed:.1f}s — it hangs on slow DNS. "
        f"This is the SAME DoS bug claimed to be fixed in resolve_to_safe_ip(). "
        f"The fix was incomplete: the validator was left vulnerable."
    )


# ─── LIE 2: Validator should be pure (no network I/O) ───────────────────────


def test_validator_is_pure_no_network_io_for_literal_ip(monkeypatch):
    """A Pydantic validator must NOT perform network I/O. For a literal
    IP, the validator should return immediately without any DNS lookup."""

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Validator performed network I/O (getaddrinfo called) for a "
            "literal IP. Validators must be pure."
        )

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", fail_if_called)

    # Literal public IP — should pass without any DNS call
    result = validate_host_for_user_input("8.8.8.8")
    assert result == "8.8.8.8"


def test_validator_is_pure_no_network_io_for_blocked_hostname(monkeypatch):
    """For a blocked hostname (localhost), the validator should reject
    without any DNS lookup."""

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Validator performed network I/O for a blocked hostname. Validators must be pure."
        )

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", fail_if_called)

    with pytest.raises(SSRFError):
        validate_host_for_user_input("localhost")


def test_validator_is_pure_no_network_io_for_hostname(monkeypatch):
    """For a regular hostname, the validator should accept it (format
    check only) WITHOUT performing DNS resolution. DNS resolution is the
    job of the service layer (resolve_to_safe_ip)."""

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Validator performed network I/O for a hostname. "
            "DNS checks belong in the service layer, not the validator. "
            "The validator should be pure (fast, deterministic, no side effects)."
        )

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", fail_if_called)

    # Should return the hostname as-is, without DNS lookup
    result = validate_host_for_user_input("example.com")
    assert result == "example.com"


def test_validator_is_deterministic(monkeypatch):
    """The validator must be deterministic: same input → same output,
    regardless of DNS state. If DNS is up vs down, the validator must
    give the same answer (otherwise it's non-deterministic, which is
    unacceptable for a Pydantic validator)."""
    call_count = [0]

    def flaky_getaddrinfo(host, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] % 2 == 0:
            # Simulate transient DNS failure
            raise socket.gaierror("Transient DNS failure")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", flaky_getaddrinfo)

    # Same input must give same output every time
    results = set()
    for _ in range(10):
        r = validate_host_for_user_input("example.com")
        results.add(r)
    assert len(results) == 1, (
        f"Validator is non-deterministic: gave {len(results)} different "
        f"results for the same input. Validators must be pure."
    )


# ─── LIE 3: Cross-host DoS via global semaphore ─────────────────────────────


def test_stuck_dns_on_host_a_does_not_block_host_b(monkeypatch):
    """CRITICAL: The global semaphore means 8 stuck lookups on host A
    blocks ALL lookups on host B. One attacker can DoS every ETAP
    integration for every user.

    This test verifies that a stuck lookup on 'evil.attacker.com' does
    NOT prevent a lookup on 'legitimate.example.com' from succeeding.
    """
    # Ensure clean semaphore state at start
    _reset_dns_state_if_possible()

    def evil_getaddrinfo(host, *args, **kwargs):
        if "evil" in host:
            time.sleep(30)  # attacker's hostname hangs
        # Legitimate hostname resolves fast
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", evil_getaddrinfo)

    # Step 1: launch N concurrent lookups on the attacker's hostname
    # (enough to exhaust the global semaphore)
    attacker_threads = []
    attacker_errors = []

    def attack():
        try:
            resolve_to_safe_ip("evil.attacker.com", dns_timeout=0.5)
        except SSRFError:
            pass  # expected timeout
        except Exception as e:
            attacker_errors.append(e)

    # Spawn 10 attacker threads (more than the semaphore limit of 8)
    for _ in range(10):
        t = threading.Thread(target=attack, daemon=True)
        attacker_threads.append(t)
        t.start()

    # Give them time to grab the semaphore
    time.sleep(0.2)

    # Step 2: a legitimate user tries to resolve a DIFFERENT hostname
    # This MUST succeed — the attacker's stuck lookups should not affect it.
    start = time.monotonic()
    try:
        result = resolve_to_safe_ip("legitimate.example.com", dns_timeout=3.0)
        elapsed = time.monotonic() - start
        # Must succeed and be fast
        assert result == "93.184.216.34", f"Expected legitimate IP, got {result}"
        assert elapsed < 2.0, (
            f"Legitimate lookup took {elapsed:.1f}s — cross-host DoS detected. "
            f"The global semaphore lets attacker's stuck lookups block legitimate users."
        )
    except SSRFError as e:
        elapsed = time.monotonic() - start
        if "concurrency limit" in str(e).lower() or "exceeded" in str(e).lower():
            pytest.fail(
                f"CROSS-HOST DoS: legitimate lookup rejected because global "
                f"semaphore was exhausted by attacker's stuck lookups. "
                f"Error: {e}"
            )
        raise

    # Cleanup: wait for attacker threads to time out
    for t in attacker_threads:
        t.join(timeout=2.0)


# ─── LIE 4: No test reset function ──────────────────────────────────────────


def test_dns_state_can_be_reset_for_testing():
    """The global semaphore cannot be reset between tests. A test that
    exhausts the semaphore pollutes all subsequent tests.

    This test verifies that a _reset_dns_state_for_testing() function
    exists and can be called to restore clean state.
    """
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    # Should be callable without error
    _reset_dns_state_for_testing()


# ─── Helper ─────────────────────────────────────────────────────────────────


def _reset_dns_state_if_possible():
    """Reset DNS state if the function exists; no-op otherwise."""
    try:
        from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

        _reset_dns_state_for_testing()
    except ImportError:
        pass


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
