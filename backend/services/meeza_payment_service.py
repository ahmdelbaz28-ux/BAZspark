"""
backend/services/meeza_payment_service.py
=========================================
Meeza (ميزة) Payment Gateway Service.

Production-ready payment flow for the Egyptian Meeza national payment network.
Supports Meeza Card transactions (National Debit / Prepaid / Credit) routed via
a configurable Payment Service Provider (PayMob / Fawry / NBE / Banque Misr).

Architecture
------------
  [BAZspark API]
        │  POST /billing/orders        → create_order()
        │  POST /billing/orders/{id}/checkout → initiate_checkout()
        │                                           │
        │                                           ▼
        │                              [PSP REST API: register order + payment_key]
        │                                           │
        │   ◄── iframe URL / redirect URL ──────────┘
        │
        │   [User completes Meeza card entry on PSP-hosted iframe]
        │                                           │
        │                                           ▼
  [PSP] ──── POST /billing/webhooks/meeza ───► handle_meeza_webhook()
                                                    │
                                                    ▼
                                        ┌───────────────────────┐
                                        │ 1. Verify HMAC        │
                                        │ 2. Idempotency check  │
                                        │ 3. Atomic status      │
                                        │    transition         │
                                        │ 4. Fulfill order      │
                                        │    (exactly once)     │
                                        └───────────────────────┘

Security
--------
- HMAC/SHA-256 (default) or HMAC/SHA-512 verification of every webhook payload.
  Constant-time comparison via `hmac.compare_digest`.
- Idempotent transaction processing:
  * Each webhook event has a derived idempotency_key = sha256(psp_name|order_id|txn_id|status|amount_cents).
  * UNIQUE constraint on payment_events.idempotency_key rejects duplicate inserts.
  * Order status transitions guarded by atomic
    `UPDATE orders SET status=? WHERE id=? AND status != 'paid'` — the
    WHERE clause guarantees only the first SUCCESS webhook flips an order to
    `paid`; subsequent duplicates hit the idempotency guard and return the
    cached response without re-fulfilling.
- Optional Redis Redlock (defense-in-depth) when REDIS_URL is configured, to
  serialise fulfillment across multiple backend instances. The SQLite atomic
  UPDATE remains the source of truth — Redlock is a fence, not a replacement.

Persistence
-----------
Uses the project-wide SQLite database (core/database.py). Tables are created
lazily on first call via `CREATE TABLE IF NOT EXISTS`, mirroring the existing
fds_queue_service pattern. Alembic ORM models live in backend/db_models.py
for migration autogeneration.

Demo mode
---------
If MEEZA_PSP_API_KEY is not set, the service runs in LOCAL_SIMULATION mode:
checkout returns a synthetic iframe URL, and `simulate_webhook()` lets tests
and demos trigger status transitions without an external PSP.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import types
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# SonarCloud S1192: avoid duplicating this literal across _paymob_checkout
_JSON_CONTENT_TYPE = "application/json"


# ── Enums ────────────────────────────────────────────────────────────────────

class OrderStatus(str, Enum):
    """Order lifecycle states. `paid` is terminal-success, the others are
    recoverable or terminal-failure."""
    PENDING   = "pending"
    PAID      = "paid"
    FAILED    = "failed"
    EXPIRED   = "expired"
    CANCELLED = "cancelled"
    REFUNDED  = "refunded"


class TxnStatus(str, Enum):
    """Per-transaction status. Mapped from PSP-specific codes by the adapter."""
    PENDING   = "PENDING"
    SUCCESS   = "SUCCESS"
    FAILED    = "FAILED"
    EXPIRED   = "EXPIRED"
    CANCELLED = "CANCELLED"


class PSPName(str, Enum):
    """Supported Payment Service Providers for Meeza card routing."""
    PAYMOB     = "paymob"
    FAWRY      = "fawry"
    NBE        = "nbe"
    BANQUE_MISR = "banque_misr"
    SANDBOX    = "sandbox"   # local demo / test adapter


# ── Configuration ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MeezaConfig:
    """All Meeza-related configuration, loaded once at module import."""
    psp_name: PSPName
    api_key: str
    hmac_secret: str
    hmac_algorithm: str                # "sha256" | "sha512"
    merchant_id: str
    iframe_id: str                     # PayMob iframe ID, or equivalent
    psp_base_url: str
    webhook_return_url: str
    currency: str                      # ISO 4217, e.g. "EGP"
    enabled: bool

    @classmethod
    def from_env(cls) -> MeezaConfig:
        psp_raw = os.getenv("MEEZA_PSP_PROVIDER", "sandbox").lower().strip()
        try:
            psp = PSPName(psp_raw)
        except ValueError:
            logger.warning(
                "MEEZA_PSP_PROVIDER=%r not in %s — falling back to sandbox",
                psp_raw, [p.value for p in PSPName],
            )
            psp = PSPName.SANDBOX

        api_key = os.getenv("MEEZA_PSP_API_KEY", "").strip()
        hmac_secret = os.getenv("MEEZA_WEBHOOK_HMAC_SECRET", "").strip()
        algo = os.getenv("MEEZA_HMAC_ALGORITHM", "sha256").lower().strip()
        if algo not in ("sha256", "sha512"):
            logger.warning("MEEZA_HMAC_ALGORITHM=%r unsupported — defaulting to sha256", algo)
            algo = "sha256"

        return cls(
            psp_name=psp,
            api_key=api_key,
            hmac_secret=hmac_secret,
            hmac_algorithm=algo,
            merchant_id=os.getenv("MEEZA_MERCHANT_ID", "").strip(),
            iframe_id=os.getenv("MEEZA_PSP_IFRAME_ID", "").strip(),
            psp_base_url=os.getenv(
                "MEEZA_PSP_BASE_URL",
                "https://accept.paymob.com/api" if psp == PSPName.PAYMOB else "",
            ).rstrip("/"),
            webhook_return_url=os.getenv("MEEZA_RETURN_URL", "").strip(),
            currency=os.getenv("MEEZA_CURRENCY", "EGP").upper().strip(),
            enabled=bool(api_key and hmac_secret),
        )


_CONFIG: Optional[MeezaConfig] = None
_CONFIG_LOCK = threading.Lock()


def get_config() -> MeezaConfig:
    """Return the cached MeezaConfig singleton."""
    global _CONFIG
    if _CONFIG is None:
        with _CONFIG_LOCK:
            if _CONFIG is None:
                _CONFIG = MeezaConfig.from_env()
                if not _CONFIG.enabled:
                    logger.info(
                        "Meeza Payment: LOCAL_SIMULATION mode — set MEEZA_PSP_API_KEY "
                        "and MEEZA_WEBHOOK_HMAC_SECRET to enable live PSP calls "
                        "(provider=%s).",
                        _CONFIG.psp_name.value,
                    )
    return _CONFIG


# ── SQLite connection (shared with project DB) ──────────────────────────────

_DB_PATH = os.environ.get(
    "FIREAI_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "data"),
)
_DB_PATH = os.path.abspath(_DB_PATH)
os.makedirs(_DB_PATH, exist_ok=True)
_BILLING_DB_PATH = os.environ.get(
    "MEEZA_DB_PATH",
    os.path.join(_DB_PATH, "billing.sqlite"),
)

_SCHEMA_LOCK = threading.Lock()
_SCHEMA_INITIALIZED = False


def _get_conn() -> sqlite3.Connection:
    """Return a SQLite connection with WAL mode + reasonable defaults.

    WAL allows concurrent readers while a writer holds the lock — critical
    for the atomic UPDATE pattern used in fulfillment.
    """
    conn = sqlite3.connect(_BILLING_DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _init_schema() -> None:
    """Create tables if missing. Idempotent — safe to call on every request."""
    global _SCHEMA_INITIALIZED
    if _SCHEMA_INITIALIZED:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_INITIALIZED:
            return
        with _get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id              TEXT PRIMARY KEY,
                    user_principal  TEXT NOT NULL,
                    amount_cents    INTEGER NOT NULL,
                    currency        TEXT NOT NULL DEFAULT 'EGP',
                    status          TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (status IN
                                        ('pending','paid','failed','expired','cancelled','refunded')),
                    description     TEXT NOT NULL DEFAULT '',
                    metadata        TEXT NOT NULL DEFAULT '{}',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    expires_at      TEXT,
                    paid_at         TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_orders_user     ON orders(user_principal);
                CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_created  ON orders(created_at);

                CREATE TABLE IF NOT EXISTS payment_transactions (
                    id                TEXT PRIMARY KEY,
                    order_id          TEXT NOT NULL,
                    psp_name          TEXT NOT NULL,
                    psp_order_id      TEXT,
                    psp_payment_key   TEXT,
                    psp_txn_id        TEXT,
                    amount_cents      INTEGER NOT NULL,
                    currency          TEXT NOT NULL DEFAULT 'EGP',
                    status            TEXT NOT NULL DEFAULT 'PENDING'
                                        CHECK (status IN
                                            ('PENDING','SUCCESS','FAILED','EXPIRED','CANCELLED')),
                    idempotency_key   TEXT NOT NULL UNIQUE,
                    raw_payload       TEXT NOT NULL DEFAULT '{}',
                    hmac_signature    TEXT,
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL,
                    completed_at      TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_txn_order ON payment_transactions(order_id);
                CREATE INDEX IF NOT EXISTS idx_txn_status ON payment_transactions(status);
                CREATE INDEX IF NOT EXISTS idx_txn_psp   ON payment_transactions(psp_txn_id);

                CREATE TABLE IF NOT EXISTS payment_events (
                    id                TEXT PRIMARY KEY,
                    transaction_id    TEXT,
                    order_id          TEXT NOT NULL,
                    event_type        TEXT NOT NULL,
                    psp_name          TEXT NOT NULL,
                    idempotency_key   TEXT NOT NULL UNIQUE,
                    raw_payload       TEXT NOT NULL DEFAULT '{}',
                    hmac_signature    TEXT,
                    processed_at      TEXT NOT NULL,
                    response_code     INTEGER NOT NULL DEFAULT 200,
                    FOREIGN KEY (transaction_id) REFERENCES payment_transactions(id) ON DELETE SET NULL,
                    FOREIGN KEY (order_id)         REFERENCES orders(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_evt_order ON payment_events(order_id);
                CREATE INDEX IF NOT EXISTS idx_evt_idem ON payment_events(idempotency_key);
                """
            )
        _SCHEMA_INITIALIZED = True


