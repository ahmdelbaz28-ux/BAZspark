# NOSONAR
"""WebSocket Transport for Distributed FACP System.

SECURITY NOTE (M-2 fix):
  - Token comparison uses hmac.compare_digest (constant-time) to prevent
    timing attacks.
  - auth_token=None means "no authentication required" — this is an
    EXPLICIT design choice for trusted internal networks. A warning is
    logged at startup to make this visible. For any deployment where
    the WebSocket port is reachable from untrusted networks, auth_token
    MUST be set.
  - VERIFY-002 fix: `start()` now FAILS CLOSED when auth_token=None — the
    server refuses to bind until auth_token is set, unless the operator
    explicitly opts out via FACP_ALLOW_UNAUTHENTICATED=1 (trusted
    dev/test networks only).
"""
import asyncio
import hmac
import json
import logging
import os
import threading
import time
from typing import Any

import websockets

from .http_transport import TransportLayer

_logger = logging.getLogger(__name__)

_FACP_PROTOCOL_VERSION = "FACP/1.1"


class WebSocketTransport(TransportLayer):
    """WebSocket transport implementation for distributed FACP"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8002, node_type: str = "l2_orchestrator",
                 auth_token: str | None = None, allowed_methods: set[str] | None = None,
                 allow_insecure_ws: bool = False):
        # L-3 FIX: secure-by-default. The default outbound URL is now wss://.
        # Use allow_insecure_ws=True to opt in to ws:// for trusted internal
        # dev/test networks. Any caller that passes a ws:// target_node without
        # setting allow_insecure_ws=True will trigger a ValueError at request
        # time (see _resolve_node_url).
        super().__init__()
        self.host = host
        self.port = port
        self.node_type = node_type
        self.auth_token = auth_token
        self.allow_insecure_ws = allow_insecure_ws
        if auth_token is None:
            _logger.warning(
                "WebSocketTransport started with auth_token=None — "
 "authentication is DISABLED. This is only safe on "
 "trusted internal networks. set auth_token for any "
 "deployment where port %s is reachable from untrusted "
 "networks.",
                port,
            )
        self.allowed_methods = allowed_methods or {
            "get_status", "get_health", "route_announcement",
            "process_alert", "query_sensor", "acknowledge_alarm",
        }
        self.clients: set[websockets.WebSocketServerProtocol] = set()
        self._authenticated: set[websockets.WebSocketServerProtocol] = set()
        self.websocket_server = None
        self.request_queue = []  # Queue for requests
        self.response_callbacks = {}  # request_id -> callback
        self.running = False
        self.loop = None

    async def _register_client(self, websocket: websockets.WebSocketServerProtocol):  # NOSONAR - python:S7503
        """Register a new client connection"""
        self.clients.add(websocket)
        print(f"Client connected: {websocket.remote_address}, Total clients: {len(self.clients)}")

    async def _unregister_client(self, websocket: websockets.WebSocketServerProtocol):  # NOSONAR - python:S7503
        """Unregister a client connection"""
        self._authenticated.discard(websocket)
        self.clients.remove(websocket)
        print(f"Client disconnected: {websocket.remote_address}, Total clients: {len(self.clients)}")

    async def _handle_client_message(self, websocket: websockets.WebSocketServerProtocol, path: str):  # NOSONAR — S3776: WebSocket message handling must dispatch many protocol types
        """Handle incoming messages from a client"""
        await self._register_client(websocket)
        try:
            async for message in websocket:
                try:
                    request_data = json.loads(message)

                    if self.auth_token and websocket not in self._authenticated:
                        # M-2 FIX: use hmac.compare_digest for constant-time
                        # comparison to prevent timing attacks that could
                        # leak the token byte-by-byte.
                        provided_token = request_data.get("token", "")
                        expected_token = self.auth_token or ""
                        token_matches = (
                            isinstance(provided_token, str)
                            and len(provided_token) == len(expected_token)
                            and hmac.compare_digest(
                                provided_token.encode("utf-8"),
                                expected_token.encode("utf-8"),
                            )
                        )
                        if request_data.get("method") != "auth" or not token_matches:
                            await websocket.send(json.dumps({
                                "protocol": _FACP_PROTOCOL_VERSION,
                                "id": request_data.get("id", "unknown"),
                                "status": "error",
                                "error": {"code": "UNAUTHORIZED", "message": "Authentication required. Send {\"method\":\"auth\",\"token\":\"<token>\"} as first message."},
                            }))
                            continue
                        self._authenticated.add(websocket)
                        await websocket.send(json.dumps({
                            "protocol": _FACP_PROTOCOL_VERSION,
                            "id": request_data.get("id", "unknown"),
                            "status": "ok",
                            "result": {"authenticated": True},
                        }))
                        continue

                    method = request_data.get("method", "")
                    if self.allowed_methods and method not in self.allowed_methods:
                        error_response = {
                            "protocol": _FACP_PROTOCOL_VERSION,
                            "id": request_data.get("id", "unknown"),
                            "status": "error",
                            "error": {"code": "METHOD_NOT_ALLOWED", "message": f"Method '{method}' is not in the allowed methods list"},
                        }
                        await websocket.send(json.dumps(error_response))
                        continue

                    # Add node information to the request
                    request_data["trace"] = request_data.get("trace", {})
                    request_data["trace"]["node_id"] = self.node_id
                    request_data["trace"]["node_type"] = self.node_type
                    request_data["trace"]["received_at"] = time.time()

                    # Route to appropriate handler
                    if method in self.handlers:
                        handler = self.handlers[method]
                        response = await handler(request_data) if asyncio.iscoroutinefunction(handler) else handler(request_data)

                        # Send response back to client
                        await websocket.send(json.dumps(response))
                    else:
                        error_response = {
                            "protocol": _FACP_PROTOCOL_VERSION,  # NOSONAR — S1192: duplicated literal acceptable in this localized context
                            "id": request_data.get("id", "unknown"),
                            "status": "error",
                            "error": {
                                "code": "METHOD_NOT_FOUND",
                                "message": f"Method {method} not found"
                            },
                            "trace": {
                                "node_id": self.node_id,
                                "node_type": self.node_type,
                                "execution_path": [self.node_type],
                                "latency_ms": 0
                            }
                        }
                        await websocket.send(json.dumps(error_response))

                except json.JSONDecodeError:
                    error_response = {
                        "protocol": _FACP_PROTOCOL_VERSION,
                        "id": "unknown",
                        "status": "error",
                        "error": {
                            "code": "INVALID_JSON",
                            "message": "Invalid JSON in request"
                        },
                        "trace": {
                            "node_id": self.node_id,
                            "node_type": self.node_type,
                            "execution_path": [self.node_type],
                            "latency_ms": 0
                        }
                    }
                    await websocket.send(json.dumps(error_response))
                except Exception as e:
                    error_response = {
                        "protocol": _FACP_PROTOCOL_VERSION,
                        "id": request_data.get("id", "unknown") if 'request_data' in locals() else "unknown",
                        "status": "error",
                        "error": {
                            "code": "WEBSOCKET_ERROR",
                            "message": str(e)
                        },
                        "trace": {
                            "node_id": self.node_id,
                            "node_type": self.node_type,
                            "execution_path": [self.node_type],
                            "latency_ms": 0
                        }
                    }
                    await websocket.send(json.dumps(error_response))
        except websockets.exceptions.ConnectionClosed:
            pass  # Connection was closed normally
        finally:
            await self._unregister_client(websocket)

    def start(self):
        """Start WebSocket server in a separate thread"""
        # VERIFY-002 FIX: fail closed instead of fail open. auth_token=None was
        # documented as "trusted internal networks only", but a listener bound
        # to 0.0.0.0 with authentication disabled is remotely exploitable if
        # the port is reachable at all. We now REFUSE to bind until auth_token
        # is set, unless the operator explicitly opts out via
        # FACP_ALLOW_UNAUTHENTICATED=1 (trusted dev/test networks only).
        if self.auth_token is None and os.environ.get(
            "FACP_ALLOW_UNAUTHENTICATED", ""
        ).strip().lower() not in ("1", "true", "yes", "on"):
            raise ValueError(
                "Refusing to start WebSocketTransport without auth_token. "
                "Authentication is required for any network-exposed deployment. "
                "set auth_token explicitly, or set FACP_ALLOW_UNAUTHENTICATED=1 "
                "for trusted dev/test networks only."
            )

        def run_server():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            start_server = websockets.serve(
                self._handle_client_message,
                self.host,
                self.port
            )

            self.websocket_server = self.loop.run_until_complete(start_server)
            print(f"WebSocket Transport listening on {self.host}:{self.port} (Node: {self.node_id})")

            self.running = True
            self.loop.run_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

    def stop(self):
        """Stop WebSocket server"""
        if self.loop and self.websocket_server:
            self.loop.call_soon_threadsafe(self.websocket_server.close)
            self.running = False
            self.is_running = False

    async def _send_to_client(self, websocket: websockets.WebSocketServerProtocol, message: str):
        """Send a message to a specific client"""
        if websocket in self.clients:
            await websocket.send(message)

    def send_request(self, request_data: dict[str, Any], target_node: str | None = None) -> dict[str, Any]:
        """
        Send request to target WebSocket endpoint
        target_node format: "ws://host:port" (e.g., "ws://localhost:8002")
        """
        # For this implementation, we'll simulate sending to another WebSocket server
        # In a real implementation, this would connect to the target WebSocket endpoint
        import asyncio

        # The original code assigned to `target_node` inside the nested
        # coroutine `send_to_target()`, which made Python treat `target_node`
        # as a LOCAL of that coroutine. Line 161 (`if not target_node:`) then
        # read it BEFORE assignment → `UnboundLocalError` on every call where
        # `target_node` was None (the default).
        #
        # Root cause: Python's scoping rule — any assignment to a name inside a
        # function makes that name local to the entire function, even at lines
        # before the assignment.
        #
        # Fix: use a separate local variable `node` for the resolved URL.
        # This is the audit's recommended fix and is the minimal change.
        # L-3 FIX: default is now wss:// (secure-by-default). Callers that
        # need ws:// for trusted internal dev/test must pass allow_insecure_ws=True
        # at construction time AND pass an explicit ws:// target_node.
        node = target_node or f"wss://{self.host}:{self.port}"
        if node.startswith("ws://") and not self.allow_insecure_ws:  # nosec: S5332 — ws:// is intentional for trusted internal dev/test; guarded by allow_insecure_ws opt-in
            raise ValueError(
                "WebSocketTransport refused to use insecure ws:// URL "
                f"{node!r} without allow_insecure_ws=True. Use wss:// or "
                "explicitly opt in to ws:// for trusted internal networks."
            )

        async def send_to_target():
            try:
                async with websockets.connect(node) as websocket:
                    await websocket.send(json.dumps(request_data))
                    response = await websocket.recv()
                    return json.loads(response)
            except Exception as e:
                return {
                    "protocol": _FACP_PROTOCOL_VERSION,
                    "id": request_data.get("id", "unknown"),
                    "status": "error",
                    "error": {
                        "code": "WEBSOCKET_CONNECTION_ERROR",
                        "message": str(e)
                    },
                    "trace": {
                        "node_id": self.node_id,
                        "node_type": self.node_type,
                        "execution_path": [self.node_type],
                        "latency_ms": 0
                    }
                }

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(send_to_target())
            loop.close()
            return result
        except Exception as e:
            return {
                "protocol": _FACP_PROTOCOL_VERSION,
                "id": request_data.get("id", "unknown"),
                "status": "error",
                "error": {
                    "code": "ASYNC_ERROR",
                    "message": str(e)
                },
                "trace": {
                    "node_id": self.node_id,
                    "node_type": self.node_type,
                    "execution_path": [self.node_type],
                    "latency_ms": 0
                }
            }

    async def broadcast_message(self, message: str):
        """Broadcast a message to all connected clients"""
        if self.clients:
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
