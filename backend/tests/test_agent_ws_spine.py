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

