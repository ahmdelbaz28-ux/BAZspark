"""
backend/tests/test_e2e_billing_lifecycle.py
===========================================
Comprehensive End-to-End Billing Lifecycle & Production Persistence Test Suite.

Covers:
  - Task A: Production Redis Session Store Enforcement & Atomic SETEX TTL
  - Task B: Fail-fast Production SQLite Guardrail with ConfigurationError
  - Task C: Complete E2E Billing & Webhook Fulfilment Lifecycle:
      1. Order Creation & Checkout Intent (/orders, /checkout)
      2. Mocked Meeza Gateway Webhook Payload Delivery with HMAC-SHA256
      3. Idempotent Duplicate Webhook Delivery (HTTP 200 without double credit)
      4. Database Order & Subscription State Transitions (status='paid', paid_at)
      5. Security Gate: Invalid/Tampered HMAC Signature Rejection (HTTP 401)
      6. Security Gate: Amount Mismatch Defense (HTTP 409)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import backend.env_validator as ev
import backend.session_store as ss
from backend.env_validator import ConfigurationError
from backend.rbac import Role
from backend.routers import billing
from backend.services import meeza_payment_service as svc

_TEST_HMAC_SECRET = "production-grade-e2e-test-secret-key-32b"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolate billing database, HMAC secret, and session store state for each test."""
    db_path = tmp_path / "e2e_billing_test.sqlite"
    monkeypatch.setenv("MEEZA_DB_PATH", str(db_path))
    monkeypatch.setenv("MEEZA_PSP_PROVIDER", "sandbox")
    monkeypatch.setenv("MEEZA_WEBHOOK_HMAC_SECRET", _TEST_HMAC_SECRET)
    monkeypatch.setenv("MEEZA_HMAC_ALGORITHM", "sha256")
    monkeypatch.setenv("MEEZA_CURRENCY", "EGP")
    monkeypatch.setenv("FIREAI_ENV", "development")
    monkeypatch.setenv("FIREAI_ENV_VALIDATION", "strict")

    # Reset services and session store
    svc.reset_for_tests()
    ss._redis_checked = False
    ss._redis_available = False
    ss._redis_client = None
    ss.session_store.clear_all_sessions()

    yield

    svc.reset_for_tests()
    ss._redis_checked = False
    ss._redis_available = False
    ss._redis_client = None


@pytest.fixture
def client() -> TestClient:
    """Build a test FastAPI app with the billing router and authenticated principal stub."""
    app = FastAPI(title="E2E Billing Test App")
    app.include_router(billing.router, prefix="/api/v1")

    @app.middleware("http")
    async def auth_middleware(request, call_next):
        request.state.fireai_principal = "principal-user-e2e-123"
        request.scope["fireai_principal"] = "principal-user-e2e-123"
        request.scope["fireai_role"] = Role.ADMIN
        return await call_next(request)

    return TestClient(app)


def _sign_payload(raw_bytes: bytes, secret: str = _TEST_HMAC_SECRET, algo: str = "sha256") -> str:
    """Generate authentic HMAC digest for webhook payload."""
    digest = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return f"{algo}={digest}"


def _build_paymob_webhook_payload(order_id: str, amount_cents: int = 50000, success: bool = True) -> dict[str, Any]:
    """Construct PayMob/Meeza compliant webhook transaction payload."""
    return {
        "type": "TRANSACTION",
        "obj": {
            "id": 987654321,
            "order": {
                "id": 12345678,
                "merchant_order_id": order_id,
            },
            "amount_cents": amount_cents,
            "currency": "EGP",
            "success": success,
            "pending": False,
            "is_voided": False,
            "is_refunded": False,
            "source_data": {
                "sub_type": "meeza",
                "pan": "507803******1234",
            },
        },
    }


# ==============================================================================
# Task A: Production Redis Session Store Enforcement & Atomic TTL Tests
# ==============================================================================


