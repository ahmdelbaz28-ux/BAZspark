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
from typing import Any

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated  # type: ignore[attr-defined]

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from backend.core.openapi_contracts import StandardizedAPIRoute
from pydantic import BaseModel, Field

from backend.auth import get_current_principal, require_permission
from backend.rbac import Permission
from backend.services import meeza_payment_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing & Meeza Payments"], route_class=StandardizedAPIRoute)

# ── Annotated dependency aliases ─────────────────────────────────────────────
Principal = Annotated[str | None, Depends(get_current_principal)]
BillingManageRole = Annotated[None, Depends(require_permission(Permission.BILLING_MANAGE))]

# ── Reused constants (SonarCloud S1192 — avoid literal duplication) ─────────
_MSG_AUTH_REQUIRED = "Authentication required"
_MSG_ORDER_NOT_FOUND = "Order not found"
_MSG_TXN_NOT_FOUND = "Transaction not found"
_CONTENT_TYPE_JSON = "application/json"


# ── Pydantic request/response models ────────────────────────────────────────


class OrderCreateRequest(BaseModel):
    amount_cents: int = Field(
        ...,
        gt=0,
        le=10_000_000_000,
        description="Amount in smallest currency unit (piastres for EGP).",
        examples=[50000],  # 500.00 EGP
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code. Defaults to EGP.",
    )
    description: str = Field(default="", max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_in_seconds: int = Field(default=1800, ge=60, le=86400)


class CheckoutRequest(BaseModel):
    billing_data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional billing details passed to the PSP (email, first_name, "
            "last_name, phone, city). Required only for live PSP mode."
        ),
    )


class DirectCheckoutRequest(BaseModel):
    order_id: str | None = None
    amount_cents: int | None = Field(default=None, gt=0, le=100_000_000)
    description: str = Field(default="Subscription checkout", max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    currency: str | None = None
    billing_data: dict[str, Any] = Field(default_factory=dict)


class OrderResponse(BaseModel):
    id: str
    user_principal: str
    amount_cents: int
    currency: str
    status: str
    description: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str
    expires_at: str | None = None
    paid_at: str | None = None


class CheckoutResponse(BaseModel):
    order_id: str
    transaction_id: str
    checkout_url: str
    method: str  # "iframe" | "redirect" | "sandbox"
    raw: dict[str, Any]


class WebhookResponse(BaseModel):
    status: str  # "processed" | "duplicate" | "rejected"
    http_status: int
    order_id: str | None = None
    transaction_status: str | None = None
    order_status: str | None = None
    idempotency_key: str | None = None
    reason: str | None = None


# ── Shared HTTPException helpers ─────────────────────────────────────────────
# SonarCloud S8415: HTTPException raises must be documented on the endpoint
# via the `responses=` parameter. Centralising the exception instances here
# keeps the response docs DRY (one place to update status codes / examples).


def _require_principal(principal: str | None) -> str:
    """Return the principal or raise 401. Used by every authenticated endpoint."""
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_MSG_AUTH_REQUIRED,
        )
    return principal


def _raise_order_not_found() -> None:
    raise HTTPException(status_code=404, detail=_MSG_ORDER_NOT_FOUND)


def _raise_txn_not_found() -> None:
    raise HTTPException(status_code=404, detail=_MSG_TXN_NOT_FOUND)


# Standard response models reused across endpoints (for OpenAPI `responses=`)
_ERROR_401 = {
    "description": "Authentication required",
    "content": {_CONTENT_TYPE_JSON: {"example": {"detail": _MSG_AUTH_REQUIRED}}},
}
_ERROR_400 = {
    "description": "Bad request (validation or business rule)",
    "content": {_CONTENT_TYPE_JSON: {"example": {"detail": "..."}}},
}
_ERROR_403 = {
    "description": "Forbidden (role required or sandbox-only)",
    "content": {_CONTENT_TYPE_JSON: {"example": {"detail": "..."}}},
}
_ERROR_404 = {
    "description": "Order or transaction not found",
    "content": {_CONTENT_TYPE_JSON: {"example": {"detail": _MSG_ORDER_NOT_FOUND}}},
}
_ERROR_501 = {
    "description": "Not implemented (live PSP not configured)",
    "content": {_CONTENT_TYPE_JSON: {"example": {"detail": "..."}}},
}
_ERROR_502 = {
    "description": "PSP communication error",
    "content": {_CONTENT_TYPE_JSON: {"example": {"detail": "PSP communication error: ..."}}},
}


