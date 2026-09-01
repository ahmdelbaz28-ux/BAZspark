from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.api_keys import validate_api_key
from backend.auth import has_permission, require_permission
from backend.core.agent_run_orchestrator import (
    AgentRunOrchestrator,
    InvalidRunStateError,
    RunNotFoundError,
    RunPermissionError,
    StaleApprovalError,
)
from backend.core.agent_run_store import (
    ApprovalAlreadyDecidedError,
    PendingApprovalNotFoundError,
)
from backend.core.capability_registry import default_capability_registry
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    DomainCommand,
    default_command_bus,
)
from backend.core.context_resolver import default_context_resolver
from backend.core.openapi_contracts import StandardizedAPIRoute
from backend.core.session_context import (
    is_revision_required_for_capability,
)
from backend.core.workflow_engine import (
    CompositeWorkflowDAG,
    WorkflowExecutor,
    WorkflowNode,
)
from backend.rbac import Permission
from backend.services.llm_service import ping_provider

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/agent", tags=["agent-ws"], route_class=StandardizedAPIRoute)

# Active connections from agents
# Map from agent_type -> list of WebSocket
active_agents: dict[str, list[WebSocket]] = {}
agent_response_futures: dict[str, asyncio.Future[Any]] = {}

# A lock per connection to serialize command dispatches
agent_locks: dict[str, asyncio.Lock] = {}

# Capability ID constants — avoid string literal duplication (SonarCloud S1192)
CAP_SPATIAL_PLACE_DEVICES = "spatial.place_devices"
CAP_SPATIAL_VERIFY_SPACING = "spatial.verify_detector_spacing"
CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP = "electrical.calculate_voltage_drop"
CAP_ELECTRICAL_CALCULATE_BATTERY = "electrical.calculate_battery"
CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH = "hydraulics.solve_darcy_weisbach"

# Track which futures belong to which websocket (for cleanup on disconnect)
# Maps websocket id -> set of pending command IDs
_agent_pending_commands: dict[str, set[str]] = {}


def get_agent_lock(websocket: WebSocket) -> asyncio.Lock:
    ws_id = str(id(websocket))
    if ws_id not in agent_locks:
        agent_locks[ws_id] = asyncio.Lock()
    return agent_locks[ws_id]


# S-06 FIX (Engineering Review): the previous signature used
#   api_key: str = Query(..., alias="api_key")
# which placed the API key in the URL query string. Query strings are logged
# by every proxy (nginx, Cloudflare, Akamai, Vercel), captured in browser
# history, and may leak via Referer headers. The key is now extracted from the
# `X-API-Key` request header BEFORE the WebSocket handshake is accepted.
#
# Backward compatibility: if the header is missing, we fall back to checking
# the Sec-WebSocket-Protocol subprotocol (clients can send the key as the
# first subprotocol). The query-string path is no longer supported.


def _extract_api_key_from_handshake(websocket: WebSocket) -> str:
    """Pull the API key or JWT auth token from headers or subprotocol."""
    # 1. Header-based (preferred)
    headers = websocket.headers
    for name in ("x-api-key", "X-API-Key", "authorization"):
        val = headers.get(name)
        if val:
            if name.lower() == "authorization" and val.lower().startswith("bearer "):
                return val[7:].strip()
            return val.strip()
    # 2. Subprotocol-based (for browsers that cannot set custom headers on WS)
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    if protocols:
        # The first token is the API key (client must send it as the subprotocol)
        return protocols.split(",")[0].strip()
    return ""


