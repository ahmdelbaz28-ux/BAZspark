"""Phase 4+ — Comprehensive SSRF defense tests.

Tests the standard SSRF guard module (_ssrf_guard.py) against every known
attack vector, plus tests that the service layer (etap_service.py) actually
uses the guard at connection time.

Attack vectors covered:
  1. Literal private IPs (IPv4): 127.0.0.1, 10.0.0.1, 192.168.1.1, 172.16.0.1
  2. Literal private IPs (IPv6): ::1, fe80::1, fc00::1
  3. IPv4-mapped IPv6 (bypass): ::ffff:127.0.0.1, ::ffff:169.254.169.254
  4. Cloud metadata IPs: 169.254.169.254 (AWS/GCP/Azure)
  5. CGNAT: 100.64.0.1 (not flagged by Python's is_private!)
  6. Localhost variants: localhost, localhost.localdomain, ip6-localhost
  7. Cloud metadata hostnames: metadata.google.internal, metadata
  8. Hostnames resolving to private IPs (localtest.me → 127.0.0.1)
  9. DNS rebinding: hostname changes between validation and connection
  10. Service layer uses literal IP (not hostname) — verified via mock
"""

import socket
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.integrations._ssrf_guard import (
    SSRFError,
    resolve_to_safe_ip,
    validate_host_for_user_input,
)
from backend.integrations.etap_schemas import EtapConnectionSettings, EtapSettingsUpdate

# ─── 1. Literal private IPv4 addresses ─────────────────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "127.255.255.255",  # loopback upper
        "10.0.0.1",  # RFC1918
        "10.255.255.255",  # RFC1918
        "172.16.0.1",  # RFC1918
        "172.31.255.255",  # RFC1918
        "192.168.1.1",  # RFC1918
        "192.168.0.0",  # RFC1918
        "169.254.169.254",  # link-local / AWS metadata
        "169.254.0.1",  # link-local
        "0.0.0.0",  # "this host"
        "0.0.0.1",  # "this host" network
        "224.0.0.1",  # multicast
        "239.255.255.255",  # multicast
        "240.0.0.1",  # reserved
        "255.255.255.255",  # broadcast (reserved)
    ],
)
def test_literal_unsafe_ipv4_is_rejected_by_validator(ip):
    with pytest.raises(SSRFError):
        validate_host_for_user_input(ip)


# ─── 2. Literal private IPv6 addresses ─────────────────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "::1",  # IPv6 loopback
        "::",  # IPv6 unspecified
        "fe80::1",  # IPv6 link-local
        "fe80::",  # IPv6 link-local
        "fc00::1",  # IPv6 ULA
        "fd00::1",  # IPv6 ULA
        "ff00::1",  # IPv6 multicast
        "ff02::1",  # IPv6 multicast
    ],
)
def test_literal_unsafe_ipv6_is_rejected_by_validator(ip):
    with pytest.raises(SSRFError):
        validate_host_for_user_input(ip)


# ─── 3. IPv4-mapped IPv6 bypass attempts ────────────────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:169.254.169.254",  # IPv4-mapped AWS metadata
        "::ffff:10.0.0.1",  # IPv4-mapped private
        "::ffff:192.168.1.1",  # IPv4-mapped private
        "::ffff:0.0.0.0",  # IPv4-mapped unspecified
        "::ffff:255.255.255.255",  # IPv4-mapped broadcast
    ],
)
def test_ipv4_mapped_ipv6_bypass_is_rejected(ip):
    """Critical: ::ffff:127.0.0.1 must be detected as 127.0.0.1 in disguise."""
    with pytest.raises(SSRFError):
        validate_host_for_user_input(ip)


# ─── 4. Cloud metadata IPs ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "169.254.169.254",  # AWS/GCP/Azure metadata
        "169.254.169.253",  # GCP metadata (older)
        "100.100.100.200",  # Alibaba Cloud metadata (CGNAT range, blocked by network list)
    ],
)
def test_cloud_metadata_ips_are_rejected(ip):
    with pytest.raises(SSRFError):
        validate_host_for_user_input(ip)


