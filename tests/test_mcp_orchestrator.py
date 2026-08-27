"""
tests/test_mcp_orchestrator.py
==============================

Tests for Stage C2: the MCPOrchestrator (backend/services/mcp_client.py).

Tests cover JSON config parsing, McpServerConfig.from_dict, capability
extraction, permission checking, secret scrubbing, the synchronous call_tool
API error paths, and the module-level singleton/reset helpers.

No real MCP servers are spawned — call_tool failure paths are exercised by
configuring orchestrator instances with fake DiscoveredTool entries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.mcp_client import (
    DiscoveredTool,
    MCPOrchestrator,
    McpServerConfig,
    get_mcp_orchestrator,
    reset_mcp_orchestrator,
)
from fireai.agents.tool_selector import ToolSelector
from fireai.core.event_bus import EventBus

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def fake_tool_selector(tmp_path: Path) -> ToolSelector:
    return ToolSelector(db_path=str(tmp_path / "mcp_tools.sqlite3"))


@pytest.fixture
def orchestrator(
    fake_event_bus: EventBus,
    fake_tool_selector: ToolSelector,
) -> MCPOrchestrator:
    """An orchestrator with no servers configured (no background thread started)."""
    return MCPOrchestrator(
        tool_selector=fake_tool_selector,
        event_bus=fake_event_bus,
        servers_config="",  # empty → no servers
    )


# ── _parse_servers ─────────────────────────────────────────────────────────────


class TestParseServers:
    def test_empty_string(self) -> None:
        assert MCPOrchestrator._parse_servers("") == []

    def test_whitespace_only(self) -> None:
        assert MCPOrchestrator._parse_servers("   ") == []

    def test_valid_single_server(self) -> None:
        config = json.dumps(
            [
                {
                    "name": "revit",
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "server"],
                    "env": {"FOO": "bar"},
                }
            ]
        )
        result = MCPOrchestrator._parse_servers(config)
        assert len(result) == 1
        cfg = result[0]
        assert cfg.name == "revit"
        assert cfg.transport == "stdio"
        assert cfg.command == "python"
        assert cfg.args == ["-m", "server"]
        assert cfg.env == {"FOO": "bar"}
        assert cfg.url is None

    def test_multiple_servers(self) -> None:
        config = json.dumps(
            [
                {"name": "srv1", "command": "cmd1"},
                {"name": "srv2", "command": "cmd2"},
            ]
        )
        result = MCPOrchestrator._parse_servers(config)
        assert len(result) == 2
        assert result[0].name == "srv1"
        assert result[1].name == "srv2"

    def test_invalid_json(self) -> None:
        result = MCPOrchestrator._parse_servers("{not valid json")
        assert result == []

    def test_non_array(self) -> None:
        result = MCPOrchestrator._parse_servers('{"name": "foo"}')
        assert result == []

    def test_item_not_object(self) -> None:
        result = MCPOrchestrator._parse_servers('["string_item", 123]')
        assert result == []

    def test_default_values(self) -> None:
        config = json.dumps([{"name": "minimal"}])
        result = MCPOrchestrator._parse_servers(config)
        cfg = result[0]
        assert cfg.transport == "stdio"
        assert cfg.command == ""
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.required_permissions == []

    def test_url_field(self) -> None:
        config = json.dumps(
            [{"name": "sse-srv", "transport": "sse", "url": "http://localhost:8080"}]
        )
        result = MCPOrchestrator._parse_servers(config)
        assert result[0].url == "http://localhost:8080"


# ── McpServerConfig ───────────────────────────────────────────────────────────


class TestMcpServerConfig:
    def test_from_dict_defaults(self) -> None:
        cfg = McpServerConfig.from_dict({})
        assert cfg.name == "unnamed"
        assert cfg.transport == "stdio"
        assert cfg.command == ""
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.required_permissions == []

    def test_from_dict_full(self) -> None:
        raw = {
            "name": "full-srv",
            "transport": "http",
            "command": "node",
            "args": ["server.js"],
            "env": {"API_KEY": "secret123"},
            "cwd": "/tmp",
            "required_permissions": ["filesystem_read"],
            "url": "http://example.com",
        }
        cfg = McpServerConfig.from_dict(raw)
        assert cfg.name == "full-srv"
        assert cfg.transport == "http"
        assert cfg.command == "node"
        assert cfg.args == ["server.js"]
        assert cfg.env == {"API_KEY": "secret123"}
        assert cfg.cwd == "/tmp"
        assert cfg.required_permissions == ["filesystem_read"]
        assert cfg.url == "http://example.com"


# ── _extract_capabilities ─────────────────────────────────────────────────────


class TestExtractCapabilities:
    def test_basic_capability(self, orchestrator: MCPOrchestrator) -> None:
        tool = DiscoveredTool(
            name="get_info",
            description="Get information",
            input_schema={"type": "object", "properties": {"query": {}}},
            server_name="revit",
            server_config=McpServerConfig(name="revit"),
        )
        caps = orchestrator._extract_capabilities(tool)
        # One for the tool itself + one per property.
        assert len(caps) == 2
        cap_names = {c.name for c in caps}
        assert "mcp:revit:get_info" in cap_names
        assert "mcp:revit:get_info:query" in cap_names

    def test_no_properties(self, orchestrator: MCPOrchestrator) -> None:
        tool = DiscoveredTool(
            name="ping",
            description="Ping server",
            input_schema={"type": "object"},
            server_name="revit",
            server_config=McpServerConfig(name="revit"),
        )
        caps = orchestrator._extract_capabilities(tool)
        assert len(caps) == 1
        assert caps[0].name == "mcp:revit:ping"

    def test_description_propagated(self, orchestrator: MCPOrchestrator) -> None:
        tool = DiscoveredTool(
            name="search",
            description="Search the database",
            input_schema={"type": "object"},
            server_name="db",
            server_config=McpServerConfig(name="db"),
        )
        caps = orchestrator._extract_capabilities(tool)
        assert caps[0].description == "Search the database"


# ── _check_permissions ────────────────────────────────────────────────────────


class TestCheckPermissions:
    def test_no_deny_list_allows_all(self, orchestrator: MCPOrchestrator) -> None:
        assert orchestrator._check_permissions(["network", "subprocess"]) == set()

    def test_deny_list_blocks(self, tmp_path: Path, fake_event_bus: EventBus) -> None:
        orch = MCPOrchestrator(
            event_bus=fake_event_bus,
            servers_config="",
            deny_permissions="network,subprocess",
        )
        denied = orch._check_permissions(["network", "filesystem_read"])
        assert denied == {"network"}

    def test_deny_list_case_insensitive(self, tmp_path: Path, fake_event_bus: EventBus) -> None:
        orch = MCPOrchestrator(
            event_bus=fake_event_bus,
            servers_config="",
            deny_permissions="NETWORK",
        )
        denied = orch._check_permissions(["network"])
        assert denied == {"network"}


# ── Secret scrubbing ──────────────────────────────────────────────────────────


class TestScrubSecrets:
    def test_api_key(self) -> None:
        result = MCPOrchestrator._scrub_secrets("apiKey=abc123")
        assert "abc123" not in result
        assert "[REDACTED]" in result

    def test_token(self) -> None:
        result = MCPOrchestrator._scrub_secrets('token: "my-token-456"')
        assert "my-token-456" not in result

    def test_secret(self) -> None:
        result = MCPOrchestrator._scrub_secrets("secret=my_secret")
        assert "my_secret" not in result

    def test_password(self) -> None:
        result = MCPOrchestrator._scrub_secrets("password=super_secret")
        assert "super_secret" not in result

    def test_no_false_positive(self) -> None:
        result = MCPOrchestrator._scrub_secrets("name=test_skill query=hello")
        assert result == "name=test_skill query=hello"


class TestScrubArguments:
    def test_sensitive_key_redacted(self, orchestrator: MCPOrchestrator) -> None:
        args = {"api_key": "secret123", "query": "hello"}
        scrubbed = orchestrator._scrub_arguments(args)
        assert scrubbed["api_key"] == "[REDACTED]"
        assert scrubbed["query"] == "hello"

    def test_nested_dict(self, orchestrator: MCPOrchestrator) -> None:
        args = {"nested": {"password": "pw123", "safe": "ok"}}
        scrubbed = orchestrator._scrub_arguments(args)
        assert scrubbed["nested"]["password"] == "[REDACTED]"
        assert scrubbed["nested"]["safe"] == "ok"

    def test_non_string_values_preserved(self, orchestrator: MCPOrchestrator) -> None:
        args = {"count": 42, "flag": True, "items": [1, 2, 3]}
        scrubbed = orchestrator._scrub_arguments(args)
        assert scrubbed["count"] == 42
        assert scrubbed["flag"] is True
        assert scrubbed["items"] == [1, 2, 3]


# ── call_tool error paths ────────────────────────────────────────────────────


class TestCallTool:
    def _make_tool(self, name: str = "get_info", perm: str = "") -> DiscoveredTool:
        return DiscoveredTool(
            name=name,
            description="Test tool",
            input_schema={"type": "object"},
            server_name="test-srv",
            server_config=McpServerConfig(name="test-srv"),
            required_permissions=[perm] if perm else [],
        )

    def test_tool_not_discovered(self, orchestrator: MCPOrchestrator) -> None:
        result = orchestrator.call_tool("nonexistent.tool")
        assert result["success"] is False
        assert "not discovered" in result["error"]

    def test_server_not_connected(self, orchestrator: MCPOrchestrator) -> None:
        tool = self._make_tool()
        with orchestrator._lock:
            orchestrator._tools["test-srv.get_info"] = tool
        result = orchestrator.call_tool("test-srv.get_info")
        assert result["success"] is False
        assert "not connected" in result["error"]

    def test_permission_denied(self) -> None:
        bus = EventBus()
        selector = ToolSelector(db_path="/tmp/test_mcp_perm.sqlite3")
        orch = MCPOrchestrator(
            event_bus=bus,
            servers_config="",
            deny_permissions="filesystem_read",
        )
        tool = self._make_tool(perm="filesystem_read")
        with orch._lock:
            orch._tools["test-srv.get_info"] = tool
        result = orch.call_tool("test-srv.get_info")
        assert result["success"] is False
        assert "Permission denied" in result["error"]
        selector.close()


# ── get_tool / tools property ────────────────────────────────────────────────


class TestToolLookup:
    def test_get_tool_found(self, orchestrator: MCPOrchestrator) -> None:
        tool = DiscoveredTool(
            name="foo",
            description="foo tool",
            input_schema={},
            server_name="srv",
            server_config=McpServerConfig(name="srv"),
        )
        with orchestrator._lock:
            orchestrator._tools["srv.foo"] = tool
        result = orchestrator.get_tool("srv.foo")
        assert result is tool

    def test_get_tool_not_found(self, orchestrator: MCPOrchestrator) -> None:
        assert orchestrator.get_tool("srv.missing") is None

    def test_tools_property_returns_copy(self, orchestrator: MCPOrchestrator) -> None:
        tool = DiscoveredTool(
            name="bar",
            description="bar tool",
            input_schema={},
            server_name="srv",
            server_config=McpServerConfig(name="srv"),
        )
        with orchestrator._lock:
            orchestrator._tools["srv.bar"] = tool
        snap = orchestrator.tools
        snap["srv.bar"] = None  # mutate the snapshot
        # Original should be unaffected.
        assert orchestrator.get_tool("srv.bar") is tool


# ── Module-level singleton ───────────────────────────────────────────────────


class TestSingleton:
    def test_get_and_reset_singleton(self) -> None:
        reset_mcp_orchestrator()
        a = get_mcp_orchestrator()
        b = get_mcp_orchestrator()
        assert a is b
        reset_mcp_orchestrator()
        assert get_mcp_orchestrator() is not a


# ── _register_tool with denied permissions ───────────────────────────────────


class TestRegisterTool:
    def test_denied_permission_blocked(self, tmp_path: Path, fake_event_bus: EventBus) -> None:
        selector = ToolSelector(db_path=str(tmp_path / "reg.sqlite3"))
        orch = MCPOrchestrator(
            tool_selector=selector,
            event_bus=fake_event_bus,
            servers_config="",
            deny_permissions="network",
        )
        tool = DiscoveredTool(
            name="net_tool",
            description="Needs network",
            input_schema={"type": "object"},
            server_name="srv",
            server_config=McpServerConfig(name="srv"),
            required_permissions=["network"],
        )
        orch._register_tool(tool)
        # Tool should NOT be registered in selector.
        assert "srv.net_tool" not in selector._tools
        selector.close()

    def test_allowed_tool_registered(
        self, orchestrator: MCPOrchestrator, fake_tool_selector: ToolSelector
    ) -> None:
        tool = DiscoveredTool(
            name="safe_tool",
            description="Safe tool",
            input_schema={"type": "object", "properties": {"q": {}}},
            server_name="srv",
            server_config=McpServerConfig(name="srv"),
        )
        orchestrator._register_tool(tool)
        assert "srv.safe_tool" in fake_tool_selector._tools
