"""
backend/tests/conftest.py — Shared auth fixtures for backend API tests.

Every test module under ``backend/tests`` exercises ``backend.app`` through a
Starlette ``TestClient``. The app mounts ``ApiKeyMiddleware``, which requires a
valid ``X-API-Key`` on every non-public endpoint (see
``backend/security_middleware.py`` and the authoritative contract asserted in
``tests/test_security_middleware_v129.py``).

These modules pre-date the middleware: their ``client`` fixtures build a plain
``TestClient(app)`` and issue requests without any credential, so every
protected call returns ``401 Unauthorized``.

This conftest adapts the whole package to the always-authenticated contract the
same way a real client would — by presenting a valid admin credential — instead
of weakening the middleware or editing every module:

  1. A genuine admin API key is registered in the RBAC key store (validated via
     the normal ``validate_api_key`` path). The store is pointed at a throwaway
     file so the developer's ``db/api_keys.json`` is never touched.
  2. ``TestClient.request`` is patched to attach that ``X-API-Key`` header to
     every request that does not already set one.

Crucially we do **not** set ``FIREAI_API_KEY``. The sync WebSocket endpoint
(``backend/routers/sync.py``) only runs origin/API-key checks when that env var
is set, and the WebSocket tests rely on the unauthenticated dev-mode path. By
authenticating HTTP requests with a registered key instead of the env-key
bypass, both surfaces are satisfied at once.

The header patch is function-scoped and reverted by ``monkeypatch`` after each
test; only tests under ``backend/tests`` are affected (auth-specific suites
elsewhere, which assert 401/403 behavior, are untouched).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest
from starlette.testclient import TestClient

from backend import api_keys
from backend.rbac import Role

# Known admin credential used by the backend API test suite.
BACKEND_TEST_API_KEY = "backend-tests-admin-key"


@pytest.fixture(scope="session", autouse=True)
def _register_backend_test_admin_key() -> Iterator[None]:
    """Register a real admin API key in an isolated key store for the suite."""
    keys_dir = tempfile.mkdtemp(prefix="fireai-test-keys-")
    keys_file = os.path.join(keys_dir, "api_keys.json")
    original_keys_file = api_keys.KEYS_FILE
    api_keys.KEYS_FILE = keys_file
    api_keys.add_api_key(BACKEND_TEST_API_KEY, Role.ADMIN, "backend test admin key")
    try:
        yield
    finally:
        api_keys.KEYS_FILE = original_keys_file


@pytest.fixture(autouse=True)
def _authenticated_test_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Attach the admin ``X-API-Key`` header to every backend TestClient request."""
    original_request = TestClient.request

    def request_with_api_key(
        self: TestClient,
        method: str,
        url: Any,
        *,
        headers: Any = None,
        **kwargs: Any,
    ) -> Any:
        merged = dict(headers or {})
        if not any(k.lower() == "x-api-key" for k in merged):
            merged["X-API-Key"] = BACKEND_TEST_API_KEY
        return original_request(self, method, url, headers=merged, **kwargs)

    monkeypatch.setattr(TestClient, "request", request_with_api_key)
