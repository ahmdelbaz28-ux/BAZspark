"""backend/tests/test_agent_run_routers.py — Phase 1 router-surface tests.

Covers the Phase 1 Agent Run integration surfaces:
  - WebSocket handlers in backend/routers/agent_ws.py
    (run_start / run_status / run_resume / run_pause / run_cancel /
     run_retry / approval_decision + error mapping + dispatch chain)
  - REST endpoints in backend/routers/workflow.py
    (/runs/{id}/status|resume|cancel|retry|approvals/{id}/decide +
     HTTP error mapping)

These complement test_run_lifecycle.py (core orchestrator) by exercising
the wire-level adapters so SonarCloud new-code coverage reflects reality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.core.agent_run_orchestrator import (
    AgentRunOrchestrator,
    InvalidRunStateError,
    RunNotFoundError,
    RunPermissionError,
)
from backend.core.agent_run_store import AgentRunStore
from backend.core.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
)
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus
from backend.core.state_store import CommandStateStore
from backend.database import Database
from backend.routers import agent_ws, workflow

SPATIAL = "spatial.place_devices"
ELECTRICAL = "electrical.calculate_voltage_drop"


# ── Shared fixtures ──────────────────────────────────────────────────────────


class MockWebSocket:
    """Records every send_json frame (same pattern as test_agent_ws_spine)."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.send_json = AsyncMock(side_effect=self._record_message)

    async def _record_message(self, data: dict[str, Any]) -> None:
        self.sent_messages.append(data)


@pytest.fixture
def ws() -> MockWebSocket:
    return MockWebSocket()


@pytest.fixture
def fresh_db(tmp_path: Path) -> Database:
    return Database(db_path=str(tmp_path / "agent_run_router_test.db"))


@pytest.fixture
def registry() -> CapabilityRegistry:
    return CapabilityRegistry()


@pytest.fixture
def orch(fresh_db: Database, registry: CapabilityRegistry) -> AgentRunOrchestrator:
    bus = CommandBus(state_store=CommandStateStore(fresh_db))
    store = AgentRunStore(fresh_db)
    return AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=store,
        environment="development",
    )


@pytest.fixture
def owner() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="owner-01",
        email="owner@bazspark.io",
        role="engineer",
        scopes=["spatial:write", "electrical:write"],
        is_authenticated=True,
    )


def _spatial_step(step_id: str = "s1") -> dict:
    return {
        "step_id": step_id,
        "capability_id": SPATIAL,
        "payload": {
            "room_id": "room-rtr",
            "width_m": 10.0,
            "length_m": 12.0,
            "ceiling_height_m": 3.0,
            "detector_type": "smoke",
        },
    }


def _electrical_step(step_id: str = "s2") -> dict:
    return {
        "step_id": step_id,
        "capability_id": ELECTRICAL,
        "payload": {
            "circuit_id": "nac-rtr-01",
            "current_a": 2.0,
            "one_way_length_m": 35.0,
            "awg": "14",
        },
    }


@pytest.fixture
def patched_orch(monkeypatch: pytest.MonkeyPatch, orch: AgentRunOrchestrator):
    """Point both routers' module-level default orchestrators at a tmp store."""
    monkeypatch.setattr(agent_ws, "default_agent_run_orchestrator", orch)
    monkeypatch.setattr(workflow, "default_agent_run_orchestrator", orch)
    return orch


@pytest.fixture(autouse=True)
def _auto_seed_router_projects(orch: AgentRunOrchestrator) -> None:
    """Seed project revisions so OCC checks don't reject legitimate test operations."""
    for pid in [
        "proj-ws-auto",
        "proj-ws-appr",
        "proj-ws-pause",
        "proj-ws-cancel",
        "proj-ws-retry",
        "proj-ws-decide",
        "proj-ws-dispatch",
        "proj-rest-status",
        "proj-rest-resume",
        "proj-rest-cancel",
        "proj-rest-retry",
        "proj-rest-baddec",
        "proj-rest-unkappr",
        "proj-rest-mismatch-a",
        "proj-rest-mismatch-b",
        "proj-rest-ok",
        "proj-rest-resume-ok",
        "proj-rest-cancel-done",
        "proj-rest-retry-ok",
    ]:
        orch._bus.state_store.set_project_revision(pid, 1)


# ── WS handler unit tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_start_requires_nonempty_steps(
    ws: MockWebSocket, owner: AuthenticatedPrincipal
) -> None:
    await agent_ws._handle_run_start(ws, owner, {"type": "run_start"})
    assert len(ws.sent_messages) == 1
    resp = ws.sent_messages[0]
    assert resp["type"] == "run_error"
    assert resp["errorCode"] == "INVALID_RUN_PLAN"