# ── Order endpoints ──────────────────────────────────────────────────────────


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new billing order",
    responses={401: _ERROR_401, 400: _ERROR_400},
)
async def create_order(
    body: OrderCreateRequest,
    principal: Principal,
) -> dict[str, Any]:
    """Create a new order. The caller's principal is taken from the auth
    middleware — never trust a client-supplied user id."""
    user = _require_principal(principal)
    try:
        return svc.create_order(
            user_principal=user,
            amount_cents=body.amount_cents,
            description=body.description,
            metadata=body.metadata,
            currency=body.currency,
            expires_in_seconds=body.expires_in_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/orders",
    response_model=list[OrderResponse],
    summary="list caller's orders",
    responses={401: _ERROR_401},
)
async def list_orders(
    principal: Principal,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    user = _require_principal(principal)
    return svc.list_orders(
        user_principal=user,
        limit=limit,
        offset=offset,
        status=status_filter,
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get a single order",
    responses={401: _ERROR_401, 404: _ERROR_404},
)
async def get_order(
    order_id: str,
    principal: Principal,
) -> dict[str, Any]:
    user = _require_principal(principal)
    order = svc.get_order(order_id, user_principal=user)
    if order is None:
        _raise_order_not_found()
    return order


@router.post(
    "/orders/{order_id}/checkout",
    response_model=CheckoutResponse,
    summary="Initiate Meeza checkout for an order",
    responses={
        401: _ERROR_401,
        400: _ERROR_400,
        501: _ERROR_501,
        502: _ERROR_502,
    },
)
async def initiate_checkout(
    order_id: str,
    body: CheckoutRequest,
    principal: Principal,
) -> dict[str, Any]:
    user = _require_principal(principal)
    try:
        return svc.initiate_checkout(
            order_id=order_id,
            user_principal=user,
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


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Direct checkout intent creation and initialization",
    responses={
        401: _ERROR_401,
        400: _ERROR_400,
        501: _ERROR_501,
        502: _ERROR_502,
    },
)
async def direct_checkout(
    body: DirectCheckoutRequest,
    principal: Principal,
) -> dict[str, Any]:
    user = _require_principal(principal)
    try:
        target_order_id = body.order_id
        if not target_order_id:
            if not body.amount_cents:
                raise HTTPException(
                    status_code=400, detail="Either order_id or amount_cents is required"
                )
            order = svc.create_order(
                user_principal=user,
                amount_cents=body.amount_cents,
                description=body.description,
                metadata=body.metadata,
                currency=body.currency,
            )
            target_order_id = order["id"]
        return svc.initiate_checkout(
            order_id=target_order_id,
            user_principal=user,
            billing_data=body.billing_data,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # NOSONAR — top-level guard for PSP HTTP errors
        logger.exception("Direct checkout failed for user %s", user)
        raise HTTPException(
            status_code=502,
            detail=f"PSP communication error: {type(exc).__name__}",
        ) from exc


# ── Direct Meeza Gateway Endpoints ──


# ── Transaction / event audit endpoints ─────────────────────────────────────


@router.get(
    "/transactions/{txn_id}",
    summary="Get a payment transaction",
    responses={401: _ERROR_401, 403: _ERROR_403, 404: _ERROR_404},
)
async def get_transaction(
    txn_id: str,
    principal: Principal,
    _: BillingManageRole,
) -> dict[str, Any]:
    """Get a single transaction. Restricted to BILLING_MANAGE role because
    transactions may span multiple users (e.g. admin reconciliation)."""
    _require_principal(principal)
    txn = svc.get_transaction(txn_id)
    if txn is None:
        _raise_txn_not_found()
    return txn


@router.get(
    "/orders/{order_id}/transactions",
    summary="list transactions for an order",
    responses={401: _ERROR_401, 404: _ERROR_404},
)
async def list_transactions_for_order(
    order_id: str,
    principal: Principal,
) -> list[dict[str, Any]]:
    user = _require_principal(principal)
    # Authorise: caller must own the order
    order = svc.get_order(order_id, user_principal=user)
    if order is None:
        _raise_order_not_found()
    return svc.list_transactions_for_order(order_id)


@router.get(
    "/orders/{order_id}/events",
    summary="list webhook events for an order (audit trail)",
    responses={401: _ERROR_401, 403: _ERROR_403, 404: _ERROR_404},
)
async def list_events_for_order(
    order_id: str,
    principal: Principal,
    _: BillingManageRole,
) -> list[dict[str, Any]]:
    user = _require_principal(principal)
    order = svc.get_order(order_id, user_principal=user)
    if order is None:
        _raise_order_not_found()
    return svc.list_events_for_order(order_id)


# ── Meeza webhook receiver (UNAUTHENTICATED — HMAC-verified) ─────────────────


@router.post(
    "/webhooks/meeza",
    response_model=WebhookResponse,
    summary="Meeza PSP webhook receiver (no auth — HMAC verified)",
    responses={400: _ERROR_400, 401: _ERROR_401},
)
async def meeza_webhook(
    request: Request,
    x_meeza_signature: Annotated[str, Header(alias="X-Meeza-Signature")] = "",
    # Common alternative header names used by PSPs:
    signature: Annotated[str, Header()] = "",
) -> dict[str, Any]:
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
    if http_status != 200:
        raise HTTPException(
            status_code=http_status,
            detail=result.get("reason", "webhook_error"),
        )
    return result


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Meeza PSP webhook receiver alias",
    include_in_schema=False,
    responses={400: _ERROR_400, 401: _ERROR_401},
)
async def meeza_webhook_alias(
    request: Request,
    x_meeza_signature: Annotated[str, Header(alias="X-Meeza-Signature")] = "",
    signature: Annotated[str, Header()] = "",
) -> dict[str, Any]:
    """Alias for /webhooks/meeza for webhook dispatchers configured with /webhook."""
    return await meeza_webhook(
        request=request, x_meeza_signature=x_meeza_signature, signature=signature
    )


# ── Sandbox-only simulate endpoint (gated behind BILLING_MANAGE) ────────────


@router.post(
    "/orders/{order_id}/simulate-webhook",
    summary="[SANDBOX] Simulate a Meeza webhook delivery for an order",
    include_in_schema=svc.get_config().psp_name == svc.PSPName.SANDBOX,
    responses={400: _ERROR_400, 403: _ERROR_403},
)
async def simulate_webhook(
    order_id: str,
    _: BillingManageRole,
    txn_status: str = "SUCCESS",
) -> dict[str, Any]:
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
