"""backend/tests/test_agent_ws_spine.py — Test AIOrchestrationService & Database methods."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.core.capability_registry import CapabilityRegistry
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus
from backend.core.context_resolver import ContextResolver
from backend.core.state_store import CommandStateStore
from backend.database import Database
from backend.routers.agent_ws import (
    AIOrchestrationService,
    _handle_ping_message,
    _handle_response_message,
    agent_response_futures,
)


class MockWebSocket:
    """Mock WebSocket for unit testing AIOrchestrationService."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.send_json = AsyncMock(side_effect=self._record_message)

    async def _record_message(self, data: dict[str, Any]) -> None:
        self.sent_messages.append(data)


@pytest.fixture
def mock_ws() -> MockWebSocket:
    return MockWebSocket()


@pytest.fixture
def test_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="ws-engineer-01",
        email="engineer@bazspark.io",
        role="engineer",
        scopes=["spatial:write", "spatial:read", "compliance:read"],
        is_authenticated=True,
    )


@pytest.fixture
def fresh_db(tmp_path: Path) -> Database:
    db_file = tmp_path / "agent_ws_test.db"
    return Database(db_path=str(db_file))


@pytest.fixture
def orchestration_service(fresh_db: Database) -> AIOrchestrationService:
    store = CommandStateStore(fresh_db)
    bus = CommandBus(state_store=store)
    resolver = ContextResolver()
    registry = CapabilityRegistry()
    return AIOrchestrationService(
        command_bus=bus,
        context_resolver=resolver,
        capability_registry=registry,
    )


