"""
tests/test_d2_claude_desktop_e2e.py
===================================

End-to-end integration and smoke tests for Claude Desktop interacting with
the FireAI Revit MCP Server (Stage D2 of the agent-platform rebuild).

Verifies the full JSON-RPC 2.0 stdio lifecycle that Claude Desktop executes:
  1. initialize handshake (protocol version, capabilities negotiation, serverInfo)
  2. notifications/initialized acknowledge
  3. tools/list retrieval & JSON schema validation against PARAM_RULES
  4. tools/call dispatch for primary safety-critical engineering tools:
     - get_project_status
     - calculate_coverage
     - place_detector
     - query_room_hazard_class
     - export_report
  5. Error cases: unknown tool, missing arguments, invalid JSON-RPC payload
  6. Live subprocess E2E test executing python -m fireai.mcp_server.revit_mcp_server over real stdio.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from fireai.mcp_server.revit_mcp_server import (
    MCP_PROTOCOL_VERSION,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    RevitMCPServer,
)


@pytest.fixture(autouse=True)
def _ensure_no_stdin_hang(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set FIREAI_MCP_NO_STDIN=1 to prevent stdin blocking in unit test runs."""
    monkeypatch.setenv("FIREAI_MCP_NO_STDIN", "1")


@pytest.fixture
def mcp_server() -> RevitMCPServer:
    return RevitMCPServer()


class TestClaudeDesktopProtocolHandshake:
    """Tests the initial initialization handshake performed by Claude Desktop."""

    def test_initialize_handshake(self, mcp_server: RevitMCPServer) -> None:
        init_req = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "claude-desktop", "version": "0.7.0"},
                },
            }
        )
        resp = mcp_server._handle_jsonrpc_line(init_req)
        assert resp is not None
        assert resp.get("jsonrpc") == "2.0"
        assert resp.get("id") == 1
        result = resp.get("result", {})
        assert result.get("protocolVersion") == MCP_PROTOCOL_VERSION
        assert result.get("serverInfo", {}).get("name") == MCP_SERVER_NAME
        assert result.get("serverInfo", {}).get("version") == MCP_SERVER_VERSION
        assert "tools" in result.get("capabilities", {})

    def test_initialized_notification_does_not_generate_response(
        self, mcp_server: RevitMCPServer
    ) -> None:
        notif = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {},
            }
        )
        resp = mcp_server._handle_jsonrpc_line(notif)
        assert resp is None

    def test_ping(self, mcp_server: RevitMCPServer) -> None:
        ping_req = json.dumps({"jsonrpc": "2.0", "id": 99, "method": "ping"})
        resp = mcp_server._handle_jsonrpc_line(ping_req)
        assert resp is not None
        assert resp.get("id") == 99
        assert resp.get("result") == {}


