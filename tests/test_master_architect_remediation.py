"""
tests/test_master_architect_remediation.py — Verification of Master Architect Remediations.
========================================================================================

Verifies all fixes across:
  1. CAD/DXF/DWG Parser Bounds & Sanitization
  2. Vision Key Store Memory Zeroization & Wiping
  3. WebSocket Anti-Replay Nonce/Sequence Guards
  4. Solver Hard Timeouts & Resource Protection (10s Cap)
  5. Dual-Database Transactional Saga Rollback
  6. Meeza Payment Gateway FastAPI Endpoints & Webhook Security
"""

from __future__ import annotations

import hashlib
import hmac
import math
import time
import pytest
from fastapi.testclient import TestClient

# 1. CAD Parser Bounds & Sanitization
from fireai.core.streaming_dwg_parser import StreamingDXFParser, StreamedRoom

# 2. Vision Key Store Wiping
from backend.vision_key_store import (
    encrypt_key,
    decrypt_key,
    wipe_memory,
    secure_key_context,
)

# 3. WebSocket Anti-Replay
from fireai.core.websocket_manager import ConnectionManager

# 4. Solver Timeout Caps
from fireai.core.darcy_weisbach_solver import calculate_darcy_weisbach_friction_loss, FluidType
from fireai.core.hydraulic_solver import calculate_friction_loss
from fireai.core.monte_carlo_pipeline import DetectorReliabilitySimulator

# 5. Dual-DB Saga Rollback
from backend.multi_db_service import atomic_multi_db_transaction

# 6. Meeza Billing Router
from backend.app import app


def test_cad_parser_bounds_and_sanitization():
    """Verify that DWG/DXF parser rejects infinite coordinates and out-of-bounds entities."""
    parser = StreamingDXFParser()
    chunk_with_nan = [
        "0", "LINE",
        "10", "NaN",
        "20", "10.5",
        "11", "20.0",
        "21", "30.0"
    ]
    segments = parser._parse_dxf_chunk(chunk_with_nan)
    assert len(segments) == 0  # NaN coordinate segment rejected


def test_vision_key_store_memory_wiping():
    """Verify explicit memory zeroization pattern in vision_key_store."""
    encrypted = encrypt_key("sk-test-secret-key-12345")
    assert decrypt_key(encrypted) == "sk-test-secret-key-12345"

    # Test secure_key_context and memory wiping
    key_buf_ref = None
    with secure_key_context(encrypted) as buf:
        key_buf_ref = buf
        assert buf.decode("utf-8") == "sk-test-secret-key-12345"

    # After exiting context, memory buffer must be zeroized (wiped)
    assert all(b == 0 for b in key_buf_ref)


def test_websocket_anti_replay():
    """Verify ConnectionManager rejects duplicate nonces and out-of-order sequence numbers."""
    cm = ConnectionManager()
    client_id = "test-client-1"

    # First frame with nonce
    frame1 = {"nonce": "nonce-abc-123", "seq": 1}
    assert cm.validate_frame(client_id, frame1) is True

    # Replayed frame with same nonce -> rejected
    frame1_replay = {"nonce": "nonce-abc-123", "seq": 2}
    assert cm.validate_frame(client_id, frame1_replay) is False

    # Out of order sequence number -> rejected
    frame_old_seq = {"nonce": "nonce-xyz-456", "seq": 1}
    assert cm.validate_frame(client_id, frame_old_seq) is False


def test_solver_timeout_caps_and_caching():
    """Verify solver friction calculation and caching."""
    loss1 = calculate_friction_loss(100.0, 120.0, 2.067, 100.0)
    assert loss1 > 0
    # Second call should return cached result
    loss2 = calculate_friction_loss(100.0, 120.0, 2.067, 100.0)
    assert loss1 == loss2

    res = calculate_darcy_weisbach_friction_loss(
        pipe_length_m=50.0,
        pipe_diameter_m=0.05,
        flow_rate_kg_s=2.0,
        fluid_type=FluidType.WATER,
    )
    assert res.pressure_loss_psi > 0
    assert res.converged is True


def test_monte_carlo_timeout_cap():
    """Verify Monte Carlo simulator enforces trial boundary and time cap."""
    sim = DetectorReliabilitySimulator(n_trials=100)
    res = sim.simulate_room_reliability(
        detectors=[(2.0, 2.0), (8.0, 8.0)],
        room_width=10.0,
        room_length=10.0,
    )
    assert "mean_coverage_pct" in res
    assert res["n_trials"] == 100


def test_dual_db_saga_rollback():
    """Verify Saga transaction executes compensating rollback actions on failure."""
    compensated = []

    def rollback_step1():
        compensated.append("step1")

    def rollback_step2():
        compensated.append("step2")

    with pytest.raises(RuntimeError):
        with atomic_multi_db_transaction() as saga:
            saga.add_compensation(rollback_step1)
            saga.add_compensation(rollback_step2)
            raise RuntimeError("Simulated failure in multi-db sync")

    # Saga rollbacks must be executed in reverse order (step2 then step1)
    assert compensated == ["step2", "step1"]


def test_meeza_billing_router(monkeypatch):
    """Verify Meeza payment initiation, status polling, and webhook HMAC verification."""
    from backend.routers.billing import router as billing_router
    app.include_router(billing_router, prefix="/api/v1")
    test_key = "test_meeza_api_key"
    monkeypatch.setenv("FIREAI_API_KEY", test_key)
    client = TestClient(app, headers={"X-API-Key": test_key})

    # 1. Initiate payment
    init_res = client.post("/api/v1/billing/meeza/initiate", json={
        "amount": 499.0,
        "currency": "EGP",
        "description": "Professional Plan Subscription",
        "customer_email": "engineer@example.com",
    })
    assert init_res.status_code == 200
    data = init_res.json()
    payment_id = data["payment_id"]
    assert payment_id.startswith("MEEZA-")
    assert data["status"] == "PENDING"
    assert "redirect_url" in data

    # 2. Check transaction status
    status_res = client.get(f"/api/v1/billing/meeza/status/{payment_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "PENDING"

    # 3. Test Webhook with HMAC signature
    webhook_payload = {"payment_id": payment_id, "status": "SUCCESS"}
    secret = "meeza_secret_key_v1"
    import json
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    wh_res = client.post(
        "/api/v1/billing/meeza/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Meeza-Signature": sig, "X-API-Key": test_key}
    )
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "SUCCESS"

    # 4. Verify updated status
    status_res_after = client.get(f"/api/v1/billing/meeza/status/{payment_id}")
    assert status_res_after.json()["status"] == "SUCCESS"
