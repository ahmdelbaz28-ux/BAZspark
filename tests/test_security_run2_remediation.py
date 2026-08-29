"""
tests/test_security_run2_remediation.py — Verification tests for Security Audit Run-2 fixes.

Verifies:
  - SEC-RUN2-001: Export execution endpoints require EXPORT_EXECUTE (VIEWER blocked with 403)
  - SEC-RUN2-002: Project child resources (devices, connections, reports) enforce tenant isolation (cross-tenant returns 404)
  - SEC-RUN2-003: Global device listing scopes query to authenticated principal's projects
  - SEC-RUN2-004: Agent ping-provider endpoint enforces CALCULATION_EXECUTE permission
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api_keys import add_api_key, validate_api_key
from backend.database import Database
from backend.rbac import Role
from backend.routers.agent_ws import router as agent_ws_router
from backend.routers.connections import router as connections_router
from backend.routers.devices import project_router as global_devices_router
from backend.routers.devices import router as devices_router
from backend.routers.export_router import router as export_router
from backend.routers.projects import router as projects_router
from backend.routers.reports import project_router as global_reports_router
from backend.routers.reports import router as reports_router
from backend.security_middleware import ApiKeyMiddleware


@pytest.fixture
def test_env(monkeypatch, tmp_path):
    """Set up an isolated database, api keys, and test client."""
    db_path = str(tmp_path / "test_sec_run2.db")
    keys_file = str(tmp_path / "api_keys.json")

    db = Database(db_path)

    with patch("backend.api_keys.KEYS_FILE", keys_file), patch("backend.database._db", db):
        # Create API Keys for different principals and roles
        key_admin = "key-admin-test-token"
        key_engineer_a = "key-engineer-a-token"
        key_engineer_b = "key-engineer-b-token"
        key_viewer = "key-viewer-test-token"

        add_api_key(key_admin, Role.ADMIN, "Admin User")
        add_api_key(key_engineer_a, Role.ENGINEER, "Engineer Tenant A")
        add_api_key(key_engineer_b, Role.ENGINEER, "Engineer Tenant B")
        add_api_key(key_viewer, Role.VIEWER, "Viewer User")

        principal_admin = validate_api_key(key_admin).key_hash
        principal_a = validate_api_key(key_engineer_a).key_hash
        principal_b = validate_api_key(key_engineer_b).key_hash
        principal_viewer = validate_api_key(key_viewer).key_hash

        # Build FastAPI test application
        app = FastAPI()
        app.include_router(projects_router, prefix="/api/v1")
        app.include_router(export_router, prefix="/api/v1")
        app.include_router(devices_router, prefix="/api/v1")
        app.include_router(global_devices_router, prefix="/api/v1")
        app.include_router(connections_router, prefix="/api/v1")
        app.include_router(reports_router, prefix="/api/v1")
        app.include_router(global_reports_router, prefix="/api/v1")
        app.include_router(agent_ws_router, prefix="/api/v1")

        app.add_middleware(ApiKeyMiddleware)
        client = TestClient(app)

        yield {
            "db": db,
            "client": client,
            "keys": {
                "admin": key_admin,
                "engineer_a": key_engineer_a,
                "engineer_b": key_engineer_b,
                "viewer": key_viewer,
            },
            "principals": {
                "admin": principal_admin,
                "engineer_a": principal_a,
                "engineer_b": principal_b,
                "viewer": principal_viewer,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SEC-RUN2-001: Export RBAC Verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportRouterRBAC:
    def test_viewer_cannot_execute_export(self, test_env):
        """Viewer role must be blocked with HTTP 403 from executing exports."""
        client = test_env["client"]
        viewer_key = test_env["keys"]["viewer"]

        # POST /api/v1/export/execute
        resp_execute = client.post(
            "/api/v1/export/execute",
            headers={"X-API-Key": viewer_key},
            json={"project_id": "proj-1", "expected_revision": 1, "target_format": "dxf"},
        )
        assert resp_execute.status_code == 403, "Viewer should be denied EXPORT_EXECUTE on /execute"

        # POST /api/v1/export/run
        resp_run = client.post(
            "/api/v1/export/run",
            headers={"X-API-Key": viewer_key},
            json={"project_id": "proj-1", "target_format": "dxf"},
        )
        assert resp_run.status_code == 403, "Viewer should be denied EXPORT_EXECUTE on /run"

    def test_engineer_is_authorized_for_export(self, test_env):
        """Engineer role is authorized to reach the export execution endpoint."""
        client = test_env["client"]
        engineer_key = test_env["keys"]["engineer_a"]

        with patch(
            "backend.routers.export_router.default_export_orchestrator.execute_export"
        ) as mock_exec:
            mock_res = MagicMock()
            mock_res.to_dict.return_value = {"exportId": "exp-123", "status": "completed"}
            mock_exec.return_value = mock_res

            resp = client.post(
                "/api/v1/export/execute",
                headers={"X-API-Key": engineer_key},
                json={"project_id": "proj-1", "expected_revision": 1, "target_format": "dxf"},
            )
            # Must not be 403
            assert resp.status_code != 403
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SEC-RUN2-002: Tenant Isolation on Child Resources (Devices, Connections, Reports)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTenantIsolationChildResources:
    def test_cross_tenant_device_access_blocked(self, test_env):
        """Tenant B engineer cannot read, create, update, or delete devices in Tenant A's project."""
        db = test_env["db"]
        client = test_env["client"]
        key_eng_a = test_env["keys"]["engineer_a"]
        key_eng_b = test_env["keys"]["engineer_b"]
        principal_a = test_env["principals"]["engineer_a"]

        # 1. Tenant A creates Project A
        proj_a_id = f"proj-a-{uuid.uuid4().hex[:8]}"
        db.create_project({"id": proj_a_id, "name": "Tenant A Project", "author": principal_a})

        # 2. Tenant A creates Device A
        dev_a_id = f"dev-a-{uuid.uuid4().hex[:8]}"
        db.create_device(
            proj_a_id,
            {
                "id": dev_a_id,
                "type": "SMOKE_DETECTOR",
                "name": "Smoke Det A1",
                "category": "initiating",
                "x": 10.0,
                "y": 10.0,
                "z": 3.0,
                "voltage": 24.0,
                "current": 0.05,
                "load": 0.05,
            },
        )

        headers_b = {"X-API-Key": key_eng_b}

        # Tenant B attempts GET /projects/{proj_a_id}/devices -> 404
        r = client.get(f"/api/v1/projects/{proj_a_id}/devices", headers=headers_b)
        assert r.status_code == 404

        # Tenant B attempts POST /projects/{proj_a_id}/devices -> 404
        r = client.post(
            f"/api/v1/projects/{proj_a_id}/devices",
            headers=headers_b,
            json={
                "type": "HEAT_DETECTOR",
                "name": "Injected Device",
                "category": "initiating",
                "x": 0.0,
                "y": 0.0,
            },
        )
        assert r.status_code == 404

        # Tenant B attempts GET /projects/{proj_a_id}/devices/{dev_a_id} -> 404
        r = client.get(f"/api/v1/projects/{proj_a_id}/devices/{dev_a_id}", headers=headers_b)
        assert r.status_code == 404

        # Tenant B attempts PUT /projects/{proj_a_id}/devices/{dev_a_id} -> 404
        r = client.put(
            f"/api/v1/projects/{proj_a_id}/devices/{dev_a_id}",
            headers=headers_b,
            json={"name": "Tampered Device"},
        )
        assert r.status_code == 404

        # Tenant B attempts DELETE /projects/{proj_a_id}/devices/{dev_a_id} -> 404
        r = client.delete(f"/api/v1/projects/{proj_a_id}/devices/{dev_a_id}", headers=headers_b)
        assert r.status_code == 404

        # Tenant A (Owner) accesses device -> 200
        headers_a = {"X-API-Key": key_eng_a}
        r_owner = client.get(f"/api/v1/projects/{proj_a_id}/devices/{dev_a_id}", headers=headers_a)
        assert r_owner.status_code == 200

    def test_cross_tenant_connections_blocked(self, test_env):
        """Tenant B cannot read, create, or modify connections in Tenant A's project."""
        db = test_env["db"]
        client = test_env["client"]
        key_eng_b = test_env["keys"]["engineer_b"]
        principal_a = test_env["principals"]["engineer_a"]

        proj_a_id = f"proj-a-{uuid.uuid4().hex[:8]}"
        db.create_project({"id": proj_a_id, "name": "Tenant A Wiring", "author": principal_a})

        headers_b = {"X-API-Key": key_eng_b}

        # Tenant B attempts GET connections -> 404
        r = client.get(f"/api/v1/projects/{proj_a_id}/connections", headers=headers_b)
        assert r.status_code == 404

        # Tenant B attempts POST connection -> 404
        r = client.post(
            f"/api/v1/projects/{proj_a_id}/connections",
            headers=headers_b,
            json={"fromId": "d1", "toId": "d2", "cableSize": "2.5mm²", "length": 15.0},
        )
        assert r.status_code == 404

    def test_cross_tenant_reports_blocked(self, test_env):
        """Tenant B cannot generate or access reports in Tenant A's project."""
        db = test_env["db"]
        client = test_env["client"]
        key_eng_b = test_env["keys"]["engineer_b"]
        principal_a = test_env["principals"]["engineer_a"]

        proj_a_id = f"proj-a-{uuid.uuid4().hex[:8]}"
        db.create_project({"id": proj_a_id, "name": "Tenant A Reports", "author": principal_a})

        headers_b = {"X-API-Key": key_eng_b}

        # Tenant B attempts POST report generation -> 404
        r = client.post(
            f"/api/v1/projects/{proj_a_id}/reports",
            headers=headers_b,
            json={"type": "voltage_drop", "name": "Unauthorized Report"},
        )
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SEC-RUN2-003: Global Device Listing Scoping
# ═══════════════════════════════════════════════════════════════════════════════


