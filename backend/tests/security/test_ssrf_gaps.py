"""Phase 4++ — Honest self-critique: tests that expose the GAPS left by
the previous "Phase 4 Complete" claim.

These tests SHOULD FAIL against the current _ssrf_guard.py / etap_service.py
(before the fixes in this round), proving the gaps are real, not theoretical.

Gap 1: socket.setdefaulttimeout is process-global → race condition
       when two threads call resolve_to_safe_ip() concurrently.

Gap 2: getaddrinfo can hang indefinitely on a slow DNS server
       (setdefaulttimeout does not reliably interrupt DNS resolution
        on all platforms).

Gap 3: export_to_etap / import_from_etap have no SSRF defense contract.
       A future developer implementing real network calls could skip
       resolve_to_safe_ip() entirely.

Gap 4: No TLS/SNI story — when HTTPS is added, certificate validation
       must use the ORIGINAL hostname, not the resolved IP.
"""
from __future__ import annotations

import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.integrations._ssrf_guard import (
    SSRFError,
    resolve_to_safe_ip,
    validate_host_for_user_input,
)


# ─── Gap 1: setdefaulttimeout race condition ────────────────────────────────


def test_resolve_to_safe_ip_does_not_mutate_global_default_timeout():
    """resolve_to_safe_ip must NOT mutate process-global socket state.

    The previous implementation did:
        old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(dns_timeout)   # ← pollutes global state
        ...
        socket.setdefaulttimeout(old)           # ← restores, but racy

    If another thread reads/writes getdefaulttimeout concurrently, the
    finally-block can restore the wrong value. This test verifies the
    function leaves getdefaulttimeout unchanged even when called with
    a non-default dns_timeout.
    """
    # Set a known starting state
    socket.setdefaulttimeout(None)
    resolve_to_safe_ip("example.com", dns_timeout=2.5)
    assert socket.getdefaulttimeout() is None, (
        "resolve_to_safe_ip mutated process-global default timeout — "
        "this is a race condition source."
    )

    socket.setdefaulttimeout(99.0)
    resolve_to_safe_ip("example.com", dns_timeout=2.5)
    assert socket.getdefaulttimeout() == 99.0, (
        "resolve_to_safe_ip overwrote a caller's default timeout — "
        "this is a race condition source."
    )
    socket.setdefaulttimeout(None)