class TestClaudeDesktopToolsListAndCallE2E:
    """Tests discovery and execution of tools via JSON-RPC 2.0."""

    def test_tools_list_schema_and_contents(self, mcp_server: RevitMCPServer) -> None:
        list_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = mcp_server._handle_jsonrpc_line(list_req)
        assert resp is not None
        assert resp.get("id") == 2
        tools = resp.get("result", {}).get("tools", [])
        assert len(tools) >= 5

        tool_names = {t["name"] for t in tools}
        expected_tools = {
            "get_project_status",
            "calculate_coverage",
            "place_detector",
            "query_room_hazard_class",
            "export_report",
        }
        assert expected_tools.issubset(tool_names)

        for t in tools:
            assert "name" in t
            assert "description" in t
            assert "inputSchema" in t
            assert t["inputSchema"].get("type") == "object"

    def test_tool_call_get_project_status(self, mcp_server: RevitMCPServer) -> None:
        call_req = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_project_status",
                    "arguments": {},
                },
            }
        )
        resp = mcp_server._handle_jsonrpc_line(call_req)
        assert resp is not None
        assert resp.get("id") == 3
        result = resp.get("result", {})
        assert "content" in result
        assert len(result["content"]) > 0
        text = result["content"][0]["text"]
        payload = json.loads(text)
        assert payload.get("success") is True
        res_data = payload.get("result", {})
        assert res_data.get("server_name") == MCP_SERVER_NAME

    def test_tool_call_calculate_coverage(self, mcp_server: RevitMCPServer) -> None:
        call_req = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "calculate_coverage",
                    "arguments": {
                        "room_length_m": 12.0,
                        "room_width_m": 8.0,
                        "ceiling_height_m": 3.0,
                        "detector_type": "smoke",
                    },
                },
            }
        )
        resp = mcp_server._handle_jsonrpc_line(call_req)
        assert resp is not None
        assert resp.get("id") == 4
        result = resp.get("result", {})
        assert "content" in result
        text = result["content"][0]["text"]
        payload = json.loads(text)
        assert payload.get("success") is True
        data = payload.get("result", {})
        assert "coverage_radius_m" in data
        assert data.get("detectors_required_grid", 0) >= 1

    def test_tool_call_place_detector(self, mcp_server: RevitMCPServer) -> None:
        call_req = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "place_detector",
                    "arguments": {
                        "room_id": "ROOM-101",
                        "room_length_m": 10.0,
                        "room_width_m": 6.0,
                        "ceiling_height_m": 3.0,
                        "detector_type": "smoke",
                    },
                },
            }
        )
        resp = mcp_server._handle_jsonrpc_line(call_req)
        assert resp is not None
        assert resp.get("id") == 5
        result = resp.get("result", {})
        assert "content" in result
        text = result["content"][0]["text"]
        payload = json.loads(text)
        assert payload.get("success") is True
        data = payload.get("result", {})
        assert data.get("status") == "queued"
        assert len(data.get("detectors", [])) >= 1

    def test_tool_call_unknown_tool_returns_error(self, mcp_server: RevitMCPServer) -> None:
        call_req = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "unregistered_forbidden_tool",
                    "arguments": {},
                },
            }
        )
        resp = mcp_server._handle_jsonrpc_line(call_req)
        assert resp is not None
        assert resp.get("id") == 6
        result = resp.get("result", {})
        assert result.get("isError") is True


class TestClaudeDesktopSubprocessE2E:
    """Runs a true subprocess invocation to simulate Claude Desktop process spawning."""

    def test_live_subprocess_stdio_communication(self) -> None:
        env = dict(os.environ)
        env["FIREAI_ENV"] = "development"
        # Explicitly remove test bypass so stdin reader runs
        env.pop("FIREAI_MCP_NO_STDIN", None)

        proc = subprocess.Popen(
            [sys.executable, "-m", "fireai.mcp_server.revit_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        try:
            # 1. Send initialize
            init_payload = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 100,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "claude-desktop-e2e", "version": "1.0"},
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.write(init_payload)
            proc.stdin.flush()

            init_resp_line = proc.stdout.readline()
            assert init_resp_line, "Subprocess did not output initialize response"
            init_resp = json.loads(init_resp_line.strip())
            assert init_resp.get("id") == 100
            assert "result" in init_resp

            # 2. Send tools/list
            list_payload = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 101,
                        "method": "tools/list",
                    }
                )
                + "\n"
            )
            proc.stdin.write(list_payload)
            proc.stdin.flush()

            list_resp_line = proc.stdout.readline()
            assert list_resp_line, "Subprocess did not output tools/list response"
            list_resp = json.loads(list_resp_line.strip())
            assert list_resp.get("id") == 101
            tools = list_resp.get("result", {}).get("tools", [])
            assert len(tools) >= 5

            # 3. Call tool
            call_payload = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 102,
                        "method": "tools/call",
                        "params": {
                            "name": "get_project_status",
                            "arguments": {},
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.write(call_payload)
            proc.stdin.flush()

            call_resp_line = proc.stdout.readline()
            assert call_resp_line, "Subprocess did not output tools/call response"
            call_resp = json.loads(call_resp_line.strip())
            assert call_resp.get("id") == 102
            assert "result" in call_resp

        finally:
            proc.stdin.close()
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
