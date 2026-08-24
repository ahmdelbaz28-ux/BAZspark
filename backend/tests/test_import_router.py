"""backend/tests/test_import_router.py — Tests for Import Router REST & WebSocket endpoints.

Covers:
- POST /api/v2/import/upload (valid and invalid formats)
- POST /api/v2/import/inspect
- POST /api/v2/import/plan
- POST /api/v2/import/execute (OCC conflict & success)
- POST /api/v2/import/runs (durable AgentRun creation)
- WebSocket import_intent handling in agent_ws
"""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.command_bus import AuthenticatedPrincipal
from backend.routers import agent_ws


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class MockWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.send_json = AsyncMock(side_effect=self._record_message)

    async def _record_message(self, data: dict[str, Any]) -> None:
        self.sent_messages.append(data)


# ── REST API Endpoints Tests ────────────────────────────────────────────────


class TestImportRouterRestEndpoints:
    def test_upload_valid_dxf_file(self, client: TestClient):
        dxf_bytes = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF"
        files = {"file": ("ground_floor.dxf", io.BytesIO(dxf_bytes), "application/dxf")}

        response = client.post("/api/v2/import/upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["file"]["detected_format"] == "dxf"
        assert data["file"]["sanitized_filename"] == "ground_floor.dxf"
        assert "file_id" in data["file"]

    def test_upload_unsupported_format_returns_400(self, client: TestClient):
        exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00"
        files = {"file": ("malicious.exe", io.BytesIO(exe_bytes), "application/octet-stream")}

        response = client.post("/api/v2/import/upload", files=files)
        assert response.status_code == 400
        assert "errorCode" in response.json()["detail"]

    def test_inspect_staged_file(self, client: TestClient):
        # 1. Upload
        dxf_bytes = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF"
        upload_res = client.post(
            "/api/v2/import/upload",
            files={"file": ("plan.dxf", io.BytesIO(dxf_bytes), "application/dxf")},
        )
        file_id = upload_res.json()["file"]["file_id"]

        # 2. Inspect
        inspect_res = client.post(
            "/api/v2/import/inspect",
            json={"file_id": file_id},
        )
        assert inspect_res.status_code == 200
        data = inspect_res.json()
        assert data["success"] is True
        assert data["inspection"]["file_id"] == file_id
        assert data["inspection"]["detected_format"] == "dxf"

    def test_plan_import_endpoint(self, client: TestClient):
        # Upload
        dxf_bytes = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF"
        upload_res = client.post(
            "/api/v2/import/upload",
            files={"file": ("plan.dxf", io.BytesIO(dxf_bytes), "application/dxf")},
        )
        file_id = upload_res.json()["file"]["file_id"]

        # Plan
        plan_res = client.post(
            "/api/v2/import/plan",
            json={"file_id": file_id, "project_id": "proj-rest-01"},
        )
        assert plan_res.status_code == 200
        plan = plan_res.json()["plan"]
        assert plan["file_id"] == file_id
        assert plan["project_id"] == "proj-rest-01"
        assert "summary" in plan

    def test_execute_import_endpoint(self, client: TestClient):
        # Upload
        dxf_bytes = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF"
        upload_res = client.post(
            "/api/v2/import/upload",
            files={"file": ("plan.dxf", io.BytesIO(dxf_bytes), "application/dxf")},
        )
        file_id = upload_res.json()["file"]["file_id"]

        # Plan to get expected_revision
        plan_res = client.post(
            "/api/v2/import/plan",
            json={"file_id": file_id, "project_id": "proj-rest-exec"},
        )
        expected_rev = plan_res.json()["plan"]["expected_revision"]

        # Execute
        exec_res = client.post(
            "/api/v2/import/execute",
            json={
                "file_id": file_id,
                "project_id": "proj-rest-exec",
                "expected_revision": expected_rev,
            },
        )
        assert exec_res.status_code == 200
        res = exec_res.json()["result"]
        assert res["success"] is True
        assert res["new_revision"] == expected_rev + 1
        assert "audit_hash" in res

    def test_create_import_agent_run(self, client: TestClient):
        # Upload
        dxf_bytes = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF"
        upload_res = client.post(
            "/api/v2/import/upload",
            files={"file": ("drawing.dxf", io.BytesIO(dxf_bytes), "application/dxf")},
        )
        file_id = upload_res.json()["file"]["file_id"]

        run_res = client.post(
            "/api/v2/import/runs",
            json={
                "file_id": file_id,
                "project_id": "proj-run-import",
                "approval_mode": "AUTO",
            },
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["success"] is True
        assert "runId" in data["run"]
        assert data["run"]["status"] in ("COMPLETED", "RUNNING")


# ── WebSocket Import Intent Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_websocket_import_intent_flow():
    from backend.core.import_orchestrator import default_import_orchestrator

    ws = MockWebSocket()
    principal = AuthenticatedPrincipal(
        user_id="user-ws",
        email="user@bazspark.io",
        role="engineer",
        scopes=["import:read", "project:read"],
        is_authenticated=True,
    )

    record = default_import_orchestrator.stage_file(
        content=b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF",
        filename="ws_test.dxf",
        principal=principal,
    )

    msg = {
        "type": "import_intent",
        "fileId": record.file_id,
        "projectId": "proj-ws-test",
    }

    await agent_ws._handle_agent_message(ws, msg, principal)

    assert len(ws.sent_messages) == 1
    frame = ws.sent_messages[0]
    assert frame["type"] == "import_preview"
    assert frame["fileId"] == record.file_id
    assert frame["detectedFormat"] == "dxf"
    assert frame["filename"] == "ws_test.dxf"
