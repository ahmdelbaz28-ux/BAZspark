from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Coroutine, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.api_keys import validate_api_key
from backend.auth import has_permission
from backend.rbac import Permission

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/agent", tags=["agent-ws"])

# Active connections from agents
# Map from agent_type -> list of WebSocket
active_agents: Dict[str, list[WebSocket]] = {}
agent_response_futures: Dict[str, asyncio.Future[Any]] = {}

# A lock per connection to serialize command dispatches
agent_locks: Dict[str, asyncio.Lock] = {}

# Track which futures belong to which websocket (for cleanup on disconnect)
# Maps websocket id -> set of pending command IDs
_agent_pending_commands: Dict[str, set[str]] = {}


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
    """Pull the API key from headers or subprotocol — never from the query string."""
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
    """Check that the Origin header value is in the CORS allow-list."""
    import os

    allowed_origins_str = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
    )
    allowed_origins = [
        o.strip().lower() for o in allowed_origins_str.split(",") if o.strip()
    ]
    origin_clean = origin.strip().lower()
    return any(
        origin_clean == o or origin_clean.startswith(o) for o in allowed_origins
    )


async def _extract_and_validate_api_key(
    websocket: WebSocket,
) -> tuple:
    """Extract API key from handshake and validate it.

    Returns ``(api_key_info, api_key)`` on success, or ``(None, "")``
    after closing the socket on any failure.
    """
    api_key = _extract_api_key_from_handshake(websocket)
    if not api_key:
        logger.warning(
            "Rejected agent connection: no API key in headers/subprotocol"
        )
        await websocket.close(code=4003)
        return None, ""

    try:
        api_key_info = validate_api_key(api_key)
    except Exception as e:
        logger.exception("Error validating agent API Key: %s", e)
        await websocket.close(code=4003)
        return None, ""

    if api_key_info is None:
        logger.warning("Rejected agent connection: invalid API Key")
        await websocket.close(code=4003)
        return None, ""

    if not has_permission(api_key_info.role, Permission.CALCULATION_EXECUTE):
        logger.warning(
            "Rejected agent connection: role %s lacks CALCULATION_EXECUTE",
            api_key_info.role,
        )
        await websocket.close(code=4003)
        return None, ""

    return api_key_info, api_key


async def _authenticate_agent_websocket(websocket: WebSocket):
    """Validate the agent's API key + RBAC + Origin before accepting the WS handshake.

    Returns the validated ``api_key_info`` on success, or ``None`` after
    closing the connection with code 4003 on any failure.
    """
    origin = websocket.headers.get("origin")
    if origin and not _validate_origin(origin):
        logger.warning("Rejected agent connection: untrusted origin '%s'", origin)
        await websocket.close(code=4003)
        return None, ""

    return await _extract_and_validate_api_key(websocket)



def _register_agent(websocket: WebSocket, agent_type: str) -> None:
    """Register an active agent connection."""
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


async def _handle_agent_message(websocket: WebSocket, msg: dict) -> None:
    """Dispatch a single decoded agent message."""
    msg_type = msg.get("type")
    if msg_type == "response":
        cmd_id = msg.get("id")
        payload = msg.get("payload")
        future = agent_response_futures.get(cmd_id)
        if future is not None:
            future.set_result(payload)
    elif msg_type == "ping":
        await websocket.send_json({"type": "pong"})


WS_HEARTBEAT_TIMEOUT_SECONDS = 30.0
WS_PING_INTERVAL_SECONDS = 25.0  # send ping 5s before timeout deadline


async def _revalidate_api_key(api_key: str) -> bool:
    """Return ``True`` if *api_key* is still valid and carries the required permission."""
    try:
        info = validate_api_key(api_key)
        return info is not None and has_permission(
            info.role, Permission.CALCULATION_EXECUTE
        )
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
    if not api_key:
        return False
    if await _revalidate_api_key(api_key):
        return False
    logger.warning(
        "Agent WebSocket heartbeat: API key revoked or expired — terminating connection"
    )
    await websocket.close(code=4003)
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
    try:
        await websocket.close(code=4008)
    except Exception:
        pass
    return True


def _run_heartbeat_loop(websocket: WebSocket, api_key: str = "") -> tuple[dict[str, bool], Callable[[], Coroutine[Any, Any, None]]]:
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
                return  # connection already dead — let message loop handle it

            if await _handle_pong_timeout(websocket, _pong_received):
                return  # signal to caller that we closed

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


    async def _message_loop() -> None:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # A pong response from the client resets the heartbeat flag
                if msg.get("type") == "pong":
                    pong_flag["value"] = True
                else:
                    await _handle_agent_message(websocket, msg)
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
    agent_type: str, action: str, args: Dict[str, Any], timeout: float = 30.0
) -> Any:
    """
    Send a command to the active agent and await the response.
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
        except asyncio.TimeoutError as exc:
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