# ── Optional Redis Redlock (defense-in-depth for multi-instance) ────────────

_REDIS_LOCK_MODULE = None
try:
    import redis
    import redis.lock  # noqa: F401
    _REDIS_LOCK_MODULE = redis
except ImportError:
    redis = None  # type: ignore[assignment]

_REDIS_CLIENT = None
_REDIS_CLIENT_LOCK = threading.Lock()


def _get_redis_client() -> Any:
    """Return a Redis client if REDIS_URL is set and redis-py is installed.

    Returns None otherwise. The caller must handle the None case gracefully
    — Redlock is a fence, not a hard requirement.
    """
    global _REDIS_CLIENT
    if _REDIS_LOCK_MODULE is None:
        return None
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    if _REDIS_CLIENT is None:
        with _REDIS_CLIENT_LOCK:
            if _REDIS_CLIENT is None:
                try:
                    _REDIS_CLIENT = _REDIS_LOCK_MODULE.from_url(
                        redis_url, decode_responses=True, socket_timeout=3.0,
                    )
                    _REDIS_CLIENT.ping()  # fail fast
                    logger.info("Meeza Payment: Redis Redlock fence enabled (%s)", redis_url)
                except Exception as exc:  # NOSONAR — broad on purpose
                    logger.warning(
                        "Meeza Payment: Redis available but connection failed (%s); "
                        "falling back to SQLite-only atomicity. This is safe for "
                        "single-instance deployments.", type(exc).__name__,
                    )
                    _REDIS_CLIENT = None
    return _REDIS_CLIENT