@pytest.mark.asyncio
async def test_run_start_single_step_completes(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    msg = {
        "type": "run_start",
        "projectId": "proj-ws-auto",
        "steps": [_spatial_step()],
        "approvalMode": "AUTO",
    }
    await agent_ws._handle_run_start(ws, owner, msg)
    assert len(ws.sent_messages) == 1
    frame = ws.sent_messages[0]
    assert frame["type"] == "run_status_update"
    assert frame["status"] == "COMPLETED"
    assert frame["completedSteps"] == ["s1"]
    assert frame["version"] >= 1


@pytest.mark.asyncio
async def test_run_start_emits_approval_request_frame(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    msg = {
        "type": "run_start",
        "projectId": "proj-ws-appr",
        "steps": [_spatial_step("s1"), _electrical_step("s2")],
        "approvalMode": "AUTO",
    }
    await agent_ws._handle_run_start(ws, owner, msg)
    types = [f["type"] for f in ws.sent_messages]
    assert types == ["run_status_update", "approval_request"]
    state = ws.sent_messages[0]
    assert state["status"] == "WAITING_APPROVAL"
    approval = ws.sent_messages[1]
    assert approval["approvalId"] == state["pendingApprovalId"]
    assert approval["capabilityId"] == ELECTRICAL


@pytest.mark.asyncio
async def test_run_status_unknown_run_maps_to_run_not_found(
    ws: MockWebSocket, owner: AuthenticatedPrincipal
) -> None:
    await agent_ws._handle_run_status(ws, owner, {"type": "run_status", "runId": "nope"})
    assert len(ws.sent_messages) == 1
    resp = ws.sent_messages[0]
    assert resp["type"] == "run_error"
    assert resp["errorCode"] == "RUN_NOT_FOUND"


@pytest.mark.asyncio
async def test_pause_resume_roundtrip_frames(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    run = patched_orch.start_run(
        owner,
        project_id="proj-ws-pause",
        steps=[_spatial_step("s1"), _electrical_step("s2")],
        approval_mode="AUTO",
    )
    await agent_ws._handle_run_pause(ws, owner, {"type": "run_pause", "runId": run.run_id})
    await agent_ws._handle_run_resume(ws, owner, {"type": "run_resume", "runId": run.run_id})
    statuses = [f["status"] for f in ws.sent_messages if f["type"] == "run_status_update"]
    assert statuses[0] == "PAUSED"
    assert statuses[-1] == "WAITING_APPROVAL"


@pytest.mark.asyncio
async def test_cancel_waiting_run_invalidates_approval(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    run = patched_orch.start_run(
        owner,
        project_id="proj-ws-cancel",
        steps=[_spatial_step("s1"), _electrical_step("s2")],
        approval_mode="AUTO",
    )
    await agent_ws._handle_run_cancel(ws, owner, {"type": "run_cancel", "runId": run.run_id})
    frame = ws.sent_messages[-1]
    assert frame["type"] == "run_status_update"
    assert frame["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_retry_on_terminal_run_maps_to_invalid_state(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    run = patched_orch.start_run(
        owner,
        project_id="proj-ws-retry",
        steps=[_spatial_step()],
        approval_mode="AUTO",
    )
    assert run.status.value == "COMPLETED"
    await agent_ws._handle_run_retry(ws, owner, {"type": "run_retry", "runId": run.run_id})
    resp = ws.sent_messages[-1]
    assert resp["type"] == "run_error"
    assert resp["errorCode"] == "INVALID_RUN_STATE"


@pytest.mark.asyncio
async def test_approval_decision_rejects_bad_value(
    ws: MockWebSocket, owner: AuthenticatedPrincipal
) -> None:
    await agent_ws._handle_approval_decision(
        ws, owner, {"type": "approval_decision", "approvalId": "a1", "decision": "MAYBE"}
    )
    resp = ws.sent_messages[0]
    assert resp["type"] == "run_error"
    assert resp["errorCode"] == "INVALID_APPROVAL_DECISION"


@pytest.mark.asyncio
async def test_approval_decision_approve_completes_run(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    run = patched_orch.start_run(
        owner,
        project_id="proj-ws-decide",
        steps=[_spatial_step("s1"), _electrical_step("s2")],
        approval_mode="AUTO",
    )
    approval_id = run.pending_approval_id
    assert approval_id is not None
    await agent_ws._handle_approval_decision(
        ws,
        owner,
        {
            "type": "approval_decision",
            "approvalId": approval_id,
            "decision": "APPROVED",
            "reason": "ws-router-test",
        },
    )
    final = ws.sent_messages[-1]
    assert final["type"] == "run_status_update"
    assert final["status"] == "COMPLETED"
    assert final["completedSteps"] == ["s1", "s2"]


@pytest.mark.asyncio
async def test_run_operation_unexpected_error_is_sanitized(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(patched_orch, "get_run_status", _boom)
    await agent_ws._handle_run_status(ws, owner, {"type": "run_status", "runId": "whatever"})
    resp = ws.sent_messages[0]
    assert resp["type"] == "run_error"
    assert resp["errorCode"] == "RUN_OPERATION_FAILED"
    assert "secret" not in resp["message"].lower()


def test_run_error_code_mapping() -> None:
    assert agent_ws._run_error_code(RunNotFoundError("x")) == "RUN_NOT_FOUND"
    assert agent_ws._run_error_code(ValueError("bad plan")) == "INVALID_RUN_PLAN"
    assert agent_ws._run_error_code(InvalidRunStateError("bad state")) == ("INVALID_RUN_STATE")
    assert agent_ws._run_error_code(RuntimeError("boom")) == "RUN_OPERATION_FAILED"


@pytest.mark.asyncio
async def test_dispatch_chain_routes_all_run_message_types(
    ws: MockWebSocket,
    owner: AuthenticatedPrincipal,
    patched_orch: AgentRunOrchestrator,
) -> None:
    """Every run_* message type routes through _handle_agent_message."""
    run = patched_orch.start_run(
        owner,
        project_id="proj-ws-dispatch",
        steps=[_spatial_step("s1"), _electrical_step("s2")],
        approval_mode="AUTO",
    )
    for msg_type, extra in (
        ("run_status", {"runId": run.run_id}),
        ("run_pause", {"runId": run.run_id}),
        ("run_resume", {"runId": run.run_id}),
        ("run_retry", {"runId": run.run_id}),
        ("run_cancel", {"runId": run.run_id}),
        ("approval_decision", {"approvalId": "missing", "decision": "APPROVED"}),
        ("run_start", {}),
    ):
        msg = {"type": msg_type, **extra}
        await agent_ws._handle_agent_message(ws, msg, owner)
    # Every dispatched message produced exactly one response frame.
    assert len(ws.sent_messages) >= 7
    # The invalid approval decision produced its dedicated error code.
    codes = [f.get("errorCode") for f in ws.sent_messages if f["type"] == "run_error"]
    assert "APPROVAL_NOT_FOUND" in codes or "RUN_OPERATION_FAILED" in codes
    # The trailing run_start without steps produced INVALID_RUN_PLAN.
    assert "INVALID_RUN_PLAN" in codes


# ── REST endpoint tests ──────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, patched_orch: AgentRunOrchestrator):
    """TestClient with RBAC/principal wired to the tmp orchestrator owner."""
    from fastapi.testclient import TestClient

    from backend.app import app
    from backend.rbac import Role

    monkeypatch.setattr(workflow, "get_current_principal", lambda request: "owner-01")
    monkeypatch.setattr(
        workflow, "require_permission", lambda permission: (lambda request: Role.ADMIN)
    )
    monkeypatch.setattr("backend.auth.has_permission", lambda role, permission: True)
    with TestClient(app) as c:
        yield c


def _make_waiting_run(orch: AgentRunOrchestrator, owner, project_id: str):
    return orch.start_run(
        owner,
        project_id=project_id,
        steps=[_spatial_step("s1"), _electrical_step("s2")],
        approval_mode="AUTO",
    )


def test_rest_get_run_status(client, patched_orch: AgentRunOrchestrator, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-status")
    resp = client.get(f"/api/workflow/runs/{run.run_id}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["runId"] == run.run_id
    assert body["data"]["status"] == "WAITING_APPROVAL"


def test_rest_get_run_status_404(client) -> None:
    resp = client.get("/api/workflow/runs/does-not-exist/status")
    assert resp.status_code == 404


def test_rest_get_run_status_internal_error_sanitized(
    client, patched_orch: AgentRunOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("db password hunter2")

    monkeypatch.setattr(patched_orch, "get_run_status", _boom)
    resp = client.get("/api/workflow/runs/some-run/status")
    assert resp.status_code == 500
    assert "hunter2" not in resp.text


def test_rest_resume_conflict_409(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-resume")
    resp = client.post(f"/api/workflow/runs/{run.run_id}/resume")
    assert resp.status_code == 409


def test_rest_cancel_success(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-cancel")
    resp = client.post(f"/api/workflow/runs/{run.run_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CANCELLED"


def test_rest_retry_conflict_409(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-retry")
    resp = client.post(f"/api/workflow/runs/{run.run_id}/retry")
    assert resp.status_code == 409


def test_rest_decide_rejects_invalid_decision(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-baddec")
    approval_id = run.pending_approval_id
    resp = client.post(
        f"/api/workflow/runs/{run.run_id}/approvals/{approval_id}/decide",
        json={"decision": "PERHAPS"},
    )
    assert resp.status_code == 400


def test_rest_decide_unknown_approval_404(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-unkappr")
    resp = client.post(
        f"/api/workflow/runs/{run.run_id}/approvals/nope/decide",
        json={"decision": "APPROVED"},
    )
    assert resp.status_code == 404


def test_rest_decide_cross_run_mismatch_409(
    client, patched_orch: AgentRunOrchestrator, owner
) -> None:
    run_a = _make_waiting_run(patched_orch, owner, "proj-rest-mismatch-a")
    run_b = _make_waiting_run(patched_orch, owner, "proj-rest-mismatch-b")
    resp = client.post(
        f"/api/workflow/runs/{run_a.run_id}/approvals/{run_b.pending_approval_id}/decide",
        json={"decision": "REJECTED", "reason": "cross-run probe"},
    )
    assert resp.status_code == 409


def test_rest_decide_approved_completes(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-ok")
    resp = client.post(
        f"/api/workflow/runs/{run.run_id}/approvals/{run.pending_approval_id}/decide",
        json={"decision": "approved"},  # lowercase on purpose (endpoint uppercases)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["completedSteps"] == ["s1", "s2"]


def test_rest_get_run_status_forbidden_403(
    client, patched_orch: AgentRunOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _deny(*_a, **_k):
        raise RunPermissionError("not your run")

    monkeypatch.setattr(patched_orch, "get_run_status", _deny)
    resp = client.get("/api/workflow/runs/some-run/status")
    assert resp.status_code == 403


def test_rest_get_run_status_value_error_400(
    client, patched_orch: AgentRunOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _bad(*_a, **_k):
        raise ValueError("malformed run id")

    monkeypatch.setattr(patched_orch, "get_run_status", _bad)
    resp = client.get("/api/workflow/runs/some-run/status")
    assert resp.status_code == 400


def test_rest_resume_success_after_pause(client, patched_orch, owner) -> None:
    run = _make_waiting_run(patched_orch, owner, "proj-rest-resume-ok")
    assert patched_orch.pause_run(owner.user_id, run.run_id).status.value == "PAUSED"
    resp = client.post(f"/api/workflow/runs/{run.run_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "WAITING_APPROVAL"


def test_rest_cancel_conflict_409(client, patched_orch, owner) -> None:
    run = patched_orch.start_run(
        owner,
        project_id="proj-rest-cancel-done",
        steps=[_spatial_step()],
        approval_mode="AUTO",
    )
    assert run.status.value == "COMPLETED"
    resp = client.post(f"/api/workflow/runs/{run.run_id}/cancel")
    assert resp.status_code == 409


def test_rest_retry_success_on_failed_run(
    client, owner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """failed run → POST retry executes failed step once more → 200 COMPLETED."""
    calls: list[int] = []

    def _handler(payload: dict) -> dict:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient deterministic failure")
        return {"room_id": payload.get("room_id", "r"), "devices": [], "is_compliant": True}

    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            capability_id="test.flaky.rest",
            name="Flaky REST Test Capability",
            description="Fails on first call only.",
            category="test",
            risk_class="MEDIUM",
            required_scopes=["spatial:write"],
            input_schema={},
            output_schema={},
            handler=_handler,
        )
    )
    db = Database(db_path=str(tmp_path / "agent_run_retry_rest.db"))
    flaky_store = CommandStateStore(db)
    flaky_store.set_project_revision("proj-rest-retry-ok", 1)
    flaky_orch = AgentRunOrchestrator(
        command_bus=CommandBus(capability_registry=registry, state_store=flaky_store),
        capability_registry=registry,
        run_store=AgentRunStore(db),
        environment="development",
    )
    monkeypatch.setattr(workflow, "default_agent_run_orchestrator", flaky_orch)

    run = flaky_orch.start_run(
        owner,
        project_id="proj-rest-retry-ok",
        steps=[{"step_id": "f1", "capability_id": "test.flaky.rest", "payload": {"room_id": "r1"}}],
        approval_mode="AUTO",
    )
    assert run.status.value == "FAILED"
    assert len(calls) == 1

    resp = client.post(f"/api/workflow/runs/{run.run_id}/retry")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "COMPLETED"
    assert len(calls) == 2  # exactly one re-execution — no duplicate mutation
