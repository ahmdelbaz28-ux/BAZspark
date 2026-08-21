"""Unit tests for backend/env_validator.py — the startup env gate."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.env_validator import (  # noqa: E402
    Severity,
    _is_placeholder,
    assert_environment,
    validate_environment,
)

# ─── Fixtures ────────────────────────────────────────────────────────────────

RUNTIME_MINIMAL = {
    "FIREAI_ENV": "production",
    "FIREAI_API_KEY": "k" * 40,
    "FIREAI_SESSION_SECRET": "s" * 64,
    "DATABASE_URL": "postgresql://u:p@host:5432/db?sslmode=require",
    "REDIS_URL": "redis://localhost:6379/0",
    "SUPABASE_URL": "https://x.supabase.co",
    "SUPABASE_ANON_KEY": "a" * 50,
    "SUPABASE_SERVICE_ROLE_KEY": "b" * 50,
    "LANGFUSE_PUBLIC_KEY": "pk-lf-" + "x" * 32,
    "LANGFUSE_SECRET_KEY": "sk-lf-" + "y" * 32,
    "LANGFUSE_HOST": "https://cloud.langfuse.com",
    "CORS_ORIGINS": "https://app.example.com",
    # P0-4: new security/HMAC/webhook HARD vars (see env_validator.py §17)
    "AUDIT_HMAC_KEY": "z" * 40,
    "FIREAI_QOMN_HMAC_KEY": "q" * 40,
    "QOMN_AUDIT_SECRET_KEY": "o" * 40,
    "FDS_WEBHOOK_SECRET": "f" * 40,
    "BAZSPARK_MASTER_ADMIN_TOKEN": "m" * 40,
    "FIREAI_VISION_KEY_ENCRYPTION_KEY": "e" * 40,
    "MEEZA_WEBHOOK_HMAC_SECRET": "w" * 40,
    "TRUSTED_PROXIES": "10.0.0.0/8",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Run each test with an empty, controlled environment."""
    for key in list(os.environ.keys()):
        monkeypatch.delenv(key, raising=False)
    return


# ─── Placeholder detection ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("", True),
        ("   ", True),
        ("<PLACEHOLDER>", True),
        ("<YOUR_API_KEY>", True),
        ("YOUR_FIREAI_API_KEY", True),
        ("pk-lf-...", True),
        ("sk-lf-...", True),
        ("re_abc", False),
        ("github_pat_1234567890abcdef", False),
        ("https://cloud.langfuse.com", False),
    ],
)
def test_is_placeholder(value, expected):
    assert _is_placeholder(value) is expected


# ─── Full / minimal / broken environments ────────────────────────────────────


def test_full_env_has_zero_issues():
    full = dict(RUNTIME_MINIMAL)
    full.update(
        {
            "NVIDIA_API_KEY": "napi_" + "z" * 20,
            "NVIDIA_BASE_URL": "https://integrate.api.nvidia.com/v1",
            "RESEND_API_KEY": "re_" + "q" * 20,
            "HF_TOKEN": "hf_" + "h" * 20,
            "GH_PAT": "github_pat_" + "g" * 20,
            "GH_REPO": "owner/repo",
            "SONAR_TOKEN": "s" * 20,
            "SONAR_HOST_URL": "https://sonarcloud.io",
            "SONAR_PROJECT_KEY": "owner_repo",
            "VERCEL_DEPLOY_TOKEN": "vcp_" + "t" * 20,
            "VERCEL_PROJECT_ID": "prj_" + "p" * 20,
            "CLOUDFLARE_API_TOKEN": "cfut_" + "c" * 20,
            "DAYTONA_API_TOKEN": "dtn_" + "d" * 20,
            "CODESANDBOX_TOKEN": "csb_v1_" + "e" * 20,
            "APS_CLIENT_ID": "aps-cid",
            "APS_CLIENT_SECRET": "aps-secret",
            # SOFT vars added after V295+ — must be present for zero-issues
            "NEON_DATABASE_URL": "postgresql://u:p@neonhost/db",
            "GEMINI_API_KEY": "gem_" + "x" * 20,
            "OPENAI_API_KEY": "sk-" + "o" * 20,
            "ZENMUX_API_KEY": "zm_" + "z" * 20,
            "RESEND_FROM_EMAIL": "noreply@example.com",
            "QOMN_AUDIT_LOG_PATH": "/var/log/qomn",
            "APS_WEBHOOK_URL": "https://aps.example.com/hook",
            "VERCEL_DEPLOY_HOOK_URL": "https://vercel.example.com/hook",
            "UPTIMEROBOT_USER_KEY": "ur_" + "u" * 20,
            "UPTIMEROBOT_MONITOR_KEY": "um_" + "m" * 20,
            "FIREAI_ENV_VALIDATION": "strict",
            "FIREAI_CSRF_DISABLED": "false",
            "AKAMAI_ENABLED": "false",
            "CF_ENABLED": "false",
            "LANGFUSE_ENABLED": "true",
        }
    )
    for k, v in full.items():
        os.environ[k] = v
    assert validate_environment() == []


def test_runtime_only_env_passes_gate():
    """HF Space runtime vars only → 0 HARD (launch OK), CI vars are SOFT."""
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    issues = validate_environment()
    hard = [i for i in issues if i.severity is Severity.HARD]
    assert hard == []


def test_missing_runtime_var_is_hard():
    """Removing a HARD variable (LANGFUSE_PUBLIC_KEY) must produce a HARD issue."""
    env = dict(RUNTIME_MINIMAL)
    del env["LANGFUSE_PUBLIC_KEY"]
    for k, v in env.items():
        os.environ[k] = v
    issues = validate_environment()
    hard = [i for i in issues if i.severity is Severity.HARD]
    names = {i.name for i in hard}
    assert "LANGFUSE_PUBLIC_KEY" in names


