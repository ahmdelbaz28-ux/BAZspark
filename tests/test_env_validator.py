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
    "SUPABASE_URL": "https://x.supabase.co",
    "SUPABASE_ANON_KEY": "a" * 50,
    "SUPABASE_SERVICE_ROLE_KEY": "b" * 50,
    "LANGFUSE_PUBLIC_KEY": "pk-lf-" + "x" * 32,
    "LANGFUSE_SECRET_KEY": "sk-lf-" + "y" * 32,
    "LANGFUSE_HOST": "https://cloud.langfuse.com",
    "CORS_ORIGINS": "https://app.example.com",
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
    env = dict(RUNTIME_MINIMAL)
    del env["SUPABASE_URL"]
    for k, v in env.items():
        os.environ[k] = v
    issues = validate_environment()
    hard = [i for i in issues if i.severity is Severity.HARD]
    names = {i.name for i in hard}
    assert "SUPABASE_URL" in names


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
    """FIREAI_ENV unset ⇒ development semantics: HARD issues warn, never raise.

    Guards the CI Playwright uvicorn job (ci.yml Gate 4b), which starts the
    backend without declaring FIREAI_ENV and without production secrets —
    the gate must not crash it (regression guard).
    """
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    os.environ.pop("FIREAI_ENV", None)
    os.environ.pop("SUPABASE_URL", None)  # simulate missing HARD var
    assert_environment()  # must NOT raise


def test_explicit_production_missing_hard_raises():
    """FIREAI_ENV=production explicitly + missing HARD var ⇒ RuntimeError."""
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    os.environ["FIREAI_ENV"] = "production"
    os.environ.pop("SUPABASE_URL", None)
    with pytest.raises(RuntimeError):
        assert_environment()


def test_escape_hatch_warn_allows_startup_in_production():
    """FIREAI_ENV_VALIDATION=warn demotes HARD issues in production mode."""
    for k, v in RUNTIME_MINIMAL.items():
        os.environ[k] = v
    os.environ["FIREAI_ENV"] = "production"
    os.environ["FIREAI_ENV_VALIDATION"] = "warn"
    os.environ.pop("SUPABASE_URL", None)
    assert_environment()  # degraded mode: must NOT raise
