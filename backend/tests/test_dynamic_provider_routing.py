"""
backend/tests/test_dynamic_provider_routing.py — Phase 3.1 Live Agent Routing & Ping Gates

Tests:
1. SSRF URL validation and host allow-list enforcement.
2. Zero-token ping probes with 5.0-second hard timeout cap.
3. Zero API key leakage in logs or responses.
4. WebSocket dynamic providerConfig envelope routing.
5. Live token telemetry validation.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

import httpx
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.command_bus import AuthenticatedPrincipal
from backend.routers.agent_ws import (
    AIOrchestrationService,
)
from backend.services.llm_service import (
    close_llm_service,
    get_llm_service,
    ping_provider,
    validate_provider_url,
)

# ---------------------------------------------------------------------------
# 1. SSRF & URL Validation Tests
# ---------------------------------------------------------------------------

class TestSSRFAndURLValidation:
    """Test SSRF protection rules for local and cloud providers."""

    def test_ollama_valid_local_endpoints(self):
        valid_urls = [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://127.0.0.1:8080",
            "http://[::1]:11434",
            None,  # defaults to http://localhost:11434
        ]
        for url in valid_urls:
            is_valid, _resolved, err = validate_provider_url("ollama", url)
            assert is_valid is True, f"Failed for {url}: {err}"
            assert err is None

    def test_ollama_ssrf_blocked_remote_endpoints(self):
        blocked_urls = [
            "http://192.168.1.100:11434",
            "http://10.0.0.1:11434",
            "http://169.254.169.254/latest/meta-data",
            "https://attacker.com/ollama",
            "ftp://localhost:11434",
        ]
        for url in blocked_urls:
            is_valid, _resolved, err = validate_provider_url("ollama", url)
            assert is_valid is False
            assert "SSRF_BLOCKED" in (err or "") or "Invalid scheme" in (err or "")

    def test_anthropic_valid_and_blocked(self):
        # Valid official HTTPS
        is_valid, _resolved, err = validate_provider_url("anthropic", "https://api.anthropic.com")
        assert is_valid is True
        assert err is None

        # Blocked: plain HTTP
        is_valid, _, err = validate_provider_url("anthropic", "http://api.anthropic.com")
        assert is_valid is False
        assert "HTTPS is required" in (err or "")

        # Blocked: unauthorized domain
        is_valid, _, err = validate_provider_url("anthropic", "https://evil-anthropic-proxy.com")
        assert is_valid is False
        assert "SSRF_BLOCKED" in (err or "")

    def test_gemini_valid_and_blocked(self):
        is_valid, _resolved, err = validate_provider_url("gemini", "https://generativelanguage.googleapis.com")
        assert is_valid is True
        assert err is None

        is_valid, _, err = validate_provider_url("gemini", "http://generativelanguage.googleapis.com")
        assert is_valid is False
        assert "HTTPS is required" in (err or "")

        is_valid, _, err = validate_provider_url("gemini", "https://fake-gemini.com")
        assert is_valid is False
        assert "SSRF_BLOCKED" in (err or "")

    def test_openai_valid_and_blocked(self):
        is_valid, _resolved, err = validate_provider_url("openai", "https://api.openai.com/v1")
        assert is_valid is True

        is_valid, _resolved, err = validate_provider_url("openai", "https://zenmux.ai/api/v1")
        assert is_valid is True

        is_valid, _, err = validate_provider_url("openai", "https://unauthorized-proxy.internal.corp")
        assert is_valid is False
        assert "SSRF_BLOCKED" in (err or "")


# ---------------------------------------------------------------------------
# 2. Ping Probes & Zero Secret Leakage Tests
# ---------------------------------------------------------------------------

class TestPingProbesAndSecretSafety:
    """Test live zero-token probe execution and secret redaction."""

    @pytest.mark.asyncio
    async def test_ollama_ping_success(self):
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json={"models": []})
            success, _latency, err = await ping_provider("ollama", "http://localhost:11434")
            assert success is True
            assert err is None

    @pytest.mark.asyncio
    async def test_ollama_ping_connection_refused(self):
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            success, _latency, err = await ping_provider("ollama", "http://localhost:11434")
            assert success is False
            assert "Connection refused" in (err or "")

    @pytest.mark.asyncio
    async def test_probe_timeout_cap_enforced(self):
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timed out")):
            success, _latency, err = await ping_provider("anthropic", "https://api.anthropic.com")
            assert success is False
            assert "timed out" in (err or "").lower()

    @pytest.mark.asyncio
    async def test_zero_api_key_leakage_in_error_message(self):
        secret_key = "sk-ant-api03-SECRET-NEVER-LEAK-THIS-12345"
        with patch(
            "httpx.AsyncClient.get",
            side_effect=Exception(f"Failed with key {secret_key} during SSL negotiation"),
        ):
            success, _latency, err = await ping_provider(
                "anthropic", "https://api.anthropic.com", api_key=secret_key
            )
            assert success is False
            assert secret_key not in (err or "")
            assert "[REDACTED]" in (err or "")

    @pytest.mark.asyncio
    async def test_anthropic_ping_success_and_auth_fail(self):
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json={"data": []})
            success, _latency, err = await ping_provider("anthropic", "https://api.anthropic.com", api_key="valid")
            assert success is True
            assert err is None

            mock_get.return_value = httpx.Response(401, json={"error": "unauthorized"})
            success, _latency, err = await ping_provider("anthropic", "https://api.anthropic.com", api_key="invalid")
            assert success is False
            assert "Invalid Anthropic API key" in (err or "")

            mock_get.return_value = httpx.Response(500, text="Internal Error")
            success, _latency, err = await ping_provider("anthropic", "https://api.anthropic.com")
            assert success is False
            assert "HTTP 500" in (err or "")

    @pytest.mark.asyncio
    async def test_gemini_ping_success_and_auth_fail(self):
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json={"models": []})
            success, _latency, err = await ping_provider("gemini", "https://generativelanguage.googleapis.com", api_key="valid")
            assert success is True
            assert err is None

            mock_get.return_value = httpx.Response(400, json={"error": "bad request"})
            success, _latency, err = await ping_provider("gemini", "https://generativelanguage.googleapis.com", api_key="invalid")
            assert success is False
            assert "Invalid Gemini API key" in (err or "")

            mock_get.return_value = httpx.Response(502, text="Bad Gateway")
            success, _latency, err = await ping_provider("gemini", "https://generativelanguage.googleapis.com")
            assert success is False
            assert "HTTP 502" in (err or "")

    @pytest.mark.asyncio
    async def test_openai_ping_success_and_auth_fail(self):
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json={"data": []})
            success, _latency, err = await ping_provider("openai", "https://api.openai.com/v1", api_key="valid")
            assert success is True
            assert err is None

            mock_get.return_value = httpx.Response(401, json={"error": "invalid_api_key"})
            success, _latency, err = await ping_provider("openai", "https://api.openai.com/v1", api_key="invalid")
            assert success is False
            assert "Invalid OpenAI API key" in (err or "")

            mock_get.return_value = httpx.Response(503, text="Service Unavailable")
            success, _latency, err = await ping_provider("openai", "https://api.openai.com/v1")
            assert success is False
            assert "HTTP 503" in (err or "")

    @pytest.mark.asyncio
    async def test_unsupported_provider(self):
        success, _latency, err = await ping_provider("unknown_prov", "https://foo.com")
        assert success is False
        assert "Unsupported provider" in (err or "")


# ---------------------------------------------------------------------------
# 3. FastAPI HTTP Endpoint Tests
# ---------------------------------------------------------------------------

class TestPingProviderEndpoint:
    """Test POST /api/v1/agent/ping-provider endpoint."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_endpoint_ping_ollama_success(self, client):
        with patch("backend.routers.agent_ws.ping_provider", return_value=(True, 15.4, None)):
            res = client.post(
                "/api/v1/agent/ping-provider",
                json={
                    "provider": "ollama",
                    "baseUrl": "http://localhost:11434",
                    "modelName": "qwen2.5-coder:7b",
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["latencyMs"] == 15.4
            assert data["error"] is None

    def test_endpoint_ping_ssrf_blocked(self, client):
        res = client.post(
            "/api/v1/agent/ping-provider",
            json={
                "provider": "ollama",
                "baseUrl": "http://192.168.1.50:11434",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert "SSRF_BLOCKED" in (data["error"] or "")


# ---------------------------------------------------------------------------
# 4. WebSocket Dynamic Provider Routing & Telemetry Tests
# ---------------------------------------------------------------------------

class TestWebSocketDynamicRoutingAndTelemetry:
    """Test dynamic routing envelope extraction and live token telemetry."""

    @pytest.fixture
    def engineer_principal(self):
        return AuthenticatedPrincipal(
            user_id="eng-phase31-01",
            email="eng@bazspark.com",
            role="ENGINEER",
            scopes=["spatial:read", "spatial:write", "electrical:read", "electrical:write", "hydraulics:read", "hydraulics:write"],
            is_authenticated=True,
        )

    @pytest.mark.asyncio
    async def test_dynamic_provider_routing_envelope_and_telemetry(self, engineer_principal):
        orchestrator = AIOrchestrationService()

        # Mock websocket to capture outgoing preview frames
        sent_messages = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent_messages.append(data)

        ws = MockWebSocket()

        # Send composite intent with dynamic provider configuration
        msg = {
            "type": "composite_intent",
            "projectId": "proj-dyn-route-01",
            "providerConfig": {
                "provider": "ollama",
                "baseUrl": "http://localhost:11434",
                "modelName": "qwen2.5-coder:7b",
                "temperature": 0.0,
            },
            "governance": {
                "autoRollbackOnPhysicsWarning": False,
            },
            "compositeSpec": {
                "room_bounds": {"width_m": 8.0, "length_m": 10.0, "ceiling_height_m": 3.0},
                "circuit": {"circuit_id": "nac-dyn-01", "current_a": 1.0, "one_way_length_m": 20.0, "awg": "14"},
                "battery": {"panel_id": "facp-dyn-01", "standby_load_amps": 0.5, "installed_ah": 50.0},
            },
        }

        await orchestrator.handle_composite_intent(cast(WebSocket, ws), engineer_principal, msg)

        progress_frames = [m for m in sent_messages if m.get("type") == "ai_progress_frame"]
        previews = [m for m in sent_messages if m.get("type") == "ai_composite_preview"]
        assert len(previews) == 1
        assert len(progress_frames) == 3
        preview = previews[0]

        # Verify real token telemetry
        telemetry = preview.get("tokenTelemetry", {})
        assert telemetry.get("provider") == "ollama"
        assert telemetry.get("model") == "qwen2.5-coder:7b"
        assert telemetry.get("temperature") == 0.0
        assert telemetry.get("prompt_tokens", 0) > 0
        assert telemetry.get("completion_tokens", 0) > 0
        assert telemetry.get("total_tokens", 0) == telemetry["prompt_tokens"] + telemetry["completion_tokens"]
        assert telemetry.get("token_budget", 1500) <= 1500

    @pytest.mark.asyncio
    async def test_dynamic_provider_routing_auto_rollback_on_warning(self, engineer_principal):
        orchestrator = AIOrchestrationService()
        sent_messages = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent_messages.append(data)

        ws = MockWebSocket()

        # Send composite intent with autoRollbackOnPhysicsWarning: True
        msg = {
            "type": "composite_intent",
            "projectId": "proj-dyn-route-02",
            "providerConfig": {
                "provider": "anthropic",
                "modelName": "claude-sonnet-4-5",
            },
            "governance": {
                "autoRollbackOnPhysicsWarning": True,
            },
            "compositeSpec": {
                "room_bounds": {"width_m": 8.0, "length_m": 10.0, "ceiling_height_m": 3.0},
                "circuit": {"circuit_id": "nac-dyn-02", "current_a": 1.0, "one_way_length_m": 20.0, "awg": "14"},
                "battery": {"panel_id": "facp-dyn-02", "standby_load_amps": 0.5, "installed_ah": 50.0},
            },
        }

        await orchestrator.handle_composite_intent(cast(WebSocket, ws), engineer_principal, msg)

        errors = [m for m in sent_messages if m.get("type") == "ai_error"]
        assert len(errors) == 1
        err_res = errors[0]
        assert err_res["errorCode"] == "PHYSICS_WARNING_ROLLBACK"

    @pytest.mark.asyncio
    async def test_dynamic_provider_routing_approval_flow(self, engineer_principal):
        orchestrator = AIOrchestrationService()
        sent_messages = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent_messages.append(data)

        ws = MockWebSocket()

        # 1. Invalid payload missing dag
        await orchestrator.handle_composite_approval(cast(WebSocket, ws), engineer_principal, {"type": "composite_approval"})
        assert any(m.get("errorCode") == "INVALID_WORKFLOW_PAYLOAD" for m in sent_messages)

        # 2. Valid dag approval
        msg = {
            "type": "composite_approval",
            "projectId": "proj-dyn-route-03",
            "expectedRevision": 1,
            "dag": {
                "nodes": [
                    {
                        "node_id": "step_1",
                        "capability_id": "spatial.place_devices",
                        "payload_template": {"room_id": "r1", "width_m": 8.0, "length_m": 10.0, "ceiling_height_m": 3.0},
                        "dependencies": [],
                    }
                ]
            },
        }
        await orchestrator.handle_composite_approval(cast(WebSocket, ws), engineer_principal, msg)
        assert any(m.get("type") == "ai_progress_frame" for m in sent_messages)

    @pytest.mark.asyncio
    async def test_handle_room_intent(self, engineer_principal):
        orchestrator = AIOrchestrationService()
        sent = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent.append(data)

        ws = MockWebSocket()
        msg = {
            "type": "room_intent",
            "projectId": "proj-room-01",
            "roomId": "hallway-01",
            "roomBounds": {"width_m": 6.0, "length_m": 12.0, "ceiling_height_m": 3.0},
            "detectorType": "smoke",
            "providerConfig": {"provider": "ollama", "modelName": "qwen2.5-coder:7b"},
        }
        await orchestrator.handle_intent(cast(WebSocket, ws), engineer_principal, msg)
        assert len(sent) == 1
        assert sent[0].get("type") == "ai_preview"
        assert sent[0].get("deviceCount", 0) > 0

    @pytest.mark.asyncio
    async def test_handle_electrical_intent(self, engineer_principal):
        orchestrator = AIOrchestrationService()
        sent = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent.append(data)

        ws = MockWebSocket()
        msg = {
            "type": "electrical_intent",
            "projectId": "proj-elec-01",
            "circuitId": "nac-01",
            "current_a": 1.2,
            "one_way_length_m": 25.0,
            "awg": "14",
            "providerConfig": {"provider": "ollama", "modelName": "qwen2.5-coder:7b"},
        }
        await orchestrator.handle_electrical_intent(cast(WebSocket, ws), engineer_principal, msg)
        assert len(sent) == 1
        assert sent[0].get("type") == "ai_electrical_preview"
        assert "voltageDropV" in sent[0]

    @pytest.mark.asyncio
    async def test_handle_hydraulic_intent(self, engineer_principal):
        orchestrator = AIOrchestrationService()
        sent = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent.append(data)

        ws = MockWebSocket()
        msg = {
            "type": "hydraulic_intent",
            "projectId": "proj-hyd-01",
            "pipeSegmentId": "pipe-01",
            "lengthM": 20.0,
            "diameterMm": 65.0,
            "flowLMin": 300.0,
            "fluidType": "water",
            "providerConfig": {"provider": "ollama", "modelName": "qwen2.5-coder:7b"},
        }
        await orchestrator.handle_hydraulic_intent(cast(WebSocket, ws), engineer_principal, msg)
        assert len(sent) == 1
        assert sent[0].get("type") == "ai_hydraulic_preview"
        assert "frictionFactor" in sent[0]

    @pytest.mark.asyncio
    async def test_handle_battery_intent(self, engineer_principal):
        orchestrator = AIOrchestrationService()
        sent = []

        class MockWebSocket:
            async def send_json(self, data: dict):
                sent.append(data)

        ws = MockWebSocket()
        msg = {
            "type": "battery_intent",
            "projectId": "proj-bat-01",
            "panelId": "facp-01",
            "batterySpec": {
                "standby_load_amps": 0.5,
                "alarm_load_amps": 2.0,
                "standby_hours": 24.0,
                "alarm_hours": 0.0833,
                "installed_ah": 50.0,
            },
            "providerConfig": {"provider": "ollama", "modelName": "qwen2.5-coder:7b"},
        }
        await orchestrator.handle_battery_intent(cast(WebSocket, ws), engineer_principal, msg)
        assert len(sent) == 1
        assert sent[0].get("type") == "ai_battery_preview"
        assert "requiredAh" in sent[0]

    @pytest.mark.asyncio
    async def test_llm_service_singleton_lifecycle(self):
        svc1 = get_llm_service()
        svc2 = get_llm_service()
        assert svc1 is svc2
        await close_llm_service()
        # Verify the transient-retry policy (moved into adapters in Stage B1).
        import httpx as _httpx

        from backend.services.providers.adapters import is_retryable_exception

        assert is_retryable_exception(_httpx.ConnectError("x"))
        assert is_retryable_exception(_httpx.TimeoutException("x"))