class _RedlockFence:
    """Context manager that acquires a Redis lock if available, else no-ops."""

    def __init__(self, key: str, ttl_ms: int = 5000):
        self.key = f"meeza:lock:{key}"
        self.ttl_ms = ttl_ms
        self._lock: Optional[Any] = None
        self._client: Optional[Any] = None

    def __enter__(self) -> _RedlockFence:
        self._client = _get_redis_client()
        if self._client is not None:
            try:
                self._lock = self._client.lock(self.key, timeout=self.ttl_ms / 1000.0)
                # `block=True` with a small timeout — if we can't acquire the
                # fence within 1.5s, we proceed without it. The SQLite atomic
                # UPDATE is the actual correctness guarantee.
                self._lock.acquire(block=True, timeout=1.5)
            except Exception as exc:  # NOSONAR — broad on purpose
                logger.warning(
                    "Meeza Payment: Redlock acquire failed (%s); proceeding "
                    "with SQLite-only atomicity.", type(exc).__name__,
                )
                self._lock = None
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc: Optional[BaseException],
        tb: Optional[types.TracebackType],
    ) -> None:
        if self._lock is not None:
            try:
                self._lock.release()
            except Exception:  # NOSONAR — lock may have expired; safe to ignore
                pass


# ── HMAC verification ────────────────────────────────────────────────────────

def _hmac_digest(secret: str, message: bytes, algorithm: str) -> str:
    """Compute the HMAC hex digest."""
    digestmod = hashlib.sha256 if algorithm == "sha256" else hashlib.sha512
    return hmac.new(secret.encode("utf-8"), message, digestmod).hexdigest()