def _validate_origin(origin: str) -> bool:
    """Check that the Origin header value is in the CORS/ALLOWED_ORIGINS allow-list."""
    import os

    allowed_origins_str = (
        os.environ.get("ALLOWED_ORIGINS")
        or os.environ.get("CORS_ALLOWED_ORIGINS")
        or "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    )
    allowed_origins = {
        o.strip().lower().rstrip("/") for o in allowed_origins_str.split(",") if o.strip()
    }
    origin_clean = origin.strip().lower().rstrip("/")
    return origin_clean in allowed_origins


async def _extract_and_validate_api_key(
    websocket: WebSocket,
) -> tuple:
    """Extract auth token / API key from handshake and validate it.

    Returns ``(api_key_info, api_key)`` on success, or ``(None, "")``
    after closing the socket with 4401 (unauthenticated) or 4403 (unauthorized).
    """
    api_key = _extract_api_key_from_handshake(websocket)
    if not api_key:
        logger.warning("Rejected agent connection: no auth token/API key in handshake")
        await websocket.close(code=4401)
        return None, ""

    try:
        api_key_info = validate_api_key(api_key)
    except Exception as e:
        logger.exception("Error validating agent auth token: %s", e)
        await websocket.close(code=4401)
        return None, ""

    if api_key_info is None:
        logger.warning("Rejected agent connection: invalid auth token / API Key")
        await websocket.close(code=4401)
        return None, ""

    if not has_permission(api_key_info.role, Permission.CALCULATION_EXECUTE):
        logger.warning(
            "Rejected agent connection: role %s lacks CALCULATION_EXECUTE",
            api_key_info.role,
        )
        await websocket.close(code=4403)
        return None, ""

    return api_key_info, api_key


async def _authenticate_agent_websocket(websocket: WebSocket):
    """Validate the agent's auth token + RBAC + Origin before accepting the WS handshake.

    Returns the validated ``api_key_info`` on success, or ``None`` after
    closing the connection with code 4401/4403 on any failure.
    """
    origin = websocket.headers.get("origin")
    if origin and not _validate_origin(origin):
        logger.warning("Rejected agent connection: untrusted origin '%s'", origin)
        await websocket.close(code=4403)
        return None, ""

    # A4 FIX: browser clients authenticate with a short-lived single-use
    # ticket obtained from POST /agent/ws-ticket (browsers cannot set
    # custom headers on WebSocket handshakes).
    ticket = websocket.query_params.get("ticket")
    if ticket:
        ticket_info = _consume_ws_ticket(ticket, origin)
        if ticket_info is None:
            logger.warning("Rejected agent connection: invalid/expired/replayed WS ticket")
            await websocket.close(code=4401)
            return None, ""
        if not has_permission(ticket_info.role, Permission.CALCULATION_EXECUTE):
            logger.warning(
                "Rejected agent connection: ticket role %s lacks CALCULATION_EXECUTE",
                ticket_info.role,
            )
            await websocket.close(code=4403)
            return None, ""
        return ticket_info, ""

    return await _extract_and_validate_api_key(websocket)


@router.post("/ws-ticket")
async def create_ws_ticket(
    request: Request,
    _permission: None = Depends(require_permission(Permission.CALCULATION_EXECUTE)),
) -> dict[str, Any]:
    """Issue a single-use WebSocket ticket (A4).

    Browsers cannot attach ``X-API-Key`` to a WS handshake. The client calls
    this authenticated endpoint first, then connects to
    ``/api/v1/agent/ws?ticket=<value>``. The ticket is bound to the caller's
    identity and Origin, expires in <=60 seconds, and is burned on first use.
    """
    from fastapi import HTTPException as _HTTPException

    api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key") or ""
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()

    info = None
    if api_key:
        try:
            info = validate_api_key(api_key)
        except Exception:  # noqa: BLE001 — validation failure means no identity
            info = None
    if info is None:
        raise _HTTPException(status_code=401, detail="Valid API key required.")

    ticket = _issue_ws_ticket(info, request.headers.get("origin"))
    return {"ticket": ticket, "expires_in": WS_TICKET_TTL_SECONDS}


def _register_agent(websocket: WebSocket, agent_type: str) -> None:
    """Register an active agent connection.

    VERIFY-003 FIX: only ONE agent is kept per type — a new connection
    atomically replaces any prior one. Previously a rogue socket that
    registered ahead of the real desktop agent stayed in ``active_agents``
    and ``send_agent_command`` dispatched to ``agents[0]``, letting the
    rogue agent intercept commands (and, by guessing command ids, resolve
    the real agent's response futures). With newest-wins registration the
    attacker-controlled socket is torn down the moment the real agent
    connects.
    """
    for existing in list(active_agents.get(agent_type, [])):
        if existing is websocket:
            continue
        logger.warning(
            "Replacing existing agent connection for type=%s (newest connection wins)",
            agent_type,
        )
        _cleanup_agent(existing, agent_type)
    active_agents.setdefault(agent_type, []).append(websocket)


def _cleanup_agent(websocket: WebSocket, agent_type: str) -> None:
    """Fail pending futures and remove the agent from the active registry."""
    ws_id = str(id(websocket))
    pending = _agent_pending_commands.pop(ws_id, set())
    for cmd_id in pending:
        future = agent_response_futures.pop(cmd_id, None)
        if future and not future.done():
            future.set_exception(
                ConnectionError(f"Agent disconnected while command {cmd_id} was pending")
            )

    if agent_type in active_agents and websocket in active_agents[agent_type]:
        active_agents[agent_type].remove(websocket)
    agent_locks.pop(ws_id, None)


_seen_agent_nonces: set[str] = set()


def _validate_agent_nonce(msg: dict) -> bool:
    """Validate frame nonce to prevent WebSocket frame hijacking and replay attacks."""
    nonce = msg.get("nonce")
    if nonce:
        if nonce in _seen_agent_nonces:
            logger.warning("Replay attack blocked for agent WS: nonce=%s", nonce)
            return False
        import time as _time

        _seen_agent_nonces.add(nonce)
        _nonce_timestamps[nonce] = _time.monotonic()
        _prune_seen_nonces()
    return True


# ── A6 FIX: sliding-TTL nonce store ─────────────────────────────────────────
# Previously the whole set was cleared when it exceeded 5000 entries, which
# re-opened a replay window for every previously seen nonce. Nonces now carry
# timestamps and only expired entries are pruned.
_NONCE_TTL_SECONDS = 3600.0
_SEEN_AGENT_NONCES_MAX = 20000
_nonce_timestamps: dict[str, float] = {}


def _prune_seen_nonces() -> None:
    import time as _time

    now = _time.monotonic()
    if len(_nonce_timestamps) > _SEEN_AGENT_NONCES_MAX:
        cutoff = now - _NONCE_TTL_SECONDS
        expired = [n for n, ts in _nonce_timestamps.items() if ts < cutoff]
        for n in expired:
            _seen_agent_nonces.discard(n)
            _nonce_timestamps.pop(n, None)
        # Hard cap fallback: drop the oldest quarter even if none expired.
        if len(_nonce_timestamps) > _SEEN_AGENT_NONCES_MAX:
            ordered = sorted(_nonce_timestamps.items(), key=lambda kv: kv[1])
            for n, _ts in ordered[: len(ordered) // 4]:
                _seen_agent_nonces.discard(n)
                _nonce_timestamps.pop(n, None)


def _register_agent_nonce(nonce: str) -> None:
    """Record a nonce with its arrival time."""
    import time as _time

    _nonce_timestamps[nonce] = _time.monotonic()


# ── A4 FIX: single-use WebSocket tickets ────────────────────────────────────
# Browsers cannot attach X-API-Key headers to a WebSocket handshake, so the
# frontend previously connected with NO credentials and was closed with 4401.
# The client now exchanges its API key (via authenticated REST) for a
# short-lived single-use ticket bound to its identity, then passes it as
# ?ticket=. The server burns the ticket on first use.
import secrets as _secrets

WS_TICKET_TTL_SECONDS = 60
_ws_tickets: dict[str, dict[str, Any]] = {}


def _issue_ws_ticket(api_key_info: Any, origin: str | None) -> str:
    """Create a one-time ticket bound to the caller identity (+origin)."""
    import time as _time

    now = _time.monotonic()
    expired = [t for t, meta in _ws_tickets.items() if meta["expires"] <= now]
    for t in expired:
        _ws_tickets.pop(t, None)

    ticket = _secrets.token_urlsafe(32)
    _ws_tickets[ticket] = {
        "expires": now + WS_TICKET_TTL_SECONDS,
        "role": getattr(api_key_info, "role", "engineer"),
        "name": getattr(api_key_info, "name", "browser_user"),
        "email": getattr(api_key_info, "email", ""),
        "origin": (origin or "").strip().lower().rstrip("/"),
    }
    try:
        from backend.core.shared_state import default_shared_state
        default_shared_state.issue_ws_ticket(api_key_info, origin, WS_TICKET_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Shared state store issue_ws_ticket failed: %s", exc)

    return ticket


def _consume_ws_ticket(ticket: str, origin: str | None) -> Any | None:
    """Validate and burn a ticket. Returns an api-key-info-like object or None."""
    import time as _time
    from types import SimpleNamespace

    meta = _ws_tickets.pop(ticket, None)  # burned immediately — single use
    try:
        from backend.core.shared_state import default_shared_state
        shared_res = default_shared_state.consume_ws_ticket(ticket, origin)
        if meta is None and shared_res is not None:
            return shared_res
    except Exception as exc:
        logger.warning("Shared state store unavailable for ticket consume: %s", exc)

    if meta is None:
        return None
    now = _time.monotonic()
    if meta["expires"] <= now:
        return None
    expected_origin = meta.get("origin")
    if expected_origin and origin:
        if origin.strip().lower().rstrip("/") != expected_origin:
            logger.warning("WS ticket rejected: origin mismatch")
            return None

    logger.info("WS ticket accepted for %s (single-use)", meta["name"])
    return SimpleNamespace(role=meta["role"], name=meta["name"], email=meta["email"])


class AIOrchestrationService:
    """Orchestrates Phase 1 Vertical Slice B:
    User Intent -> Context Resolution -> Capability Discovery -> Deterministic Planning ->
    Dry-Run DomainCommand -> Preview -> Approval -> OCC Check -> Deterministic Commit -> Event & Audit.
    """

    def __init__(
        self,
        command_bus=None,
        context_resolver=None,
        capability_registry=None,
    ) -> None:
        self.command_bus = command_bus or default_command_bus
        self.context_resolver = context_resolver or default_context_resolver
        self.capability_registry = capability_registry or default_capability_registry

    def _build_telemetry(
        self,
        context_pkt: Any,
        result_data: dict[str, Any] | None = None,
        provider_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        telemetry = (
            dict(context_pkt.telemetry) if context_pkt and hasattr(context_pkt, "telemetry") else {}
        )
        prompt_tokens = getattr(context_pkt, "token_count", 0) if context_pkt else 0
        telemetry["prompt_tokens"] = prompt_tokens
        completion_tokens = max(1, len(str(result_data or {})) // 4) if result_data else 0
        telemetry["completion_tokens"] = completion_tokens
        telemetry["total_tokens"] = prompt_tokens + completion_tokens
        if provider_config:
            telemetry["provider"] = provider_config.get("provider", "anthropic")
            telemetry["model"] = provider_config.get("model") or provider_config.get(
                "modelName", "claude-sonnet-4-5"
            )
            if "temperature" in provider_config:
                telemetry["temperature"] = provider_config["temperature"]
            if "baseUrl" in provider_config:
                telemetry["baseUrl"] = provider_config["baseUrl"]
        return telemetry

    async def handle_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process an AI intent: resolve context, plan placement deterministically, and return dry-run preview."""
        project_id = str(msg.get("projectId") or "")
        room_id = str(msg.get("roomId", "room-101"))
        room_bounds = msg.get(
            "roomBounds", {"width_m": 10.0, "length_m": 15.0, "ceiling_height_m": 3.0}
        )
        existing_devices = msg.get("existingDevices", [])
        detector_type = msg.get("detectorType", "smoke")
        provider_config = msg.get("providerConfig") or msg.get("llm") or {}

        # 1. Context Resolution with hard <=1500 token budget
        current_rev = self.command_bus.get_project_revision(project_id)
        context_pkt = self.context_resolver.resolve_room_context(
            project_id=project_id,
            room_id=room_id,
            revision=current_rev,
            room_bounds=room_bounds,
            existing_devices=existing_devices,
        )

        # 2. Capability Discovery (spatial.place_devices)
        caps = self.capability_registry.discover(categories=["spatial"], scopes=principal.scopes)
        if not caps:
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "NO_CAPABILITY_AVAILABLE",
                    "message": "No matching spatial capabilities available for user scopes.",
                }
            )
            return

        # 3. Create Dry-Run Domain Command
        command_id = f"cmd-{uuid.uuid4().hex[:12]}"
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        command = DomainCommand(
            commandId=command_id,
            correlationId=correlation_id,
            capabilityId=CAP_SPATIAL_PLACE_DEVICES,
            projectId=project_id,
            expectedRevision=current_rev,
            timestamp=datetime.now(UTC).isoformat(),
            principal=principal,
            riskClass="MEDIUM",
            isDryRun=True,
            payload={
                "room_id": room_id,
                "width_m": context_pkt.room_bounds["width_m"],
                "length_m": context_pkt.room_bounds["length_m"],
                "ceiling_height_m": context_pkt.room_bounds["ceiling_height_m"],
                "detector_type": detector_type,
            },
        )

        # 4. Execute Dry-Run via CommandBus in worker thread
        result = await asyncio.to_thread(self.command_bus.execute, command)

        # 5. Send Preview to Client via WS
        await websocket.send_json(
            {
                "type": "ai_preview",
                "commandId": command_id,
                "correlationId": correlation_id,
                "projectId": project_id,
                "expectedRevision": current_rev,
                "capabilityId": CAP_SPATIAL_PLACE_DEVICES,
                "previewDevices": result.resultData.get("devices", []),
                "deviceCount": result.resultData.get("device_count", 0),
                "coveragePct": result.resultData.get("coverage_pct", 100.0),
                "isCompliant": result.resultData.get("is_compliant", True),
                "tokenTelemetry": self._build_telemetry(
                    context_pkt, result.resultData, provider_config
                ),
                "payload": command.payload,
            }
        )

    async def handle_electrical_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process an electrical calculation intent: resolve circuit context and return deterministic preview."""
        project_id = str(msg.get("projectId") or "")
        circuit_id = str(msg.get("circuit_id", msg.get("circuitId", "nac-circuit-01")))
        current_a = float(msg.get("current_a") or msg.get("currentA") or 1.5)
        one_way_length_m = float(msg.get("one_way_length_m") or msg.get("oneWayLengthM") or 30.0)
        awg = str(msg.get("awg") or "14").strip()
        nominal_voltage = float(msg.get("nominal_voltage") or msg.get("nominalVoltage") or 24.0)
        temperature_c = float(msg.get("temperature_c") or msg.get("temperatureC") or 75.0)
        provider_config = msg.get("providerConfig") or msg.get("llm") or {}

        current_rev = self.command_bus.get_project_revision(project_id)
        context_pkt = self.context_resolver.resolve_circuit_context(
            project_id=project_id,
            circuit_id=circuit_id,
            revision=current_rev,
            circuit_spec={
                "current_a": current_a,
                "one_way_length_m": one_way_length_m,
                "awg": awg,
                "nominal_voltage": nominal_voltage,
                "temperature_c": temperature_c,
            },
        )

        caps = self.capability_registry.discover(categories=["electrical"], scopes=principal.scopes)
        if not caps:
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "NO_CAPABILITY_AVAILABLE",
                    "message": "No matching electrical capabilities available for user scopes.",
                }
            )
            return

        command_id = f"cmd-{uuid.uuid4().hex[:12]}"
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        command = DomainCommand(
            commandId=command_id,
            correlationId=correlation_id,
            capabilityId=CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
            projectId=project_id,
            expectedRevision=current_rev,
            timestamp=datetime.now(UTC).isoformat(),
            principal=principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "circuit_id": circuit_id,
                "current_a": current_a,
                "one_way_length_m": one_way_length_m,
                "awg": awg,
                "nominal_voltage": nominal_voltage,
                "temperature_c": temperature_c,
            },
        )

        result = await asyncio.to_thread(self.command_bus.execute, command)

        await websocket.send_json(
            {
                "type": "ai_electrical_preview",
                "commandId": command_id,
                "correlationId": correlation_id,
                "projectId": project_id,
                "expectedRevision": current_rev,
                "capabilityId": CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
                "circuitId": circuit_id,
                "voltageDropV": result.resultData.get("voltage_drop_v", 0.0),
                "voltageDropPct": result.resultData.get("voltage_drop_pct", 0.0),
                "terminalVoltageV": result.resultData.get("terminal_voltage_v", 24.0),
                "isCompliant": result.resultData.get("is_compliant", True),
                "recommendedAwg": result.resultData.get("recommended_awg", awg),
                "tokenTelemetry": self._build_telemetry(
                    context_pkt, result.resultData, provider_config
                ),
                "payload": command.payload,
            }
        )

    async def handle_hydraulic_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process natural language / structured hydraulic intent into bounded preview proposal (Phase 2C)."""
        project_id = str(msg.get("projectId") or "")
        current_rev = self.command_bus.get_project_revision(project_id)
        pipe_segment_id = str(msg.get("pipeSegmentId", "pipe-seg-01"))
        length_m = float(msg.get("lengthM", 15.0))
        diameter_mm = float(msg.get("diameterMm", 50.0))
        flow_rate_kg_s = msg.get("flowRateKgS")
        flow_l_min = msg.get("flowLMin", 250.0 if flow_rate_kg_s is None else None)
        fluid_type = str(msg.get("fluidType", "water")).strip().lower()
        roughness_mm = msg.get("roughnessMm")
        elevation_m = float(msg.get("elevationM", 0.0))
        provider_config = msg.get("providerConfig") or msg.get("llm") or {}

        context_pkt = self.context_resolver.resolve_hydraulic_context(
            project_id=project_id,
            pipe_segment_id=pipe_segment_id,
            revision=current_rev,
            hydraulic_spec={
                "length_m": length_m,
                "diameter_mm": diameter_mm,
                "flow_rate_kg_s": flow_rate_kg_s,
                "flow_l_min": flow_l_min,
                "fluid_type": fluid_type,
                "roughness_mm": roughness_mm,
                "elevation_m": elevation_m,
            },
        )

        caps = self.capability_registry.discover(categories=["hydraulics"], scopes=principal.scopes)
        if not caps:
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "NO_CAPABILITY_AVAILABLE",
                    "message": "No matching hydraulic capabilities available for user scopes.",
                }
            )
            return

        command_id = f"cmd-{uuid.uuid4().hex[:12]}"
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        command = DomainCommand(
            commandId=command_id,
            correlationId=correlation_id,
            capabilityId=CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
            projectId=project_id,
            expectedRevision=current_rev,
            timestamp=datetime.now(UTC).isoformat(),
            principal=principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "pipe_segment_id": pipe_segment_id,
                "length_m": length_m,
                "diameter_mm": diameter_mm,
                "flow_rate_kg_s": flow_rate_kg_s,
                "flow_l_min": flow_l_min,
                "fluid_type": fluid_type,
                "roughness_mm": roughness_mm,
                "elevation_m": elevation_m,
            },
        )

        result = await asyncio.to_thread(self.command_bus.execute, command)

        await websocket.send_json(
            {
                "type": "ai_hydraulic_preview",
                "commandId": command_id,
                "correlationId": correlation_id,
                "projectId": project_id,
                "expectedRevision": current_rev,
                "capabilityId": CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
                "pipeSegmentId": pipe_segment_id,
                "flowVelocityMS": result.resultData.get("flow_velocity_m_s", 0.0),
                "reynoldsNumber": result.resultData.get("reynolds_number", 0.0),
                "frictionFactor": result.resultData.get("friction_factor", 0.0),
                "flowRegime": result.resultData.get("flow_regime", "turbulent"),
                "headLossM": result.resultData.get("head_loss_m", 0.0),
                "pressureLossPa": result.resultData.get("pressure_loss_pa", 0.0),
                "pressureLossPsi": result.resultData.get("pressure_loss_psi", 0.0),
                "totalPressureLossPsi": result.resultData.get("total_pressure_loss_psi", 0.0),
                "isCompliant": result.resultData.get("is_compliant", True),
                "warnings": result.resultData.get("warnings", []),
                "tokenTelemetry": self._build_telemetry(
                    context_pkt, result.resultData, provider_config
                ),
                "payload": command.payload,
            }
        )

    async def handle_battery_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process an electrical battery calculation intent: resolve bounded context and return dry-run preview."""
        project_id = str(msg.get("projectId") or "")
        panel_id = str(msg.get("panelId", "facp-01"))
        spec = msg.get("batterySpec", {})
        provider_config = msg.get("providerConfig") or msg.get("llm") or {}

        current_rev = self.command_bus.get_project_revision(project_id)

        standby_load_amps = float(spec.get("standby_load_amps", 0.5))
        alarm_load_amps = float(spec.get("alarm_load_amps", 2.0))
        standby_hours = float(spec.get("standby_hours", 24.0))
        alarm_hours = float(spec.get("alarm_hours", 5.0 / 60.0))
        min_temperature_c = float(spec.get("min_temperature_c", 20.0))
        service_life_years = float(spec.get("service_life_years", 5.0))
        battery_type = str(spec.get("battery_type", "vrla")).strip().lower()
        installed_ah = float(spec["installed_ah"]) if spec.get("installed_ah") is not None else None
        aging_factor = float(spec.get("aging_factor", 1.25))

        context_pkt = self.context_resolver.resolve_battery_context(
            project_id=project_id,
            panel_id=panel_id,
            revision=current_rev,
            battery_spec={
                "standby_load_amps": standby_load_amps,
                "alarm_load_amps": alarm_load_amps,
                "standby_hours": standby_hours,
                "alarm_hours": alarm_hours,
                "min_temperature_c": min_temperature_c,
                "service_life_years": service_life_years,
                "battery_type": battery_type,
                "installed_ah": installed_ah,
                "aging_factor": aging_factor,
            },
        )

        caps = self.capability_registry.discover(categories=["electrical"], scopes=principal.scopes)
        if not any(c.capability_id == CAP_ELECTRICAL_CALCULATE_BATTERY for c in caps):
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "NO_CAPABILITY_AVAILABLE",
                    "message": "No matching electrical battery capabilities available for user scopes.",
                }
            )
            return

        command_id = f"cmd-{uuid.uuid4().hex[:12]}"
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        command = DomainCommand(
            commandId=command_id,
            correlationId=correlation_id,
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId=project_id,
            expectedRevision=current_rev,
            timestamp=datetime.now(UTC).isoformat(),
            principal=principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "panel_id": panel_id,
                "standby_load_amps": standby_load_amps,
                "alarm_load_amps": alarm_load_amps,
                "standby_hours": standby_hours,
                "alarm_hours": alarm_hours,
                "min_temperature_c": min_temperature_c,
                "service_life_years": service_life_years,
                "battery_type": battery_type,
                "installed_ah": installed_ah,
                "aging_factor": aging_factor,
            },
        )

        result = await asyncio.to_thread(self.command_bus.execute, command)

        await websocket.send_json(
            {
                "type": "ai_battery_preview",
                "commandId": command_id,
                "correlationId": correlation_id,
                "projectId": project_id,
                "expectedRevision": current_rev,
                "capabilityId": CAP_ELECTRICAL_CALCULATE_BATTERY,
                "panelId": panel_id,
                "baseCapacityAh": result.resultData.get("base_capacity_ah", 0.0),
                "requiredAh": result.resultData.get("required_ah", 0.0),
                "installedAh": result.resultData.get("installed_ah"),
                "usableAh": result.resultData.get("usable_ah"),
                "temperatureDerating": result.resultData.get("temperature_derating", 1.0),
                "agingDerating": result.resultData.get("aging_derating", 1.0),
                "dischargeRateCorrection": result.resultData.get("discharge_rate_correction", 1.0),
                "isAdequate": result.resultData.get("is_adequate", True),
                "marginPct": result.resultData.get("margin_pct"),
                "warnings": result.resultData.get("warnings", []),
                "tokenTelemetry": self._build_telemetry(
                    context_pkt, result.resultData, provider_config
                ),
                "payload": command.payload,
            }
        )

    async def handle_import_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process an import intent: inspect staged file, generate import plan, evaluate execution policy, and return preview."""
        from backend.core.import_orchestrator import default_import_orchestrator

        file_id = str(msg.get("fileId", msg.get("file_id", "")))
        project_id = str(msg.get("projectId") or "")

        try:
            record = default_import_orchestrator.get_staged_file(file_id)
            plan = default_import_orchestrator.plan_import(file_id, project_id, principal=principal)

            await websocket.send_json(
                {
                    "type": "import_preview",
                    "fileId": file_id,
                    "projectId": project_id,
                    "filename": record.sanitized_filename,
                    "detectedFormat": record.detected_format,
                    "estimatedRooms": plan.estimated_rooms,
                    "estimatedDevices": plan.estimated_devices,
                    "estimatedLayers": plan.estimated_layers,
                    "warnings": plan.warnings,
                    "requiredPolicy": plan.required_policy,
                    "expectedRevision": plan.expected_revision,
                    "summary": plan.summary,
                }
            )
        except Exception as exc:
            logger.warning("Import intent handling failed: %s", exc)
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "IMPORT_INTENT_FAILED",
                    "message": str(exc),
                }
            )

    async def handle_approval(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process user approval: execute deterministic commit with OCC validation."""
        command_id = str(msg.get("commandId", f"cmd-{uuid.uuid4().hex[:12]}"))
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        project_id = str(msg.get("projectId") or msg.get("project_id") or "")
        capability_id = (
            msg.get("capabilityId")
            or msg.get("capability_id")
            or msg.get("action")
            or CAP_SPATIAL_PLACE_DEVICES
        )

        expected_rev_raw = msg.get("expectedRevision") if "expectedRevision" in msg else msg.get("expected_revision")
        if expected_rev_raw is None:
            if is_revision_required_for_capability(capability_id, self.capability_registry):
                await websocket.send_json(
                    {
                        "type": "ai_error",
                        "commandId": command_id,
                        "errorCode": "MISSING_EXPECTED_REVISION",
                        "message": (
                            f"Capability '{capability_id}' requires canonical project state revision binding, "
                            f"but expected_revision was not provided for project '{project_id}'."
                        ),
                    }
                )
                return
            expected_revision = None
        else:
            try:
                expected_revision = int(expected_rev_raw)
            except (ValueError, TypeError):
                await websocket.send_json(
                    {
                        "type": "ai_error",
                        "commandId": command_id,
                        "errorCode": "INVALID_EXPECTED_REVISION",
                        "message": f"expected_revision must be an integer, got: {expected_rev_raw!r}",
                    }
                )
                return

        payload = msg.get("payload", {})

        command = DomainCommand(
            commandId=command_id,
            correlationId=correlation_id,
            capabilityId=capability_id,
            projectId=project_id,
            expectedRevision=expected_revision if expected_revision is not None else 0,
            timestamp=datetime.now(UTC).isoformat(),
            principal=principal,
            riskClass="ENGINEERING_MUTATION"
            if ("electrical" in capability_id or "hydraulics" in capability_id)
            else "MEDIUM",
            isDryRun=False,
            payload=payload,
        )

        result = await asyncio.to_thread(self.command_bus.execute, command)

        if not result.success:
            if result.errorCode == "CONCURRENCY_CONFLICT":
                await websocket.send_json(
                    {
                        "type": "ai_conflict",
                        "commandId": command_id,
                        "projectId": project_id,
                        "expectedRevision": expected_revision,
                        "currentRevision": result.revision,
                        "errorCode": result.errorCode,
                        "message": result.errorMessage,
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "ai_error",
                        "commandId": command_id,
                        "errorCode": result.errorCode,
                        "message": result.errorMessage,
                    }
                )
            return

        # Success: emit committed state & audit event
        await websocket.send_json(
            {
                "type": "ai_committed",
                "commandId": command_id,
                "projectId": project_id,
                "revision": result.revision,
                "devices": result.resultData.get("devices", []),
                "circuit": result.resultData if "voltage_drop_v" in result.resultData else None,
                "hydraulic": result.resultData if "head_loss_m" in result.resultData else None,
                "battery": result.resultData
                if ("required_ah" in result.resultData or "base_capacity_ah" in result.resultData)
                else None,
                "event": result.event.to_dict() if result.event else None,
                "auditReference": result.event.auditReference if result.event else "",
                "coveragePct": result.resultData.get("coverage_pct", 100.0),
            }
        )

    async def handle_user_mutation(self, websocket: WebSocket, msg: dict[str, Any]) -> None:
        """Simulate/commit a direct manual user edit that increments canonical revision (N -> N+1)."""
        project_id = str(msg.get("projectId") or "")
        current_rev = self.command_bus.get_project_revision(project_id)
        new_rev = current_rev + 1
        self.command_bus.set_project_revision(project_id, new_rev)

        devices = msg.get("devices", [])
        await asyncio.to_thread(
            self.command_bus.save_canonical_state,
            project_id=project_id,
            state={
                "devices": devices,
                "last_mutation": "user_manual_edit",
                "revision": new_rev,
            },
            revision=new_rev,
        )

        await websocket.send_json(
            {
                "type": "user_mutation_committed",
                "projectId": project_id,
                "revision": new_rev,
                "devices": devices,
            }
        )

    @staticmethod
    def _create_progress_callback(
        websocket: WebSocket,
        loop: asyncio.AbstractEventLoop,
        workflow_id: str,
        correlation_id: str,
    ):
        """Create a thread-safe WebSocket progress frame dispatcher."""

        def _cb(
            step_idx: int,
            total_steps: int,
            node_id: str,
            elapsed_ms: float,
            status: str = "in_progress",
        ) -> None:
            frame = {
                "type": "ai_progress_frame",
                "workflowId": workflow_id,
                "correlationId": correlation_id,
                "stepIndex": step_idx,
                "totalSteps": total_steps,
                "stepId": node_id,
                "progressPct": round((step_idx / max(1, total_steps)) * 100.0, 1),
                "elapsedMs": round(elapsed_ms, 2),
                "status": status,
            }
            try:
                asyncio.run_coroutine_threadsafe(websocket.send_json(frame), loop)
            except Exception:
                pass

        return _cb

    async def handle_composite_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process natural language/composite spec intent into a multi-step DAG proposal."""
        project_id = str(msg.get("projectId") or msg.get("project_id") or "")
        expected_rev_raw = msg.get("expectedRevision") if "expectedRevision" in msg else msg.get("expected_revision")
        if expected_rev_raw is not None:
            try:
                current_rev = int(expected_rev_raw)
            except (ValueError, TypeError):
                await websocket.send_json(
                    {
                        "type": "ai_error",
                        "errorCode": "INVALID_EXPECTED_REVISION",
                        "message": f"expected_revision must be an integer, got: {expected_rev_raw!r}",
                    }
                )
                return
        else:
            current_rev = self.command_bus.get_project_revision(project_id) if project_id else 0

        # 1. Bounded Context Resolution (<= 1500 tokens)
        composite_spec = msg.get("compositeSpec", {})
        context_pkt = self.context_resolver.resolve_composite_context(
            project_id=project_id,
            revision=current_rev,
            composite_spec=composite_spec,
        )

        # 2. Construct or extract DAG
        nodes_data = msg.get("nodes")
        if nodes_data and isinstance(nodes_data, list):
            nodes = [WorkflowNode.from_dict(n) for n in nodes_data]
            dag = CompositeWorkflowDAG(nodes=nodes)
        else:
            rb = composite_spec.get(
                "room_bounds", {"width_m": 12.0, "length_m": 16.0, "ceiling_height_m": 3.2}
            )
            circ = composite_spec.get(
                "circuit",
                {"circuit_id": "nac-01", "current_a": 2.0, "one_way_length_m": 35.0, "awg": "14"},
            )
            bat = composite_spec.get(
                "battery",
                {
                    "panel_id": "facp-01",
                    "standby_load_amps": 0.8,
                    "alarm_load_amps": 3.0,
                    "installed_ah": 55.0,
                },
            )

            dag = CompositeWorkflowDAG(
                [
                    WorkflowNode(
                        node_id="step-1-spatial",
                        capability_id=CAP_SPATIAL_PLACE_DEVICES,
                        dependencies=[],
                        payload_template={
                            "room_id": "main-hall",
                            "width_m": rb.get("width_m", 12.0),
                            "length_m": rb.get("length_m", 16.0),
                            "ceiling_height_m": rb.get("ceiling_height_m", 3.2),
                        },
                        description="Place initiating devices per NFPA 72 §17",
                    ),
                    WorkflowNode(
                        node_id="step-2-electrical",
                        capability_id=CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
                        dependencies=["step-1-spatial"],
                        payload_template={
                            "circuit_id": circ.get("circuit_id", "nac-01"),
                            "current_a": circ.get("current_a", 2.0),
                            "one_way_length_m": circ.get("one_way_length_m", 35.0),
                            "awg": circ.get("awg", "14"),
                        },
                        description="Calculate NAC circuit voltage drop",
                    ),
                    WorkflowNode(
                        node_id="step-3-battery",
                        capability_id=CAP_ELECTRICAL_CALCULATE_BATTERY,
                        dependencies=["step-2-electrical"],
                        payload_template={
                            "panel_id": bat.get("panel_id", "facp-01"),
                            "standby_load_amps": bat.get("standby_load_amps", 0.8),
                            "alarm_load_amps": bat.get("alarm_load_amps", 3.0),
                            "installed_ah": bat.get("installed_ah", 55.0),
                        },
                        description="Size secondary battery power supply",
                    ),
                ]
            )

        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        provider_config = msg.get("providerConfig") or msg.get("llm") or {}
        governance_policy = msg.get("governance") or msg.get("governancePolicy")
        auto_rollback = (
            bool(governance_policy.get("autoRollbackOnPhysicsWarning", False))
            if isinstance(governance_policy, dict)
            else False
        )

        # 3. Dry-run pipeline execution over EphemeralStateOverlay in worker thread
        loop = asyncio.get_running_loop()
        progress_cb = self._create_progress_callback(websocket, loop, workflow_id, correlation_id)

        executor = WorkflowExecutor(self.capability_registry, self.command_bus.state_store)
        res = await asyncio.to_thread(
            executor.execute,
            dag=dag,
            project_id=project_id,
            expected_revision=current_rev,
            principal=principal,
            is_dry_run=True,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            auto_rollback_on_warning=auto_rollback,
            governance_policy=governance_policy,
            on_step_progress=progress_cb,
        )

        if not res.success:
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "workflowId": workflow_id,
                    "errorCode": res.error_code or "WORKFLOW_EXECUTION_FAILED",
                    "message": res.error_message or "Composite workflow dry-run failed.",
                }
            )
            return

        # 4. Send composite preview to client
        await websocket.send_json(
            {
                "type": "ai_composite_preview",
                "workflowId": workflow_id,
                "correlationId": correlation_id,
                "projectId": project_id,
                "expectedRevision": current_rev,
                "dag": dag.to_dict(),
                "stepResults": [s.to_dict() for s in res.step_results],
                "projectedState": res.projected_state,
                "combinedAuditDigest": res.combined_audit_digest,
                "tokenTelemetry": self._build_telemetry(
                    context_pkt, res.projected_state, provider_config
                ),
                "isCompliant": True,
            }
        )

    async def handle_composite_approval(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process user approval for composite workflow: atomically commit all steps at expectedRevision."""
        project_id = str(msg.get("projectId") or msg.get("project_id") or "")
        workflow_id = str(msg.get("workflowId", f"wf-{uuid.uuid4().hex[:12]}"))
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        dag_data = msg.get("dag", {})

        if not dag_data or "nodes" not in dag_data:
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "workflowId": workflow_id,
                    "errorCode": "INVALID_WORKFLOW_PAYLOAD",
                    "message": "Approval message missing DAG structure.",
                }
            )
            return

        expected_rev_raw = msg.get("expectedRevision") if "expectedRevision" in msg else msg.get("expected_revision")
        if expected_rev_raw is None:
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "workflowId": workflow_id,
                    "errorCode": "MISSING_EXPECTED_REVISION",
                    "message": f"Composite approval mutates project state and requires expectedRevision for project '{project_id}'.",
                }
            )
            return
        try:
            expected_revision = int(expected_rev_raw)
        except (ValueError, TypeError):
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "workflowId": workflow_id,
                    "errorCode": "INVALID_EXPECTED_REVISION",
                    "message": f"expected_revision must be an integer, got: {expected_rev_raw!r}",
                }
            )
            return

        dag = CompositeWorkflowDAG.from_dict(dag_data)
        loop = asyncio.get_running_loop()
        progress_cb = self._create_progress_callback(websocket, loop, workflow_id, correlation_id)

        executor = WorkflowExecutor(self.capability_registry, self.command_bus.state_store)

        res = await asyncio.to_thread(
            executor.execute,
            dag=dag,
            project_id=project_id,
            expected_revision=expected_revision,
            principal=principal,
            is_dry_run=False,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            on_step_progress=progress_cb,
        )

        if not res.success:
            if res.error_code == "CONCURRENCY_CONFLICT":
                await websocket.send_json(
                    {
                        "type": "ai_conflict",
                        "workflowId": workflow_id,
                        "projectId": project_id,
                        "expectedRevision": expected_revision,
                        "currentRevision": res.new_revision,
                        "errorCode": res.error_code,
                        "message": res.error_message,
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "ai_error",
                        "workflowId": workflow_id,
                        "errorCode": res.error_code or "COMPOSITE_COMMIT_FAILED",
                        "message": res.error_message or "Composite workflow commit failed.",
                    }
                )
            return

        # Success: emit composite committed state & audit event
        await websocket.send_json(
            {
                "type": "ai_composite_committed",
                "workflowId": workflow_id,
                "projectId": project_id,
                "revision": res.new_revision,
                "projectedState": res.projected_state,
                "stepResults": [s.to_dict() for s in res.step_results],
                "combinedAuditDigest": res.combined_audit_digest,
                "event": res.event.to_dict() if res.event else None,
            }
        )

    async def handle_autonomous_workflow_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process natural language or structured autonomous workflow intent (Phase 6).
        Synthesizes DAG plan, evaluates policy, generates dry-run preview, and emits ai_autonomous_plan.
        """
        from backend.core.workflow_planner import AutonomousPlannerError, default_workflow_planner

        prompt = str(msg.get("prompt") or msg.get("message") or "").strip()
        project_id = str(msg.get("projectId") or "")
        expected_rev = msg.get("expectedRevision")
        expected_revision = int(expected_rev) if expected_rev is not None else None
        composite_spec = msg.get("compositeSpec") or msg.get("spec") or {}
        approval_mode = str(msg.get("approvalMode", "AUTO"))
        governance_policy = msg.get("governance") or msg.get("governancePolicy")

        try:
            plan = await asyncio.to_thread(
                default_workflow_planner.plan_workflow,
                prompt=prompt or "Autonomous engineering analysis and layout",
                principal=principal,
                project_id=project_id,
                expected_revision=expected_revision,
                composite_spec=composite_spec,
                approval_mode=approval_mode,
                governance_policy=governance_policy,
            )

            await websocket.send_json(
                {
                    "type": "ai_autonomous_plan",
                    "plan": plan.to_dict(),
                    "planId": plan.plan_id,
                    "projectId": plan.project_id,
                    "expectedRevision": plan.expected_revision,
                    "intentSummary": plan.intent_summary,
                    "intentCategory": plan.intent_category,
                    "steps": [s.to_dict() for s in plan.steps],
                    "dag": plan.dag,
                    "requiresHumanApproval": plan.requires_human_approval,
                    "overallPolicyDecision": plan.overall_policy_decision,
                    "projectedState": plan.projected_state,
                    "combinedAuditDigest": plan.combined_audit_digest,
                    "telemetry": plan.token_telemetry,
                }
            )

            # If autoExecute flag is set and all steps are AUTO_APPROVED, launch AgentRun immediately
            if (
                msg.get("autoExecute")
                and not plan.requires_human_approval
                and plan.overall_policy_decision == "AUTO_APPROVED"
            ):
                run = await asyncio.to_thread(
                    default_workflow_planner.execute_plan,
                    plan,
                    principal=principal,
                    approval_mode=approval_mode,
                    conversation_id=str(msg.get("conversationId", "")),
                    governance_policy=governance_policy,
                )
                await _emit_run_state(websocket, run)

        except AutonomousPlannerError as exc:
            logger.warning("Autonomous workflow planning failed: %s", exc)
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "AUTONOMOUS_PLANNING_FAILED",
                    "message": str(exc),
                }
            )
        except Exception as exc:
            logger.exception("Unexpected error in autonomous workflow planning: %s", exc)
            await websocket.send_json(
                {
                    "type": "ai_error",
                    "errorCode": "PLANNING_ERROR",
                    "message": "Autonomous workflow planning failed.",
                }
            )


default_orchestration_service = AIOrchestrationService()

# Phase 1: durable Agent Run lifecycle orchestrator (server-authoritative).
# Shares the same default CommandBus / capability registry as the orchestration
# service above so both pipelines operate on one canonical revision ledger.
default_agent_run_orchestrator = AgentRunOrchestrator()

_RUN_ERROR_MAP: tuple[tuple[type[Exception], str], ...] = (
    (RunNotFoundError, "RUN_NOT_FOUND"),
    (RunPermissionError, "RUN_FORBIDDEN"),
    (InvalidRunStateError, "INVALID_RUN_STATE"),
    (StaleApprovalError, "STALE_APPROVAL"),
    (ApprovalAlreadyDecidedError, "APPROVAL_ALREADY_DECIDED"),
    (PendingApprovalNotFoundError, "APPROVAL_NOT_FOUND"),
)


def _run_error_code(exc: Exception) -> str:
    for exc_type, code in _RUN_ERROR_MAP:
        if isinstance(exc, exc_type):
            return code
    if isinstance(exc, ValueError):
        return "INVALID_RUN_PLAN"
    return "RUN_OPERATION_FAILED"


def _run_state_frame(run) -> dict[str, Any]:
    """Build a wire frame describing persisted Agent Run state."""
    return {
        "type": "run_status_update",
        "runId": run.run_id,
        "projectId": run.project_id,
        "status": run.status.value,
        "approvalMode": run.approval_mode.value,
        "currentStep": run.current_step,
        "completedSteps": list(run.completed_steps),
        "failedSteps": list(run.failed_steps),
        "pendingApprovalId": run.pending_approval_id,
        "recoveryState": dict(run.recovery_state),
        "auditReference": run.audit_reference,
        "version": run.version,
    }


async def _emit_run_state(websocket: WebSocket, run) -> None:
    """Emit the run state frame plus an approval_request frame when halted."""
    await websocket.send_json(_run_state_frame(run))
    if run.status.value == "WAITING_APPROVAL" and run.pending_approval_id:
        pa = default_agent_run_orchestrator._store.get_pending_approval(run.pending_approval_id)
        if pa is not None:
            await websocket.send_json(
                {
                    "type": "approval_request",
                    "approvalId": pa.approval_id,
                    "runId": pa.run_id,
                    "stepId": pa.step_id,
                    "projectId": pa.project_id,
                    "projectRevision": pa.project_revision,
                    "capabilityId": pa.capability_id,
                    "policyResult": pa.policy_result,
                    "stepPayloadHash": pa.step_payload_hash,
                }
            )


async def _run_operation(websocket: WebSocket, principal: AuthenticatedPrincipal, op) -> None:
    """Execute a synchronous run-lifecycle operation off the event loop."""
    try:
        run = await asyncio.to_thread(op)
    except Exception as exc:
        logger.warning("Agent Run operation failed: %s", exc)
        # Sanitize unexpected (non-domain) errors before echoing to the wire,
        # mirroring the REST surface's stack-trace-exposure posture.
        if _run_error_code(exc) == "RUN_OPERATION_FAILED":
            detail = "Agent Run operation failed (details sanitized)"
        else:
            detail = str(exc)[:300]
        await websocket.send_json(
            {
                "type": "run_error",
                "errorCode": _run_error_code(exc),
                "message": detail,
            }
        )
        return
    await _emit_run_state(websocket, run)


async def _handle_run_start(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    """run_start: create a durable Agent Run and begin policy-gated execution."""
    steps = msg.get("steps")
    if not isinstance(steps, list) or not steps:
        await websocket.send_json(
            {
                "type": "run_error",
                "errorCode": "INVALID_RUN_PLAN",
                "message": "run_start requires a non-empty 'steps' array.",
            }
        )
        return

    project_id = str(msg.get("projectId") or msg.get("project_id") or "")
    model_id = msg.get("modelId") or msg.get("model_id")
    expected_rev = (
        msg.get("expectedRevision")
        if msg.get("expectedRevision") is not None
        else msg.get("expected_revision")
    )
    if expected_rev is not None:
        try:
            expected_rev = int(expected_rev)
        except (ValueError, TypeError):
            await websocket.send_json(
                {
                    "type": "run_error",
                    "errorCode": "INVALID_EXPECTED_REVISION",
                    "message": f"expected_revision must be an integer, got: {msg.get('expectedRevision', msg.get('expected_revision'))!r}",
                }
            )
            return

    # Derive targeted capabilities to inspect revision_binding contract (D-1b)
    target_cap_ids: list[str] = []
    for step in steps:
        if isinstance(step, dict):
            cid = step.get("capability_id") or step.get("capabilityId") or step.get("action")
            if cid and isinstance(cid, str):
                target_cap_ids.append(cid)

    plan_obj = msg.get("plan")
    if isinstance(plan_obj, dict):
        plan_steps = plan_obj.get("steps") or plan_obj.get("nodes") or []
        if isinstance(plan_steps, list):
            for ps in plan_steps:
                if isinstance(ps, dict):
                    cid = ps.get("capability_id") or ps.get("capabilityId") or ps.get("action")
                    if cid and isinstance(cid, str):
                        target_cap_ids.append(cid)

    msg_cap_id = msg.get("capability_id") or msg.get("capabilityId")
    if msg_cap_id and isinstance(msg_cap_id, str):
        target_cap_ids.append(msg_cap_id)

    requires_canonical_revision = False
    for cid in target_cap_ids:
        cap_def = default_capability_registry.get(cid)
        if (
            cap_def
            and cap_def.contract
            and cap_def.contract.revision_binding == "canonical_project_state"
        ):
            requires_canonical_revision = True
            break

    if requires_canonical_revision and expected_rev is None:
        await websocket.send_json(
            {
                "type": "run_error",
                "errorCode": "MISSING_EXPECTED_REVISION",
                "message": (
                    f"run_start targets capability requiring canonical project state revision binding, "
                    f"but expected_revision was not provided for project '{project_id}'."
                ),
            }
        )
        return

    # Context reconciliation & OCC validation if project_id is specified
    if project_id:
        import backend.database as _db_mod

        db = getattr(default_agent_run_orchestrator._store, "_db", None) or _db_mod.get_db()
        project = db.get_project(project_id)
        if project:
            author = project.get("author", "")
            principal_ids = {
                getattr(principal, "user_id", None),
                getattr(principal, "name", None),
                getattr(principal, "email", None),
            } - {None, ""}
            if principal.role != "admin" and author and author not in principal_ids:
                await websocket.send_json(
                    {
                        "type": "run_error",
                        "errorCode": "PROJECT_NOT_FOUND",
                        "message": f"Project '{project_id}' not found",
                    }
                )
                return

            canonical_model_id = project.get("modelId") or f"dt-{project_id}"
            if model_id and model_id != canonical_model_id:
                await websocket.send_json(
                    {
                        "type": "run_error",
                        "errorCode": "INVALID_MODEL_ID",
                        "message": f"Model '{model_id}' does not belong to project '{project_id}'",
                    }
                )
                return

            raw_eids = msg.get("entity_ids") if "entity_ids" in msg else msg.get("entityIds")
            all_eids = [str(e) for e in raw_eids if e] if isinstance(raw_eids, list) else []
            single_eid = msg.get("entity_id") if "entity_id" in msg else msg.get("entityId")
            if single_eid and str(single_eid) not in all_eids:
                all_eids.append(str(single_eid))
            for eid in all_eids:
                if not db.get_device(project_id, eid):
                    await websocket.send_json(
                        {
                            "type": "run_error",
                            "errorCode": "ENTITY_NOT_FOUND",
                            "message": f"Entity '{eid}' does not belong to project '{project_id}'",
                        }
                    )
                    return

        # Check revision against state_store or project
        canonical_rev = default_agent_run_orchestrator._bus.state_store.get_project_revision(
            project_id
        )
        if canonical_rev is None and project:
            canonical_rev = project.get("revision", 1)
        if canonical_rev is not None and expected_rev is not None and expected_rev != canonical_rev:
            await websocket.send_json(
                {
                    "type": "run_error",
                    "errorCode": "REVISION_CONFLICT",
                    "message": f"Project revision conflict: expected {expected_rev}, current canonical is {canonical_rev}",
                }
            )
            return

    def _op():
        return default_agent_run_orchestrator.start_run(
            principal,
            project_id=project_id,
            steps=steps,
            approval_mode=str(msg.get("approvalMode", "AUTO")),
            conversation_id=str(msg.get("conversationId", "")),
            plan=msg.get("plan") or None,
            governance_policy=msg.get("governance") or msg.get("governancePolicy") or None,
        )

    await _run_operation(websocket, principal, _op)


async def _handle_run_status(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    run_id = str(msg.get("runId", ""))
    await _run_operation(
        websocket,
        principal,
        lambda: default_agent_run_orchestrator.get_run_status(principal.user_id, run_id),
    )


async def _handle_run_resume(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    run_id = str(msg.get("runId", ""))
    await _run_operation(
        websocket,
        principal,
        lambda: default_agent_run_orchestrator.resume_run(principal.user_id, run_id),
    )


async def _handle_run_pause(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    run_id = str(msg.get("runId", ""))
    await _run_operation(
        websocket,
        principal,
        lambda: default_agent_run_orchestrator.pause_run(principal.user_id, run_id),
    )


async def _handle_run_cancel(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    run_id = str(msg.get("runId", ""))
    await _run_operation(
        websocket,
        principal,
        lambda: default_agent_run_orchestrator.cancel_run(principal.user_id, run_id),
    )


async def _handle_run_retry(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    run_id = str(msg.get("runId", ""))
    await _run_operation(
        websocket,
        principal,
        lambda: default_agent_run_orchestrator.retry_run(principal.user_id, run_id),
    )


async def _handle_approval_decision(
    websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
) -> None:
    approval_id = str(msg.get("approvalId", ""))
    decision = str(msg.get("decision", "")).upper()
    reason = str(msg.get("reason", ""))[:2000]
    if decision not in ("APPROVED", "REJECTED"):
        await websocket.send_json(
            {
                "type": "run_error",
                "errorCode": "INVALID_APPROVAL_DECISION",
                "message": "approval_decision requires decision APPROVED or REJECTED.",
            }
        )
        return
    await _run_operation(
        websocket,
        principal,
        lambda: default_agent_run_orchestrator.decide_approval(
            principal.user_id, approval_id, decision, reason=reason
        ),
    )


async def _handle_agent_message(
    websocket: WebSocket, msg: dict, principal: AuthenticatedPrincipal | None = None
) -> None:
    """Dispatch a single decoded agent message."""
    if not _validate_agent_nonce(msg):
        return

    msg_type = msg.get("type")
    if msg_type == "response":
        await _handle_response_message(msg)
    elif msg_type == "ping":
        await _handle_ping_message(websocket)
    elif (
        msg_type
        in ("ai_plan_workflow", "plan_workflow", "ai_autonomous_intent", "autonomous_intent")
        and principal
    ):
        await default_orchestration_service.handle_autonomous_workflow_intent(
            websocket, principal, msg
        )
    elif msg_type in ("ai_intent", "intent_submit") and principal:
        await default_orchestration_service.handle_intent(websocket, principal, msg)
    elif msg_type in ("ai_electrical_intent", "electrical_intent") and principal:
        await default_orchestration_service.handle_electrical_intent(websocket, principal, msg)
    elif msg_type in ("ai_battery_intent", "battery_intent") and principal:
        await default_orchestration_service.handle_battery_intent(websocket, principal, msg)
    elif msg_type in ("ai_hydraulic_intent", "hydraulic_intent") and principal:
        await default_orchestration_service.handle_hydraulic_intent(websocket, principal, msg)
    elif msg_type in ("ai_composite_intent", "composite_intent") and principal:
        await default_orchestration_service.handle_composite_intent(websocket, principal, msg)
    elif msg_type in ("ai_import_intent", "import_intent") and principal:
        await default_orchestration_service.handle_import_intent(websocket, principal, msg)
    elif (
        msg_type in ("ai_approve_composite", "approve_composite", "composite_approval")
        and principal
    ):
        await default_orchestration_service.handle_composite_approval(websocket, principal, msg)
    elif msg_type in ("ai_approve", "command_approve", "approval") and principal:
        await default_orchestration_service.handle_approval(websocket, principal, msg)
    elif msg_type in ("user_mutate", "manual_edit") and principal:
        await default_orchestration_service.handle_user_mutation(websocket, msg)
    elif msg_type == "run_start" and principal:
        await _handle_run_start(websocket, principal, msg)
    elif msg_type == "run_status" and principal:
        await _handle_run_status(websocket, principal, msg)
    elif msg_type == "run_resume" and principal:
        await _handle_run_resume(websocket, principal, msg)
    elif msg_type == "run_pause" and principal:
        await _handle_run_pause(websocket, principal, msg)
    elif msg_type == "run_cancel" and principal:
        await _handle_run_cancel(websocket, principal, msg)
    elif msg_type == "run_retry" and principal:
        await _handle_run_retry(websocket, principal, msg)
    elif msg_type == "approval_decision" and principal:
        await _handle_approval_decision(websocket, principal, msg)


async def _handle_response_message(msg: dict) -> None:
    """Handle a response message from the agent."""
    cmd_id = msg.get("id")
    payload = msg.get("payload")
    if cmd_id is not None:
        future = agent_response_futures.get(str(cmd_id))
        if future is not None:
            future.set_result(payload)


async def _handle_ping_message(websocket: WebSocket) -> None:
    """Handle a ping message from the agent."""
    await websocket.send_json({"type": "pong"})


WS_HEARTBEAT_TIMEOUT_SECONDS = 30.0
WS_PING_INTERVAL_SECONDS = 25.0  # send ping 5s before timeout deadline


async def _revalidate_api_key(api_key: str) -> bool:
    """Return ``True`` if *api_key* is still valid and carries the required permission."""
    try:
        info = validate_api_key(api_key)
        return info is not None and has_permission(info.role, Permission.CALCULATION_EXECUTE)
    except Exception:
        return False


async def _wait_for_pong(pong_flag: dict[str, bool], timeout: float) -> bool:
    """Poll *pong_flag* every 0.5 s for up to *timeout* seconds.

    Returns ``True`` as soon as the flag is set, ``False`` on timeout.
    """
    remaining = timeout
    while remaining > 0:
        await asyncio.sleep(0.5)
        remaining -= 0.5
        if pong_flag["value"]:
            return True
    return False


async def _check_api_key_revoked(websocket: WebSocket, api_key: str) -> bool:
    """Re-authenticate API key; close socket and return True if revoked."""
    if not api_key or await _revalidate_api_key(api_key):
        return False
    logger.warning("Agent WebSocket heartbeat: API key revoked or expired — terminating connection")
    await websocket.close(code=4401)
    return True


async def _handle_pong_timeout(
    websocket: WebSocket,
    pong_received: dict[str, bool],
) -> bool:
    """Wait for pong; close socket and return True if timeout occurs."""
    if await _wait_for_pong(pong_received, WS_HEARTBEAT_TIMEOUT_SECONDS):
        return False
    logger.warning(
        "Agent WebSocket heartbeat timeout: no pong within %ss — terminating connection",
        WS_HEARTBEAT_TIMEOUT_SECONDS,
    )
    await _safe_close_websocket(websocket, code=4008)
    return True


async def _safe_close_websocket(websocket: WebSocket, code: int) -> None:
    """Safely close a websocket connection, suppressing any exceptions."""
    try:
        await websocket.close(code=code)
    except Exception:
        pass


def _run_heartbeat_loop(
    websocket: WebSocket, api_key: str = ""
) -> tuple[dict[str, bool], Callable[[], Coroutine[Any, Any, None]]]:
    """Active ping/pong heartbeat loop with periodic token re-authentication.

    Sends a ping every WS_PING_INTERVAL_SECONDS. After sending, waits up
    to WS_HEARTBEAT_TIMEOUT_SECONDS for a pong response. Also re-verifies
    API key validity on every cycle to detect revoked keys/expired sessions.
    If no pong arrives or key is revoked, closes socket immediately.
    """
    _pong_received: dict[str, bool] = {"value": True}  # mutable flag shared with message handler

    async def _ping_cycle() -> None:
        while True:
            await asyncio.sleep(WS_PING_INTERVAL_SECONDS)
            # Re-authenticate API key on every heartbeat cycle to prevent session hijacking
            if await _check_api_key_revoked(websocket, api_key):
                return

            _pong_received["value"] = False
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                return

            if await _handle_pong_timeout(websocket, _pong_received):
                return

    return _pong_received, _ping_cycle


@router.websocket("/ws")
async def agent_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for the local agent.

    Security:
      - Origin validated against CORS_ALLOWED_ORIGINS (CSWSH protection).
      - API key verified before handshake is accepted.
      - Active 30-second ping/pong heartbeat: if client fails to pong,
        socket is terminated immediately with code 4008.
    """
    api_key_info, raw_api_key = await _authenticate_agent_websocket(websocket)
    if api_key_info is None:
        return  # already closed with code 4003

    await websocket.accept()
    logger.info("Local Agent connected to WebSocket successfully")

    agent_type = "autocad_revit"
    _register_agent(websocket, agent_type)

    pong_flag, ping_cycle_fn = _run_heartbeat_loop(websocket, api_key=raw_api_key)

    principal = AuthenticatedPrincipal(
        user_id=getattr(api_key_info, "name", "agent_user"),
        email=getattr(api_key_info, "email", "agent@bazspark.com"),
        role=getattr(api_key_info, "role", "engineer"),
        scopes=["spatial:write", "compliance:read"],
        is_authenticated=True,
    )

    async def _message_loop() -> None:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # A pong response from the client resets the heartbeat flag
                if msg.get("type") == "pong":
                    pong_flag["value"] = True
                else:
                    await _handle_agent_message(websocket, msg, principal)
            except Exception as e:
                logger.warning("Error handling agent message: %s", e)

    try:
        await asyncio.gather(_message_loop(), ping_cycle_fn())
    except WebSocketDisconnect:
        logger.info("Local Agent disconnected from WebSocket")
    except Exception as e:
        logger.warning("Agent WebSocket session ended: %s", e)
    finally:
        _cleanup_agent(websocket, agent_type)


