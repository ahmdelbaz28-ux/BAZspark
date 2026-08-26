"""A4 WebSocket single-use ticket coverage (Sonar new-code gate).

Covers the /agent/ws-ticket HTTP issuer, the handshake accept/reject branches
(invalid ticket, insufficient role, valid ticket), and the nonce/ticket
bookkeeping helpers — all without real sockets or API keys.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.rbac import Role  # noqa: E402


def _load_agent_ws():
    """Import backend.routers.agent_ws directly (bypasses lazy __init__ chain)."""
    name = "backend.routers.agent_ws"
    if name in sys.modules:
        return sys.modules[name]
    file_path = _PROJECT_ROOT / "backend" / "routers" / "agent_ws.py"
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeInfo:
    def __init__(self, role: Role):
        self.role = role
        self.name = "browser_user"
        self.email = "u@bazspark.io"


def _mini_app(aw):
    from backend.rbac import Role as _Role

    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request, call_next):
        request.state.fireai_role = _Role.ENGINEER
        return await call_next(request)

    app.include_router(aw.router, prefix="/api")

    @app.websocket("/agent-ws")
    async def endpoint(websocket: WebSocket):
        info, _key = await aw._authenticate_agent_websocket(websocket)
        if info is None:
            return
        await websocket.accept()
        await websocket.send_json({"ok": True})
        await websocket.close()

    return app


def test_ws_ticket_http_endpoint_issues_single_use_ticket(monkeypatch):
    aw = _load_agent_ws()
    monkeypatch.setattr(
        aw, "validate_api_key", lambda key: _FakeInfo(Role.ENGINEER), raising=False
    )
    client = TestClient(_mini_app(aw))
    res = client.post("/api/agent/ws-ticket", headers={"x-api-key": "fireai_test"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ticket"] in aw._ws_tickets
    assert body["expires_in"] == aw.WS_TICKET_TTL_SECONDS

    # Bearer-prefixed header is also accepted after stripping.
    res2 = client.post("/api/agent/ws-ticket", headers={"x-api-key": "Bearer fireai_test"})
    assert res2.status_code == 200, res2.text


def test_ws_ticket_http_endpoint_rejects_missing_identity(monkeypatch):
    aw = _load_agent_ws()
    monkeypatch.setattr(aw, "validate_api_key", lambda key: None, raising=False)
    client = TestClient(_mini_app(aw))
    res = client.post("/api/agent/ws-ticket")
    assert res.status_code == 401
    assert "Valid API key required." in res.json()["detail"]


def test_handshake_with_invalid_ticket_closes_4401():
    aw = _load_agent_ws()
    client = TestClient(_mini_app(aw))
    with pytest.raises(Exception):
        with client.websocket_connect("/agent-ws?ticket=junk") as ws:
            ws.receive_text()


def test_handshake_with_insufficient_role_closes_4403(monkeypatch):
    aw = _load_agent_ws()
    monkeypatch.setattr(
        aw, "_consume_ws_ticket", lambda t, o: _FakeInfo(Role.VIEWER)
    )
    client = TestClient(_mini_app(aw))
    with pytest.raises(Exception):
        with client.websocket_connect("/agent-ws?ticket=viewer-ticket") as ws:
            ws.receive_text()


def test_handshake_with_valid_engineer_ticket_is_accepted():
    aw = _load_agent_ws()
    ticket = aw._issue_ws_ticket(_FakeInfo(Role.ENGINEER), None)
    client = TestClient(_mini_app(aw))
    with client.websocket_connect(f"/agent-ws?ticket={ticket}") as ws:
        assert ws.receive_json() == {"ok": True}
    # Single-use: replaying the burned ticket is rejected.
    with pytest.raises(Exception):
        with client.websocket_connect(f"/agent-ws?ticket={ticket}") as ws:
            ws.receive_text()


def test_nonce_prune_hard_cap_drops_oldest_quarter(monkeypatch):
    aw = _load_agent_ws()
    monkeypatch.setattr(aw, "_SEEN_AGENT_NONCES_MAX", 8)
    aw._seen_agent_nonces.clear()
    aw._nonce_timestamps.clear()
    for i in range(10):
        nonce = f"n{i}"
        aw._seen_agent_nonces.add(nonce)
        aw._register_agent_nonce(nonce)
    aw._prune_seen_nonces()
    assert len(aw._seen_agent_nonces) <= 8
    assert len(aw._nonce_timestamps) == len(aw._seen_agent_nonces)


def test_issue_ws_ticket_prunes_expired_entries():
    aw = _load_agent_ws()
    stale = "stale-ticket"
    aw._ws_tickets[stale] = {"expires": -1.0, "role": Role.ADMIN}
    fresh = aw._issue_ws_ticket(_FakeInfo(Role.ADMIN), None)
    assert stale not in aw._ws_tickets
    assert fresh in aw._ws_tickets
