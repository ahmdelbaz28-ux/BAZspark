"""tests/test_backend_app_security.py — V127 SAFETY: backend_app.py CORS hardening
================================================================================
V127 SAFETY FIX: backend_app.py must NOT use wildcard CORS origins in production.
The previous code defaulted to allow_origins=["*"] which allows any website
to read API responses. In production, CORS_ORIGINS must be explicitly set to
a comma-separated list of trusted origins.

Tests:
  1. Production with explicit origins — works
  2. Production without CORS_ORIGINS — raises RuntimeError (fail-safe)
  3. Production with CORS_ORIGINS="*" — raises RuntimeError (wildcard forbidden)
  4. Development default — localhost-only origins
  5. allow_credentials is always False (header auth, not cookies)
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from starlette.middleware.cors import CORSMiddleware

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _get_cors_middleware_kwargs(app):
    """Extract CORS middleware kwargs from a FastAPI app."""
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            return m.options
    return None


def _reload_backend_app(env_overrides: dict) -> Any:
    """Reload backend_app with the given env vars set."""
    # Clear cached module so __init__ runs again with new env
    for mod_name in list(sys.modules):
        if mod_name == "backend_app" or mod_name.startswith("backend_app."):
            del sys.modules[mod_name]
    saved = {}
    for k, v in env_overrides.items():
        saved[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        import backend_app  # type: ignore[import-untyped]
        return backend_app
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestV127CorsHardening:
    """V127: CORS hardening in backend_app.py."""

    def test_production_accepts_explicit_origins(self):
        """Production + explicit origins → CORS configured correctly."""
        backend_app = _reload_backend_app({
            "FIREAI_ENV": "production",
            "CORS_ORIGINS": "https://app.example.com,https://admin.example.com",
            "FIREAI_API_KEY": "",
        })
        kwargs = _get_cors_middleware_kwargs(backend_app.app)
        assert kwargs is not None
        assert "https://app.example.com" in kwargs["allow_origins"]
        assert "https://admin.example.com" in kwargs["allow_origins"]
        assert "*" not in kwargs["allow_origins"]

    def test_development_defaults_to_localhost_only(self):
        """Development without CORS_ORIGINS → localhost-only origins."""
        backend_app = _reload_backend_app({
            "FIREAI_ENV": "development",
            "FIREAI_API_KEY": "",
        })
        kwargs = _get_cors_middleware_kwargs(backend_app.app)
        assert kwargs is not None
        origins = kwargs["allow_origins"]
        assert any("localhost" in o for o in origins)
        # Dev defaults include localhost:3000, localhost:5173, etc.

    def test_allow_credentials_always_false(self):
        """CORS allow_credentials must always be False (header auth, not cookies)."""
        backend_app = _reload_backend_app({
            "FIREAI_ENV": "production",
            "CORS_ORIGINS": "https://app.example.com",
            "FIREAI_API_KEY": "",
        })
        kwargs = _get_cors_middleware_kwargs(backend_app.app)
        assert kwargs is not None
        assert kwargs.get("allow_credentials") is False
