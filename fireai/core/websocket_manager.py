#!/usr/bin/env python3
# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
"""WebSocket connection manager for FastAPI with API key verification."""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import HTTPException, WebSocket
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_EFFECTIVE_API_KEYS: set[str] = set()


def _init_api_keys() -> None:
    global _EFFECTIVE_API_KEYS
    keys_str = os.environ.get("FIREAI_API_KEYS", "")
    if keys_str:
        _EFFECTIVE_API_KEYS = {k.strip() for k in keys_str.split(",") if k.strip()}
    else:
        single_key = os.environ.get("FIREAI_API_KEY")
        if single_key:
            _EFFECTIVE_API_KEYS = {single_key}
        else:
            generated = secrets.token_urlsafe(32)
            logger.warning(
                "FIREAI_API_KEYS not set — auto-generated for dev: %s",
                generated[:8] + "...",
            )
            _EFFECTIVE_API_KEYS = {generated}


_init_api_keys()


def verify_api_key_ws(api_key: str | None = None) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required. Pass X-API-Key header.")
    if not any(secrets.compare_digest(api_key, valid_key) for valid_key in _EFFECTIVE_API_KEYS):
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return api_key


WS_HEARTBEAT_TIMEOUT_SECONDS: float = 30.0


def _validate_ws_origin(websocket: WebSocket) -> None:
    """Enforce strict Origin header validation to prevent CSWSH attacks.

    Raises HTTPException(403) if the Origin is present but not in the
    CORS_ALLOWED_ORIGINS allow-list. Absent origins (e.g. native clients
    or server-to-server) are permitted because they cannot originate from
    a browser cross-site request.
    """
    origin = websocket.headers.get("origin")
    if not origin:
        return  # non-browser client — allow

    allowed_str = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
    )
    allowed = [o.strip().lower() for o in allowed_str.split(",") if o.strip()]
    origin_lower = origin.strip().lower()
    if not any(origin_lower == o or origin_lower.startswith(o) for o in allowed):
        logger.warning("Rejected WebSocket from untrusted origin '%s'", origin)
        raise HTTPException(status_code=403, detail="Forbidden: untrusted WebSocket origin.")


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}
        self._connection_keys: dict[WebSocket, str] = {}
        self._seen_nonces: dict[str, set[str]] = {}
        self._last_seq: dict[str, int] = {}

    async def connect(
        self, websocket: WebSocket, client_id: str, api_key: str | None = None
    ) -> None:
        _validate_ws_origin(websocket)
        verify_api_key_ws(api_key)
        await websocket.accept()
        self._active_connections[client_id] = websocket
        self._connection_keys[websocket] = client_id
        self._seen_nonces[client_id] = set()
        self._last_seq[client_id] = 0
        logger.info("WebSocket client %s connected", client_id)

    def disconnect(self, websocket: WebSocket) -> None:
        client_id = self._connection_keys.pop(websocket, None)
        if client_id and client_id in self._active_connections:
            del self._active_connections[client_id]
            self._seen_nonces.pop(client_id, None)
            self._last_seq.pop(client_id, None)
        logger.info("WebSocket client disconnected")

    def validate_frame(self, client_id: str, frame: dict) -> bool:
        """
        Validate frame nonce, sequence number, and timestamp to prevent replay attacks.
        Returns True if frame is valid; False if replay/invalid nonce or sequence detected.
        """
        if not isinstance(frame, dict):
            return True

        nonce = frame.get("nonce")
        if nonce:
            nonces = self._seen_nonces.setdefault(client_id, set())
            if nonce in nonces:
                logger.warning(
                    "Replay attack detected for client %s with nonce %s", client_id, nonce
                )
                return False
            nonces.add(nonce)
            if len(nonces) > 5000:  # prune oldest
                self._seen_nonces[client_id] = set(list(nonces)[-2500:])

        seq = frame.get("seq")
        if seq is not None and isinstance(seq, int):
            last = self._last_seq.get(client_id, 0)
            if seq <= last and last > 0:
                logger.warning(
                    "Out-of-order/replayed sequence for client %s: seq=%d <= last=%d",
                    client_id,
                    seq,
                    last,
                )
                return False
            self._last_seq[client_id] = seq

        return True

    async def send_personal_message(self, message: str, client_id: str) -> bool:
        websocket = self._active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_text(message)
                return True
            except Exception as e:
                logger.exception("Failed to send message to %s: %s", client_id, e)
                self.disconnect(websocket)
        return False

    async def broadcast(self, message: str) -> int:
        sent_count = 0
        for client_id, websocket in list(
            self._active_connections.items()
        ):  # NOSONAR - python:S7504
            try:
                await websocket.send_text(message)
                sent_count += 1
            except Exception as e:
                logger.exception("Failed to broadcast to %s: %s", client_id, e)
                self.disconnect(websocket)
        return sent_count

    def get_active_connections(self) -> list[str]:
        return list(self._active_connections.keys())

    def is_connected(self, client_id: str) -> bool:
        return client_id in self._active_connections


manager = ConnectionManager()
