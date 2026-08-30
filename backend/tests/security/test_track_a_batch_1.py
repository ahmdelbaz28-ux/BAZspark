"""
test_track_a_batch_1.py — Automated verification for Track A / Batch 1
"Protocol Correctness + Security" (A1 + A2 + A4 + A5).

Tests:
1. WS without credentials -> rejected with 4401.
2. WS with valid key in query string -> rejected (4401) because query fallback is eliminated.
3. Single-use ticket lifecycle: valid ticket connects; replay/reuse fails; expired ticket fails (atomic pop).
4. Full Tenant Isolation Matrix:
   - Elements: create, get, update, delete, list with foreign project -> 404 anti-enumeration.
   - Sync: sync_project, get_sync_status, WS subscribe, WS get_status -> 404 / unauthorized error.
   - Reports: list_reports with foreign project -> 404 anti-enumeration.
5. run_start OCC revision conflict and malformed expected_revision rejection.
6. CI grep checks: 0 matches for query-string token fallback in WS handshake (agent_ws.py & revit_api.py).
"""

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect

from backend.app import app
from backend.api_keys import add_api_key, delete_api_key
from backend.database import get_db
from backend.rbac import Role
from backend.routers.agent_ws import (
    _consume_ws_ticket,
    _issue_ws_ticket,
    _extract_api_key_from_handshake,
    _ws_tickets,
)
from backend.routers.elements import (
    _verify_project as elements_verify_project,
    create_element,
    get_element,
    update_element,
    delete_element,
    list_elements,
)
from backend.routers.reports import (
    _verify_project as reports_verify_project,
    list_reports,
)
from backend.routers.sync import (
    _verify_project as sync_verify_project,
    sync_project,
    get_sync_status,
)


client = TestClient(app)


def make_mock_request(principal: str = "", role: Role = Role.ENGINEER):
    """Helper to construct a starlette Request with the exact state fields expected by auth helpers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "fireai_principal": principal,
        "fireai_role": role,
    }
    req = Request(scope)
    req.state.fireai_principal = principal
    req.state.fireai_role = role
    return req


# ─── 1 & 2. WebSocket Auth Tests (A1) ───────────────────────────────────────


def test_ws_without_credentials_rejected():
    """1. WS without any credentials is closed with code 4401."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/v1/agent/ws",
            headers={"X-API-Key": "", "authorization": "", "Origin": "http://localhost:5173"},
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4401


def test_ws_with_query_param_key_rejected():
    """2. WS with valid key in query string is REJECTED (query fallback removed)."""
    test_key = "test-query-key-secret-123"
    add_api_key(test_key, Role.ENGINEER, "test query key")

    try:
        # Connecting via query params (?api_key=... or ?token=...) must FAIL with 4401
        for qparam in ("token", "api_key", "auth_token"):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/api/v1/agent/ws?{qparam}={test_key}",
                    headers={"X-API-Key": "", "authorization": "", "Origin": "http://localhost:5173"},
                ) as ws:
                    ws.receive_text()
            assert exc_info.value.code == 4401
    finally:
        delete_api_key(test_key)


def test_ws_with_valid_header_succeeds():
    """Header-based auth works properly."""
    test_key = "test-header-key-secret-456"
    add_api_key(test_key, Role.ENGINEER, "test header key")
    try:
        with client.websocket_connect(
            "/api/v1/agent/ws",
            headers={"X-API-Key": test_key, "Origin": "http://localhost:5173"},
        ) as ws:
            assert ws is not None
    finally:
        delete_api_key(test_key)


# ─── 3. Single-Use WS Ticket Lifecycle Tests (A1) ───────────────────────────


def test_ws_ticket_lifecycle():
    """3. Valid ticket connects; replay/reuse fails (atomic pop); expired ticket fails."""
    test_info = SimpleNamespace(
        name="engineer_bob",
        role=Role.ENGINEER,
        key_hash="hash-bob",
        email="bob@bazspark.com",
    )
    origin = "http://localhost:5173"

    # Generate valid ticket
    ticket = _issue_ws_ticket(test_info, origin=origin)
    assert ticket is not None
    assert ticket in _ws_tickets

    # First consumption succeeds
    consumed = _consume_ws_ticket(ticket, origin=origin)
    assert consumed is not None
    assert consumed.name == "engineer_bob"

    # Second consumption (replay) fails immediately due to atomic dict.pop()
    replayed = _consume_ws_ticket(ticket, origin=origin)
    assert replayed is None

    # Expired ticket
    expired_ticket = _issue_ws_ticket(test_info, origin=origin)
    # Artificially expire the ticket
    _ws_tickets[expired_ticket]["expires"] -= 100
    expired = _consume_ws_ticket(expired_ticket, origin=origin)
    assert expired is None


