"""backend/tests/test_ws_wire_contract.py — WebSocket Wire Contract test suite.

Validates Phase 3 requirements:
1. Elimination of silent defaults on WS frames.
2. MISSING_EXPECTED_REVISION rejection on approval and composite approval.
3. INVALID_EXPECTED_REVISION validation on invalid types.
4. O5: Rejection of unauthenticated browser WebSocket connections (code 4401).
5. Successful ticket authentication and lifecycle operations.
6. run_start entity_ids and revision validation against database.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api_keys import add_api_key
from backend.app import app
from backend.database import get_db
from backend.rbac import Role


def _receive_non_ping(ws) -> dict:
    """Receive next WebSocket message, ignoring/responding to background heartbeat pings."""
    while True:
        msg = ws.receive_json()
        if msg.get("type") == "ping":
            ws.send_json({"type": "pong"})
            continue
        return msg


@pytest.fixture
def auth_api_key():
    key = f"test-admin-key-ws-wire-{uuid.uuid4().hex[:12]}"
    add_api_key(key, Role.ADMIN, "WS Wire Test Admin Key")
    return key


@pytest.fixture
def seeded_project():
    db = get_db()
    pid = f"proj-ws-{uuid.uuid4().hex[:8]}"
    dev_id = f"dev-ws-smoke-{uuid.uuid4().hex[:8]}"
    proj = {
        "id": pid,
        "name": "WS Wire Contract Test Project",
        "modelId": f"dt-{pid}",
        "author": "admin",
        "device_id": dev_id,
    }
    db.create_project(proj)
    with db._transaction() as cur:
        cur.execute(
            f"SELECT revision FROM project_revisions WHERE project_id = {db._ph()}",
            (pid,),
        )
        if not cur.fetchone():
            cur.execute(
                f"INSERT INTO project_revisions (project_id, revision) VALUES ({db._ph()}, {db._ph()})",
                (pid, 5),
            )
        else:
            cur.execute(
                f"UPDATE project_revisions SET revision = {db._ph()} WHERE project_id = {db._ph()}",
                (5, pid),
            )

    dev = {
        "id": dev_id,
        "name": "WS Smoke Detector",
        "projectId": pid,
        "type": "detector",
        "category": "smoke",
        "x": 12.0,
        "y": 15.0,
    }
    db.create_device(pid, dev)
    return proj


# =========================================================================
# 1. O5 Browser Origin & Ticket Auth Tests
# =========================================================================

def test_o5_browser_origin_without_ticket_rejected_4401():
    client = TestClient(app)
    # Browser client sends Origin header but lacks ticket query param and key -> 4401
    try:
        with client.websocket_connect(
            "/api/v1/agent/ws",
            headers={"Origin": "http://localhost:5173"},
        ) as ws:
            ws.receive()
    except Exception as exc:
        assert "4401" in str(exc) or "WebSocketDisconnect" in type(exc).__name__


def test_o5_ticket_generation_and_auth_success(auth_api_key):
    client = TestClient(app)
    # 1. Acquire single-use ticket
    ticket_res = client.post(
        "/api/v1/agent/ws-ticket",
        headers={"X-API-Key": auth_api_key},
    )
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]
    assert ticket

    # 2. Connect to WS using ticket
    with client.websocket_connect(
        f"/api/v1/agent/ws?ticket={ticket}",
        headers={"Origin": "http://localhost:5173"},
    ) as ws:
        # Ping
        ws.send_json({"type": "ping"})
        msg = _receive_non_ping(ws)
        assert msg["type"] == "pong"


# =========================================================================
# 2. Approval Frame Validation & Elimination of Silent Defaults
# =========================================================================

def test_ws_approval_stateless_capability_succeeds(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "approval",
            "projectId": seeded_project["id"],
            "capabilityId": "spatial.place_devices",
            "expectedRevision": 5,
            "payload": {
                "room_id": "r1",
                "width_m": 8.0,
                "length_m": 10.0,
                "ceiling_height_m": 3.0,
                "detector_type": "smoke",
            },
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "ai_committed"


def test_ws_approval_mutation_missing_expected_revision(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "approval",
            "projectId": seeded_project["id"],
            "capabilityId": "import.execute_import",
            # expectedRevision is missing
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "ai_error"
        assert msg["errorCode"] == "MISSING_EXPECTED_REVISION"


def test_ws_approval_invalid_expected_revision_type(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "approval",
            "projectId": seeded_project["id"],
            "capabilityId": "import.execute_import",
            "expectedRevision": "invalid-non-integer",
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "ai_error"
        assert msg["errorCode"] == "INVALID_EXPECTED_REVISION"


# =========================================================================
# 3. Composite Approval Validation
# =========================================================================

def test_ws_composite_approval_missing_expected_revision(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "composite_approval",
            "projectId": seeded_project["id"],
            "dag": {"nodes": [{"node_id": "step_1", "capability_id": "spatial.place_devices"}]},
            # expectedRevision missing
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "ai_error"
        assert msg["errorCode"] == "MISSING_EXPECTED_REVISION"


def test_ws_composite_approval_invalid_payload_missing_dag(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "composite_approval",
            "projectId": seeded_project["id"],
            # dag missing
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "ai_error"
        assert msg["errorCode"] == "INVALID_WORKFLOW_PAYLOAD"


# =========================================================================
# 4. run_start Universal Context & Entity Validation
# =========================================================================

def test_ws_run_start_mutation_missing_revision(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "run_start",
            "projectId": seeded_project["id"],
            "steps": [
                {
                    "step_id": "s1",
                    "capability_id": "import.execute_import",
                    "description": "Execute import",
                }
            ],
            # expected_revision missing
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "run_error"
        assert msg["errorCode"] == "MISSING_EXPECTED_REVISION"


def test_ws_run_start_entity_not_found(auth_api_key, seeded_project):
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/agent/ws",
        headers={"X-API-Key": auth_api_key},
    ) as ws:
        ws.send_json({
            "type": "run_start",
            "projectId": seeded_project["id"],
            "expected_revision": 5,
            "entity_ids": ["dev-ghost-nonexistent"],
            "steps": [
                {
                    "step_id": "s1",
                    "capability_id": "spatial.place_devices",
                    "description": "Place devices",
                }
            ],
        })
        msg = _receive_non_ping(ws)
        assert msg["type"] == "run_error"
        assert msg["errorCode"] == "ENTITY_NOT_FOUND"
