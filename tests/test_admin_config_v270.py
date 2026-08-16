"""
tests/test_admin_config_v270.py — Tests for the V270 admin config endpoints.

These tests close the 7 confirmed broken frontend API calls identified by
the BAZspark UI Coverage Audit (Phase 1 systematic-debugging, 2026-07-30):

  1. GET  /api/v1/feature-flags                  (was 404)
  2. POST /api/v1/feature-flags                  (was 404)
  3. GET  /api/v1/env-config                     (was 404)
  4. PUT  /api/v1/env-config                     (was 404)
  5. POST /api/v1/settings/secret-rotation/rotate (was 404)
  6. POST /api/v1/settings/admin-token/rotate    (was 404)
  7. GET  /api/v1/admin/rbac/permissions         (was 404)
  8. POST /api/v1/auth/verify                    (was 404)

Each test:
  - Logs in with an admin-role API key to obtain a session cookie
  - Calls the endpoint
  - Asserts 200 + expected response shape
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def _setup_env_module() -> None:
    """Set test environment BEFORE module-scoped fixtures import the app."""
    os.environ["FIREAI_ENV"] = "development"
    os.environ["FIREAI_API_KEY"] = "test_key_for_admin_config_v270_123"
    os.environ["DATABASE_URL"] = "sqlite:///./test_db_admin_config_v270.db"
    os.environ["FIREAI_CSRF_DISABLED"] = "1"
    # Ensure session secret is long enough (>=43 chars per session_secret.py)
    os.environ["FIREAI_SESSION_SECRET"] = "v270_test_session_secret_minimum_43_chars_long_xxxxxx"


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    from backend.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_cookie(client: TestClient) -> str:
    """Login as admin and inject the __Host-fireai_session cookie manually.

    Function-scoped so each test gets a fresh login — avoids cookie-jar
    contamination between tests that need auth and tests that need no auth.

    httpx (which backs TestClient) rejects __Host- prefixed cookies with the
    Secure flag over HTTP, so we have to extract the token from Set-Cookie
    and inject it via client.cookies.set(). This mirrors the pattern used
    in tests/test_auth_router.py::TestAuthMe::test_me_with_valid_cookie_returns_role.
    """
    # Always start from a clean cookie jar — defensive against prior tests
    client.cookies.clear()
    resp = client.post(
        "/api/v1/auth/login",
        json={"api_key": "test_key_for_admin_config_v270_123"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "__Host-fireai_session=" in set_cookie, "No session cookie in Set-Cookie header"
    # Extract the token value (between "=" and the first ";")
    session_token = set_cookie.split("__Host-fireai_session=")[1].split(";")[0]
    assert session_token, "Empty session token extracted"
    # Manually inject — bypasses httpx's __Host- Secure cookie rejection
    client.cookies.set("__Host-fireai_session", session_token)
    return session_token


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FEATURE FLAGS — GET + POST
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeatureFlags:
    """GET/POST /api/v1/feature-flags — closes SettingsPage.tsx L149 broken call."""

    def test_get_feature_flags_returns_200(self, client: TestClient, admin_cookie: str) -> None:
        """GET /feature-flags must return 200 with the flags dict."""
        resp = client.get("/api/v1/feature-flags")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        flags = body["data"]["flags"]
        # Must include all 9 default feature flags
        expected = {
            "SMOKE_SIMULATION",
            "DIGITAL_TWIN_SYNC",
            "SELF_LEARNING",
            "RESILIENCE_CHECK",
            "PROOF_CERTIFICATE",
            "VORONOI_VERIFICATION",
            "AUTOCAD_BRIDGE",
            "REVIT_BRIDGE",
            "DIALUX_BRIDGE",
        }
        assert expected.issubset(set(flags.keys())), (
            f"Missing flags: {expected - set(flags.keys())}"
        )

    def test_get_feature_flags_requires_auth(self, client: TestClient) -> None:
        """Without auth, the endpoint should deny access (401/403, not 404)."""
        client.cookies.clear()  # Defensive: ensure no leaked cookies
        resp = client.get("/api/v1/feature-flags")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        assert resp.status_code != 404, "Endpoint should exist; 404 means router not registered"

    def test_post_feature_flag_toggles_value(self, client: TestClient, admin_cookie: str) -> None:
        """POST /feature-flags with {flag, enabled} should toggle and return 200."""
        # Set SMOKE_SIMULATION to True (default is False per V215 docstring)
        resp = client.post(
            "/api/v1/feature-flags",
            json={"flag": "SMOKE_SIMULATION", "enabled": True},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["flag"] == "SMOKE_SIMULATION"
        assert body["data"]["enabled"] is True

        # Verify the change is reflected on subsequent GET
        get_resp = client.get("/api/v1/feature-flags")
        assert get_resp.status_code == 200
        get_body = get_resp.json()
        assert get_body["data"]["flags"]["SMOKE_SIMULATION"] is True

    def test_post_feature_flag_rejects_unknown_flag(
        self, client: TestClient, admin_cookie: str
    ) -> None:
        """POST /feature-flags with unknown flag name should return 400."""
        resp = client.post(
            "/api/v1/feature-flags",
            json={"flag": "NONEXISTENT_FLAG", "enabled": True},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ENV CONFIG — GET + PUT
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnvConfig:
    """GET/PUT /api/v1/env-config — closes AdvancedSettingsPage.tsx L69/L132 broken calls."""

    def test_get_env_config_returns_200(self, client: TestClient, admin_cookie: str) -> None:
        """GET /env-config must return 200 with categorized config."""
        resp = client.get("/api/v1/env-config")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        config = body["data"]["config"]
        # Must include the 4 safe categories
        for category in ("database", "api", "integration", "security"):
            assert category in config, f"Missing category: {category}"

    def test_get_env_config_requires_auth(self, client: TestClient) -> None:
        """Without auth, the endpoint should deny access (not 404)."""
        client.cookies.clear()
        resp = client.get("/api/v1/env-config")
        assert resp.status_code in (401, 403)
        assert resp.status_code != 404

    def test_put_env_config_applies_overrides(self, client: TestClient, admin_cookie: str) -> None:
        """PUT /env-config with overrides should return 200 and apply them."""
        resp = client.put(
            "/api/v1/env-config",
            json={"overrides": {"api": {"API_TIMEOUT": 60, "RETRY_ATTEMPTS": 5}}},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert "api" in body["data"]["applied"]

        # Verify the override is reflected on subsequent GET
        get_resp = client.get("/api/v1/env-config")
        assert get_resp.status_code == 200
        get_body = get_resp.json()
        assert get_body["data"]["config"]["api"]["API_TIMEOUT"] == 60
        assert get_body["data"]["config"]["api"]["RETRY_ATTEMPTS"] == 5

    def test_put_env_config_rejects_invalid_category(
        self, client: TestClient, admin_cookie: str
    ) -> None:
        """PUT /env-config with invalid category name should return 400."""
        resp = client.put(
            "/api/v1/env-config",
            json={"overrides": {"bad;category": {"foo": "bar"}}},
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SECRET ROTATION — POST
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecretRotation:
    """POST /api/v1/settings/secret-rotation/rotate — closes SettingsPage.tsx L650 broken call."""

    def test_rotate_secret_with_generated_value(
        self, client: TestClient, admin_cookie: str
    ) -> None:
        """POST /settings/secret-rotation/rotate with no new_secret should generate one."""
        resp = client.post(
            "/api/v1/settings/secret-rotation/rotate",
            json={"key_name": "FIREAI_TEST_SECRET_TO_ROTATE"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["rotated"] is True
        new_secret = body["data"]["new_secret"]
        assert len(new_secret) >= 32, "Generated secret should be at least 32 chars"

    def test_rotate_secret_with_explicit_value(self, client: TestClient, admin_cookie: str) -> None:
        """POST /settings/secret-rotation/rotate with explicit new_secret should use it."""
        explicit = "averylongandsecuresecretvaluefortesting1234567890"
        resp = client.post(
            "/api/v1/settings/secret-rotation/rotate",
            json={"key_name": "FIREAI_TEST_SECRET_EXPLICIT", "new_secret": explicit},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["data"]["new_secret"] == explicit

    def test_rotate_secret_requires_auth(self, client: TestClient) -> None:
        """Without auth, endpoint should deny (not 404)."""
        client.cookies.clear()
        resp = client.post(
            "/api/v1/settings/secret-rotation/rotate",
            json={"key_name": "FIREAI_API_KEY"},
        )
        assert resp.status_code in (401, 403)
        assert resp.status_code != 404


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ADMIN TOKEN ROTATION — POST
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminTokenRotation:
    """POST /api/v1/settings/admin-token/rotate — closes SettingsPage.tsx L700 broken call."""

    def test_rotate_admin_token_returns_new_token(
        self, client: TestClient, admin_cookie: str
    ) -> None:
        """POST /settings/admin-token/rotate should return a new token."""
        resp = client.post("/api/v1/settings/admin-token/rotate")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["rotated"] is True
        new_token = body["data"]["new_token"]
        assert len(new_token) >= 32, "New admin token should be at least 32 chars"

    def test_rotate_admin_token_requires_auth(self, client: TestClient) -> None:
        """Without auth, endpoint should deny (not 404)."""
        client.cookies.clear()
        resp = client.post("/api/v1/settings/admin-token/rotate")
        assert resp.status_code in (401, 403)
        assert resp.status_code != 404


# ═══════════════════════════════════════════════════════════════════════════════
# 5. RBAC PERMISSIONS — GET
# ═══════════════════════════════════════════════════════════════════════════════


class TestRbacPermissions:
    """GET /api/v1/admin/rbac/permissions — closes RbacPage.tsx L249 broken call."""

    def test_get_permissions_returns_matrix(self, client: TestClient, admin_cookie: str) -> None:
        """GET /admin/rbac/permissions should return the role-permission matrix."""
        resp = client.get("/api/v1/admin/rbac/permissions")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        # Must include all 3 roles
        role_names = {r["role"] for r in data["roles"]}
        assert {"admin", "engineer", "viewer"} == role_names

        # Must include all permissions
        assert "permissions" in data
        assert len(data["permissions"]) > 0

        # Matrix must be present and consistent
        assert "matrix" in data
        assert "admin" in data["matrix"]
        # Admin must have all permissions = true
        admin_matrix = data["matrix"]["admin"]
        assert all(admin_matrix.values()), "Admin should have all permissions"

    def test_get_permissions_requires_auth(self, client: TestClient) -> None:
        """Without auth, endpoint should deny (not 404)."""
        client.cookies.clear()
        resp = client.get("/api/v1/admin/rbac/permissions")
        assert resp.status_code in (401, 403)
        assert resp.status_code != 404


# ═══════════════════════════════════════════════════════════════════════════════
# 6. AUTH VERIFY — POST
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthVerify:
    """POST /api/v1/auth/verify — closes fullApi.ts L1217 verifyToken() broken call."""

    def test_verify_with_valid_token(self, client: TestClient, admin_cookie: str) -> None:
        """POST /auth/verify with a valid session token should return valid=true.

        The admin_cookie fixture returns the token string directly (it also
        injects it into the client's cookie jar, but we use the string here
        to avoid httpx's CookieConflict when multiple cookies share a name).
        """
        # admin_cookie is the raw token string
        resp = client.post("/api/v1/auth/verify", json={"token": admin_cookie})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["valid"] is True
        assert body["data"]["role"] in ("admin", "engineer", "viewer")

    def test_verify_with_invalid_token(self, client: TestClient, admin_cookie: str) -> None:
        """POST /auth/verify with bogus token should return valid=false (NOT 401)."""
        resp = client.post("/api/v1/auth/verify", json={"token": "bogus.token.value"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["valid"] is False

    def test_verify_with_empty_token_rejected_by_pydantic(
        self, client: TestClient, admin_cookie: str
    ) -> None:
        """POST /auth/verify with empty token should fail Pydantic validation (422)."""
        resp = client.post("/api/v1/auth/verify", json={"token": ""})
        assert resp.status_code == 422  # Pydantic rejects min_length=1

    def test_verify_endpoint_is_publicly_callable(self, client: TestClient) -> None:
        """POST /auth/verify must be callable WITHOUT an active session (it's a token-check endpoint)."""
        resp = client.post("/api/v1/auth/verify", json={"token": "any.token.value"})
        # Should NOT be 401/403/404 — verify is intentionally public
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CROSS-CUTTING: all new endpoints exist (no 404)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEndpointExistence:
    """Cross-cutting test: every endpoint from the audit report must now exist."""

    def test_all_7_endpoints_exist(self, client: TestClient, admin_cookie: str) -> None:
        """All 7 previously-404 endpoints must now return non-404."""
        # Each tuple: (method, path, json_body_or_None, expected_min_status, expected_max_status)
        cases = [
            ("GET", "/api/v1/feature-flags", None, 200, 200),
            (
                "POST",
                "/api/v1/feature-flags",
                {"flag": "SMOKE_SIMULATION", "enabled": False},
                200,
                200,
            ),
            ("GET", "/api/v1/env-config", None, 200, 200),
            ("PUT", "/api/v1/env-config", {"overrides": {}}, 200, 200),
            (
                "POST",
                "/api/v1/settings/secret-rotation/rotate",
                {"key_name": "FIREAI_API_KEY"},
                200,
                200,
            ),
            ("POST", "/api/v1/settings/admin-token/rotate", None, 200, 200),
            ("GET", "/api/v1/admin/rbac/permissions", None, 200, 200),
            ("POST", "/api/v1/auth/verify", {"token": "any"}, 200, 200),
        ]
        for method, path, body, min_status, max_status in cases:
            resp = client.request(method, path, json=body)
            assert resp.status_code != 404, (
                f"ENDPOINT STILL MISSING: {method} {path} returned 404. "
                f"Router not registered. Got: {resp.status_code}"
            )
            assert min_status <= resp.status_code <= max_status, (
                f"{method} {path} returned {resp.status_code}, expected {min_status}-{max_status}. Body: {resp.text[:500]}"
            )