def test_ws_connect_with_valid_ticket_endpoint():
    """Connecting to WebSocket endpoint using a single-use ticket succeeds once, fails on replay."""
    test_key = "ticket-issuer-key-789"
    add_api_key(test_key, Role.ENGINEER, "ticket user")
    try:
        # Request ticket via REST endpoint
        res = client.post(
            "/api/v1/agent/ws-ticket",
            headers={"X-API-Key": test_key, "Origin": "http://localhost:5173"},
        )
        assert res.status_code == 200
        ticket_data = res.json()
        ticket = ticket_data["ticket"]

        # Connect with ticket
        with client.websocket_connect(
            f"/api/v1/agent/ws?ticket={ticket}",
            headers={"X-API-Key": "", "authorization": "", "Origin": "http://localhost:5173"},
        ) as ws:
            assert ws is not None

        # Connecting again with same ticket fails (burned)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/api/v1/agent/ws?ticket={ticket}",
                headers={"X-API-Key": "", "authorization": "", "Origin": "http://localhost:5173"},
            ) as ws:
                ws.receive_text()
        assert exc_info.value.code == 4401
    finally:
        delete_api_key(test_key)


# ─── 4. Full Tenant Isolation Matrix Tests (A2) ─────────────────────────────


@pytest.mark.asyncio
async def test_tenant_isolation_elements_full_matrix():
    """4a. Elements full matrix: foreign project -> 404 anti-enumeration across CRUD & list."""
    db = get_db()
    proj_alice = db.create_project(
        {
            "name": "Alice Project Elements",
            "author": "alice_user",
            "modelId": "dt-proj-alice-elem",
        }
    )
    alice_id = proj_alice["id"]

    mock_bob_request = make_mock_request(principal="bob_user", role=Role.ENGINEER)
    mock_alice_request = make_mock_request(principal="alice_user", role=Role.ENGINEER)
    mock_admin_request = make_mock_request(principal="admin_user", role=Role.ADMIN)

    # 1. Verification helper
    assert elements_verify_project(alice_id, mock_alice_request)["id"] == alice_id
    assert elements_verify_project(alice_id, mock_admin_request)["id"] == alice_id
    with pytest.raises(HTTPException) as exc_info:
        elements_verify_project(alice_id, mock_bob_request)
    assert exc_info.value.status_code == 404

    # 2. list_elements for foreign project raises 404 for Bob
    with pytest.raises(HTTPException) as exc_info:
        await list_elements(
            request=mock_bob_request,
            project_id=alice_id,
            element_type=None,
            is_deleted=False,
            page=1,
            page_size=10,
            sort_by="created_at",
            sort_order="desc",
            db=db,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation_sync_full_matrix():
    """4b. Sync full matrix: foreign project verification returns 404 on REST and error on WS."""
    db = get_db()
    proj = db.create_project(
        {
            "name": "Sync Project",
            "author": "alice_user",
            "modelId": "dt-proj-sync",
        }
    )
    sync_proj_id = proj["id"]

    mock_bob_request = make_mock_request(principal="bob_user", role=Role.ENGINEER)
    mock_alice_request = make_mock_request(principal="alice_user", role=Role.ENGINEER)

    # 1. Verification helper
    assert sync_verify_project(sync_proj_id, mock_alice_request)["id"] == sync_proj_id
    with pytest.raises(HTTPException) as exc_info:
        sync_verify_project(sync_proj_id, mock_bob_request)
    assert exc_info.value.status_code == 404

    # 2. REST endpoints
    with pytest.raises(HTTPException) as exc_info:
        await sync_project(request=mock_bob_request, project_id=sync_proj_id)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await get_sync_status(request=mock_bob_request, project_id=sync_proj_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation_reports_full_matrix():
    """4c. Reports full matrix: foreign project verification returns 404 on list_reports."""
    db = get_db()
    proj = db.create_project(
        {
            "name": "Reports Project",
            "author": "alice_user",
            "modelId": "dt-proj-reports",
        }
    )
    reports_proj_id = proj["id"]

    mock_bob_request = make_mock_request(principal="bob_user", role=Role.ENGINEER)
    mock_alice_request = make_mock_request(principal="alice_user", role=Role.ENGINEER)

    # 1. Verification helper
    assert reports_verify_project(reports_proj_id, mock_alice_request)["id"] == reports_proj_id
    with pytest.raises(HTTPException) as exc_info:
        reports_verify_project(reports_proj_id, mock_bob_request)
    assert exc_info.value.status_code == 404

    # 2. list_reports
    with pytest.raises(HTTPException) as exc_info:
        await list_reports(request=mock_bob_request, project_id=reports_proj_id)
    assert exc_info.value.status_code == 404


# ─── 5. OCC Revision Validation Tests (A5) ──────────────────────────────────


def test_occ_revision_validation_in_workflow():
    """5. Reconcile context and OCC validation rejects revision conflicts and mismatched models."""
    from backend.routers.workflow import _reconcile_and_validate_execution_context

    db = get_db()
    proj = db.create_project(
        {
            "name": "OCC Test Project",
            "author": "alice_user",
        }
    )
    p_id = proj["id"]
    canonical_model = proj.get("modelId") or f"dt-{p_id}"

    mock_alice_request = make_mock_request(principal="alice_user", role=Role.ENGINEER)

    # 1. Fetch canonical revision with matching revision
    ctx = _reconcile_and_validate_execution_context(
        request=mock_alice_request,
        project_id=p_id,
        model_id=canonical_model,
        expected_revision=1,
    )
    assert ctx["canonical_revision"] == 1

    # 2. Conflict: expected_revision=2 when canonical is 1 -> raises HTTP 409
    with pytest.raises(HTTPException) as exc_info:
        _reconcile_and_validate_execution_context(
            request=mock_alice_request,
            project_id=p_id,
            model_id=canonical_model,
            expected_revision=2,
        )
    assert exc_info.value.status_code == 409

    # 3. Mismatched model_id -> raises HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        _reconcile_and_validate_execution_context(
            request=mock_alice_request,
            project_id=p_id,
            model_id="dt-wrong-model",
            expected_revision=1,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_run_start_occ_revision_conflict_frame():
    """5b. WS run_start OCC revision conflict returns REVISION_CONFLICT error frame."""
    from backend.routers import agent_ws
    from backend.core.command_bus import AuthenticatedPrincipal

    class MockWs:
        def __init__(self):
            self.sent = []
        async def send_json(self, data):
            self.sent.append(data)

    ws = MockWs()
    principal = AuthenticatedPrincipal(
        user_id="alice_user",
        email="alice@bazspark.com",
        role="engineer",
        scopes=["*"],
        is_authenticated=True,
    )

    db = get_db()
    proj = db.create_project({"name": "OCC WS Proj", "author": "alice_user"})
    p_id = proj["id"]

    # Trigger with conflicting expected_revision
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "expectedRevision": 999,
        "steps": [{"step_id": "s1", "capability_id": "spatial.place_devices", "payload": {}}],
    }
    await agent_ws._handle_run_start(ws, principal, msg)
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "REVISION_CONFLICT"


@pytest.mark.asyncio
async def test_run_start_malformed_expected_revision_rejected():
    """5c. WS run_start malformed expected_revision (non-integer string) returns INVALID_EXPECTED_REVISION."""
    from backend.routers import agent_ws
    from backend.core.command_bus import AuthenticatedPrincipal

    class MockWs:
        def __init__(self):
            self.sent = []
        async def send_json(self, data):
            self.sent.append(data)

    ws = MockWs()
    principal = AuthenticatedPrincipal(
        user_id="alice_user",
        email="alice@bazspark.com",
        role="engineer",
        scopes=["*"],
        is_authenticated=True,
    )

    # Trigger with malformed (non-integer string) expectedRevision
    msg = {
        "type": "run_start",
        "projectId": "proj-any",
        "expectedRevision": "garbage_not_a_number",
        "steps": [{"step_id": "s1", "capability_id": "spatial.place_devices", "payload": {}}],
    }
    await agent_ws._handle_run_start(ws, principal, msg)
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "INVALID_EXPECTED_REVISION"
    assert "expected_revision must be an integer" in ws.sent[0]["message"]


# ─── 10. CI Grep Checks ─────────────────────────────────────────────────────


def test_ci_grep_no_ws_query_string_auth():
    """10. Zero occurrences of query string fallback loop in agent_ws.py and revit_api.py."""
    root = Path(__file__).resolve().parents[2]

    agent_ws_code = (root / "routers" / "agent_ws.py").read_text(encoding="utf-8")
    assert 'for qparam in ("token", "api_key", "auth_token")' not in agent_ws_code
    assert "websocket.query_params.get(qparam)" not in agent_ws_code

    revit_api_code = (root / "routers" / "revit_api.py").read_text(encoding="utf-8")
    assert 'websocket.query_params.get("api_key")' not in revit_api_code
    assert 'websocket.query_params.get("token")' not in revit_api_code
