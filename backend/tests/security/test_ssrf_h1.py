"""Phase 4 — Failing test for H-1 (SSRF via DNS rebinding + missing check on EtapSettingsUpdate).

Evidence chain:
- backend/integrations/etap_schemas.py:23-44  EtapConnectionSettings.validate_host
  Only blocks literal private IPs. Hostnames resolving to private IPs pass.
- backend/integrations/etap_schemas.py:128-145  EtapSettingsUpdate.validate_host
  Has NO SSRF check at all — accepts any string including 127.0.0.1, 169.254.169.254.
- backend/routers/etap.py:54   POST /integrations/etap/connect (uses EtapConnectionSettings)
- backend/routers/etap.py:238  PUT /integrations/etap/settings  (uses EtapSettingsUpdate)

Both endpoints require INTEGRATION_MANAGE permission (RBAC), so this is HIGH not CRITICAL.
However, any user with INTEGRATION_MANAGE can:
  1. Probe internal network via connection attempts (timing/error-based)
  2. Reach AWS/GCP metadata endpoints (169.254.169.254, metadata.google.internal)
  3. Pivot to internal services (Redis on 6379, Qdrant on 6333, Neo4j on 7687)
"""

import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from backend.integrations.etap_schemas import EtapConnectionSettings, EtapSettingsUpdate

# ─── Test fixtures ─────────────────────────────────────────────────────────

# A real public DNS name that resolves to 127.0.0.1.
# Source: https://localtest.me about page — resolves all subdomains to 127.0.0.1.
DNS_REBINDING_HOST = "localtest.me"

# Verify the host actually resolves to a private IP (otherwise the test is moot)
try:
    resolved = socket.gethostbyname(DNS_REBINDING_HOST)
    if not resolved.startswith("127."):
        print(
            f"WARNING: {DNS_REBINDING_HOST} resolved to {resolved}, not 127.0.0.1. "
            f"Test may not be meaningful."
        )
except socket.gaierror:
    pass  # Test will still fail at validation layer


# ─── Tests for EtapConnectionSettings ──────────────────────────────────────


def test_etap_connection_settings_rejects_literal_loopback():
    """Baseline: literal 127.0.0.1 IS rejected (existing fix works)."""
    try:
        EtapConnectionSettings(host="127.0.0.1", port=80, username="u", password="p")
        raise AssertionError("Should have rejected 127.0.0.1")
    except ValidationError as e:
        assert "SSRF" in str(e) or "private" in str(e).lower()


def test_etap_connection_settings_rejects_dns_rebinding_to_loopback():
    """ARCHITECTURE CHANGE: the validator is now PURE (no DNS).
    It accepts 'localtest.me' (valid hostname format, not in blocklist).
    The DNS check happens at the SERVICE LAYER (resolve_to_safe_ip).

    This test verifies the full chain:
      1. Validator accepts the hostname (pure check)
      2. Service-layer resolver rejects it (DNS resolves to 127.0.0.1)
    """
    from backend.integrations._ssrf_guard import (
        SSRFError,
        _reset_dns_state_for_testing,
        resolve_to_safe_ip,
    )

    _reset_dns_state_for_testing()

    # Step 1: validator accepts (pure — no DNS)
    s = EtapConnectionSettings(host=DNS_REBINDING_HOST, port=80, username="u", password="p")
    assert s.host == DNS_REBINDING_HOST

    # Step 2: service-layer resolver rejects (DNS resolves to 127.0.0.1)
    try:
        resolve_to_safe_ip(DNS_REBINDING_HOST)
        raise AssertionError(
            f"SSRF bypass: resolve_to_safe_ip accepted '{DNS_REBINDING_HOST}' "
            f"which resolves to 127.0.0.1. The service layer should reject "
            f"hostnames that resolve to private IPs."
        )
    except SSRFError:
        pass  # Good: service layer rejected it


def test_etap_connection_settings_rejects_aws_metadata_literal():
    """Baseline: AWS metadata IP IS rejected."""
    try:
        EtapConnectionSettings(host="169.254.169.254", port=80, username="u", password="p")
        raise AssertionError("Should have rejected 169.254.169.254")
    except ValidationError as e:
        assert "SSRF" in str(e) or "private" in str(e).lower() or "reserved" in str(e).lower()


# ─── Tests for EtapSettingsUpdate ──────────────────────────────────────────


def test_etap_settings_update_rejects_literal_loopback():
    """EtapSettingsUpdate must reject 127.0.0.1 (currently has NO SSRF check)."""
    try:
        EtapSettingsUpdate(host="127.0.0.1", port=80, username="u", password="p")
        raise AssertionError(
            "SSRF: EtapSettingsUpdate accepted host='127.0.0.1'. "
            "This model has NO SSRF check at all — any INTEGRATION_MANAGE user "
            "can target internal network via PUT /integrations/etap/settings."
        )
    except ValidationError:
        pass


def test_etap_settings_update_rejects_aws_metadata_literal():
    """EtapSettingsUpdate must reject AWS metadata IP."""
    try:
        EtapSettingsUpdate(host="169.254.169.254", port=80, username="u", password="p")
        raise AssertionError(
            "SSRF: EtapSettingsUpdate accepted host='169.254.169.254'. "
            "AWS/GCP metadata endpoints would be reachable."
        )
    except ValidationError:
        pass


def test_etap_settings_update_rejects_dns_rebinding():
    """ARCHITECTURE CHANGE: the validator is now PURE (no DNS).
    It accepts 'localtest.me' (valid hostname format).
    The DNS check happens at the SERVICE LAYER.

    This test verifies the full chain:
      1. Validator accepts the hostname
      2. Service-layer resolver rejects it (DNS resolves to 127.0.0.1)
    """
    from backend.integrations._ssrf_guard import (
        SSRFError,
        _reset_dns_state_for_testing,
        resolve_to_safe_ip,
    )

    _reset_dns_state_for_testing()

    # Step 1: validator accepts (pure — no DNS)
    s = EtapSettingsUpdate(host=DNS_REBINDING_HOST, port=80, username="u", password="p")
    assert s.host == DNS_REBINDING_HOST

    # Step 2: service-layer resolver rejects
    try:
        resolve_to_safe_ip(DNS_REBINDING_HOST)
        raise AssertionError(f"SSRF bypass: resolve_to_safe_ip accepted '{DNS_REBINDING_HOST}'.")
    except SSRFError:
        pass  # Good: service layer rejected it


# ─── Tests for legitimate public hostnames (regression guard) ──────────────


def test_etap_connection_settings_accepts_public_hostname():
    """Regression: legitimate public hostnames (e.g. example.com) must still work."""
    s = EtapConnectionSettings(host="example.com", port=80, username="u", password="p")
    assert s.host == "example.com"


def test_etap_settings_update_accepts_public_hostname():
    """Regression: legitimate public hostnames must still work for updates."""
    s = EtapSettingsUpdate(host="example.com", port=80, username="u", password="p")
    assert s.host == "example.com"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