@pytest.mark.asyncio
async def test_handle_intent_success(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
    test_principal: AuthenticatedPrincipal,
) -> None:
    msg = {
        "type": "ai_intent",
        "projectId": "proj-ws-1",
        "roomId": "room-101",
        "roomBounds": {"width_m": 10.0, "length_m": 12.0, "ceiling_height_m": 3.0},
        "detectorType": "smoke",
        "correlationId": "corr-intent-1",
    }
    await orchestration_service.handle_intent(mock_ws, test_principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_preview"
    assert resp["projectId"] == "proj-ws-1"
    assert resp["expectedRevision"] == 1
    assert "previewDevices" in resp
    assert len(resp["previewDevices"]) >= 1


@pytest.mark.asyncio
async def test_handle_intent_no_capability(
    mock_ws: MockWebSocket,
) -> None:
    restricted_principal = AuthenticatedPrincipal(
        user_id="viewer-01",
        email="viewer@bazspark.io",
        role="viewer",
        scopes=["spatial:read"],
        is_authenticated=True,
    )
    svc = AIOrchestrationService()
    msg = {"type": "ai_intent", "projectId": "proj-ws-2"}
    await svc.handle_intent(mock_ws, restricted_principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_error"
    assert resp["errorCode"] == "NO_CAPABILITY_AVAILABLE"


@pytest.mark.asyncio
async def test_handle_approval_success_and_concurrency_conflict(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
    test_principal: AuthenticatedPrincipal,
) -> None:
    msg = {
        "type": "ai_approve",
        "commandId": "cmd-appr-01",
        "correlationId": "corr-appr-01",
        "projectId": "proj-ws-appr",
        "expectedRevision": 1,
        "payload": {
            "room_id": "r1",
            "width_m": 8.0,
            "length_m": 10.0,
            "ceiling_height_m": 3.0,
            "detector_type": "smoke",
        },
    }
    await orchestration_service.handle_approval(mock_ws, test_principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_committed"
    assert resp["revision"] == 2

    # Second approval with stale revision 1 must return ai_conflict
    mock_ws.sent_messages.clear()
    msg2 = {
        "type": "ai_approve",
        "commandId": "cmd-appr-02",
        "projectId": "proj-ws-appr",
        "expectedRevision": 1,  # Stale
        "payload": {"room_id": "r1", "width_m": 8.0, "length_m": 10.0},
    }
    await orchestration_service.handle_approval(mock_ws, test_principal, msg2)
    assert len(mock_ws.sent_messages) == 1
    resp2 = mock_ws.sent_messages[0]
    assert resp2["type"] == "ai_conflict"
    assert resp2["errorCode"] == "CONCURRENCY_CONFLICT"


@pytest.mark.asyncio
async def test_handle_user_mutation(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    msg = {
        "type": "user_mutate",
        "projectId": "proj-user-mut",
        "devices": [{"id": "manual-dev-1", "x": 100, "y": 150}],
    }
    await orchestration_service.handle_user_mutation(mock_ws, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "user_mutation_committed"
    assert resp["revision"] == 2
    assert len(resp["devices"]) == 1


@pytest.mark.asyncio
async def test_handle_agent_message_dispatch(
    mock_ws: MockWebSocket,
    test_principal: AuthenticatedPrincipal,
) -> None:
    # Test ping
    await _handle_ping_message(mock_ws)
    assert len(mock_ws.sent_messages) == 1
    assert mock_ws.sent_messages[0]["type"] == "pong"

    # Test response future resolution
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[Any] = loop.create_future()
    agent_response_futures["cmd-resp-test"] = fut

    await _handle_response_message({"id": "cmd-resp-test", "payload": {"status": "ok"}})
    assert fut.done()
    assert fut.result() == {"status": "ok"}


def test_database_sqlite_methods(tmp_path: Path) -> None:
    """Test Database helper methods and schema initialization."""
    db_file = tmp_path / "direct_db.db"
    db = Database(db_path=str(db_file))
    with db._transaction() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    # Test Database._row_to_project branch coverage
    # 1. Dict with explicit revision
    d1 = Database._row_to_project(
        {"id": "p1", "name": "n1", "description": "d1", "author": "a1", "created_at": "c1", "updated_at": "u1", "status": "active", "revision": 7}
    )
    assert d1["revision"] == 7

    # 2. Dict without revision key
    d2 = Database._row_to_project(
        {"id": "p2", "name": "n2", "description": "d2", "author": "a2", "created_at": "c2", "updated_at": "u2", "status": "active"},
        revision=3,
    )
    assert d2["revision"] == 3

    # 3. Custom class with __getitem__ raising KeyError
    class RowWithKeyError:
        def __getitem__(self, item):
            if item == "revision":
                raise KeyError("revision")
            return f"val_{item}"

    d3 = Database._row_to_project(RowWithKeyError(), revision=4)
    assert d3["revision"] == 4

    # 4. Custom class with __getitem__ raising TypeError
    class RowWithTypeError:
        def __getitem__(self, item):
            if item == "revision":
                raise TypeError("bad type")
            return f"val_{item}"

    d4 = Database._row_to_project(RowWithTypeError(), revision=9)
    assert d4["revision"] == 9

    # 5. Dict with revision=None
    d5 = Database._row_to_project(
        {"id": "p5", "name": "n5", "description": "d5", "author": "a5", "created_at": "c5", "updated_at": "u5", "status": "active", "revision": None}
    )
    assert d5["revision"] == 1

    # 6. Object without __getitem__
    class ObjectWithoutGetItem:
        id = "p6"
        name = "n6"
        description = "d6"
        author = "a6"
        created_at = "c6"
        updated_at = "u6"
        status = "active"

        def __getitem__(self, item):
            return getattr(self, item)

    d6 = Database._row_to_project(ObjectWithoutGetItem(), revision=2)
    assert d6["revision"] == 2


def test_validate_agent_nonce_valid_and_duplicate() -> None:
    """Test frame nonce validation and replay prevention."""
    from backend.routers.agent_ws import _validate_agent_nonce

    # No nonce provided (optional)
    assert _validate_agent_nonce({}) is True

    # Valid fresh nonce
    msg1 = {"nonce": "nonce-fresh-001"}
    assert _validate_agent_nonce(msg1) is True

    # Duplicate replay nonce must fail
    assert _validate_agent_nonce(msg1) is False


@pytest.mark.asyncio
async def test_handle_agent_message_full_dispatch(
    mock_ws: MockWebSocket,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """Test _handle_agent_message dispatching for all supported message types."""
    from backend.routers.agent_ws import _handle_agent_message, _seen_agent_nonces

    # Pre-populate a nonce to simulate replay attack
    _seen_agent_nonces.add("nonce-replayed")
    await _handle_agent_message(mock_ws, {"type": "ping", "nonce": "nonce-replayed"})
    assert len(mock_ws.sent_messages) == 0

    # Test valid ping message
    await _handle_agent_message(mock_ws, {"type": "ping", "nonce": "nonce-ping-01"})
    assert len(mock_ws.sent_messages) == 1
    assert mock_ws.sent_messages[0]["type"] == "pong"

    # Test intent_submit alias
    mock_ws.sent_messages.clear()
    msg_intent = {
        "type": "intent_submit",
        "nonce": "nonce-intent-01",
        "projectId": "proj-dispatch",
        "roomBounds": {"width_m": 8.0, "length_m": 10.0, "ceiling_height_m": 3.0},
    }
    await _handle_agent_message(mock_ws, msg_intent, test_principal)
    assert len(mock_ws.sent_messages) == 1
    assert mock_ws.sent_messages[0]["type"] == "ai_preview"


@pytest.mark.asyncio
async def test_cleanup_agent_with_pending_futures(
    mock_ws: MockWebSocket,
) -> None:
    """Test _cleanup_agent cleans up active registries and fails pending futures."""
    from backend.routers.agent_ws import (
        _agent_pending_commands,
        _cleanup_agent,
        active_agents,
        agent_response_futures,
    )

    ws_id = str(id(mock_ws))
    cmd_id = "cmd-pending-01"
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[Any] = loop.create_future()
    agent_response_futures[cmd_id] = fut
    _agent_pending_commands[ws_id] = {cmd_id}
    active_agents["autocad"] = [mock_ws]

    _cleanup_agent(mock_ws, "autocad")

    assert fut.done()
    with pytest.raises(ConnectionError):
        fut.result()
    assert mock_ws not in active_agents.get("autocad", [])


@pytest.mark.asyncio
async def test_handle_electrical_intent_success(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="elec-eng-01",
        email="elec@bazspark.io",
        role="engineer",
        scopes=["electrical:read", "electrical:write"],
        is_authenticated=True,
    )
    msg = {
        "type": "ai_electrical_intent",
        "projectId": "proj-ws-elec-1",
        "circuit_id": "nac-01",
        "current_a": 1.2,
        "one_way_length_m": 25.0,
        "awg": "14",
        "nominal_voltage": 24.0,
        "correlationId": "corr-elec-1",
    }
    await orchestration_service.handle_electrical_intent(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_electrical_preview"
    assert resp["projectId"] == "proj-ws-elec-1"
    assert resp["circuitId"] == "nac-01"
    assert resp["isCompliant"] is True
    assert resp["voltageDropV"] > 0
    assert resp["tokenTelemetry"]["measured_tokens"] <= 1500


@pytest.mark.asyncio
async def test_handle_electrical_intent_no_scope(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="viewer-01",
        email="viewer@bazspark.io",
        role="viewer",
        scopes=["spatial:read"],  # Lacks electrical scopes
        is_authenticated=True,
    )
    msg = {
        "type": "ai_electrical_intent",
        "projectId": "proj-ws-elec-2",
        "circuit_id": "nac-02",
        "current_a": 1.2,
        "one_way_length_m": 25.0,
        "awg": "14",
    }
    await orchestration_service.handle_electrical_intent(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_error"
    assert resp["errorCode"] == "NO_CAPABILITY_AVAILABLE"


@pytest.mark.asyncio
async def test_handle_electrical_approval_commit(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="elec-eng-02",
        email="elec2@bazspark.io",
        role="engineer",
        scopes=["electrical:read", "electrical:write"],
        is_authenticated=True,
    )
    msg = {
        "type": "ai_approve",
        "commandId": "cmd-elec-commit-01",
        "projectId": "proj-ws-elec-commit",
        "expectedRevision": 1,
        "capabilityId": "electrical.calculate_voltage_drop",
        "payload": {
            "circuit_id": "nac-commit-01",
            "current_a": 1.5,
            "one_way_length_m": 30.0,
            "awg": "14",
            "nominal_voltage": 24.0,
        },
    }
    await orchestration_service.handle_approval(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_committed"
    assert resp["projectId"] == "proj-ws-elec-commit"
    assert resp["revision"] == 2
    assert resp["circuit"] is not None
    assert resp["circuit"]["circuit_id"] == "nac-commit-01"
    assert resp["event"]["eventType"] == "VOLTAGE_DROP_CALCULATED"


@pytest.mark.asyncio
async def test_handle_hydraulic_intent_success(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="hyd-eng-01",
        email="hyd1@bazspark.io",
        role="engineer",
        scopes=["hydraulics:read", "hydraulics:write"],
        is_authenticated=True,
    )
    msg = {
        "type": "ai_hydraulic_intent",
        "projectId": "proj-ws-hyd-1",
        "pipeSegmentId": "pipe-01",
        "lengthM": 20.0,
        "diameterMm": 50.0,
        "flowLMin": 300.0,
        "fluidType": "water",
    }
    await orchestration_service.handle_hydraulic_intent(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_hydraulic_preview"
    assert resp["pipeSegmentId"] == "pipe-01"
    assert resp["flowVelocityMS"] > 0.0
    assert resp["headLossM"] > 0.0
    assert resp["tokenTelemetry"]["measured_tokens"] <= 1500


@pytest.mark.asyncio
async def test_handle_hydraulic_intent_no_scope(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="viewer-02",
        email="viewer2@bazspark.io",
        role="viewer",
        scopes=["spatial:read"],  # Lacks hydraulics scopes
        is_authenticated=True,
    )
    msg = {
        "type": "ai_hydraulic_intent",
        "projectId": "proj-ws-hyd-2",
        "pipeSegmentId": "pipe-02",
        "lengthM": 15.0,
        "diameterMm": 50.0,
        "flowLMin": 250.0,
    }
    await orchestration_service.handle_hydraulic_intent(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_error"
    assert resp["errorCode"] == "NO_CAPABILITY_AVAILABLE"


@pytest.mark.asyncio
async def test_handle_hydraulic_approval_commit(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="hyd-eng-02",
        email="hyd2@bazspark.io",
        role="engineer",
        scopes=["hydraulics:read", "hydraulics:write"],
        is_authenticated=True,
    )
    msg = {
        "type": "ai_approve",
        "commandId": "cmd-hyd-commit-01",
        "projectId": "proj-ws-hyd-commit",
        "expectedRevision": 1,
        "capabilityId": "hydraulics.solve_darcy_weisbach",
        "payload": {
            "pipe_segment_id": "pipe-commit-01",
            "length_m": 25.0,
            "diameter_mm": 65.0,
            "flow_l_min": 450.0,
            "fluid_type": "water",
        },
    }
    await orchestration_service.handle_approval(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_committed"
    assert resp["projectId"] == "proj-ws-hyd-commit"
    assert resp["revision"] == 2
    assert resp["hydraulic"] is not None
    assert resp["hydraulic"]["pipe_segment_id"] == "pipe-commit-01"
    assert resp["event"]["eventType"] == "HYDRAULIC_CALCULATION_SOLVED"


@pytest.mark.asyncio
async def test_handle_battery_intent_success(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="elec-eng-bat",
        email="elec-bat@bazspark.io",
        role="engineer",
        scopes=["electrical:read", "electrical:write"],
        is_authenticated=True,
    )
    msg = {
        "type": "ai_battery_intent",
        "projectId": "proj-ws-bat-1",
        "panelId": "facp-ws-01",
        "batterySpec": {
            "standby_load_amps": 0.8,
            "alarm_load_amps": 3.0,
            "standby_hours": 24.0,
            "alarm_hours": 5 / 60,
            "min_temperature_c": 18.0,
            "installed_ah": 55.0,
        },
    }
    await orchestration_service.handle_battery_intent(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_battery_preview"
    assert resp["panelId"] == "facp-ws-01"
    assert resp["requiredAh"] > 0.0
    assert resp["baseCapacityAh"] > 19.0
    assert resp["tokenTelemetry"]["measured_tokens"] <= 1500


@pytest.mark.asyncio
async def test_handle_battery_intent_no_scope(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="viewer-bat-02",
        email="viewer-bat@bazspark.io",
        role="viewer",
        scopes=["spatial:read"],  # Lacks electrical scopes
        is_authenticated=True,
    )
    msg = {
        "type": "ai_battery_intent",
        "projectId": "proj-ws-bat-2",
        "panelId": "facp-ws-02",
        "batterySpec": {
            "standby_load_amps": 0.5,
            "alarm_load_amps": 2.0,
        },
    }
    await orchestration_service.handle_battery_intent(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_error"
    assert resp["errorCode"] == "NO_CAPABILITY_AVAILABLE"


@pytest.mark.asyncio
async def test_handle_battery_approval_commit(
    orchestration_service: AIOrchestrationService,
    mock_ws: MockWebSocket,
) -> None:
    principal = AuthenticatedPrincipal(
        user_id="elec-eng-bat-03",
        email="elec-bat3@bazspark.io",
        role="engineer",
        scopes=["electrical:read", "electrical:write"],
        is_authenticated=True,
    )
    msg = {
        "type": "ai_approve",
        "commandId": "cmd-bat-commit-01",
        "projectId": "proj-ws-bat-commit",
        "expectedRevision": 1,
        "capabilityId": "electrical.calculate_battery",
        "payload": {
            "panel_id": "facp-ws-commit-01",
            "standby_load_amps": 0.9,
            "alarm_load_amps": 3.2,
            "standby_hours": 24.0,
            "alarm_hours": 5 / 60,
            "installed_ah": 55.0,
        },
    }
    await orchestration_service.handle_approval(mock_ws, principal, msg)

    assert len(mock_ws.sent_messages) == 1
    resp = mock_ws.sent_messages[0]
    assert resp["type"] == "ai_committed"
    assert resp["projectId"] == "proj-ws-bat-commit"
    assert resp["revision"] == 2
    assert resp["battery"] is not None
    assert resp["battery"]["panel_id"] == "facp-ws-commit-01"
    assert resp["event"]["eventType"] == "BATTERY_CALCULATION_SOLVED"
