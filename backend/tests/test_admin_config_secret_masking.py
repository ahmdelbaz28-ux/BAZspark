"""
test_admin_config_secret_masking.py — C-06 regression tests.

Verifies that the /api/v1/env-config resolver never returns full secret
values (API keys, secrets, tokens, passwords) — only a masked preview or
None — while keeping intentionally-public identifiers unmasked.
"""

from __future__ import annotations

from backend.routers.admin_config import _resolve_env_var_value


class TestSecretMasking:
    """Key/secret/token/password env vars must never appear in full."""

    def test_nvidia_api_key_masked(self):
        """C-06: NVIDIA_API_KEY must not leak in full."""
        out = _resolve_env_var_value("NVIDIA_API_KEY", "napi_abcdef1234567890")
        assert out == "napi***"
        assert "abcdef" not in out

    def test_langfuse_secret_key_masked(self):
        """C-06: LANGFUSE_SECRET_KEY must not leak in full."""
        out = _resolve_env_var_value("LANGFUSE_SECRET_KEY", "sk-lf-secret-value")
        assert out == "sk-l***"
        assert "secret-value" not in out

    def test_token_and_password_masked(self):
        """Any *_TOKEN / *_PASSWORD var is masked too."""
        assert _resolve_env_var_value("CLOUDFLARE_API_TOKEN", "cfut_abc123") == "cfut***"
        assert _resolve_env_var_value("SOME_PASSWORD", "p4ssw0rd") == "p4ss***"

    def test_unset_secret_returns_none(self):
        assert _resolve_env_var_value("NVIDIA_API_KEY", None) is None

    def test_public_key_kept_full(self):
        """LANGFUSE_PUBLIC_KEY is intentionally public — returned raw."""
        assert _resolve_env_var_value("LANGFUSE_PUBLIC_KEY", "pk-lf-public") == "pk-lf-public"

    def test_non_secret_value_unchanged(self):
        assert _resolve_env_var_value("NVIDIA_MODEL", "z-ai/glm-5.2") == "z-ai/glm-5.2"
        assert (
            _resolve_env_var_value("LANGFUSE_HOST", "https://cloud.langfuse.com")
            == "https://cloud.langfuse.com"
        )

    def test_url_with_credentials_masked(self):
        """URLs containing credentials are masked before the last @."""
        out = _resolve_env_var_value("DATABASE_URL", "postgres://u:pw@db.example.com:5432/x")
        assert "pw" not in out
        assert out == "***@db.example.com:5432/x"
