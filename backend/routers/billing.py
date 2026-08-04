"""
backend/routers/billing.py
==========================
Meeza (ميزة) Payment Gateway Router.

Exposes the billing/order/transaction endpoints and the Meeza webhook receiver.

Endpoints
---------
  POST /api/v1/billing/orders                       — create a new order
  GET  /api/v1/billing/orders                       — list caller's orders
  GET  /api/v1/billing/orders/{order_id}            — get a single order
  POST /api/v1/billing/orders/{order_id}/checkout   — initiate Meeza checkout
  GET  /api/v1/billing/transactions/{txn_id}        — get a transaction
  GET  /api/v1/billing/orders/{order_id}/transactions — list transactions for order
  GET  /api/v1/billing/orders/{order_id}/events     — list webhook events (audit)
  POST /api/v1/billing/webhooks/meeza               — Meeza PSP webhook (NO AUTH)

Security
--------
- All endpoints except the webhook require an authenticated principal.
- The webhook endpoint is UNAUTHENTICATED by design (the PSP cannot log in);
  it relies on HMAC/SHA-256 verification of the raw body. Reject with 401 on
  any signature mismatch.
- The webhook returns 200 for both processed and idempotent-duplicate events
  (per PSP best practice — returning non-2xx causes the PSP to retry, which
  wastes resources on already-processed events).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.auth import get_current_principal, require_permission
from backend.rbac import Permission
from backend.services import meeza_payment_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing & Meeza Payments"])

# ── Annotated dependency aliases ─────────────────────────────────────────────
Principal = Annotated[Optional[str], Depends(get_current_principal)]
BillingManageRole = Annotated[None, Depends(require_permission(Permission.BILLING_MANAGE))]


# ── Pydantic request/response models ────────────────────────────────────────

class OrderCreateRequest(BaseModel):
    amount_cents: int = Field(
        ..., gt=0, le=10_000_000_000,
        description="Amount in smallest currency unit (piastres for EGP).",
        examples=[50000],  # 500.00 EGP
    )
    currency: Optional[str] = Field(
        default=None, min_length=3, max_length=3,
        description="ISO 4217 currency code. Defaults to EGP.",
    )
    description: str = Field(default="", max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expires_in_seconds: int = Field(default=1800, ge=60, le=86400)


class CheckoutRequest(BaseModel):
    billing_data: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional billing details passed to the PSP (email, first_name, "
            "last_name, phone, city). Required only for live PSP mode."
        ),
    )


class OrderResponse(BaseModel):
    id: str
    user_principal: str
    amount_cents: int
    currency: str
    status: str
    description: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None
    paid_at: Optional[str] = None


class CheckoutResponse(BaseModel):
    order_id: str
    transaction_id: str
    checkout_url: str
    method: str  # "iframe" | "redirect" | "sandbox"
    raw: Dict[str, Any]


class WebhookResponse(BaseModel):
    status: str   # "processed" | "duplicate" | "rejected"
    http_status: int
    order_id: Optional[str] = None
    transaction_status: Optional[str] = None
    order_status: Optional[str] = None
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None


# ── Order endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new billing order",
)
async def create_order(
    body: OrderCreateRequest,
    principal: Principal,
) -> Dict[str, Any]:
    """Create a new order. The caller's principal is taken from the auth
    middleware — never trust a client-supplied user id."""
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        return svc.create_order(
            user_principal=principal,
            amount_cents=body.amount_cents,
            description=body.description,
            metadata=body.metadata,
            currency=body.currency,
            expires_in_seconds=body.expires_in_seconds,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get(
    "/orders",
    response_model=List[OrderResponse],
    summary="List caller's orders",
)
async def list_orders(
    principal: Principal,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required")
    return svc.list_orders(
        user_principal=principal,
        limit=limit, offset=offset,
        status=status_filter,
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get a single order",
)
async def get_order(
    order_id: str,
    principal: Principal,
) -> Dict[str, Any]:
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required")
    order = svc.get_order(order_id, user_principal=principal)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post(
    "/orders/{order_id}/checkout",
    response_model=CheckoutResponse,
    summary="Initiate Meeza checkout for an order",
)
async def initiate_checkout(
    order_id: str,
    body: CheckoutRequest,
    principal: Principal,
) -> Dict[str, Any]:
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return svc.initiate_checkout(
            order_id=order_id,
            user_principal=principal,
            billing_data=body.billing_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # NOSONAR — top-level guard for PSP HTTP errors
        logger.exception("Meeza checkout failed for order %s", order_id)
        raise HTTPException(
            status_code=502,
            detail=f"PSP communication error: {type(exc).__name__}",
        ) from exc


# ── Transaction / event audit endpoints ─────────────────────────────────────

@router.get(
    "/transactions/{txn_id}",
    summary="Get a payment transaction",
)
async def get_transaction(
    txn_id: str,
    principal: Principal,
    _: BillingManageRole,
) -> Dict[str, Any]:
    """Get a single transaction. Restricted to BILLING_MANAGE role because
    transactions may span multiple users (e.g. admin reconciliation)."""
    txn = svc.get_transaction(txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.get(
    "/orders/{order_id}/transactions",
    summary="List transactions for an order",
)
async def list_transactions_for_order(
    order_id: str,
    principal: Principal,
) -> List[Dict[str, Any]]:
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required")
    # Authorise: caller must own the order
    order = svc.get_order(order_id, user_principal=principal)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return svc.list_transactions_for_order(order_id)


@router.get(
    "/orders/{order_id}/events",
    summary="List webhook events for an order (audit trail)",
)
async def list_events_for_order(
    order_id: str,
    principal: Principal,
    _: BillingManageRole,
) -> List[Dict[str, Any]]:
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required")
    order = svc.get_order(order_id, user_principal=principal)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return svc.list_events_for_order(order_id)


# ── Meeza webhook receiver (UNAUTHENTICATED — HMAC-verified) ─────────────────

@router.post(
    "/webhooks/meeza",
    response_model=WebhookResponse,
    summary="Meeza PSP webhook receiver (no auth — HMAC verified)",
)
async def meeza_webhook(
    request: Request,
    x_meeza_signature: Annotated[str, Header(alias="X-Meeza-Signature")] = "",
    # Common alternative header names used by PSPs:
    signature: Annotated[str, Header()] = "",
) -> Dict[str, Any]:
    """Receive a Meeza webhook from the PSP.

    The raw body is read BEFORE any parsing so HMAC verification uses the
    exact bytes the PSP sent. JSON re-serialisation would change byte
    ordering and break the signature.

    Returns 200 for both processed and idempotent-duplicate events (PSP
    best practice). Returns 401 on signature mismatch. Returns 400 on
    malformed payload.
    """
    payload_raw = await request.body()
    sig_header = x_meeza_signature or signature
    if not sig_header:
        # Some PSPs use a query parameter or a different header name; if your
        # PSP uses one of those, extend this fallback list.
        sig_header = request.headers.get("X-Paymob-Signature", "")
    result = svc.handle_meeza_webhook(payload_raw, sig_header)
    http_status = result.get("http_status", 200)
    if http_status == 401:
        raise HTTPException(status_code=401, detail=result.get("reason", "unauthorized"))
    if http_status == 400:
        raise HTTPException(status_code=400, detail=result.get("reason", "bad_request"))
    return result


# ── Sandbox-only simulate endpoint (gated behind BILLING_MANAGE) ────────────

@router.post(
    "/orders/{order_id}/simulate-webhook",
    summary="[SANDBOX] Simulate a Meeza webhook delivery for an order",
    include_in_schema=svc.get_config().psp_name == svc.PSPName.SANDBOX,
)
async def simulate_webhook(
    order_id: str,
    _: BillingManageRole,
    txn_status: str = "SUCCESS",
) -> Dict[str, Any]:
    """Test-only endpoint to drive webhook flow without a live PSP.

    Only included in the OpenAPI schema when MEEZA_PSP_PROVIDER=sandbox.
    """
    cfg = svc.get_config()
    if cfg.psp_name != svc.PSPName.SANDBOX:
        raise HTTPException(
            status_code=403,
            detail="Simulation endpoint requires MEEZA_PSP_PROVIDER=sandbox",
        )
    try:
        target = svc.TxnStatus(txn_status.upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid txn_status. Valid: {[s.value for s in svc.TxnStatus]}",
        ) from exc
    return svc.simulate_webhook(order_id, target)