def has_active_agent(agent_type: str = "autocad_revit") -> bool:
    """Check if there is at least one active agent connected across cluster."""
    bucket = _resolve_agent_bucket(agent_type)
    if len(active_agents.get(bucket, [])) > 0:
        return True
    try:
        from backend.core.shared_state import default_shared_state
        return default_shared_state.has_active_agent(bucket)
    except Exception:
        return False


# ── ROOT-CAUSE FIX (found by the D3 E2E chain test) ─────────────────────────
# The WebSocket endpoint registers every desktop agent under the single
# combined bucket "autocad_revit", but routers call
# ``send_agent_command("revit", …)`` / ``send_agent_command("autocad", …)``.
# The raw dict lookup therefore always missed and EVERY remote-control
# request returned 503 even with a live agent connected. One desktop agent
# process serves both CAD applications, so service-level types resolve to
# the shared bucket while keeping their own action prefix on the wire.
_AGENT_TYPE_BUCKETS: dict[str, str] = {
    "revit": "autocad_revit",
    "autocad": "autocad_revit",
    "autocad_revit": "autocad_revit",
}


def _resolve_agent_bucket(agent_type: str) -> str:
    """Map a service-level agent type onto its connection registry bucket."""
    return _AGENT_TYPE_BUCKETS.get(agent_type, agent_type)