# ─── 5. CGNAT (not flagged by Python's is_private) ────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "100.64.0.1",  # CGNAT start
        "100.127.255.255",  # CGNAT end
    ],
)
def test_cgnat_range_is_rejected(ip):
    """Python's ipaddress.is_private does NOT flag CGNAT (100.64.0.0/10).
    Our explicit _BLOCKED_NETWORKS list must catch it."""
    with pytest.raises(SSRFError):
        validate_host_for_user_input(ip)


# ─── 6. Localhost variants ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hostname",
    [
        "localhost",
        "localhost.localdomain",
        "localhost4",
        "localhost6",
        "ip6-localhost",
        "ip6-loopback",
        "Localhost",  # case-insensitive
        "LOCALHOST",  # case-insensitive
        "localhost.",  # trailing dot
    ],
)
def test_localhost_variants_are_rejected(hostname):
    with pytest.raises(SSRFError):
        validate_host_for_user_input(hostname)


# ─── 7. Cloud metadata hostnames ──────────────────────────────────────────


@pytest.mark.parametrize(
    "hostname",
    [
        "metadata.google.internal",  # GCP
        "metadata",  # GCP alias
        "metadata.azure.com",  # Azure
        "Metadata.Google.Internal",  # case-insensitive
    ],
)
def test_cloud_metadata_hostnames_are_rejected(hostname):
    with pytest.raises(SSRFError):
        validate_host_for_user_input(hostname)


# ─── 8. Hostnames resolving to private IPs (DNS check) ────────────────────


def test_hostname_resolving_to_loopback_is_rejected():
    """localtest.me is a public DNS name that resolves to 127.0.0.1.
    The validator accepts it (pure check, no DNS), but the service-layer
    resolver must reject it."""
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()

    # Step 1: validator accepts (pure check — no DNS, no network I/O)
    assert validate_host_for_user_input("localtest.me") == "localtest.me"

    # Step 2: service-layer resolver rejects (DNS resolves to 127.0.0.1)
    with pytest.raises(SSRFError, match="resolves only to unsafe"):
        resolve_to_safe_ip("localtest.me")


# ─── 9. DNS rebinding is defeated by service-layer resolver ────────────────


def test_dns_rebinding_attack_is_defeated():
    """Simulate DNS rebinding: the hostname resolves to a public IP first
    (passes validator), then to a private IP at connection time (must be
    rejected by resolve_to_safe_ip).

    Note: the validator no longer does DNS (it's pure). The rebinding defense
    is entirely in the service layer. We simulate two consecutive
    resolve_to_safe_ip calls where DNS changes between them.

    PARALLEL EXECUTION ROBUSTNESS:
    ------------------------------
    This test does NOT use a call_count to determine which IP to return.
    Instead, it uses a STATEFUL FLAG that is toggled by the test itself
    (not by getaddrinfo call count). This prevents interference from
    leftover daemon threads (started by _resolve_host_with_timeout in
    previous tests) that might call getaddrinfo and increment a counter.

    The flag is explicitly set to 'public' before step 2, and 'private'
    before step 4. The fake getaddrinfo reads the flag at call time,
    so the order is deterministic regardless of how many times
    getaddrinfo is called by leftover threads.
    """
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()

    # Unique hostname — no other test uses this.
    test_host = "rebinding-attacker-test-xyzzy.com"

    # Stateful flag: 'public' or 'private'. The test explicitly toggles
    # this before each resolve_to_safe_ip call.
    dns_state = {"ip": "public"}

    def fake_getaddrinfo(host, *args, **kwargs):
        # For other hosts (leftover daemon threads), return a safe default.
        if host != test_host:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        # For our test host, return based on the current state.
        if dns_state["ip"] == "public":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    with patch("backend.integrations._ssrf_guard.socket.getaddrinfo", side_effect=fake_getaddrinfo):
        # Step 1: validator passes (pure check — no DNS, no network I/O)
        host = validate_host_for_user_input(test_host)
        assert host == test_host

        # Step 2: first service-layer call succeeds (DNS returns public IP)
        dns_state["ip"] = "public"
        safe_ip = resolve_to_safe_ip(host)
        assert safe_ip == "93.184.216.34"

        # Step 3: clear cache to simulate a fresh request after DNS rebinding.
        # Also wait briefly for any in-flight daemon threads from previous
        # tests to finish caching their results (which would repopulate the
        # cache AFTER our reset). The 0.3s wait is enough for daemon threads
        # to complete their caching logic (which is just a dict assignment).
        _reset_dns_state_for_testing()
        import time as _time

        _time.sleep(0.3)
        # Clear AGAIN after the wait, in case a daemon thread repopulated
        # the cache during the sleep.
        _reset_dns_state_for_testing()

        # Step 4: second service-layer call rejects (DNS now returns private IP)
        dns_state["ip"] = "private"
        with pytest.raises(SSRFError, match="resolves only to unsafe"):
            resolve_to_safe_ip(host)


