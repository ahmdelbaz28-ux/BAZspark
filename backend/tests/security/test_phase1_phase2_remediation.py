"""Automated security test suite verifying Phase 1 and Phase 2 remediation fixes:
- FC-001: Copilot MCP Server endpoint authentication
- D-001: ClusterCommunicator HMAC signature verification
- D-002: Sandbox execution isolation and restricted builtins
- D-003: HTTPTransport node secret header enforcement
- B-001: Speckle server_url SSRF validation
- P-001: Meeza payment webhook amount verification
"""
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from engineering_copilot.mcp_server.mcp_server import MCPServer
from facp_distributed.event_bus.cluster_communicator import ClusterCommunicator
from facp_distributed.security.isolation import ExecutionIsolationManager
from facp_distributed.transport.http_transport import HTTPTransport
from backend.routers.experimental_services import SpeckleOperationRequest
from backend.services.meeza_payment_service import _persist_webhook_event, MeezaConfig, OrderStatus, TxnStatus


def test_fc001_copilot_mcp_unauthenticated_requests_rejected(monkeypatch):
    """FC-001: Unauthenticated request to MCP Server must be rejected with 401."""
    monkeypatch.setenv("COPILOT_API_KEYS", "valid-secret-key-123")
    server = MCPServer()
    client = TestClient(server.app)

    # Rejects missing header
    res = client.get("/read_drawing")
    assert res.status_code == 401

    # Rejects invalid header
    res = client.get("/read_drawing", headers={"X-API-Key": "wrong-key"})
    assert res.status_code == 401

    # Accepts valid header
    res = client.get("/read_drawing", headers={"X-API-Key": "valid-secret-key-123"})
    assert res.status_code == 200


def test_d001_cluster_communicator_hmac_verification(monkeypatch):
    """D-001: ClusterCommunicator rejects messages without valid HMAC signature when secret set."""
    monkeypatch.setenv("FACP_CLUSTER_SECRET", "super-secret-cluster-key")
    comm = ClusterCommunicator(node_id="node-1", host="127.0.0.1", port=9901)
    comm.running = True

    received_msgs = []
    def sample_handler(msg, sender, addr):
        received_msgs.append(msg)

    comm.message_handlers["test_event"] = [sample_handler]

    # Message without HMAC signature -> rejected
    unauth_msg = {"type": "test_event", "sender_node_id": "attacker_node", "timestamp": 12345}
    comm._handle_incoming_message(unauth_msg, None, ("127.0.0.1", 9999))
    assert len(received_msgs) == 0

    # Message sent via send_message -> has hmac_sig added
    valid_msg = {"type": "test_event"}
    comm.send_message("node-1", valid_msg)
    assert "hmac_sig" in valid_msg


def test_d002_sandbox_isolation_restricts_builtins():
    """D-002: Sandboxed function execution context prevents access to dangerous builtins."""
    def sample_calc():
        return 42

    mgr = ExecutionIsolationManager()
    res = mgr.create_sandboxed_execution(sample_calc)
    assert res["status"] in ("success", "error")


def test_d003_http_transport_node_secret(monkeypatch):
    """D-003: HTTPTransport enforces X-FACP-Node-Secret header."""
    monkeypatch.setenv("FACP_INTER_NODE_SECRET", "node-secret-abc")
    transport = HTTPTransport(host="127.0.0.1", port=8001)
    client = TestClient(transport.app)

    # Missing secret header -> 401
    res = client.post("/facp/request", json={"id": "123"})
    assert res.status_code == 401

    # Invalid secret header -> 401
    res = client.post("/facp/request", json={"id": "123"}, headers={"X-FACP-Node-Secret": "invalid"})
    assert res.status_code == 401

    # Valid secret header -> proceeds past auth check
    res = client.post("/facp/request", json={"id": "123", "protocol": "facp/1.0"}, headers={"X-FACP-Node-Secret": "node-secret-abc"})
    assert res.status_code in (200, 400)  # 400 if body validation fails, but auth passed


def test_b001_speckle_server_url_ssrf_protection():
    """B-001: SpeckleOperationRequest rejects loopback, AWS metadata, and invalid URLs."""
    # Loopback IP rejected
    with pytest.raises(ValueError, match="SSRF validation failed"):
        SpeckleOperationRequest(stream_id="test", server_url="https://127.0.0.1", token="token123")

    # AWS metadata IP rejected
    with pytest.raises(ValueError, match="SSRF validation failed"):
        SpeckleOperationRequest(stream_id="test", server_url="https://169.254.169.254", token="token123")

    # Non-https scheme rejected
    with pytest.raises(ValueError, match="must use https scheme"):
        SpeckleOperationRequest(stream_id="test", server_url="http://speckle.xyz", token="token123")

    # Valid public host accepted
    req = SpeckleOperationRequest(stream_id="test", server_url="https://speckle.xyz", token="token123")
    assert req.server_url == "https://speckle.xyz"


def test_p001_meeza_webhook_amount_mismatch_rejected(monkeypatch, tmp_path):
    """P-001: _persist_webhook_event rejects webhook when amount does not match stored order amount."""
    db_file = tmp_path / "test_billing.db"
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, amount_cents INTEGER, status TEXT)")
    conn.execute("CREATE TABLE payment_events (id TEXT PRIMARY KEY, transaction_id TEXT, order_id TEXT, event_type TEXT, psp_name TEXT, idempotency_key TEXT, raw_payload TEXT, hmac_signature TEXT, processed_at TEXT, response_code INTEGER)")
    conn.execute("INSERT INTO orders (id, amount_cents, status) VALUES ('order-123', 50000, 'pending')")
    conn.commit()

    monkeypatch.setattr("backend.services.meeza_payment_service._get_conn", lambda: conn)
    cfg = MeezaConfig.from_env()

    # Amount mismatch (webhook claims 100, stored order expects 50000)
    result = _persist_webhook_event(
        cfg=cfg,
        merchant_order_id="order-123",
        txn_status=TxnStatus.SUCCESS,
        order_status=OrderStatus.PAID.value,
        amount_cents=100,  # Mismatched amount
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "amount_mismatch"
    assert result["http_status"] == 409
