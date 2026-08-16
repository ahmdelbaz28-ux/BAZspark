"""
test_env_validator_cors_alias.py — Regression test for the CORS_ORIGINS /
CORS_ALLOWED_ORIGINS backward-compat fix in backend/env_validator.py.

Context: the production env validation gate (added in 33473e6) hard-required
`CORS_ORIGINS`, but backend/app.py has always supported the legacy
`CORS_ALLOWED_ORIGINS` alias (and the HF Space only had the legacy secret set),
so the app refused to start with a HARD validation failure. This test locks in
the alias behavior while preserving the no-wildcard / missing-var protections.
"""

from __future__ import annotations

import pytest

import backend.env_validator as ev

# All other HARD variables must be satisfied so the CORS checks are isolated.
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
    # P0-4: new security/HMAC/webhook HARD vars (see env_validator.py §17)
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
    """Provide a valid production-like environment for every HARD var.

    Restores all touched vars afterwards so tests don't leak into each other.
    """
    monkeypatch.setenv("FIREAI_ENV", "production")
    for key in _HARD_KEYS:
        if key in ("SUPABASE_URL", "LANGFUSE_HOST"):
            prefix = key.lower().split("_")[0]
            monkeypatch.setenv(key, f"https://{prefix}.example.co")
        else:
            monkeypatch.setenv(key, "x" * 64)
    # CORS handled per-test.
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)


def _hard_names() -> set[str]:
    return {i.name for i in ev.validate_environment() if i.severity is ev.Severity.HARD}


def test_legacy_cors_allowed_origins_alone_satisfies_hard_check(monkeypatch):
    """Only the legacy alias set → no CORS HARD issue, assert_environment passes."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://ahmdelbaz28-bazspark.hf.space")
    assert "CORS_ORIGINS" not in _hard_names()
    ev.assert_environment()  # must not raise


def test_both_unset_still_hard():
    """Neither CORS var set → CORS_ORIGINS stays a HARD launch blocker."""
    assert "CORS_ORIGINS" in _hard_names()


def test_wildcard_via_legacy_alias_still_blocked(monkeypatch):
    """Wildcard through the legacy alias is still a HARD violation."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    assert "CORS_ORIGINS" in _hard_names()


def test_new_var_takes_precedence(monkeypatch):
    """CORS_ORIGINS set explicitly → no CORS HARD issue (even if legacy unset)."""
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    assert "CORS_ORIGINS" not in _hard_names()
    ev.assert_environment()  # must not raise


# ─── P0-4: new security/HMAC/webhook HARD vars ──────────────────────────────


def test_p0_4_security_vars_missing_are_hard(monkeypatch):
    """Each newly-added security var is a HARD launch blocker when unset."""
    p0_4_keys = (
        "AUDIT_HMAC_KEY",
        "FIREAI_QOMN_HMAC_KEY",
        "QOMN_AUDIT_SECRET_KEY",
        "FDS_WEBHOOK_SECRET",
        "BAZSPARK_MASTER_ADMIN_TOKEN",
        "FIREAI_VISION_KEY_ENCRYPTION_KEY",
        "MEEZA_WEBHOOK_HMAC_SECRET",
        "TRUSTED_PROXIES",
    )
    for key in p0_4_keys:
        monkeypatch.delenv(key, raising=False)
    hard = _hard_names()
    assert set(p0_4_keys) <= hard
