"""
test_env_validator_placeholders.py — C-02/C-03/C-04 + L-18 regression tests.

Verifies that production boot fails (HARD) when any legacy placeholder value
from the old .env.example templates is supplied as a secret:
  - FIREAI_API_KEY      = "dev-fireai-key-local"                 (C-02)
  - FIREAI_SESSION_SECRET = "dev-session-secret-please-replace…" (C-03)
  - QOMN_AUDIT_SECRET_KEY = "change-me-please"                   (C-04)
  - FIREAI_API_KEY      = "test-api-key-for-testing-only"        (L-18)

These must be treated as placeholders even though they are non-empty strings.
"""
from __future__ import annotations

import pytest

import backend.env_validator as ev

# Valid production-like values for every other HARD var (mirrors
# test_env_validator_cors_alias.py).
_HARD_KEYS = (
    "FIREAI_API_KEY",
    "FIREAI_SESSION_SECRET",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "AUDIT_HMAC_KEY",
    "FIREAI_QOMN_HMAC_KEY",
    "QOMN_AUDIT_SECRET_KEY",
    "FDS_WEBHOOK_SECRET",
    "BAZSPARK_MASTER_ADMIN_TOKEN",
    "FIREAI_VISION_KEY_ENCRYPTION_KEY",
    "MEEZA_WEBHOOK_HMAC_SECRET",
    "TRUSTED_PROXIES",
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREAI_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    for key in _HARD_KEYS:
        monkeypatch.setenv(key, "x" * 64)


def _hard_for(name: str) -> set[str]:
    return {i.name for i in ev.validate_environment() if i.severity is ev.Severity.HARD}


@pytest.mark.parametrize(
    "var,value",
    [
        ("FIREAI_API_KEY", "dev-fireai-key-local"),                       # C-02
        ("FIREAI_SESSION_SECRET", "dev-session-secret-please-replace"),   # C-03
        ("QOMN_AUDIT_SECRET_KEY", "change-me-please"),                    # C-04
        ("FIREAI_API_KEY", "test-api-key-for-testing-only"),              # L-18
    ],
)
def test_legacy_placeholder_values_are_hard(monkeypatch, var, value):
    """A non-empty legacy placeholder value is still a HARD launch blocker."""
    monkeypatch.setenv(var, value)
    assert var in _hard_for(var)


def test_valid_values_pass(monkeypatch):
    """Sanity: real-looking secrets are NOT flagged as placeholders."""
    assert "FIREAI_API_KEY" not in _hard_for("FIREAI_API_KEY")


def test_empty_secret_is_hard(monkeypatch):
    """Blank secret (the new .env.example default) is still HARD in production."""
    monkeypatch.setenv("FIREAI_API_KEY", "")
    assert "FIREAI_API_KEY" in _hard_for("FIREAI_API_KEY")


def test_assert_environment_raises_on_legacy_placeholder(monkeypatch):
    """Production boot must refuse to start with an old default key."""
    monkeypatch.setenv("FIREAI_API_KEY", "dev-fireai-key-local")
    with pytest.raises(RuntimeError, match="FIREAI_API_KEY"):
        ev.assert_environment(prod_mode=True)