def _validate_command_against_registry(agent_type: str, action: str, args: dict[str, Any]) -> None:
    """
    D4 FIX: every LLM-planned (or REST-driven) command MUST exist in
    core/command_registry.json before it is dispatched to a desktop agent.
    Anything unregistered — or missing required params — is hard-rejected.
    """
    try:
        from core import command_registry as _registry
    except Exception as e:  # noqa: BLE001
        # Fail closed: without the registry we refuse to forward commands.
        raise HTTPException(
            status_code=503,
            detail="Command registry unavailable — refusing to dispatch desktop commands.",
        ) from e

    if not _registry.is_allowed(agent_type, action):
        logger.warning(
            "Rejected %s/%s — not present in command registry allow-list", agent_type, action
        )
        raise HTTPException(
            status_code=400,
            detail=f"Command '{agent_type}/{action}' is not allowed (not in command registry).",
        )
    error = _registry.validate_params(agent_type, action, args)
    if error:
        raise HTTPException(status_code=400, detail=error)


async def send_agent_command(
    agent_type: str, action: str, args: dict[str, Any], timeout: float = 30.0
) -> Any:
    """
    Send a command to the active agent and await the response.

    VERIFY-003 FIX: ``_register_agent`` enforces a single active agent per
    type (newest wins), so ``agents[0]`` here is always the most recently
    authenticated connection — a stale/rogue socket cannot sit ahead of the
    real agent in the registry and intercept commands.

    D4 FIX: commands are validated against core/command_registry.json
    (allow-list + required params) before leaving the server.
    """
    agents = active_agents.get(_resolve_agent_bucket(agent_type), [])
    if not agents:
        raise HTTPException(status_code=503, detail="No active local agent connected.")

    _validate_command_against_registry(agent_type, action, args)

    websocket = agents[0]
    ws_id = str(id(websocket))
    cmd_id = str(uuid.uuid4())
    future = asyncio.get_running_loop().create_future()
    agent_response_futures[cmd_id] = future

    # Track future ownership for cleanup on disconnect
    if ws_id not in _agent_pending_commands:
        _agent_pending_commands[ws_id] = set()
    _agent_pending_commands[ws_id].add(cmd_id)

    lock = get_agent_lock(websocket)
    async with lock:
        try:
            await websocket.send_json(
                {"type": "command", "id": cmd_id, "action": f"{agent_type}/{action}", "args": args}
            )
            async with asyncio.timeout(timeout):
                response = await future
            if isinstance(response, dict) and "error" in response:
                raise HTTPException(status_code=400, detail=response["error"])
            return response
        except TimeoutError as exc:
            logger.warning("Agent command %s timed out after %s seconds", action, timeout)
            raise HTTPException(
                status_code=504, detail="Local Agent command execution timed out."
            ) from exc
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.exception("Error executing agent command %s: %s", action, e)
            raise HTTPException(
                status_code=502, detail=f"Failed to execute local agent command: {e}"
            )
        finally:
            agent_response_futures.pop(cmd_id, None)
            # Clean up tracking
            pending = _agent_pending_commands.get(ws_id)
            if pending is not None:
                pending.discard(cmd_id)
                if not pending:
                    _agent_pending_commands.pop(ws_id, None)


# ── Live Provider Ping Endpoint (Phase 3.1) ──────────────────────────────────


class PingProviderRequest(BaseModel):
    provider: str = Field(..., description="Target provider: anthropic, gemini, openai, ollama")
    baseUrl: str | None = Field(default=None, description="Optional custom base URL")
    apiKey: str | None = Field(
        default=None, description="Ephemeral API key (never logged/persisted)"
    )
    modelName: str | None = Field(default=None, description="Target model name")


class PingProviderResponse(BaseModel):
    success: bool
    latencyMs: float
    error: str | None = None


@router.post(
    "/ping-provider",
    response_model=PingProviderResponse,
    dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))],
)
async def ping_provider_endpoint(
    req: PingProviderRequest,
) -> PingProviderResponse:
    """Execute a live zero-token probe/ping to the target LLM provider.

    Enforces SSRF protection, hard 5.0-second timeout, and zero API key logging.
    """
    success, latency_ms, error = await ping_provider(
        provider=req.provider,
        base_url=req.baseUrl,
        api_key=req.apiKey,
        model_name=req.modelName,
    )
    return PingProviderResponse(
        success=success,
        latencyMs=latency_ms,
        error=error,
    )