def test_resolve_to_safe_ip_concurrent_calls_do_not_interfere(monkeypatch):
    """Two concurrent calls with different dns_timeout values must not
    corrupt each other's process-global state.

    The previous implementation would race on setdefaulttimeout. This
    test runs N threads in parallel and verifies getdefaulttimeout is
    unchanged after all of them complete.

    We mock getaddrinfo to return immediately (no real DNS) so the test
    is deterministic and not affected by network conditions.
    """
    # Mock getaddrinfo to return immediately (no real DNS lookup)
    monkeypatch.setattr(
        "backend.integrations._ssrf_guard.socket.getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    )

    socket.setdefaulttimeout(None)
    errors: list[str] = []

    def worker():
        try:
            resolve_to_safe_ip("example.com", dns_timeout=5.0)
        except Exception as e:
            errors.append(f"worker raised: {e!r}")

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Workers raised: {errors}"
    assert socket.getdefaulttimeout() is None, (
        "Concurrent calls corrupted process-global default timeout."
    )


# ─── Gap 2: getaddrinfo hang must be bounded by dns_timeout ─────────────────


def test_resolve_to_safe_ip_enforces_dns_timeout_even_when_getaddrinfo_hangs(monkeypatch):
    """A malicious slow-DNS server can hang getaddrinfo for minutes.
    socket.setdefaulttimeout does NOT reliably interrupt getaddrinfo
    on all platforms (Linux glibc may ignore it for DNS resolution).

    The fix must run getaddrinfo in a separate thread and enforce the
    timeout via thread.join(timeout=...). If the thread is still alive
    after the timeout, raise SSRFError.

    This test simulates a hanging getaddrinfo and asserts that
    resolve_to_safe_ip returns (or raises) within a reasonable bound.
    """
    def slow_getaddrinfo(host, *args, **kwargs):
        # Simulate a hung DNS resolver
        time.sleep(30)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("backend.integrations._ssrf_guard.socket.getaddrinfo", slow_getaddrinfo)

    start = time.monotonic()
    with pytest.raises(SSRFError, match="timed out|timeout"):
        resolve_to_safe_ip("slow-dns.attacker.com", dns_timeout=1.5)
    elapsed = time.monotonic() - start

    # Must return within 5 seconds even though getaddrinfo sleeps for 30
    assert elapsed < 5.0, (
        f"resolve_to_safe_ip took {elapsed:.1f}s — DNS timeout is not enforced. "
        f"A slow-DNS attacker can DoS the worker pool."
    )


# ─── Gap 3: export/import must declare SSRF defense contract ────────────────


def test_export_to_etap_must_use_resolve_to_safe_ip_when_real_network_added():
    """If a future developer implements real network calls in
    export_to_etap() or import_from_etap(), they MUST call
    resolve_to_safe_ip() first. This test verifies that either:
      (a) the method is still simulated (no real network call), OR
      (b) the method calls resolve_to_safe_ip() before any network I/O.

    A real network call without resolve_to_safe_ip() would re-introduce
    the SSRF vulnerability we just fixed in test_connection().
    """
    import inspect
    from backend.integrations.etap_service import EtapService

    src = inspect.getsource(EtapService.export_to_etap) + inspect.getsource(EtapService.import_from_etap)

    # If the source contains an HTTP client call, it must also contain
    # resolve_to_safe_ip.
    http_indicators = ["requests.", "httpx.", "urllib.request", "aiohttp.", "socket.create_connection"]
    uses_http = any(ind in src for ind in http_indicators)
    uses_resolver = "resolve_to_safe_ip" in src

    if uses_http:
        assert uses_resolver, (
            "export_to_etap/import_from_etap make network calls but do NOT "
            "call resolve_to_safe_ip(). This re-introduces the SSRF "
            "vulnerability fixed in test_connection()."
        )


def test_export_to_etap_has_explicit_ssrf_contract_comment():
    """The source must contain an explicit contract comment warning
    future developers to call resolve_to_safe_ip() before network I/O.
    This is a defense-in-depth measure to prevent regression."""
    import inspect
    from backend.integrations.etap_service import EtapService

    src = inspect.getsource(EtapService.export_to_etap) + inspect.getsource(EtapService.import_from_etap)
    assert "resolve_to_safe_ip" in src or "SSRF" in src or "ssrf" in src.lower(), (
        "export_to_etap / import_from_etap must reference resolve_to_safe_ip "
        "or SSRF in comments — future developers need to know to call the guard."
    )


# ─── Gap 4: TLS SNI story ───────────────────────────────────────────────────


def test_resolve_to_safe_ip_returns_original_hostname_for_tls_sni():
    """When TLS is added in the future, certificate validation MUST use
    the original hostname (for SNI and cert CN/SAN matching), NOT the
    resolved IP. Otherwise a MITM could serve a valid cert for
    'attacker.com' on a different IP and we'd accept it.

    This test verifies resolve_to_safe_ip exposes the original hostname
    alongside the safe IP, so future HTTPS code can:
        safe_ip, original_host = resolve_to_safe_ip_for_tls(host)
        sock = create_connection((safe_ip, port))
        ctx = ssl.create_default_context()
        # SNI uses original_host, not safe_ip
        tls_sock = ctx.wrap_socket(sock, server_hostname=original_host)

    The current API only returns the IP. This is a latent gap.
    """
    # Try to import the new function — should exist after the fix
    try:
        from backend.integrations._ssrf_guard import resolve_to_safe_ip_with_hostname
    except ImportError:
        pytest.fail(
            "resolve_to_safe_ip_with_hostname() does not exist. "
            "Future HTTPS code will have no way to do correct SNI/cert validation."
        )

    with patch("backend.integrations._ssrf_guard.socket.getaddrinfo") as mock:
        mock.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ]
        result = resolve_to_safe_ip_with_hostname("example.com")
        # Must return a tuple of (safe_ip, original_hostname)
        assert isinstance(result, tuple), "Must return (safe_ip, hostname) tuple"
        assert len(result) == 2
        safe_ip, hostname = result
        assert safe_ip == "93.184.216.34"
        assert hostname == "example.com", (
            "Original hostname must be returned for TLS SNI / cert validation."
        )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