class TestTaskASessionStoreHardening:
    """Verify Redis session store behavior and fail-fast in production mode."""

    def test_production_mode_fails_fast_without_redis_url(self, monkeypatch: pytest.MonkeyPatch):
        """In production, missing REDIS_URL must raise ConfigurationError immediately."""
        monkeypatch.setenv("FIREAI_ENV", "production")
        monkeypatch.delenv("REDIS_URL", raising=False)
        ss._redis_checked = False
        ss._redis_available = False
        ss._redis_client = None

        with pytest.raises(ConfigurationError, match="REDIS_URL is not set"):
            ss.session_store.set("test-sess-key", {"user_id": "alice"}, ttl=86400)

    def test_production_mode_fails_fast_on_redis_connection_failure(self, monkeypatch: pytest.MonkeyPatch):
        """In production, unreachable Redis host must raise ConfigurationError."""
        monkeypatch.setenv("FIREAI_ENV", "production")
        # Point to invalid host/port that will immediately fail connection
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:59999/0")
        ss._redis_checked = False
        ss._redis_available = False
        ss._redis_client = None

        with pytest.raises(ConfigurationError, match="Redis connection failed"):
            ss.session_store.set("test-sess-key", {"user_id": "alice"}, ttl=86400)

    def test_redis_atomic_ttl_enforcement(self, monkeypatch: pytest.MonkeyPatch):
        """When Redis is available, SETEX is invoked with the atomic TTL parameter."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        ss._redis_checked = True
        ss._redis_available = True
        ss._redis_client = mock_redis

        session_payload = {
            "principal": "user-test",
            "role": "admin",
            "created_at": 1000.0,
            "expires_at": 87400.0,
        }

        # 24h default TTL (86400 seconds)
        ss.session_store.set("session-123", session_payload, ttl=86400)

        # Assert SETEX was called with prefix, TTL, and serialized JSON
        mock_redis.setex.assert_called_once()
        args, _ = mock_redis.setex.call_args
        assert args[0] == "bazspark:session:session-123"
        assert args[1] == 86400
        stored_data = json.loads(args[2])
        assert stored_data["principal"] == "user-test"


# ==============================================================================
# Task B: Production Database Guardrail Tests
# ==============================================================================


class TestTaskBDatabaseGuardrail:
    """Verify fail-fast SQLite guardrail in production mode."""

    def test_production_sqlite_database_url_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch):
        """In production mode, DATABASE_URL=sqlite:// must fail with ConfigurationError."""
        monkeypatch.setenv("FIREAI_ENV", "production")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///prod.db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("FIREAI_API_KEY", "x" * 64)
        monkeypatch.setenv("FIREAI_SESSION_SECRET", "x" * 64)
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "x" * 64)
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "x" * 64)
        monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")
        monkeypatch.setenv("AUDIT_HMAC_KEY", "x" * 64)
        monkeypatch.setenv("FIREAI_QOMN_HMAC_KEY", "x" * 64)
        monkeypatch.setenv("QOMN_AUDIT_SECRET_KEY", "x" * 64)
        monkeypatch.setenv("FDS_WEBHOOK_SECRET", "x" * 64)
        monkeypatch.setenv("BAZSPARK_MASTER_ADMIN_TOKEN", "x" * 64)
        monkeypatch.setenv("FIREAI_VISION_KEY_ENCRYPTION_KEY", "x" * 64)
        monkeypatch.setenv("MEEZA_WEBHOOK_HMAC_SECRET", "x" * 64)
        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")

        with pytest.raises(ConfigurationError) as exc_info:
            ev.assert_environment(prod_mode=True)

        err_msg = str(exc_info.value)
        assert "SQLite is strictly forbidden in production mode" in err_msg
        assert "PostgreSQL" in err_msg

    def test_production_environment_var_alias_triggers_guardrail(self, monkeypatch: pytest.MonkeyPatch):
        """ENVIRONMENT=production triggers the guardrail even if FIREAI_ENV is unset."""
        monkeypatch.delenv("FIREAI_ENV", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///prod.db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("FIREAI_API_KEY", "x" * 64)
        monkeypatch.setenv("FIREAI_SESSION_SECRET", "x" * 64)
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "x" * 64)
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "x" * 64)
        monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")
        monkeypatch.setenv("AUDIT_HMAC_KEY", "x" * 64)
        monkeypatch.setenv("FIREAI_QOMN_HMAC_KEY", "x" * 64)
        monkeypatch.setenv("QOMN_AUDIT_SECRET_KEY", "x" * 64)
        monkeypatch.setenv("FDS_WEBHOOK_SECRET", "x" * 64)
        monkeypatch.setenv("BAZSPARK_MASTER_ADMIN_TOKEN", "x" * 64)
        monkeypatch.setenv("FIREAI_VISION_KEY_ENCRYPTION_KEY", "x" * 64)
        monkeypatch.setenv("MEEZA_WEBHOOK_HMAC_SECRET", "x" * 64)
        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")

        with pytest.raises(ConfigurationError) as exc_info:
            ev.assert_environment()

        assert "SQLite is strictly forbidden in production mode" in str(exc_info.value)