def test_service_layer_pins_to_literal_ip_not_hostname():
    """After resolve_to_safe_ip succeeds, the returned value must be a
    literal IP — so the caller's socket.create_connection uses the IP
    directly without further DNS lookup. This is the core DNS-rebinding
    defense."""
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()

    with patch("backend.integrations._ssrf_guard.socket.getaddrinfo") as mock:
        mock.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        result = resolve_to_safe_ip("example.com")
        # Must return the literal IP, not the hostname
        assert result == "93.184.216.34"
        assert result != "example.com"


def test_resolver_skips_unsafe_ips_in_resolution_list():
    """If a hostname resolves to BOTH public and private IPs, the resolver
    must return the public IP (not fail)."""
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()

    with patch("backend.integrations._ssrf_guard.socket.getaddrinfo") as mock:
        mock.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),  # unsafe
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),  # safe
        ]
        result = resolve_to_safe_ip("dual-stack.example.com")
        assert result == "93.184.216.34"


def test_resolver_rejects_when_all_resolved_ips_are_unsafe():
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()
    with patch("backend.integrations._ssrf_guard.socket.getaddrinfo") as mock:
        mock.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0)),
        ]
        with pytest.raises(SSRFError, match="resolves only to unsafe"):
            resolve_to_safe_ip("evil-internal.com")


# ─── 10. Public IPs and hostnames still work (regression guards) ──────────


@pytest.mark.parametrize(
    "ip",
    [
        "8.8.8.8",  # Google DNS
        "1.1.1.1",  # Cloudflare DNS
        "93.184.216.34",  # example.com
    ],
)
def test_public_ipv4_addresses_are_allowed(ip):
    assert validate_host_for_user_input(ip) == ip


@pytest.mark.parametrize(
    "ip",
    [
        "2606:4700:4700::1111",  # Cloudflare
        "2001:4860:4860::8888",  # Google
    ],
)
def test_public_ipv6_addresses_are_allowed(ip):
    assert validate_host_for_user_input(ip) == ip


def test_public_hostname_is_allowed():
    assert validate_host_for_user_input("example.com") == "example.com"


# ─── 11. Schema-level integration tests ───────────────────────────────────


@pytest.mark.parametrize(
    "bad_host",
    [
        "127.0.0.1",
        "169.254.169.254",
        "localhost",
        "metadata.google.internal",
        "::1",
        "::ffff:127.0.0.1",
        "fe80::1",
        "fc00::1",
        "10.0.0.1",
        "100.64.0.1",  # CGNAT
    ],
)
def test_etap_connection_settings_rejects_all_attack_vectors(bad_host):
    with pytest.raises(ValidationError):
        EtapConnectionSettings(host=bad_host, port=80, username="u", password="p")


@pytest.mark.parametrize(
    "bad_host",
    [
        "127.0.0.1",
        "169.254.169.254",
        "localhost",
        "metadata.google.internal",
        "::1",
        "::ffff:127.0.0.1",
        "fe80::1",
        "fc00::1",
        "10.0.0.1",
        "100.64.0.1",  # CGNAT
    ],
)
def test_etap_settings_update_rejects_all_attack_vectors(bad_host):
    with pytest.raises(ValidationError):
        EtapSettingsUpdate(host=bad_host, port=80, username="u", password="p")


def test_etap_connection_settings_accepts_public_hostname():
    s = EtapConnectionSettings(host="example.com", port=80, username="u", password="p")
    assert s.host == "example.com"


