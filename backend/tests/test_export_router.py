"""backend/tests/test_export_router.py — Tests for API v2 Export Endpoints.

Covers:
- POST /api/v2/export/plan
- POST /api/v2/export/execute
- POST /api/v2/export/run
- GET /api/v2/export/artifacts/{artifact_id}
- GET /api/v2/export/artifacts/{artifact_id}/download
- 400 Bad Request on unsupported format
- 409 Conflict on OCC revision drift
- 404 Not Found on missing artifacts
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.state_store import default_state_store
from backend.database import get_db


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


import uuid


@pytest.fixture
def seeded_project():
    db = get_db()
    pid = f"proj-exp-{uuid.uuid4().hex[:8]}"
    db.create_project({"id": pid, "name": "HQ Tower", "author": "Lead Architect"})
    db.create_device(
        pid,
        {
            "id": f"dev-{uuid.uuid4().hex[:8]}",
            "name": "Tower Smoke Detector",
            "type": "smoke_detector",
            "category": "FIRE_ALARM",
            "x": 12.0,
            "y": 18.0,
            "z": 3.2,
            "voltage": 24.0,
            "current": 0.06,
            "zone": "Zone A",
        },
    )
    return pid


class TestExportRouterEndpoints:
    def test_plan_export_success(self, client: TestClient, seeded_project: str):
        res = client.post(
            "/api/v2/export/plan",
            json={
                "project_id": seeded_project,
                "target_format": "dxf",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["plan"]["target_format"] == "dxf"
        assert data["plan"]["project_id"] == seeded_project

    def test_plan_export_unsupported_format(self, client: TestClient, seeded_project: str):
        res = client.post(
            "/api/v2/export/plan",
            json={
                "project_id": seeded_project,
                "target_format": "unsupported_xyz",
            },
        )
        assert res.status_code == 400
        assert res.json()["detail"]["errorCode"] == "UNSUPPORTED_FORMAT"

    def test_execute_export_success_and_download(self, client: TestClient, seeded_project: str):
        rev = default_state_store.get_project_revision(seeded_project)
        exec_res = client.post(
            "/api/v2/export/execute",
            json={
                "project_id": seeded_project,
                "expected_revision": rev,
                "target_format": "xlsx",
            },
        )
        assert exec_res.status_code == 200
        data = exec_res.json()
        assert data["success"] is True
        artifact_id = data["result"]["artifact"]["artifact_id"]

        # Check metadata endpoint
        meta_res = client.get(f"/api/v2/export/artifacts/{artifact_id}")
        assert meta_res.status_code == 200
        assert meta_res.json()["artifact"]["artifact_id"] == artifact_id

        # Check download endpoint
        dl_res = client.get(f"/api/v2/export/artifacts/{artifact_id}/download")
        assert dl_res.status_code == 200
        assert "Content-Disposition" in dl_res.headers
        assert len(dl_res.content) > 0

    def test_execute_export_occ_conflict_returns_409(self, client: TestClient, seeded_project: str):
        rev = default_state_store.get_project_revision(seeded_project)
        res = client.post(
            "/api/v2/export/execute",
            json={
                "project_id": seeded_project,
                "expected_revision": rev + 999,  # Stale revision
                "target_format": "dxf",
            },
        )
        assert res.status_code == 409
        assert res.json()["detail"]["errorCode"] == "PROJECT_REVISION_CHANGED"

    def test_create_export_agent_run(self, client: TestClient, seeded_project: str):
        res = client.post(
            "/api/v2/export/run",
            json={
                "project_id": seeded_project,
                "target_format": "json",
                "approval_mode": "AUTO",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "runId" in data["run"]
        assert data["run"]["projectId"] == seeded_project

    def test_get_nonexistent_artifact_returns_404(self, client: TestClient):
        res = client.get("/api/v2/export/artifacts/art-missing-id-999")
        assert res.status_code == 404
        assert res.json()["detail"]["errorCode"] == "ARTIFACT_NOT_FOUND"
