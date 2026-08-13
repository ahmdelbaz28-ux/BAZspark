"""
backend/tests/test_billing_meeza.py
===================================
Tests for the Meeza (ميزة) payment gateway integration.

Covers:
  - Service layer: order CRUD, checkout (sandbox), webhook handling
  - HMAC signature verification (valid, missing, tampered)
  - Idempotency: duplicate webhook deliveries do NOT double-fulfill
  - Status transitions: SUCCESS, FAILED, EXPIRED, CANCELLED
  - Atomic order status guard: a CANCELLED after SUCCESS does not flip the order
  - Router: 401 unauthenticated, 404 unknown order, 200 happy path
  - Edge cases: invalid amount, empty principal, expired order

All tests run in sandbox mode (no live PSP calls). The test fixture
isolates each test with a fresh SQLite DB and a known HMAC secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so `backend.*` imports work even
# when pytest is invoked from a subdirectory.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolate_billing_db(monkeypatch, tmp_path):
    """Each test gets a fresh SQLite DB + known HMAC secret."""
    db_path = tmp_path / "billing_test.sqlite"
    monkeypatch.setenv("MEEZA_DB_PATH", str(db_path))
    monkeypatch.setenv("MEEZA_PSP_PROVIDER", "sandbox")
    monkeypatch.setenv("MEEZA_WEBHOOK_HMAC_SECRET", "test-secret-do-not-use-in-prod")
    monkeypatch.setenv("MEEZA_HMAC_ALGORITHM", "sha256")
    monkeypatch.setenv("MEEZA_CURRENCY", "EGP")

    # Force re-evaluation of cached config + schema state
    from backend.services import meeza_payment_service as svc
    svc.reset_for_tests()

    yield

    svc.reset_for_tests()


# ── Service: order CRUD ──────────────────────────────────────────────────────

def test_create_order_happy_path():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(
        user_principal="user-1",
        amount_cents=50000,
        description="Pro plan",
    )
    assert order["status"] == "pending"
    assert order["amount_cents"] == 50000
    assert order["currency"] == "EGP"
    assert order["user_principal"] == "user-1"
    assert order["expires_at"] is not None


def test_create_order_rejects_non_positive_amount():
    from backend.services import meeza_payment_service as svc
    with pytest.raises(ValueError, match="amount_cents"):
        svc.create_order(user_principal="u", amount_cents=0)
    with pytest.raises(ValueError, match="amount_cents"):
        svc.create_order(user_principal="u", amount_cents=-100)


def test_create_order_rejects_empty_principal():
    from backend.services import meeza_payment_service as svc
    with pytest.raises(ValueError, match="user_principal"):
        svc.create_order(user_principal="", amount_cents=100)


def test_create_order_rejects_oversize_description():
    from backend.services import meeza_payment_service as svc
    with pytest.raises(ValueError, match="description"):
        svc.create_order(user_principal="u", amount_cents=100, description="x" * 501)


def test_list_orders_filters_by_principal():
    from backend.services import meeza_payment_service as svc
    svc.create_order(user_principal="alice", amount_cents=100)
    svc.create_order(user_principal="bob",   amount_cents=200)
    svc.create_order(user_principal="alice", amount_cents=300)
    alice_orders = svc.list_orders("alice")
    bob_orders   = svc.list_orders("bob")
    assert len(alice_orders) == 2
    assert len(bob_orders) == 1
    assert all(o["user_principal"] == "alice" for o in alice_orders)


def test_get_order_idor_protection():
    """get_order(order_id, user_principal=X) returns None when the order
    belongs to a different user — defence against IDOR."""
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="alice", amount_cents=100)
    # Bob cannot read Alice's order
    assert svc.get_order(order["id"], user_principal="bob") is None
    # Alice can
    assert svc.get_order(order["id"], user_principal="alice") is not None


# ── Service: checkout ────────────────────────────────────────────────────────

def test_checkout_sandbox_returns_synthetic_url():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=1000)
    chk = svc.initiate_checkout(order["id"], "u")
    assert chk["method"] == "sandbox"
    assert chk["checkout_url"].startswith("https://sandbox.bazspark.local/meeza/checkout")
    assert chk["transaction_id"]
    assert chk["order_id"] == order["id"]


def test_checkout_rejects_already_paid_order():
    """Critical: cannot checkout an order that has already been paid —
    prevents double-charging if the frontend retries."""
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=1000)
    svc.simulate_webhook(order["id"], svc.TxnStatus.SUCCESS)
    with pytest.raises(ValueError, match="not pending"):
        svc.initiate_checkout(order["id"], "u")


def test_checkout_rejects_other_users_order():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="alice", amount_cents=1000)
    with pytest.raises(ValueError, match="not found for principal"):
        svc.initiate_checkout(order["id"], "bob")


# ── Service: HMAC verification ───────────────────────────────────────────────

def test_hmac_verify_valid_signature():
    from backend.services import meeza_payment_service as svc
    secret = "test-secret-do-not-use-in-prod"
    payload = b'{"obj":{"id":1,"order":{"merchant_order_id":"x"},"amount_cents":100,"success":true}}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert svc.verify_webhook_signature(payload, f"sha256={sig}") is True
    # Also tolerate bare hex header
    assert svc.verify_webhook_signature(payload, sig) is True


def test_hmac_verify_rejects_tampered_payload():
    from backend.services import meeza_payment_service as svc
    secret = "test-secret-do-not-use-in-prod"
    payload = b'{"obj":{"amount_cents":100}}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    tampered = b'{"obj":{"amount_cents":99999}}'  # changed amount
    assert svc.verify_webhook_signature(tampered, f"sha256={sig}") is False


def test_hmac_verify_rejects_wrong_secret():
    from backend.services import meeza_payment_service as svc
    payload = b'{"x":1}'
    sig = hmac.new(b"wrong-secret", payload, hashlib.sha256).hexdigest()
    assert svc.verify_webhook_signature(payload, sig) is False


def test_hmac_verify_rejects_empty_signature():
    from backend.services import meeza_payment_service as svc
    assert svc.verify_webhook_signature(b'{"x":1}', "") is False


def test_hmac_verify_rejects_empty_secret():
    from backend.services import meeza_payment_service as svc
    # Bypass env-cached config by passing secret explicitly as empty
    assert svc.verify_webhook_signature(b'{"x":1}', "deadbeef", secret="") is False


# ── Service: webhook handling ────────────────────────────────────────────────

def test_webhook_success_marks_order_paid():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")
    res = svc.simulate_webhook(order["id"], svc.TxnStatus.SUCCESS)
    assert res["status"] == "processed"
    assert res["order_status"] == "paid"
    final = svc.get_order(order["id"])
    assert final["status"] == "paid"
    assert final["paid_at"] is not None


def test_webhook_failed_marks_order_failed():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")
    res = svc.simulate_webhook(order["id"], svc.TxnStatus.FAILED)
    assert res["order_status"] == "failed"
    assert svc.get_order(order["id"])["status"] == "failed"


def test_webhook_expired_marks_order_expired():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")
    res = svc.simulate_webhook(order["id"], svc.TxnStatus.EXPIRED)
    assert res["order_status"] == "expired"


def test_webhook_cancelled_marks_order_cancelled():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")
    res = svc.simulate_webhook(order["id"], svc.TxnStatus.CANCELLED)
    assert res["order_status"] == "cancelled"


def test_webhook_idempotent_duplicate_does_not_double_fulfill():
    """CRITICAL: two SUCCESS webhooks for the same order must not double-
    fulfill. The first processes; the second returns status='duplicate'."""
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")

    res1 = svc.simulate_webhook(order["id"], svc.TxnStatus.SUCCESS)
    res2 = svc.simulate_webhook(order["id"], svc.TxnStatus.SUCCESS)

    assert res1["status"] == "processed"
    assert res2["status"] == "duplicate"
    # Idempotency key MUST be identical (same payload → same key)
    assert res1["idempotency_key"] == res2["idempotency_key"]
    # Only one payment_event row should exist
    events = svc.list_events_for_order(order["id"])
    assert len(events) == 1


def test_webhook_atomic_cancel_after_success_does_not_flip_order():
    """Edge case: a delayed CANCELLED arrives after the order has already
    been marked PAID. The atomic UPDATE WHERE status='pending' clause must
    prevent the cancellation from overwriting the paid state."""
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")

    svc.simulate_webhook(order["id"], svc.TxnStatus.SUCCESS)
    # Now a delayed CANCELLED arrives — must NOT flip the order
    res = svc.simulate_webhook(order["id"], svc.TxnStatus.CANCELLED)
    assert res["status"] == "duplicate"  # idempotency layer or atomic guard
    final = svc.get_order(order["id"])
    assert final["status"] == "paid"  # still paid, not cancelled


def test_webhook_rejects_invalid_signature():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    raw = b'{"obj":{"order":{"merchant_order_id":"' + order["id"].encode() + b'"},"amount_cents":5000,"success":true}}'
    res = svc.handle_meeza_webhook(raw, "deadbeef-invalid-signature")
    assert res["status"] == "rejected"
    assert res["http_status"] == 401


def test_webhook_rejects_malformed_json():
    from backend.services import meeza_payment_service as svc
    secret = "test-secret-do-not-use-in-prod"
    raw = b"not valid json {{{"
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    res = svc.handle_meeza_webhook(raw, f"sha256={sig}")
    assert res["status"] == "rejected"
    assert res["http_status"] == 400


def test_webhook_rejects_missing_order_id():
    from backend.services import meeza_payment_service as svc
    secret = "test-secret-do-not-use-in-prod"
    payload = {"obj": {"amount_cents": 100, "success": True}}  # no order.merchant_order_id
    raw = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    res = svc.handle_meeza_webhook(raw, f"sha256={sig}")
    assert res["status"] == "rejected"
    assert res["http_status"] == 400
    assert res["reason"] == "missing_order_id"


def test_webhook_audit_events_recorded():
    """Every processed webhook creates an audit row in payment_events."""
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=5000)
    svc.initiate_checkout(order["id"], "u")
    svc.simulate_webhook(order["id"], svc.TxnStatus.SUCCESS)
    events = svc.list_events_for_order(order["id"])
    assert len(events) == 1
    assert events[0]["event_type"] == "SUCCESS"
    assert events[0]["hmac_signature"]  # non-empty


# ── Service: idempotency key derivation ──────────────────────────────────────

def test_idempotency_key_deterministic():
    from backend.services import meeza_payment_service as svc
    k1 = svc.derive_idempotency_key("paymob", "order-1", "txn-1", "SUCCESS", 5000)
    k2 = svc.derive_idempotency_key("paymob", "order-1", "txn-1", "SUCCESS", 5000)
    assert k1 == k2


def test_idempotency_key_changes_on_status():
    from backend.services import meeza_payment_service as svc
    k1 = svc.derive_idempotency_key("paymob", "order-1", "txn-1", "SUCCESS", 5000)
    k2 = svc.derive_idempotency_key("paymob", "order-1", "txn-1", "FAILED",  5000)
    assert k1 != k2  # different status → different event → different key


def test_idempotency_key_changes_on_amount():
    from backend.services import meeza_payment_service as svc
    k1 = svc.derive_idempotency_key("paymob", "order-1", "txn-1", "SUCCESS", 5000)
    k2 = svc.derive_idempotency_key("paymob", "order-1", "txn-1", "SUCCESS", 5001)
    assert k1 != k2  # partial-capture follow-up must not collide


# ── Service: configuration ───────────────────────────────────────────────────

def test_config_from_env_sandbox_default():
    from backend.services.meeza_payment_service import MeezaConfig
    cfg = MeezaConfig.from_env()
    assert cfg.psp_name.value == "sandbox"
    assert cfg.hmac_algorithm == "sha256"
    assert cfg.currency == "EGP"


def test_config_invalid_provider_falls_back_to_sandbox(monkeypatch):
    from backend.services.meeza_payment_service import MeezaConfig
    monkeypatch.setenv("MEEZA_PSP_PROVIDER", "invalid-provider")
    cfg = MeezaConfig.from_env()
    assert cfg.psp_name.value == "sandbox"


# ── Service: transaction listing ─────────────────────────────────────────────

def test_list_transactions_for_order():
    from backend.services import meeza_payment_service as svc
    order = svc.create_order(user_principal="u", amount_cents=1000)
    svc.initiate_checkout(order["id"], "u")
    txns = svc.list_transactions_for_order(order["id"])
    assert len(txns) == 1
    assert txns[0]["status"] == "PENDING"
    assert txns[0]["psp_name"] == "sandbox"


# ── Router-level tests (FastAPI TestClient) ──────────────────────────────────

@pytest.fixture
def fastapi_client(isolate_billing_db):
    """Build a minimal FastAPI app with ONLY the billing router — avoids
    importing the full app.py which has many optional deps."""
    from fastapi import FastAPI

    from backend.rbac import Role
    from backend.routers import billing

    app = FastAPI(title="Billing Test")
    app.include_router(billing.router, prefix="/api/v1")

    # Stub the auth middleware so every request appears authenticated as
    # user-1 with ADMIN role (full permissions). require_permission() checks
    # `isinstance(scope_role, Role)` — must pass the enum, not a string.
    @app.middleware("http")
    async def stub_auth(request, call_next):
        request.state.fireai_principal = "user-1"
        request.scope["fireai_principal"] = "user-1"
        request.scope["fireai_role"] = Role.ADMIN
        return await call_next(request)

    from fastapi.testclient import TestClient
    return TestClient(app)


def test_router_create_order(fastapi_client):
    res = fastapi_client.post("/api/v1/billing/orders", json={
        "amount_cents": 50000,
        "description": "Pro plan",
    })
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "pending"
    assert data["amount_cents"] == 50000


def test_router_list_orders(fastapi_client):
    fastapi_client.post("/api/v1/billing/orders", json={"amount_cents": 1000})
    fastapi_client.post("/api/v1/billing/orders", json={"amount_cents": 2000})
    res = fastapi_client.get("/api/v1/billing/orders")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_router_get_order(fastapi_client):
    create = fastapi_client.post("/api/v1/billing/orders", json={"amount_cents": 1000})
    order_id = create.json()["id"]
    res = fastapi_client.get(f"/api/v1/billing/orders/{order_id}")
    assert res.status_code == 200
    assert res.json()["id"] == order_id


def test_router_get_order_404(fastapi_client):
    res = fastapi_client.get("/api/v1/billing/orders/does-not-exist")
    assert res.status_code == 404


def test_router_checkout(fastapi_client):
    create = fastapi_client.post("/api/v1/billing/orders", json={"amount_cents": 5000})
    order_id = create.json()["id"]
    res = fastapi_client.post(f"/api/v1/billing/orders/{order_id}/checkout", json={})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["method"] == "sandbox"
    assert data["checkout_url"]


def test_router_webhook_rejects_invalid_signature(fastapi_client):
    res = fastapi_client.post(
        "/api/v1/billing/webhooks/meeza",
        content=b'{"obj":{"order":{"merchant_order_id":"x"},"amount_cents":100,"success":true}}',
        headers={"X-Meeza-Signature": "invalid"},
    )
    assert res.status_code == 401


def test_router_webhook_processes_valid_signature(fastapi_client):
    secret = "test-secret-do-not-use-in-prod"
    # Create + checkout first
    create = fastapi_client.post("/api/v1/billing/orders", json={"amount_cents": 5000})
    order_id = create.json()["id"]
    fastapi_client.post(f"/api/v1/billing/orders/{order_id}/checkout", json={})

    # Build a valid PayMob-shaped payload
    payload = {
        "type": "TRANSACTION",
        "obj": {
            "id": 12345,
            "order": {"id": 67890, "merchant_order_id": order_id},
            "amount_cents": 5000,
            "currency": "EGP",
            "success": True,
            "pending": False,
            "is_voided": False,
            "is_refunded": False,
            "source_data": {"sub_type": "meeza"},
        },
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    res = fastapi_client.post(
        "/api/v1/billing/webhooks/meeza",
        content=raw,
        headers={"X-Meeza-Signature": f"sha256={sig}", "Content-Type": "application/json"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "processed"


def test_router_simulate_webhook_sandbox(fastapi_client):
    """Sandbox-only simulate endpoint drives the full pipeline."""
    create = fastapi_client.post("/api/v1/billing/orders", json={"amount_cents": 5000})
    order_id = create.json()["id"]
    fastapi_client.post(f"/api/v1/billing/orders/{order_id}/checkout", json={})
    res = fastapi_client.post(
        f"/api/v1/billing/orders/{order_id}/simulate-webhook?txn_status=SUCCESS"
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "processed"