def test_placeholder_value_is_rejected():
    env = dict(RUNTIME_MINIMAL)
    env["FIREAI_API_KEY"] = "<FIREAI_API_KEY>"
    for k, v in env.items():
        os.environ[k] = v
    issues = validate_environment()
    hard = {i.name for i in issues if i.severity is Severity.HARD}
    assert "FIREAI_API_KEY" in hard


def test_short_session_secret_is_hard():
    env = dict(RUNTIME_MINIMAL)
    env["FIREAI_SESSION_SECRET"] = "too-short"
    for k, v in env.items():
        os.environ[k] = v
    issues = validate_environment()
    hard = {i.name for i in issues if i.severity is Severity.HARD}
    assert "FIREAI_SESSION_SECRET" in hard


def test_cors_wildcard_forbidden_in_production():
    env = dict(RUNTIME_MINIMAL)
    env["CORS_ORIGINS"] = "*"
    for k, v in env.items():
        os.environ[k] = v
    issues = validate_environment()
    hard = {i.name for i in issues if i.severity is Severity.HARD}
    assert "CORS_ORIGINS" in hard


# ─── assert_environment() mode detection ─────────────────────────────────────


def test_unset_fireai_env_never_blocks_startup():
    """FIREAI_ENV=development ⇒ HARD issues warn, never raise.

    Guards the CI Playwright uvicorn job (ci.yml Gate 4b), which starts the
    backend without production secrets — the gate must not crash it
    (regression guard).

    NOTE: V246 fail-safe defaults FIREAI_ENV to "production" when unset.
    Callers must explicitly set FIREAI_ENV=development to get non-blocking
    semantics.
    """
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    os.environ["FIREAI_ENV"] = "development"
    os.environ.pop("LANGFUSE_PUBLIC_KEY", None)  # simulate missing HARD var
    assert_environment()  # must NOT raise


def test_explicit_production_missing_hard_raises():
    """FIREAI_ENV=production explicitly + missing HARD var ⇒ RuntimeError."""
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    os.environ["FIREAI_ENV"] = "production"
    os.environ.pop("LANGFUSE_PUBLIC_KEY", None)  # HARD var
    with pytest.raises(RuntimeError):
        assert_environment()


def test_escape_hatch_warn_allows_startup_in_production():
    """FIREAI_ENV_VALIDATION=warn demotes HARD issues in production mode."""
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    os.environ["FIREAI_ENV"] = "production"
    os.environ["FIREAI_ENV_VALIDATION"] = "warn"
    os.environ.pop("LANGFUSE_PUBLIC_KEY", None)  # HARD var
    assert_environment()  # degraded mode: must NOT raise


# ─── LANGFUSE_ENABLED gating (V303 — clean-launch fix) ──────────────────────


def test_langfuse_disabled_downgrades_keys_to_soft(monkeypatch):
    """LANGFUSE_ENABLED=false must demote LANGFUSE_* from HARD to SOFT.

    Operators who opt out of Langfuse should NOT be forced to supply dummy
    keys just to satisfy the validator — the runtime already skips Langfuse
    when the flag is off (see fireai/env_config.py:151-153).
    """
    env = dict(RUNTIME_MINIMAL)
    del env["LANGFUSE_PUBLIC_KEY"]
    del env["LANGFUSE_SECRET_KEY"]
    del env["LANGFUSE_HOST"]
    # Use monkeypatch (Sonar S8997): avoids leaking global-state mutations
    # across tests and auto-restores env after the test exits.
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for absent in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(absent, raising=False)
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    issues = validate_environment()
    hard = {i.name for i in issues if i.severity is Severity.HARD}
    soft = {i.name for i in issues if i.severity is Severity.SOFT}
    # All three LANGFUSE_* must be SOFT, NOT HARD
    assert "LANGFUSE_PUBLIC_KEY" not in hard
    assert "LANGFUSE_SECRET_KEY" not in hard
    assert "LANGFUSE_HOST" not in hard
    assert "LANGFUSE_PUBLIC_KEY" in soft
    assert "LANGFUSE_SECRET_KEY" in soft
    assert "LANGFUSE_HOST" in soft


def test_langfuse_enabled_keeps_keys_hard(monkeypatch):
    """LANGFUSE_ENABLED=true (or unset) must keep LANGFUSE_* as HARD.

    Regression guard: the gating logic must only trigger when the flag is
    EXPLICITLY set to a falsy value. Unset or truthy values preserve HARD.
    """
    # Case 1: LANGFUSE_ENABLED=true → HARD (keys missing)
    env = dict(RUNTIME_MINIMAL)
    del env["LANGFUSE_PUBLIC_KEY"]
    del env["LANGFUSE_SECRET_KEY"]
    del env["LANGFUSE_HOST"]
    # Use monkeypatch (Sonar S8997) for all env mutations.
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for absent in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(absent, raising=False)
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    issues = validate_environment()
    hard = {i.name for i in issues if i.severity is Severity.HARD}
    assert "LANGFUSE_PUBLIC_KEY" in hard
    assert "LANGFUSE_SECRET_KEY" in hard
    assert "LANGFUSE_HOST" in hard

    # Case 2: LANGFUSE_ENABLED unset → HARD (default posture is fail-closed)
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    issues = validate_environment()
    hard = {i.name for i in issues if i.severity is Severity.HARD}
    assert "LANGFUSE_PUBLIC_KEY" in hard
    assert "LANGFUSE_SECRET_KEY" in hard
    assert "LANGFUSE_HOST" in hard