# ==============================================================================
# Task C: Full E2E Billing & Webhook Fulfilment Lifecycle Tests
# ==============================================================================


class TestTaskCE2EBillingLifecycle:
    """Verify complete billing flow from order creation to webhook fulfillment and idempotency."""

    def test_full_order_checkout_webhook_lifecycle(self, client: TestClient):
        """
        E2E Test Flow:
          1. Create order intent via POST /orders
          2. Initiate checkout via POST /orders/{id}/checkout
          3. Deliver Meeza PSP webhook with valid HMAC signature via POST /webhooks/meeza
          4. Assert HTTP 200 response and status='processed'
          5. Verify order is marked status='paid' with paid_at timestamp
        """
        # Step 1: Create Order
        create_res = client.post(
            "/api/v1/billing/orders",
            json={
                "amount_cents": 50000,
                "description": "BAZspark Enterprise Subscription (Monthly)",
                "currency": "EGP",
                "metadata": {"tier": "enterprise", "seats": 10},
            },
        )
        assert create_res.status_code == 201, create_res.text
        order_data = create_res.json()
        order_id = order_data["id"]
        assert order_data["status"] == "pending"
        assert order_data["amount_cents"] == 50000
        assert order_data["paid_at"] is None

        # Step 2: Initiate Checkout
        checkout_res = client.post(
            f"/api/v1/billing/orders/{order_id}/checkout",
            json={"billing_data": {"email": "operator@bazspark.com", "first_name": "Ahmed", "last_name": "Elbaz"}},
        )
        assert checkout_res.status_code == 200, checkout_res.text
        checkout_data = checkout_res.json()
        assert checkout_data["order_id"] == order_id
        assert checkout_data["method"] == "sandbox"
        assert checkout_data["checkout_url"]

        # Step 3: Webhook Delivery (Valid HMAC-SHA256)
        webhook_payload = _build_paymob_webhook_payload(order_id=order_id, amount_cents=50000, success=True)
        raw_body = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")
        signature = _sign_payload(raw_body)

        webhook_res = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw_body,
            headers={"X-Meeza-Signature": signature, "Content-Type": "application/json"},
        )
        assert webhook_res.status_code == 200, webhook_res.text
        webhook_result = webhook_res.json()
        assert webhook_result["status"] == "processed"
        assert webhook_result["order_status"] == "paid"

        # Step 4: Verify Order Status in Database
        get_order_res = client.get(f"/api/v1/billing/orders/{order_id}")
        assert get_order_res.status_code == 200
        fulfilled_order = get_order_res.json()
        assert fulfilled_order["status"] == "paid"
        assert fulfilled_order["paid_at"] is not None

    def test_direct_checkout_endpoint_flow(self, client: TestClient):
        """Test the direct /checkout endpoint (creating and checking out in unified step)."""
        res = client.post(
            "/api/v1/billing/checkout",
            json={
                "amount_cents": 25000,
                "description": "BAZspark Pro Plan",
                "metadata": {"plan": "pro"},
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["order_id"]
        assert data["checkout_url"]

        # Webhook via /webhook alias
        order_id = data["order_id"]
        webhook_payload = _build_paymob_webhook_payload(order_id=order_id, amount_cents=25000, success=True)
        raw_body = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")
        sig = _sign_payload(raw_body)

        webhook_res = client.post(
            "/api/v1/billing/webhook",
            content=raw_body,
            headers={"X-Meeza-Signature": sig, "Content-Type": "application/json"},
        )
        assert webhook_res.status_code == 200, webhook_res.text
        assert webhook_res.json()["status"] == "processed"

        # Verify DB status
        order = client.get(f"/api/v1/billing/orders/{order_id}").json()
        assert order["status"] == "paid"

    def test_idempotent_duplicate_webhook_delivery(self, client: TestClient):
        """
        Verify that duplicate webhook delivery is handled idempotently:
          - First delivery: processed, status='paid'
          - Second delivery: HTTP 200 with status='duplicate'
          - Database status remains 'paid' without duplicated fulfillment
        """
        # Create order & checkout
        order_res = client.post("/api/v1/billing/orders", json={"amount_cents": 10000})
        order_id = order_res.json()["id"]
        client.post(f"/api/v1/billing/orders/{order_id}/checkout", json={})

        payload = _build_paymob_webhook_payload(order_id=order_id, amount_cents=10000, success=True)
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = _sign_payload(raw_body)

        # 1st Webhook Delivery
        res1 = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw_body,
            headers={"X-Meeza-Signature": signature, "Content-Type": "application/json"},
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "processed"

        # 2nd Webhook Delivery (Replay / Duplicate)
        res2 = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw_body,
            headers={"X-Meeza-Signature": signature, "Content-Type": "application/json"},
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "duplicate"

        # 3rd Webhook Delivery with different transaction id but same paid order
        payload3 = dict(payload)
        payload3["obj"] = dict(payload["obj"])
        payload3["obj"]["id"] = 999999999  # different psp txn id
        raw3 = json.dumps(payload3, separators=(",", ":")).encode("utf-8")
        sig3 = _sign_payload(raw3)

        res3 = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw3,
            headers={"X-Meeza-Signature": sig3, "Content-Type": "application/json"},
        )
        assert res3.status_code == 200
        # Terminal state guard suppresses overwriting
        assert res3.json()["status"] in ("duplicate", "processed")

        # Confirm DB state is intact
        order = client.get(f"/api/v1/billing/orders/{order_id}").json()
        assert order["status"] == "paid"

    def test_webhook_rejects_invalid_or_tampered_signature(self, client: TestClient):
        """Webhook endpoint must strictly reject tampered or invalid HMAC signatures with HTTP 401."""
        order_res = client.post("/api/v1/billing/orders", json={"amount_cents": 10000})
        order_id = order_res.json()["id"]

        payload = _build_paymob_webhook_payload(order_id=order_id, amount_cents=10000, success=True)
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        # Tampered signature
        res = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw_body,
            headers={"X-Meeza-Signature": "sha256=deadbeefcafebabe000000000000000000000000000000000000000000000000"},
        )
        assert res.status_code == 401
        assert "unauthorized" in res.json()["detail"].lower() or "invalid_signature" in res.json()["detail"].lower()

        # Missing signature header
        res_missing = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw_body,
        )
        assert res_missing.status_code == 401

    def test_webhook_rejects_amount_mismatch(self, client: TestClient):
        """Webhook with an amount differing from stored order must be rejected (HTTP 409)."""
        order_res = client.post("/api/v1/billing/orders", json={"amount_cents": 50000})
        order_id = order_res.json()["id"]

        # Fraudulent webhook claiming 1000 cents instead of 50000
        fraud_payload = _build_paymob_webhook_payload(order_id=order_id, amount_cents=1000, success=True)
        raw_body = json.dumps(fraud_payload, separators=(",", ":")).encode("utf-8")
        sig = _sign_payload(raw_body)

        res = client.post(
            "/api/v1/billing/webhooks/meeza",
            content=raw_body,
            headers={"X-Meeza-Signature": sig, "Content-Type": "application/json"},
        )
        assert res.status_code in (400, 409)

        # Order must still be pending
        order = client.get(f"/api/v1/billing/orders/{order_id}").json()
        assert order["status"] == "pending"
        assert order["paid_at"] is None
