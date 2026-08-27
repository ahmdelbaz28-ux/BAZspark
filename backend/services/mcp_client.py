"""
backend/services/mcp_client.py — MCP Client Orchestrator (Stage C2).
====================================================================

Discovers, connects to, and orchestrates MCP (Model Context Protocol) servers
using the **official** ``mcp`` SDK.  Replaces the misleading
``SmitheryMCPClient`` stub (which only performed a connectivity check and did
not implement the real MCP transport).

Design (Stage C2 of the agent-platform rebuild):

* ``MCP_SERVERS`` env var (JSON) lists server descriptors::

    [{"name": "revit", "transport": "stdio", "command": "python",
      "args": ["-m", "fireai.mcp_server.revit_mcp_server"],
      "env": {"FIREAI_ENV": "development"},
      "required_permissions": ["filesystem_read"]}]

* On startup each server is connected via stdio transport, initialised, and
  ``list_tools`` is called.  Every returned tool is converted to a
  ``ToolSelector.register_tool`` registration with capabilities derived from
  the tool description and ``inputSchema``.
* A background thread refreshes the tool list periodically
  (``MCP_TOOL_REFRESH_INTERVAL`` seconds, default 60).
* Each tool call passes through the **same permission gates** as the skill
  loader (C1), plus secret scrubbing (CommandBus pattern) and an audit entry.
* Events are published on the system ``EventBus`` for observability.

The SmitheryMCPClient in ``fireai/mcp_server/smithery_mcp_integration.py``
is deprecated — it only searched local Revit API docs and proposed (never
executed) actions.  All MCP transport functionality now lives here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover
    ClientSession = Any  # type: ignore[assignment,misc]
    StdioServerParameters = Any  # type: ignore[assignment,misc]
    stdio_client = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False

from fireai.agents.tool_selector import Capability, ToolSelector
from fireai.core.event_bus import EventBus

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_ENV_SERVERS = "MCP_SERVERS"
_ENV_REFRESH_INTERVAL = "MCP_TOOL_REFRESH_INTERVAL"
_DEFAULT_REFRESH_INTERVAL = 60  # seconds

# Permission gate: deny-list (same mechanism as skills/loader.py)
_DENY_ENV = "SKILL_DENY_PERMISSIONS"

# Sensitive env-var name patterns for scrubbing.
_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)api[_-]?key"),
    re.compile(r"(?i)secret"),
    re.compile(r"(?i)password"),
    re.compile(r"(?i)token"),
    re.compile(r"(?i)credential"),
    re.compile(r"(?i)auth"),
)


# ── Event constants ───────────────────────────────────────────────────────────

EVENT_MCP_CONNECTED = "mcp.server.connected"
EVENT_MCP_DISCONNECTED = "mcp.server.disconnected"
EVENT_MCP_TOOL_REGISTERED = "mcp.tool.registered"
EVENT_MCP_TOOL_CALL = "mcp.tool.call"
EVENT_MCP_TOOL_ERROR = "mcp.tool.error"
EVENT_MCP_SCAN_ERROR = "mcp.scan.error"


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class McpServerConfig:
    """Parsed descriptor for a single MCP server."""

    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    required_permissions: list[str] = field(default_factory=list)
    # For non-stdio transports (sse, http)
    url: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> McpServerConfig:
        return cls(
            name=raw.get("name", "unnamed"),
            transport=raw.get("transport", "stdio"),
            command=raw.get("command", ""),
            args=list(raw.get("args", [])),
            env=dict(raw.get("env", {})),
            cwd=raw.get("cwd"),
            required_permissions=list(raw.get("required_permissions", [])),
            url=raw.get("url"),
        )


@dataclass
class DiscoveredTool:
    """A tool discovered from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    server_config: McpServerConfig
    required_permissions: list[str] = field(default_factory=list)


# ── Orchestrator ─────────────────────────────────────────────────────────────