def verify_webhook_signature(
    payload_raw: bytes,
    signature_header: str,
    secret: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> bool:
    """Verify the HMAC signature of a webhook payload.

    Args:
        payload_raw:       Raw request body bytes (NEVER the parsed dict —
                           JSON re-serialisation changes byte ordering and
                           breaks the signature).
        signature_header:  Value of the signature header (e.g. `sha256=<hex>`
                           or just `<hex>`).
        secret:            HMAC secret. Defaults to config.hmac_secret.
        algorithm:         "sha256" or "sha512". Defaults to config.hmac_algorithm.

    Returns:
        True if signature matches; False otherwise (or if secret is empty).

    Security notes:
        - Uses `hmac.compare_digest` for constant-time comparison.
        - Strips optional `sha256=` / `sha512=` prefix from the header
          (GitHub/PayMob-style).
        - Returns False (not raises) on any mismatch — the caller decides
          whether to 401 or 400.
    """
    cfg = get_config()
    secret = secret if secret is not None else cfg.hmac_secret
    algorithm = algorithm if algorithm is not None else cfg.hmac_algorithm
    if not secret:
        logger.error(
            "Meeza Payment: webhook verification attempted with empty secret — "
            "set MEEZA_WEBHOOK_HMAC_SECRET."
        )
        return False
    if not signature_header:
        return False

    # Strip "sha256=" / "sha512=" prefix if present (GitHub/Stripe convention).
    expected = signature_header.strip()
    for prefix in (f"{algorithm}=", "sha256=", "sha512="):
        if expected.lower().startswith(prefix):
            expected = expected[len(prefix):]
            break

    actual = _hmac_digest(secret, payload_raw, algorithm)
    # Constant-time compare. We compare full hex strings of equal length;
    # compare_digest still short-circuits safely if lengths differ.
    return hmac.compare_digest(actual, expected)


# ── Idempotency key derivation ───────────────────────────────────────────────

def derive_idempotency_key(
    psp_name: str,
    order_id: str,
    txn_id: str,
    status: str,
    amount_cents: int,
) -> str:
    """Derive a deterministic idempotency key from the PSP webhook fields.

    Two webhook deliveries that carry the same (psp, order, txn, status,
    amount) tuple are treated as duplicates. The amount is included so a
    partial-capture follow-up event does NOT collide with the original
    authorization event.
    """
    raw = f"{psp_name}|{order_id}|{txn_id}|{status}|{amount_cents}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Public service API ───────────────────────────────────────────────────────

@dataclass
class Order:
    id: str
    user_principal: str
    amount_cents: int
    currency: str
    status: str
    description: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    expires_at: Optional[str]
    paid_at: Optional[str]


@dataclass
class CheckoutResult:
    order_id: str
    transaction_id: str
    checkout_url: str
    method: str   # "iframe" | "redirect" | "sandbox"
    raw: Dict[str, Any]


def create_order(
    user_principal: str,
    amount_cents: int,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    currency: Optional[str] = None,
    expires_in_seconds: int = 1800,
) -> Dict[str, Any]:
    """Create a new order.

    Args:
        user_principal:  Caller's opaque principal id (from auth middleware).
        amount_cents:    Positive integer in smallest currency unit (e.g. piastres).
        description:     Human-readable description (max 500 chars).
        metadata:        Arbitrary caller metadata (JSON-serialisable).
        currency:        ISO 4217 currency. Defaults to config.currency (EGP).
        expires_in_seconds: Order expiration window. Default 30 minutes.

    Returns:
        Dict representation of the created order.

    Raises:
        ValueError: on invalid input (non-positive amount, empty principal,
                    description > 500 chars).
    """
    if not user_principal:
        raise ValueError("user_principal is required")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be a positive integer")
    if amount_cents > 10_000_000_000:  # 100k EGP sanity cap
        raise ValueError("amount_cents exceeds sanity cap (100k EGP)")
    if len(description) > 500:
        raise ValueError("description must be <= 500 chars")

    _init_schema()
    cfg = get_config()
    now = datetime.now(timezone.utc).isoformat()
    expires_at = datetime.now(timezone.utc).timestamp() + expires_in_seconds
    expires_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()

    order_id = str(uuid.uuid4())
    metadata_json = json.dumps(metadata or {}, separators=(",", ":"))

    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO orders
                (id, user_principal, amount_cents, currency, status,
                 description, metadata, created_at, updated_at, expires_at, paid_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, NULL)
            """,
            (order_id, user_principal, amount_cents,
             currency or cfg.currency, description, metadata_json,
             now, now, expires_iso),
        )

    logger.info(
        "Meeza Payment: order created (user=%s, amount=%d %s)",
        user_principal[:8], amount_cents, currency or cfg.currency,
    )
    return {
        "id": order_id,
        "user_principal": user_principal,
        "amount_cents": amount_cents,
        "currency": currency or cfg.currency,
        "status": OrderStatus.PENDING.value,
        "description": description,
        "metadata": metadata or {},
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_iso,
    }


def get_order(order_id: str, user_principal: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch an order by id. If `user_principal` is given, the order must
    belong to that principal (otherwise None is returned — defence-in-depth
    against IDOR)."""
    _init_schema()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?" +
            (" AND user_principal = ?" if user_principal else ""),
            (order_id, user_principal) if user_principal else (order_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_order_dict(row)


def list_orders(
    user_principal: str,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List orders for a principal, newest first."""
    _init_schema()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    sql = "SELECT * FROM orders WHERE user_principal = ?"
    params: Tuple[Any, ...] = (user_principal,)
    if status:
        sql += " AND status = ?"
        params = (*params, status)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params = (*params, limit, offset)
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_order_dict(r) for r in rows]


def initiate_checkout(
    order_id: str,
    user_principal: str,
    billing_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Initiate a Meeza checkout for an order.

    Returns a dict with:
        - checkout_url:  URL the frontend should load in an iframe or redirect to.
        - method:        "iframe" | "redirect" | "sandbox"
        - transaction_id: Internal transaction id for tracking.
        - order_id, raw

    In sandbox mode (no PSP configured), returns a synthetic URL and the
    transaction is recorded in PENDING state for later `simulate_webhook()`.

    In live mode (PayMob), this calls:
        1. POST /auth/tokens           → auth token
        2. POST /ecommerce/orders      → psp_order_id
        3. POST /acceptance/payment_keys → payment_key
        4. Build iframe URL: {base}/acceptance/iframes/{iframe_id}?payment_token={key}
    """
    _init_schema()
    cfg = get_config()

    order = get_order(order_id, user_principal=user_principal)
    if order is None:
        raise ValueError(f"Order {order_id} not found for principal")
    if order["status"] != OrderStatus.PENDING.value:
        raise ValueError(f"Order {order_id} is not pending (status={order['status']})")

    # Check expiration
    if order["expires_at"]:
        try:
            exp_ts = datetime.fromisoformat(order["expires_at"]).timestamp()
            if datetime.now(timezone.utc).timestamp() > exp_ts:
                _expire_order(order_id)
                raise ValueError(f"Order {order_id} has expired")
        except (ValueError, TypeError):
            pass  # malformed expires_at — don't block checkout

    txn_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    # Per-attempt idempotency key (different from webhook idempotency key,
    # which is derived from PSP-side fields). This prevents double-charge if
    # the frontend retries the checkout call.
    init_idem = hashlib.sha256(
        f"init|{order_id}|{txn_id}".encode()
    ).hexdigest()

    if not cfg.enabled:
        # ── Sandbox / demo mode ─────────────────────────────────────────
        checkout_url = (
            f"https://sandbox.bazspark.local/meeza/checkout?"
            f"order_id={order_id}&txn_id={txn_id}"
        )
        psp_order_id = f"sandbox-{order_id[:8]}"
        psp_payment_key = f"sandbox-key-{txn_id[:8]}"
        method = "sandbox"
        raw: Dict[str, Any] = {"mode": "sandbox", "demo": True}
    else:
        # ── Live PSP call ──────────────────────────────────────────────
        # Adapter dispatch — currently PayMob is fully implemented; other
        # providers raise NotImplementedError with a clear message so the
        # caller can configure a supported provider.
        if cfg.psp_name == PSPName.PAYMOB:
            checkout_url, psp_order_id, psp_payment_key, raw = _paymob_checkout(
                cfg, order, billing_data or {},
            )
            method = "iframe"
        else:
            raise NotImplementedError(
                f"PSP adapter for {cfg.psp_name.value} is not yet implemented. "
                f"Configure MEEZA_PSP_PROVIDER=paymob or sandbox."
            )

    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO payment_transactions
                (id, order_id, psp_name, psp_order_id, psp_payment_key,
                 psp_txn_id, amount_cents, currency, status, idempotency_key,
                 raw_payload, hmac_signature, created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 'PENDING', ?, ?, NULL, ?, ?, NULL)
            """,
            (txn_id, order_id, cfg.psp_name.value, psp_order_id,
             psp_payment_key, order["amount_cents"], order["currency"],
             init_idem, json.dumps(raw, separators=(",", ":")),
             now, now),
        )

    logger.info(
        "Meeza Payment: checkout initiated (order=%s, txn=%s, method=%s)",
        order_id[:8], txn_id[:8], method,
    )
    return {
        "order_id": order_id,
        "transaction_id": txn_id,
        "checkout_url": checkout_url,
        "method": method,
        "raw": raw,
    }


def _paymob_checkout(
    cfg: MeezaConfig,
    order: Dict[str, Any],
    billing_data: Dict[str, Any],
) -> Tuple[str, str, str, Dict[str, Any]]:
    """PayMob-specific checkout flow. Returns (iframe_url, psp_order_id,
    payment_key, raw_response).

    Live HTTP calls happen here. Kept separate so tests can monkeypatch
    `_paymob_checkout` to mock the network.
    """
    import urllib.error
    import urllib.request

    base = cfg.psp_base_url

    # 1. Auth token
    auth_req = urllib.request.Request(
        f"{base}/auth/tokens",
        data=json.dumps({"api_key": cfg.api_key}).encode("utf-8"),
        headers={"Content-Type": _JSON_CONTENT_TYPE},
        method="POST",
    )
    with urllib.request.urlopen(auth_req, timeout=10) as resp:  # nosec: B310 — verified URL
        auth_body = json.loads(resp.read())
    auth_token = auth_body["token"]

    # 2. Register order
    order_req = urllib.request.Request(
        f"{base}/ecommerce/orders",
        data=json.dumps({
            "auth_token": auth_token,
            "delivery_needed": "false",
            "merchant_id": cfg.merchant_id,
            "amount_cents": order["amount_cents"],
            "currency": order["currency"],
            "merchant_order_id": order["id"],
            "items": [],
        }).encode("utf-8"),
        headers={"Content-Type": _JSON_CONTENT_TYPE},
        method="POST",
    )
    with urllib.request.urlopen(order_req, timeout=10) as resp:  # nosec: B310
        order_body = json.loads(resp.read())
    psp_order_id = str(order_body["id"])

    # 3. Payment key
    pay_req = urllib.request.Request(
        f"{base}/acceptance/payment_keys",
        data=json.dumps({
            "auth_token": auth_token,
            "amount_cents": order["amount_cents"],
            "expiration": 3600,
            "order_id": psp_order_id,
            "billing_data": {
                "apartment": "803",
                "email": billing_data.get("email", "customer@bazspark.com"),
                "floor": "42",
                "first_name": billing_data.get("first_name", "Customer"),
                "last_name": billing_data.get("last_name", "BAZspark"),
                "street": "Nile Street",
                "building": "Cairo Tower",
                "phone_number": billing_data.get("phone", "+201000000000"),
                "shipping_method": "PKG",
                "postal_code": "11511",
                "city": billing_data.get("city", "Cairo"),
                "country": "EG",
                "state": "Cairo",
            },
            "currency": order["currency"],
            "integration_id": int(os.getenv("MEEZA_PAYMOB_INTEGRATION_ID", "0")),
            "lock_order_when_paid": "true",
        }).encode("utf-8"),
        headers={"Content-Type": _JSON_CONTENT_TYPE},
        method="POST",
    )
    with urllib.request.urlopen(pay_req, timeout=10) as resp:  # nosec: B310
        pay_body = json.loads(resp.read())
    payment_key = pay_body["token"]

    # 4. Iframe URL — Meeza cards are routed via PayMob's Meeza integration ID.
    iframe_url = f"https://accept.paymob.com/api/acceptance/iframes/{cfg.iframe_id}?payment_token={payment_key}"
    return iframe_url, psp_order_id, payment_key, {
        "psp_order_id": psp_order_id,
        "payment_key_prefix": payment_key[:8] + "...",
        "iframe_url_prefix": iframe_url[:60] + "...",
    }


def _extract_webhook_fields(
    payload_parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract standard fields from a Meeza/PayMob webhook payload.

    Tolerates both nested (``{obj: {...}}``) and flat shapes. Returns a dict
    with merchant_order_id, psp_txn_id, amount_cents, and the boolean flags
    success / pending / is_voided / is_refunded / expired_flag.
    """
    obj = payload_parsed.get("obj") or payload_parsed  # tolerate flat shape
    psp_order = obj.get("order") or {}
    # NOTE: psp_order.get("id") is the PSP-side numeric order id. We don't
    # store it here — it was already persisted on the payment_transactions
    # row when /checkout was called. We only need merchant_order_id (our
    # own order id) to locate the order.
    merchant_order_id = (
        psp_order.get("merchant_order_id")
        or payload_parsed.get("merchant_order_id")
        or ""
    )
    return {
        "merchant_order_id": merchant_order_id,
        "psp_txn_id": str(obj.get("id") or payload_parsed.get("txn_id") or ""),
        "amount_cents": int(
            obj.get("amount_cents") or payload_parsed.get("amount_cents") or 0
        ),
        "success_flag": bool(obj.get("success")),
        "pending_flag": bool(obj.get("pending")),
        "is_voided": bool(obj.get("is_voided") or obj.get("voided")),
        "is_refunded": bool(obj.get("is_refunded") or obj.get("refunded")),
        "expired_flag": bool(obj.get("expired") or payload_parsed.get("expired")),
    }


def _map_psp_flags_to_status(
    fields: Dict[str, Any],
) -> Tuple[TxnStatus, str]:
    """Map PSP boolean flags to (TxnStatus, order_status) pair.

    Order of precedence: refund > void > expired > success > pending > failed.
    """
    if fields["is_refunded"]:
        return TxnStatus.FAILED, OrderStatus.REFUNDED.value
    if fields["is_voided"]:
        return TxnStatus.CANCELLED, OrderStatus.CANCELLED.value
    if fields["expired_flag"]:
        return TxnStatus.EXPIRED, OrderStatus.EXPIRED.value
    if fields["success_flag"] and not fields["pending_flag"]:
        return TxnStatus.SUCCESS, OrderStatus.PAID.value
    if fields["pending_flag"]:
        return TxnStatus.PENDING, OrderStatus.PENDING.value
    return TxnStatus.FAILED, OrderStatus.FAILED.value


def handle_meeza_webhook(
    payload_raw: bytes,
    signature_header: str,
    payload_parsed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Process a Meeza webhook.

    Args:
        payload_raw:       Raw body bytes (used for HMAC verification).
        signature_header:  Signature header value.
        payload_parsed:    Parsed JSON dict. If None, parsed from payload_raw.

    Returns:
        Dict with `status` ("processed" | "duplicate" | "rejected"),
        `http_status`, and optional `reason`.

    Idempotency & atomicity:
        1. HMAC verified; reject on mismatch (401).
        2. Idempotency key derived from (psp, order, txn, status, amount).
        3. INSERT into payment_events is rejected by UNIQUE constraint if
           duplicate — returns 200 with status="duplicate".
        4. New event: atomic UPDATE orders SET status='paid' WHERE id=? AND
           status='pending' — only the first SUCCESS webhook flips the order.
        5. Redlock fence around fulfillment (optional, when REDIS_URL set).
    """
    _init_schema()
    cfg = get_config()

    # 1. HMAC verification
    if not verify_webhook_signature(payload_raw, signature_header):
        logger.warning(
            "Meeza Payment: webhook rejected — HMAC verification failed"
        )
        return {"status": "rejected", "http_status": 401, "reason": "invalid_signature"}

    # 2. Parse payload
    if payload_parsed is None:
        try:
            payload_parsed = json.loads(payload_raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Meeza Payment: webhook rejected — invalid JSON (%s)", exc)
            return {"status": "rejected", "http_status": 400, "reason": "invalid_json"}

    # 3. Extract standard fields (PayMob nested shape or flat).
    fields = _extract_webhook_fields(payload_parsed)
    merchant_order_id = fields["merchant_order_id"]
    if not merchant_order_id:
        logger.warning("Meeza Payment: webhook rejected — no merchant_order_id")
        return {"status": "rejected", "http_status": 400, "reason": "missing_order_id"}

    psp_txn_id = fields["psp_txn_id"]
    amount_cents = fields["amount_cents"]
    txn_status, order_status = _map_psp_flags_to_status(fields)

    idem_key = derive_idempotency_key(
        psp_name=cfg.psp_name.value,
        order_id=merchant_order_id,
        txn_id=psp_txn_id or "no-txn",
        status=txn_status.value,
        amount_cents=amount_cents,
    )
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    raw_json = json.dumps(payload_parsed, separators=(",", ":"))
    sig_truncated = signature_header[:128] if signature_header else ""

    # 4-8. Persistence + atomic transitions inside the Redlock fence
    return _persist_webhook_event(
        cfg=cfg,
        merchant_order_id=merchant_order_id,
        txn_status=txn_status,
        order_status=order_status,
        idem_key=idem_key,
        event_id=event_id,
        now=now,
        raw_json=raw_json,
        sig_truncated=sig_truncated,
    )


def _persist_webhook_event(
    *,
    cfg: MeezaConfig,
    merchant_order_id: str,
    txn_status: TxnStatus,
    order_status: str,
    idem_key: str,
    event_id: str,
    now: str,
    raw_json: str,
    sig_truncated: str,
) -> Dict[str, Any]:
    """Insert the webhook event, link the transaction, and apply the atomic
    order status transition. Extracted from `handle_meeza_webhook` to keep
    cognitive complexity below the SonarCloud S3776 threshold (15).

    Returns the webhook result dict (processed / duplicate / order_already_terminal).
    """
    with _RedlockFence(f"order:{merchant_order_id}", ttl_ms=5000):
        with _get_conn() as conn:
            # 5. Idempotent event insert — UNIQUE constraint guards duplicates
            try:
                conn.execute(
                    """
                    INSERT INTO payment_events
                        (id, transaction_id, order_id, event_type, psp_name,
                         idempotency_key, raw_payload, hmac_signature,
                         processed_at, response_code)
                    VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, 200)
                    """,
                    (event_id, merchant_order_id, txn_status.value,
                     cfg.psp_name.value, idem_key, raw_json,
                     sig_truncated, now),
                )
            except sqlite3.IntegrityError:
                # Duplicate — already processed. Return cached success.
                logger.info(
                    "Meeza Payment: duplicate webhook suppressed (order=%s, idem=%s...)",
                    merchant_order_id[:8], idem_key[:8],
                )
                return {
                    "status": "duplicate",
                    "http_status": 200,
                    "reason": "idempotent_duplicate",
                    "idempotency_key": idem_key,
                }

            # 6. Link transaction if we have one for this order
            txn_row = conn.execute(
                "SELECT id FROM payment_transactions WHERE order_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (merchant_order_id,),
            ).fetchone()
            txn_id_internal = txn_row["id"] if txn_row else None
            if txn_id_internal:
                conn.execute(
                    "UPDATE payment_events SET transaction_id = ? WHERE id = ?",
                    (txn_id_internal, event_id),
                )
                # 7. Update transaction status (atomic — only if not terminal)
                conn.execute(
                    """
                    UPDATE payment_transactions
                       SET status = ?, updated_at = ?, completed_at = ?,
                           raw_payload = ?, hmac_signature = ?
                     WHERE id = ? AND status NOT IN ('SUCCESS','FAILED','EXPIRED','CANCELLED')
                    """,
                    (txn_status.value, now,
                     now if txn_status == TxnStatus.SUCCESS else None,
                     raw_json, sig_truncated, txn_id_internal),
                )

            # 8. Atomic order status transition.
            return _apply_order_status_transition(
                conn=conn,
                merchant_order_id=merchant_order_id,
                txn_status=txn_status,
                order_status=order_status,
                idem_key=idem_key,
                now=now,
            )


def _apply_order_status_transition(
    *,
    conn: sqlite3.Connection,
    merchant_order_id: str,
    txn_status: TxnStatus,
    order_status: str,
    idem_key: str,
    now: str,
) -> Dict[str, Any]:
    """Atomically flip the order status from 'pending' to the terminal
    state. Returns the appropriate webhook result.

    Critical: `status = 'pending'` in the WHERE clause ensures only the
    first terminal-status webhook flips the order. Subsequent webhooks
    for the same order (e.g. duplicate SUCCESS) hit the idempotency guard
    above; this UPDATE is a second layer of protection against
    double-fulfillment for edge cases like a SUCCESS arriving
    milliseconds before a CANCELLED.
    """
    if order_status not in (
        OrderStatus.PAID.value, OrderStatus.FAILED.value,
        OrderStatus.EXPIRED.value, OrderStatus.CANCELLED.value,
    ):
        # PENDING / REFUNDED — no order transition, just log and return
        logger.info(
            "Meeza Payment: webhook processed (order=%s, txn_status=%s, "
            "order_status=%s, idem=%s...)",
            merchant_order_id[:8], txn_status.value, order_status, idem_key[:8],
        )
        return {
            "status": "processed",
            "http_status": 200,
            "order_id": merchant_order_id,
            "transaction_status": txn_status.value,
            "order_status": order_status,
            "idempotency_key": idem_key,
        }

    cursor = conn.execute(
        """
        UPDATE orders
           SET status = ?, updated_at = ?,
               paid_at = CASE WHEN ? = 'paid' THEN ? ELSE paid_at END
         WHERE id = ? AND status = 'pending'
        """,
        (order_status, now, order_status,
         now if order_status == OrderStatus.PAID.value else None,
         merchant_order_id),
    )
    rows_affected = cursor.rowcount
    if rows_affected == 0:
        # Order was already in a terminal state. The WHERE clause `status='pending'`
        # matched 0 rows so the status was NOT overwritten. Return the ACTUAL
        # DB status so the caller knows the truth.
        actual = conn.execute(
            "SELECT status FROM orders WHERE id = ?",
            (merchant_order_id,),
        ).fetchone()
        actual_status = actual["status"] if actual else "unknown"
        logger.info(
            "Meeza Payment: order %s already in terminal state '%s' — "
            "incoming %s webhook did NOT flip it (idempotent guard)",
            merchant_order_id[:8], actual_status, order_status,
        )
        return {
            "status": "duplicate",
            "http_status": 200,
            "order_id": merchant_order_id,
            "transaction_status": txn_status.value,
            "order_status": actual_status,
            "idempotency_key": idem_key,
            "reason": "order_already_terminal",
        }
    if order_status == OrderStatus.PAID.value:
        # Fulfillment hook — extend here for subscription grants, license
        # activations, etc. Kept as a no-op log for now.
        logger.info(
            "Meeza Payment: order %s FULFILLED (paid) — "
            "trigger subscription grant here",
            merchant_order_id[:8],
        )
    logger.info(
        "Meeza Payment: webhook processed (order=%s, txn_status=%s, "
        "order_status=%s, idem=%s...)",
        merchant_order_id[:8], txn_status.value, order_status, idem_key[:8],
    )
    return {
        "status": "processed",
        "http_status": 200,
        "order_id": merchant_order_id,
        "transaction_status": txn_status.value,
        "order_status": order_status,
        "idempotency_key": idem_key,
    }


def _expire_order(order_id: str) -> None:
    """Mark an order as expired (called when checkout is attempted on a stale
    order)."""
    _init_schema()
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status = 'expired', updated_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, order_id),
        )


def get_transaction(txn_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a transaction by id."""
    _init_schema()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payment_transactions WHERE id = ?", (txn_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["raw_payload"] = json.loads(d.get("raw_payload") or "{}")
    return d


def list_transactions_for_order(order_id: str) -> List[Dict[str, Any]]:
    """List all transactions for an order."""
    _init_schema()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_transactions WHERE order_id = ? "
            "ORDER BY created_at ASC",
            (order_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["raw_payload"] = json.loads(d.get("raw_payload") or "{}")
        out.append(d)
    return out


def list_events_for_order(order_id: str) -> List[Dict[str, Any]]:
    """List all webhook events for an order (audit trail)."""
    _init_schema()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_events WHERE order_id = ? "
            "ORDER BY processed_at ASC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _row_to_order_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    try:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["metadata"] = {}
    return d


# ── Test/demo helpers ────────────────────────────────────────────────────────

def simulate_webhook(
    order_id: str,
    txn_status: TxnStatus = TxnStatus.SUCCESS,
    amount_cents: Optional[int] = None,
) -> Dict[str, Any]:
    """Simulate a Meeza webhook delivery (sandbox / test mode only).

    Builds a synthetic PayMob-shaped payload, signs it with the configured
    HMAC secret, and routes it through `handle_meeza_webhook`. This lets
    tests exercise the full HMAC + idempotency + atomic-transition pipeline
    without a live PSP.

    NOT exposed via the router — internal helper for tests and the sandbox UI.
    """
    cfg = get_config()
    order = get_order(order_id)
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    amount = amount_cents if amount_cents is not None else order["amount_cents"]

    # Deterministic ids derived from (order_id, txn_status) so that two calls
    # with the same arguments produce the SAME payload — exercising the real
    # idempotency path. A real PSP redelivery sends the exact same payload
    # (including the same PSP transaction id) twice; this helper mirrors that.
    psp_txn_id_int = int(
        hashlib.sha256(f"{order_id}|{txn_status.value}".encode()).hexdigest()[:12],
        16,
    ) % 1_000_000
    psp_order_id_int = int(
        hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:12], 16
    ) % 1_000_000

    obj: Dict[str, Any] = {
        "id": psp_txn_id_int,
        "order": {"id": psp_order_id_int, "merchant_order_id": order_id},
        "amount_cents": amount,
        "currency": order["currency"],
        "success": txn_status == TxnStatus.SUCCESS,
        "pending": txn_status == TxnStatus.PENDING,
        "is_voided": txn_status == TxnStatus.CANCELLED,
        "is_refunded": False,
        "expired": txn_status == TxnStatus.EXPIRED,
        "source_data": {"sub_type": "meeza"},
    }
    payload = {"type": "TRANSACTION", "obj": obj}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = _hmac_digest(cfg.hmac_secret or "sandbox-secret", raw, cfg.hmac_algorithm)
    sig_header = f"{cfg.hmac_algorithm}={sig}"
    return handle_meeza_webhook(raw, sig_header, payload)


def reset_for_tests() -> None:
    """Drop all billing tables. TEST-ONLY — never call from production code."""
    global _SCHEMA_INITIALIZED, _CONFIG
    with _SCHEMA_LOCK:
        with _get_conn() as conn:
            conn.executescript(
                "DROP TABLE IF EXISTS payment_events;"
                "DROP TABLE IF EXISTS payment_transactions;"
                "DROP TABLE IF EXISTS orders;"
            )
        _SCHEMA_INITIALIZED = False
        _CONFIG = None  # force re-read of env
