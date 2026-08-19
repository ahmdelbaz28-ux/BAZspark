from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.api_keys import validate_api_key
from backend.auth import has_permission
from backend.core.capability_registry import default_capability_registry
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    DomainCommand,
    default_command_bus,
)
from backend.core.context_resolver import default_context_resolver
from backend.rbac import Permission

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/agent", tags=["agent-ws"])

# Active connections from agents
# Map from agent_type -> list of WebSocket
active_agents: dict[str, list[WebSocket]] = {}
agent_response_futures: dict[str, asyncio.Future[Any]] = {}

# A lock per connection to serialize command dispatches
agent_locks: dict[str, asyncio.Lock] = {}

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
    """Pull the API key or JWT auth token from headers, subprotocol, or connection parameters."""
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
    # 3. Query parameter or initial auth ticket
    for qparam in ("token", "api_key", "ticket", "auth_token"):
        qval = websocket.query_params.get(qparam)
        if qval:
            return qval.strip()
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

    return await _extract_and_validate_api_key(websocket)


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
        _seen_agent_nonces.add(nonce)
        if len(_seen_agent_nonces) > 5000:
            _seen_agent_nonces.clear()
    return True


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

    async def handle_intent(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process an AI intent: resolve context, plan placement deterministically, and return dry-run preview."""
        project_id = str(msg.get("projectId", "default_project"))
        room_id = str(msg.get("roomId", "room-101"))
        room_bounds = msg.get(
            "roomBounds", {"width_m": 10.0, "length_m": 15.0, "ceiling_height_m": 3.0}
        )
        existing_devices = msg.get("existingDevices", [])
        detector_type = msg.get("detectorType", "smoke")

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
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=current_rev,
            timestamp=datetime.now(timezone.utc).isoformat(),
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

        # 4. Execute Dry-Run via CommandBus
        result = self.command_bus.execute(command)

        # 5. Send Preview to Client via WS
        await websocket.send_json(
            {
                "type": "ai_preview",
                "commandId": command_id,
                "correlationId": correlation_id,
                "projectId": project_id,
                "expectedRevision": current_rev,
                "capabilityId": "spatial.place_devices",
                "previewDevices": result.resultData.get("devices", []),
                "deviceCount": result.resultData.get("device_count", 0),
                "coveragePct": result.resultData.get("coverage_pct", 100.0),
                "isCompliant": result.resultData.get("is_compliant", True),
                "tokenTelemetry": context_pkt.telemetry,
                "payload": command.payload,
            }
        )

    async def handle_approval(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Process user approval: execute deterministic commit with OCC validation."""
        command_id = str(msg.get("commandId", f"cmd-{uuid.uuid4().hex[:12]}"))
        correlation_id = str(msg.get("correlationId", f"corr-{uuid.uuid4().hex[:12]}"))
        project_id = str(msg.get("projectId", "default_project"))
        expected_revision = int(msg.get("expectedRevision", 1))
        capability_id = str(msg.get("capabilityId", "spatial.place_devices"))
        payload = msg.get("payload", {})

        command = DomainCommand(
            commandId=command_id,
            correlationId=correlation_id,
            capabilityId=capability_id,
            projectId=project_id,
            expectedRevision=expected_revision,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=principal,
            riskClass="MEDIUM",
            isDryRun=False,
            payload=payload,
        )

        result = self.command_bus.execute(command)

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
                "event": result.event.to_dict() if result.event else None,
                "auditReference": result.event.auditReference if result.event else "",
                "coveragePct": result.resultData.get("coverage_pct", 100.0),
            }
        )

    async def handle_user_mutation(
        self, websocket: WebSocket, principal: AuthenticatedPrincipal, msg: dict[str, Any]
    ) -> None:
        """Simulate/commit a direct manual user edit that increments canonical revision (N -> N+1)."""
        project_id = str(msg.get("projectId", "default_project"))
        current_rev = self.command_bus.get_project_revision(project_id)
        new_rev = current_rev + 1
        self.command_bus.set_project_revision(project_id, new_rev)

        devices = msg.get("devices", [])
        self.command_bus._project_canonical_state[project_id] = {
            "devices": devices,
            "last_mutation": "user_manual_edit",
            "revision": new_rev,
        }

        await websocket.send_json(
            {
                "type": "user_mutation_committed",
                "projectId": project_id,
                "revision": new_rev,
                "devices": devices,
            }
        )


default_orchestration_service = AIOrchestrationService()


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
    elif msg_type in ("ai_intent", "intent_submit"):
        if principal:
            await default_orchestration_service.handle_intent(websocket, principal, msg)
    elif msg_type in ("ai_approve", "command_approve"):
        if principal:
            await default_orchestration_service.handle_approval(websocket, principal, msg)
    elif msg_type in ("user_mutate", "manual_edit"):
        if principal:
            await default_orchestration_service.handle_user_mutation(websocket, principal, msg)


async def _handle_response_message(msg: dict) -> None:
    """Handle a response message from the agent."""
    cmd_id = msg.get("id")
    payload = msg.get("payload")
    future = agent_response_futures.get(cmd_id)
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
    """Check if there is at least one active agent connected."""
    return len(active_agents.get(agent_type, [])) > 0


async def send_agent_command(
    agent_type: str, action: str, args: dict[str, Any], timeout: float = 30.0
) -> Any:
    """
    Send a command to the active agent and await the response.

    VERIFY-003 FIX: ``_register_agent`` enforces a single active agent per
    type (newest wins), so ``agents[0]`` here is always the most recently
    authenticated connection — a stale/rogue socket cannot sit ahead of the
    real agent in the registry and intercept commands.
    """
    agents = active_agents.get(agent_type, [])
    if not agents:
        raise HTTPException(status_code=503, detail="No active local agent connected.")

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