def test_etap_settings_update_accepts_public_hostname():
    s = EtapSettingsUpdate(host="example.com", port=80, username="u", password="p")
    assert s.host == "example.com"


# ─── 12. Service-layer integration test (verifies the full chain) ──────────


def test_etap_service_test_connection_blocks_ssrf_via_dns_rebinding(monkeypatch):
    """End-to-end: simulate DNS rebinding between validator and service layer.
    Verify EtapService.test_connection() refuses to connect.

    With the new TTL cache, DNS rebinding is actually DEFEATED by the cache
    (within the 60s positive-TTL window): the cached safe IP is reused.
    This test verifies the OTHER case: when the hostname resolves to a
    private IP at connection time (no prior cache), the service layer rejects.
    """
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()

    # Setup: getaddrinfo returns PRIVATE IP (simulating DNS rebinding BEFORE
    # the cache is populated, or after the cache expires)
    def fake_getaddrinfo(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    # Import here to ensure we patch the right module
    from backend.integrations import _ssrf_guard

    monkeypatch.setattr(_ssrf_guard.socket, "getaddrinfo", fake_getaddrinfo)

    # Step 1: validator passes (pure check — no DNS, no network I/O)
    settings = EtapConnectionSettings(
        host="rebinding.attacker.com", port=80, username="u", password="p"
    )
    assert settings.host == "rebinding.attacker.com"

    # Step 2: build a fake EtapService with the validated settings
    from backend.integrations.etap_service import EtapService

    fake_db = MagicMock()
    svc = EtapService(fake_db)
    # Monkey-patch get_settings to return our validated host
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda project_id: {
            "id": "test",
            "project_id": project_id,
            "host": settings.host,
            "port": settings.port,
            "username": settings.username,
            "password": "encrypted_placeholder",  # bypass decrypt check
            "enabled": True,
            "timeout_seconds": 5,
            "last_sync": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )
    # Bypass decrypt_password — return truthy
    monkeypatch.setattr("backend.integrations.etap_service.decrypt_password", lambda x: "decrypted")

    # Step 3: service layer must reject the connection (DNS returns private IP)
    result = svc.test_connection("test_project")
    assert result["success"] is False
    assert "refused" in result["message"].lower() or "not allowed" in result["message"].lower()


def test_etap_service_test_connection_uses_literal_ip_not_hostname(monkeypatch):
    """Verify EtapService.test_connection passes a LITERAL IP to
    socket.create_connection, not a hostname. This is the core defense
    against DNS rebinding at the socket layer."""
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing

    _reset_dns_state_for_testing()

    captured_args = []

    class FakeSocket:
        def close(self):
            pass

    def fake_create_connection(address, *args, **kwargs):
        captured_args.append(address)
        return FakeSocket()

    # Make getaddrinfo return a stable public IP (no rebinding)
    from backend.integrations import _ssrf_guard

    monkeypatch.setattr(
        _ssrf_guard.socket,
        "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    # etap_service.py does `import socket as _socket` INSIDE the function,
    # so patching the global socket module is the correct approach.
    monkeypatch.setattr("socket.create_connection", fake_create_connection)

    from backend.integrations.etap_service import EtapService

    fake_db = MagicMock()
    svc = EtapService(fake_db)
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda project_id: {
            "id": "test",
            "project_id": project_id,
            "host": "example.com",
            "port": 80,
            "username": "u",
            "password": "encrypted",
            "enabled": True,
            "timeout_seconds": 5,
            "last_sync": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )
    monkeypatch.setattr("backend.integrations.etap_service.decrypt_password", lambda x: "decrypted")

    result = svc.test_connection("test_project")
    assert result["success"] is True
    # The critical assertion: create_connection was called with a LITERAL IP
    # (93.184.216.34), NOT with the hostname "example.com".
    assert len(captured_args) == 1, (
        f"Expected 1 call to create_connection, got {len(captured_args)}"
    )
    ip_passed, port_passed = captured_args[0]
    assert ip_passed == "93.184.216.34", (
        f"Expected literal IP '93.184.216.34' but got '{ip_passed}'. "
        f"DNS rebinding defense is broken — service is using hostname, not IP."
    )
    assert port_passed == 80


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
