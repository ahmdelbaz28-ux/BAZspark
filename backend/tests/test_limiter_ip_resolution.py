"""
test_limiter_ip_resolution.py — C-01 regression tests.

Verifies that get_remote_address() only trusts proxy headers (CF-Connecting-IP,
True-Client-IP, X-Forwarded-For) when the request actually transited a
configured/enabled proxy, and otherwise falls back to the TCP peer IP.

VULN C-01: previously an attacker could spoof X-Forwarded-For / CF-Connecting-IP
to evade per-IP rate limits.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from backend.limiter import get_remote_address


def _make_request(client_ip: str, headers: dict[str, str] | None = None) -> Request:
    """Build a minimal ASGI scope Request with a given TCP peer and headers."""
    headers = headers or {}
    raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
    scope: dict = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


class TestNoProxyConfigured:
    """Without TRUSTED_PROXIES and with CDNs disabled, only the peer is used."""

    def test_spoofed_xff_ignored(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        monkeypatch.setenv("CF_ENABLED", "false")
        monkeypatch.setenv("AKAMAI_ENABLED", "false")

        req = _make_request("1.2.3.4", {"X-Forwarded-For": "6.6.6.6"})
        assert get_remote_address(req) == "1.2.3.4"

    def test_spoofed_cf_connecting_ip_ignored(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        monkeypatch.setenv("CF_ENABLED", "false")

        req = _make_request("1.2.3.4", {"CF-Connecting-IP": "6.6.6.6"})
        assert get_remote_address(req) == "1.2.3.4"

    def test_spoofed_true_client_ip_ignored(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        monkeypatch.setenv("AKAMAI_ENABLED", "false")

        req = _make_request("1.2.3.4", {"True-Client-IP": "6.6.6.6"})
        assert get_remote_address(req) == "1.2.3.4"

    def test_spoofed_akamai_client_ip_ignored(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        monkeypatch.setenv("AKAMAI_ENABLED", "false")

        req = _make_request("1.2.3.4", {"Akamai-Client-IP": "6.6.6.6"})
        assert get_remote_address(req) == "1.2.3.4"

    def test_no_headers_uses_peer(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

        req = _make_request("1.2.3.4")
        assert get_remote_address(req) == "1.2.3.4"


class TestTrustedProxy:
    """When the TCP peer is a trusted proxy, XFF's LAST hop is honored."""

    def test_xff_last_hop_from_trusted_peer(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("CF_ENABLED", "false")
        monkeypatch.setenv("AKAMAI_ENABLED", "false")

        req = _make_request("10.0.0.1", {"X-Forwarded-For": "6.6.6.6, 203.0.113.5"})
        assert get_remote_address(req) == "203.0.113.5"

    def test_xff_from_untrusted_peer_ignored(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("CF_ENABLED", "false")
        monkeypatch.setenv("AKAMAI_ENABLED", "false")

        req = _make_request("203.0.113.9", {"X-Forwarded-For": "6.6.6.6"})
        assert get_remote_address(req) == "203.0.113.9"


class TestProxyEnabled:
    """When Cloudflare/Akamai integration is enabled, edge headers are trusted ONLY from trusted peers."""

    def test_cf_header_trusted_from_trusted_proxy(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("CF_ENABLED", "true")

        req = _make_request("10.0.0.1", {"CF-Connecting-IP": "6.6.6.6"})
        assert get_remote_address(req) == "6.6.6.6"

    def test_cf_header_ignored_from_untrusted_peer_even_if_cf_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("CF_ENABLED", "true")

        # Untrusted direct peer connecting directly with forged CF-Connecting-IP header
        req = _make_request("198.51.100.2", {"CF-Connecting-IP": "1.1.1.1"})
        assert get_remote_address(req) == "198.51.100.2"

    def test_akamai_header_trusted_from_trusted_proxy(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("AKAMAI_ENABLED", "true")

        req = _make_request("10.0.0.1", {"True-Client-IP": "6.6.6.6"})
        assert get_remote_address(req) == "6.6.6.6"

    def test_akamai_header_ignored_from_untrusted_peer_even_if_akamai_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("AKAMAI_ENABLED", "true")

        # Untrusted direct peer connecting directly with forged True-Client-IP header
        req = _make_request("198.51.100.2", {"True-Client-IP": "1.1.1.1"})
        assert get_remote_address(req) == "198.51.100.2"

    def test_akamai_client_ip_trusted_from_trusted_proxy(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("AKAMAI_ENABLED", "true")

        req = _make_request("10.0.0.1", {"Akamai-Client-IP": "6.6.6.6"})
        assert get_remote_address(req) == "6.6.6.6"

    def test_akamai_client_ip_ignored_from_untrusted_peer_even_if_akamai_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("AKAMAI_ENABLED", "true")

        # Untrusted direct peer connecting directly with forged Akamai-Client-IP header
        req = _make_request("198.51.100.2", {"Akamai-Client-IP": "1.1.1.1"})
        assert get_remote_address(req) == "198.51.100.2"

    def test_edge_headers_beat_xff(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
        monkeypatch.setenv("CF_ENABLED", "true")

        req = _make_request(
            "10.0.0.1", {"CF-Connecting-IP": "6.6.6.6", "X-Forwarded-For": "9.9.9.9"}
        )
        assert get_remote_address(req) == "6.6.6.6"