class TestGlobalDeviceListingTenantScoping:
    def test_global_devices_does_not_leak_other_tenants(self, test_env):
        """GET /api/v1/devices returns only devices belonging to the caller's tenant."""
        db = test_env["db"]
        client = test_env["client"]
        key_eng_b = test_env["keys"]["engineer_b"]
        principal_a = test_env["principals"]["engineer_a"]
        principal_b = test_env["principals"]["engineer_b"]

        # Create Tenant A project and device
        proj_a_id = f"proj-a-{uuid.uuid4().hex[:8]}"
        db.create_project(
            {"id": proj_a_id, "name": "Tenant A Secret Project", "author": principal_a}
        )
        db.create_device(
            proj_a_id,
            {
                "id": "dev-secret-a",
                "type": "SMOKE_DETECTOR",
                "name": "Secret Detector A",
                "category": "initiating",
                "x": 1.0,
                "y": 1.0,
                "z": 1.0,
            },
        )

        # Create Tenant B project and device
        proj_b_id = f"proj-b-{uuid.uuid4().hex[:8]}"
        db.create_project({"id": proj_b_id, "name": "Tenant B Project", "author": principal_b})
        db.create_device(
            proj_b_id,
            {
                "id": "dev-b-1",
                "type": "HEAT_DETECTOR",
                "name": "Tenant B Detector",
                "category": "initiating",
                "x": 2.0,
                "y": 2.0,
                "z": 2.0,
            },
        )

        # Tenant B calls GET /api/v1/devices
        resp = client.get("/api/v1/devices", headers={"X-API-Key": key_eng_b})
        assert resp.status_code == 200
        data = resp.json().get("data", {})
        items = data.get("data", [])

        # Must only see Tenant B devices, NOT Tenant A's device
        device_ids = [d["id"] for d in items]
        assert "dev-secret-a" not in device_ids
        if items:
            assert "dev-b-1" in device_ids


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SEC-RUN2-004: Ping-Provider RBAC Protection
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentWsPingProviderRBAC:
    def test_viewer_denied_ping_provider(self, test_env):
        """Viewer role must receive HTTP 403 on ping-provider endpoint."""
        client = test_env["client"]
        viewer_key = test_env["keys"]["viewer"]

        resp = client.post(
            "/api/v1/agent/ping-provider",
            headers={"X-API-Key": viewer_key},
            json={"provider": "ollama", "baseUrl": "http://127.0.0.1:11434"},
        )
        assert resp.status_code == 403, (
            "Viewer must be denied CALCULATION_EXECUTE on /ping-provider"
        )

    def test_engineer_authorized_ping_provider(self, test_env):
        """Engineer role is authorized to invoke ping-provider."""
        client = test_env["client"]
        engineer_key = test_env["keys"]["engineer_a"]

        with patch("backend.routers.agent_ws.ping_provider", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (True, 45.2, None)

            resp = client.post(
                "/api/v1/agent/ping-provider",
                headers={"X-API-Key": engineer_key},
                json={"provider": "ollama", "baseUrl": "http://127.0.0.1:11434"},
            )
            assert resp.status_code == 200
            json_body = resp.json()
            assert json_body["success"] is True
            assert json_body["latencyMs"] == 45.2