class MCPOrchestrator:
    """
    Connects to MCP servers, discovers their tools, and routes calls through
    ``ToolSelector`` with permission gating, secret scrubbing, and audit.

    Thread-safety: all public methods are safe to call from multiple threads.
    MCP SDK sessions are managed in a dedicated asyncio event loop running
    in a background thread.
    """

    def __init__(
        self,
        tool_selector: ToolSelector | None = None,
        event_bus: EventBus | None = None,
        servers_config: str | None = None,
        refresh_interval: int | None = None,
        deny_permissions: str | None = None,
    ) -> None:
        self._selector = tool_selector or ToolSelector()
        self._bus = event_bus or EventBus.instance()

        raw = servers_config or os.environ.get(_ENV_SERVERS, "")
        self._server_configs: list[McpServerConfig] = self._parse_servers(raw)

        self._refresh_interval = (
            refresh_interval
            if refresh_interval is not None
            else int(os.environ.get(_ENV_REFRESH_INTERVAL, _DEFAULT_REFRESH_INTERVAL))
        )

        deny_str = deny_permissions or os.environ.get(_DENY_ENV, "")
        self._deny_permissions: set[str] = {
            p.strip().lower() for p in deny_str.split(",") if p.strip()
        }

        self._sessions: dict[str, ClientSession] = {}
        self._tools: dict[str, DiscoveredTool] = {}
        self._lock = threading.RLock()
        self._loop: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── Environment parsing ──────────────────────────────────────────

    @staticmethod
    def _parse_servers(raw: str) -> list[McpServerConfig]:
        """Parse the ``MCP_SERVERS`` JSON env var into config objects."""
        if not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("MCP_SERVERS is not valid JSON: %s", exc)
            return []
        if not isinstance(parsed, list):
            logger.error("MCP_SERVERS must be a JSON array of server objects")
            return []
        configs = []
        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                logger.warning("MCP_SERVERS[%d] is not an object — skipping", i)
                continue
            configs.append(McpServerConfig.from_dict(item))
        return configs

    # ── Session management ───────────────────────────────────────────

    def start(self) -> None:
        """Start the background asyncio loop and connect to all servers."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("MCPOrchestrator already started")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="mcp-orchestrator",
            daemon=True,
        )
        self._thread.start()
        logger.info("MCPOrchestrator started (refresh interval: %ds)", self._refresh_interval)

    def _run_loop(self) -> None:
        """Background entry point — runs the asyncio event loop."""
        # The event loop must be created in the thread that runs it.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bootstrap())
            while not self._stop_event.is_set():
                try:
                    self._loop.run_until_complete(
                        asyncio.wait_for(
                            self._refresh_loop(),
                            timeout=self._refresh_interval,
                        )
                    )
                except TimeoutError:
                    pass  # periodic refresh interval elapsed
                except Exception:
                    logger.exception("MCP orchestrator refresh loop error")
                    time.sleep(5)
        finally:
            self._loop.run_until_complete(self._shutdown())
            self._loop.close()

    async def _shutdown(self) -> None:
        """Close all active MCP sessions."""
        for name, session in list(self._sessions.items()):
            try:
                if hasattr(session, "aclose"):
                    await session.aclose()
            except Exception:
                logger.debug("Error closing MCP session '%s'", name, exc_info=True)
        self._sessions.clear()

    async def _bootstrap(self) -> None:
        """Initial connection to all configured servers."""
        for config in self._server_configs:
            await self._connect_server(config)

    async def _refresh_loop(self) -> None:
        """Continuously refresh tool listings with a short sleep."""
        while not self._stop_event.is_set():
            for name, session in list(self._sessions.items()):
                config = next(
                    (c for c in self._server_configs if c.name == name),
                    None,
                )
                if config is not None:
                    await self._refresh_tools(config, session)
            await asyncio.sleep(self._refresh_interval)

    async def _connect_server(self, config: McpServerConfig) -> None:
        """Connect to a single MCP server and discover its tools."""
        if config.transport != "stdio":
            logger.warning(
                "MCP server '%s' uses unsupported transport '%s' — skipping",
                config.name,
                config.transport,
            )
            self._bus.publish(
                EVENT_MCP_SCAN_ERROR,
                data={"server": config.name, "error": f"unsupported transport: {config.transport}"},
                source="mcp_orchestrator",
            )
            return

        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env or None,
            cwd=config.cwd or None,
        )

        try:
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    self._bus.publish(
                        EVENT_MCP_CONNECTED,
                        data={"server": config.name, "transport": config.transport},
                        source="mcp_orchestrator",
                    )
                    await self._refresh_tools(config, session)
                    # Keep session alive — block until stopped.
                    self._sessions[config.name] = session
                    while not self._stop_event.is_set():
                        await asyncio.sleep(1)
        except Exception as exc:
            self._bus.publish(
                EVENT_MCP_SCAN_ERROR,
                data={"server": config.name, "error": str(exc)},
                source="mcp_orchestrator",
            )
            logger.exception("Failed to connect to MCP server '%s'", config.name)

    async def _refresh_tools(self, config: McpServerConfig, session: ClientSession) -> None:
        """List tools from a server and register/deregister in ToolSelector."""
        try:
            result = await session.list_tools()
        except Exception as exc:
            logger.warning("Failed to list tools from MCP server '%s': %s", config.name, exc)
            return

        current_names: set[str] = set()
        for tool in result.tools:
            tool_name = f"{config.name}.{tool.name}"
            current_names.add(tool_name)

            tool_obj = DiscoveredTool(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
                server_name=config.name,
                server_config=config,
                required_permissions=list(config.required_permissions),
            )

            with self._lock:
                self._tools[tool_name] = tool_obj

            self._register_tool(tool_obj)

        # Remove tools that disappeared
        with self._lock:
            stale = {
                tn
                for tn in self._tools
                if tn.startswith(f"{config.name}.") and tn not in current_names
            }
            for tn in stale:
                del self._tools[tn]
        logger.debug(
            "Refreshed tools for MCP server '%s': %d tools", config.name, len(current_names)
        )

    # ── ToolSelector integration ──────────────────────────────────────

    def _extract_capabilities(self, tool: DiscoveredTool) -> list[Capability]:
        """
        Derive capabilities from the MCP tool's description and inputSchema.

        Each schema property becomes a capability ``mcp:<prop>``; the tool
        itself gets a capability ``mcp:<server>:<tool>``.
        """
        caps: list[Capability] = []
        caps.append(
            Capability(
                name=f"mcp:{tool.server_name}:{tool.name}",
                description=tool.description,
            )
        )
        schema = tool.input_schema
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for prop_name in properties:
                caps.append(
                    Capability(
                        name=f"mcp:{tool.server_name}:{tool.name}:{prop_name}",
                        description=f"Input parameter '{prop_name}' for {tool.name}",
                    )
                )
        return caps

    def _check_permissions(self, permissions: list[str]) -> set[str]:
        """Return the set of permission names denied by the global deny-list."""
        if not self._deny_permissions:
            return set()
        return {p for p in permissions if p.lower() in self._deny_permissions}

    def _register_tool(self, tool: DiscoveredTool) -> None:
        """Register a discovered MCP tool in ToolSelector with capability scoring."""
        denied = self._check_permissions(tool.required_permissions)
        if denied:
            logger.warning(
                "MCP tool '%s' rejected — denied permissions: %s",
                tool.name,
                sorted(denied),
            )
            self._bus.publish(
                EVENT_MCP_TOOL_ERROR,
                data={
                    "tool": f"{tool.server_name}.{tool.name}",
                    "error": f"permission denied: {sorted(denied)}",
                },
                source="mcp_orchestrator",
            )
            return

        capabilities = self._extract_capabilities(tool)
        tool_name = f"{tool.server_name}.{tool.name}"

        def _make_score_fn(tool_desc: str, cap_names: list[str]) -> Callable[[Any, Any], float]:
            def _score_fn(task: Any, context: Any) -> float:
                if not hasattr(task, "description"):
                    return 0.0
                task_text = (task.description or "").lower()
                matches = sum(1 for c in cap_names if c.split(":")[-1] in task_text)
                return float(matches) / max(len(cap_names), 1) if matches else 0.0

            return _score_fn

        self._selector.register_tool(
            name=tool_name,
            capabilities=capabilities,
            score_fn=_make_score_fn(tool.description, [c.name for c in capabilities]),
        )
        self._bus.publish(
            EVENT_MCP_TOOL_REGISTERED,
            data={
                "tool": tool_name,
                "server": tool.server_name,
                "capabilities": [c.name for c in capabilities],
            },
            source="mcp_orchestrator",
        )
        logger.info("MCP tool registered: %s (%d capabilities)", tool_name, len(capabilities))

    # ── Secret scrubbing ──────────────────────────────────────────────

    @staticmethod
    def _scrub_secrets(text: str) -> str:
        """
        Redact anything that looks like a secret in a string.

        Matches common secret patterns (API keys, tokens, passwords) and
        replaces them with ``[REDACTED]``.
        """
        # Generic key=value or "key": "value" patterns
        patterns = [
            # apiKey / api_key / API_KEY = value
            re.compile(r"(?i)(api[_-]?key)\s*[=:]\s*['\"]?([^\s'\",}]+)"),
            # token = value
            re.compile(r"(?i)(token)\s*[=:]\s*['\"]?([^\s'\",}]+)"),
            # secret = value
            re.compile(r"(?i)(secret)\s*[=:]\s*['\"]?([^\s'\",}]+)"),
            # password = value
            re.compile(r"(?i)(password)\s*[=:]\s*['\"]?([^\s'\",}]+)"),
        ]
        redacted = text
        for pat in patterns:
            redacted = pat.sub(r"\1=[REDACTED]", redacted)
        return redacted

    def _scrub_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of arguments with sensitive values redacted."""
        scrubbed: dict[str, Any] = {}
        for key, value in arguments.items():
            if isinstance(key, str) and any(p.search(key) for p in _SENSITIVE_PATTERNS):
                scrubbed[key] = "[REDACTED]"
            elif isinstance(value, str):
                scrubbed[key] = self._scrub_secrets(value)
            elif isinstance(value, dict):
                scrubbed[key] = self._scrub_arguments(value)
            else:
                scrubbed[key] = value
        return scrubbed

    # ── Public tool-call API ──────────────────────────────────────────

    @property
    def tools(self) -> dict[str, DiscoveredTool]:
        """Snapshot of all discovered MCP tools."""
        with self._lock:
            return dict(self._tools)

    def get_tool(self, qualified_name: str) -> DiscoveredTool | None:
        """Look up a tool by ``server.tool`` qualified name."""
        with self._lock:
            return self._tools.get(qualified_name)

    def call_tool(
        self,
        qualified_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Synchronously call an MCP tool from a non-async context.

        Applies permission gating, secret scrubbing, and publishes an audit
        entry on the EventBus.

        Returns a dict with ``success``, ``result``, ``error`` keys.
        """
        tool = self.get_tool(qualified_name)
        if tool is None:
            error_msg = f"Tool '{qualified_name}' is not discovered"
            self._bus.publish(
                EVENT_MCP_TOOL_ERROR,
                data={"tool": qualified_name, "error": error_msg},
                source="mcp_orchestrator",
            )
            return {"success": False, "error": error_msg}

        denied = self._check_permissions(tool.required_permissions)
        if denied:
            error_msg = f"Permission denied: {sorted(denied)}"
            self._bus.publish(
                EVENT_MCP_TOOL_ERROR,
                data={"tool": qualified_name, "error": error_msg},
                source="mcp_orchestrator",
            )
            return {"success": False, "error": error_msg}

        scrubbed = self._scrub_arguments(arguments or {})
        call_id = str(uuid.uuid4())
        started = time.monotonic()

        session = self._sessions.get(tool.server_name)
        if session is None:
            error_msg = f"MCP server '{tool.server_name}' is not connected"
            self._bus.publish(
                EVENT_MCP_TOOL_ERROR,
                data={"tool": qualified_name, "error": error_msg, "call_id": call_id},
                source="mcp_orchestrator",
            )
            return {"success": False, "error": error_msg}

        # Run the async call in the background loop
        fut = asyncio.run_coroutine_threadsafe(
            self._async_call_tool(session, tool.name, scrubbed),
            self._loop,
        )
        try:
            result = fut.result(timeout=30)
        except Exception as exc:
            duration_ms = (time.monotonic() - started) * 1000
            self._bus.publish(
                EVENT_MCP_TOOL_ERROR,
                data={
                    "tool": qualified_name,
                    "error": str(exc),
                    "call_id": call_id,
                    "duration_ms": round(duration_ms, 2),
                    "scrubbed_args": scrubbed,
                },
                source="mcp_orchestrator",
            )
            return {"success": False, "error": str(exc)}

        duration_ms = (time.monotonic() - started) * 1000
        self._bus.publish(
            EVENT_MCP_TOOL_CALL,
            data={
                "tool": qualified_name,
                "call_id": call_id,
                "duration_ms": round(duration_ms, 2),
                "scrubbed_args": scrubbed,
                "success": result.get("success", True),
            },
            source="mcp_orchestrator",
        )
        return result

    async def _async_call_tool(
        self,
        session: ClientSession,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool call on an MCP session and return a normalised result."""
        result = await session.call_tool(tool_name, arguments)
        content: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                content.append(text)
            else:
                content.append(str(block))
        return {
            "success": not result.isError,
            "result": {"content": content, "structuredContent": result.structuredContent},
        }

    # ── Lifecycle ───────────────────────────────────────────────────

    def stop(self) -> None:
        """Signal the background loop to shut down and wait."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        with self._lock:
            self._sessions.clear()


# ── Module-level convenience ─────────────────────────────────────────────────


_orchestrator: MCPOrchestrator | None = None
_orch_lock = threading.Lock()


def get_mcp_orchestrator() -> MCPOrchestrator:
    """Return the shared MCPOrchestrator singleton (thread-safe)."""
    global _orchestrator
    if _orchestrator is None:
        with _orch_lock:
            if _orchestrator is None:
                _orchestrator = MCPOrchestrator()
    return _orchestrator


def reset_mcp_orchestrator() -> None:
    """Reset the singleton (for testing only)."""
    global _orchestrator
    with _orch_lock:
        if _orchestrator is not None:
            _orchestrator.stop()
        _orchestrator = None


__all__ = [
    "DiscoveredTool",
    "MCPOrchestrator",
    "McpServerConfig",
    "get_mcp_orchestrator",
    "reset_mcp_orchestrator",
]
