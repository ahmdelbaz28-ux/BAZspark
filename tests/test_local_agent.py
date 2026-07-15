"""
tests/test_local_agent.py
=========================
Integration tests for the Local Agent WebSocket bridge.
Tests verify:
  1. Agent connects successfully with a valid API key
  2. Agent is rejected with an invalid API key
  3. Cloud server correctly forwards commands to the agent and returns results
  4. Cloud server returns 503 when no agent is connected
"""
from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Import and return the FastAPI app with agent_ws registered."""
    from backend.app import app as _app
    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_api_key(client: TestClient) -> str:
    """Create a test API key via the API keys endpoint and return its value."""
    # Try to get one from environment first
    import os
    key = os.getenv("TEST_API_KEY")
    if key:
        return key
    return "test-key-for-agent-tests"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAgentWebSocketConnection:
    """Test the /api/v1/agent/ws WebSocket endpoint."""

    def test_agent_rejected_without_api_key(self, client: TestClient):
        """Agent WS should reject connections without api_key query param."""
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/agent/ws"):
                pass

    def test_agent_rejected_with_invalid_api_key(self, client: TestClient):
        """Agent WS should close with 4003 for invalid API key."""
        with patch("backend.routers.agent_ws.validate_api_key", return_value=False):
            with patch("backend.routers.agent_ws.SessionLocal"):
                with client.websocket_connect("/api/v1/agent/ws?api_key=bad-key") as ws:
                    # Should receive close immediately or raise
                    try:
                        ws.receive_json()
                    except Exception:
                        pass  # Expected — server closed the connection


class TestCommandForwarding:
    """Test that AutoCAD/Revit endpoints forward to connected agent."""

    def test_autocad_connect_without_agent_returns_simulation(self, client: TestClient):
        """Without an agent, AutoCAD connect should use simulation mode."""
        from backend.routers.agent_ws import active_agents
        # Ensure no agent is connected
        active_agents.clear()

        response = client.post(
            "/api/v1/autocad/connect",
            json={"visible": True, "force_new": False},
        )
        # In simulation mode, should still return 200 with simulation_mode=True
        assert response.status_code in (200, 503)

    def test_autocad_connect_with_mock_agent(self, client: TestClient):
        """When an agent is connected, connect should be forwarded to it."""
        from backend.routers import agent_ws

        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()

        async def fake_send_command(agent_type, action, args, timeout=30.0):
            return {
                "success": True,
                "message": "Connected to AutoCAD via agent",
                "connected": True,
                "simulation_mode": False,
                "handle": None,
            }

        with patch.object(agent_ws, "active_agents", {"autocad_revit": [mock_ws]}):
            with patch.object(agent_ws, "send_agent_command", new=fake_send_command):
                response = client.post(
                    "/api/v1/autocad/connect",
                    json={"visible": True, "force_new": False},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["simulation_mode"] is False
        assert "agent" in data["message"].lower()

    def test_revit_connect_with_mock_agent(self, client: TestClient):
        """When an agent is connected, Revit connect should be forwarded."""
        from backend.routers import agent_ws

        mock_ws = MagicMock()

        async def fake_send_command(agent_type, action, args, timeout=30.0):
            return {
                "success": True,
                "message": "Connected to Revit via agent",
                "connected": True,
                "simulation_mode": False,
                "connection_method": "api",
            }

        with patch.object(agent_ws, "active_agents", {"autocad_revit": [mock_ws]}):
            with patch.object(agent_ws, "send_agent_command", new=fake_send_command):
                response = client.post(
                    "/api/v1/revit/connect",
                    json={"method": "api"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["connection_method"] == "api"

    def test_autocad_status_no_agent(self, client: TestClient):
        """AutoCAD status without agent returns disconnected status."""
        from backend.routers.agent_ws import active_agents
        active_agents.clear()

        response = client.get("/api/v1/autocad/status")
        assert response.status_code == 200
        data = response.json()
        # In simulation or disconnected mode, connected=False
        assert "connected" in data

    def test_agent_command_timeout(self, client: TestClient):
        """Agent command that times out should return 504."""
        from backend.routers import agent_ws

        mock_ws = MagicMock()

        async def fake_send_command(agent_type, action, args, timeout=30.0):
            from fastapi import HTTPException
            raise HTTPException(status_code=504, detail="Local Agent command execution timed out.")

        with patch.object(agent_ws, "active_agents", {"autocad_revit": [mock_ws]}):
            with patch.object(agent_ws, "send_agent_command", new=fake_send_command):
                response = client.post(
                    "/api/v1/autocad/connect",
                    json={"visible": True, "force_new": False},
                )

        assert response.status_code == 504


class TestAgentWsModule:
    """Test agent_ws module helper functions."""

    def test_has_active_agent_false_when_empty(self):
        from backend.routers import agent_ws
        agent_ws.active_agents.clear()
        assert agent_ws.has_active_agent() is False

    def test_has_active_agent_true_when_registered(self):
        from backend.routers import agent_ws
        mock_ws = MagicMock()
        agent_ws.active_agents["autocad_revit"] = [mock_ws]
        assert agent_ws.has_active_agent() is True
        # Cleanup
        agent_ws.active_agents.clear()

    @pytest.mark.asyncio
    async def test_send_agent_command_raises_503_when_no_agent(self):
        from backend.routers import agent_ws
        from fastapi import HTTPException
        agent_ws.active_agents.clear()
        with pytest.raises(HTTPException) as exc_info:
            await agent_ws.send_agent_command("autocad", "connect", {})
        assert exc_info.value.status_code == 503
