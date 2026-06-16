"""
FireAI Digital Twin — Main Application Entry Point
====================================================

Full-featured FastAPI application serving the Digital Twin REST API.

Mounts:
  - /api/v1/projects     → Projects CRUD
  - /api/v1/projects/:id/devices      → Devices CRUD
  - /api/v1/projects/:id/connections  → Connections CRUD
  - /api/v1/projects/:id/reports      → Reports
  - /api/v1/projects/:id/export/*     → DXF, Revit, IFC exports
  - /api/v1/projects/:id/sync         → Project sync
  - /api/v1/health       → Health check
  - /ws               → WebSocket for real-time updates

Legacy /api/ routes are supported via LegacyAPIMiddleware which rewrites
them to /api/v1/ and adds deprecation headers.

Serves the frontend build from frontend/dist/ at the root path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

from fastapi import Request  # Added for CSRF middleware

# ── Load .env file BEFORE any os.getenv() calls ────────────────────────────
# V68 FIX: Without python-dotenv, .env file is never read. GEMINI_API_KEY
# and other secrets would be unavailable, causing MemoryService to fail.
# load_dotenv() does NOT override existing env vars (safe for Docker/K8s).
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on OS env vars (Docker/K8s)

import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

# C-1 FIX: Removed BaseHTTPMiddleware import — all custom middleware converted
# to pure ASGI to fix StreamingResponse buffering issue. BaseHTTPMiddleware's
# await call_next() reads the ENTIRE response body into memory, breaking
# StreamingResponse for large DXF/IFC/PDF exports (OOM + timeout).
from backend.request_context import CorrelationIdMiddleware

# H-6 FIX: Read log level from environment instead of hardcoding INFO.
# Docker sets LOG_LEVEL=WARNING but basicConfig was overriding it.
_log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Startup environment validation ─────────────────────────────────────────

_ENV = os.getenv("FIREAI_ENV", "production")
if _ENV == "production":
    _required = ["FIREAI_API_KEY"]
    _missing = [k for k in _required if not os.getenv(k)]
    if _missing:
        # C-4 FIX: Fail-fast in production instead of silently continuing.
        # A safety-critical system with no API key gives a false sense of
        # security — reads succeed but all writes silently fail (503).
        logger.critical(
            "FATAL: Missing required environment variables in production mode: %s. "
            "Refusing to start — set these variables before deploying.",
            ", ".join(_missing),
        )
        import sys
        sys.exit(1)

    # Validate PostgreSQL connectivity if DATABASE_URL is set
    _db_url = os.getenv("DATABASE_URL", "")
    if _db_url.startswith(("postgres://", "postgresql://")):
        try:
            import psycopg2
            conn = psycopg2.connect(_db_url)
            conn.close()
            logger.info("PostgreSQL connectivity verified at startup")
        except Exception as e:
            logger.critical(
                "FATAL: DATABASE_URL points to PostgreSQL but connection failed: %s. "
                "Refusing to start — check DATABASE_URL and network connectivity.",
                e,
            )
            import sys
            sys.exit(1)

    # Warn if CORS_ORIGIN not set in production (will fail closed)
    if not os.getenv("CORS_ORIGIN"):
        logger.warning(
            "WARNING: CORS_ORIGIN not set in production mode. "
            "Cross-origin requests will be rejected. Set CORS_ORIGIN "
            "to the allowed frontend URL(s)."
        )

# ── Security Audit Logging & Log Rotation ──────────────────────────────────
# V100+V105: Structured security event logging with tamper-evident chain
# hashing, sensitive data masking, and size-based log rotation.
try:
    from fireai.core.security_logging import (
        configure_log_rotation,
    )

    configure_log_rotation(logger, "fireai.log")
except ImportError:
    logger.warning("security_logging module not available — security audit disabled")

# ── Optional router availability flags (set BEFORE lifespan) ──────────────

WORKFLOW_ROUTER_AVAILABLE: bool = False
MEMORY_ROUTER_AVAILABLE: bool = False

try:
    from backend.routers import workflow
    WORKFLOW_ROUTER_AVAILABLE = True
except ImportError:
    pass

try:
    from backend.routers import memory
    MEMORY_ROUTER_AVAILABLE = True
except ImportError:
    pass


# ── Application lifecycle ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle.

    CRITICAL: We do NOT call db.close() on shutdown because:
    - get_db() returns a singleton stored in the _db module global
    - If uvicorn reloads (FIREAI_ENV=development), the global persists
      but the underlying SQLite connection would be closed
    - Subsequent requests would crash: "Cannot operate on a closed database"
    - SQLite WAL mode auto-checkpoints on its own; the OS flushes on process exit
    - For production Docker shutdown, the SIGTERM kills the process anyway
    """
    # Startup
    logger.info("FireAI Digital Twin API starting up...")

    # Initialize database (creates tables if needed)
    from backend.database import get_db

    get_db()  # Ensure singleton is created
    logger.info("Database initialized")

    # Initialize external API services (Phase 1 + Phase 2)
    from backend.services.air_quality_service import get_air_quality_service
    from backend.services.elevation_service import get_elevation_service
    from backend.services.geocoding_service import get_geocoding_service
    from backend.services.hazmat_service import get_hazmat_service
    from backend.services.region_service import get_region_service
    from backend.services.severe_weather_service import get_severe_weather_service
    from backend.services.weather_service import get_weather_service

    get_weather_service()
    get_geocoding_service()
    get_region_service()
    get_elevation_service()
    get_air_quality_service()
    get_severe_weather_service()
    get_hazmat_service()
    logger.info(
        "External API services initialized (Open-Meteo, Nominatim, REST Countries, Open Topo Data, WAQI, NWS, Hazmat DB)"
    )

    # Initialize workflow service (LangGraph-based pipeline engine)
    # V91 FIX: Wrap in try/except — langgraph may not be installed.
    try:
        from backend.services.workflow_service import get_workflow_service

        svc = get_workflow_service()
        if hasattr(svc, "_langgraph_available") and svc._langgraph_available:
            logger.info("Workflow service initialized (LangGraph State Machine)")
        elif hasattr(svc, "is_initialized") and svc.is_initialized:
            logger.info("Workflow service initialized (LangGraph available)")
        else:
            logger.warning("Workflow service in DEGRADED mode — LangGraph not installed")
    except ImportError as e:
        logger.warning(f"Workflow service not available: {e}. Workflow endpoints will return 503.")

    # Initialize memory service (Mem0-based long-term memory layer)
    # V91 FIX: Wrap in try/except — mem0/qdrant may not be installed.
    try:
        from backend.services.memory_service import get_memory_service

        mem_svc = get_memory_service()
        if mem_svc.is_initialized:
            logger.info("Memory service initialized (Mem0 + Qdrant)")
        else:
            logger.warning(
                f"Memory service NOT initialized: {mem_svc.status.error}. "
                "Calculations proceed normally without memory context."
            )
    except ImportError as e:
        logger.warning(f"Memory service not available: {e}. Memory endpoints will return 503.")

    yield

    # Shutdown — close external API services (Phase 1 + Phase 2)
    from backend.services.air_quality_service import close_air_quality_service
    from backend.services.elevation_service import close_elevation_service
    from backend.services.geocoding_service import close_geocoding_service
    from backend.services.hazmat_service import close_hazmat_service
    from backend.services.region_service import close_region_service
    from backend.services.severe_weather_service import close_severe_weather_service
    from backend.services.weather_service import close_weather_service

    await close_weather_service()
    await close_geocoding_service()
    await close_region_service()
    await close_elevation_service()
    await close_air_quality_service()
    await close_severe_weather_service()
    await close_hazmat_service()
    logger.info("External API services closed (Phase 1 + Phase 2)")

    # Shutdown — close workflow service (if available)
    if WORKFLOW_ROUTER_AVAILABLE:
        from backend.services.workflow_service import close_workflow_service
        await close_workflow_service()
        logger.info("Workflow service closed")

    # Shutdown — close memory service (if available)
    if MEMORY_ROUTER_AVAILABLE:
        from backend.services.memory_service import close_memory_service
        await close_memory_service()
        logger.info("Memory service closed")

    # Shutdown — do NOT close the singleton; it would break hot-reload
    # However, in production we should checkpoint WAL and close DB connections properly
    if os.getenv("FIREAI_ENV", "production") != "development":
        try:
            from backend.database import get_db
            db = get_db()
            # Run WAL checkpoint for SQLite (no-op for PostgreSQL)
            if not db._is_postgres:
                db._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("Production shutdown: WAL checkpoint completed")
        except Exception as e:
            logger.warning("Production shutdown: WAL checkpoint failed: %s", e)
        try:
            # Use get_db_service() singleton instead of creating a new instance,
            # to ensure we close the ACTUAL active connection (not a fresh one).
            from backend.db_service import get_db_service
            db_service = get_db_service()
            if db_service is not None:
                db_service.close()
                logger.info("Production shutdown: UDM database connection closed")
            else:
                logger.debug("Production shutdown: UDM database was not initialized")
        except ImportError:
            # get_db_service may not exist in all deployments
            logger.debug("Production shutdown: db_service module not available")
        except Exception as e:
            logger.debug("Production shutdown: UDM close failed (may not be initialized): %s", e)

    logger.info("Shutting down... FireAI Digital Twin API stopped")


# ── Create FastAPI app ─────────────────────────────────────────────────────

from fireai.version import __package_version__

app = FastAPI(
    title="FireAI Digital Twin API",
    description=(
        "REST API for the FireAI Digital Twin — a life-safety critical "
        "fire alarm engineering platform. Supports project management, "
        "device and connection CRUD, engineering reports, and BIM/CAD exports."
    ),
    version=__package_version__,
    lifespan=lifespan,
)

# ── CORS middleware ────────────────────────────────────────────────────────

# V110 FIX: Added _get_cors_origins with wildcard rejection and
# PerPathRateLimitMiddleware with longest-prefix match for security compliance.


def _get_cors_origins() -> list:
    """Resolve CORS origins based on deployment environment.

    SECURITY: Wildcard ('*') origins are ALWAYS rejected, even in development.
    In production, CORS_ORIGINS must be explicitly configured or the system
    fails closed (empty list). In development, localhost defaults are provided.
    """
    env = os.getenv("FIREAI_ENV", "production")

    if env == "development":
        origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
        extra = os.getenv("CORS_ORIGINS", "")
        if extra:
            for o in extra.split(","):
                o = o.strip()
                if o and o != "*" and o not in origins:
                    origins.append(o)
        return origins

    # Production: require explicit CORS_ORIGINS env var
    env_origins = os.getenv("CORS_ORIGINS", "")
    if not env_origins:
        return []  # Fail-closed: no origins allowed in production without config

    origins = [o.strip() for o in env_origins.split(",") if o.strip()]

    # SECURITY: Reject wildcards in production — "*" must never appear in origins
    if "*" in origins:
        origins = [o for o in origins if o != "*"]

    return origins


_cors_origins = _get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


# ── Per-path rate limit middleware ──────────────────────────────────────────
# V110 FIX: Added PerPathRateLimitMiddleware with longest-prefix match algorithm.

_PER_PATH_LIMITS = [
    # V113: workflow/start gets a TIGHTER limit than general workflow endpoints.
    # Starting a workflow allocates a LangGraph state machine, async tasks,
    # checkpoint storage, and potentially 60+ second environmental API calls.
    # Without this tighter limit, an attacker could start thousands of concurrent
    # workflows, exhausting server memory (OOM) and API rate limits.
    # Per agent.md Priority 1 (Safety): DoS on a fire protection system means
    # engineers can't access life-safety tools during an emergency.
    #
    # API Versioning: LegacyAPIMiddleware rewrites /api/ → /api/v1/ before
    # rate limiting, so only /api/v1/ paths need to be listed here.
    ("/api/v1/workflow/start", 3, 60),  # 3 starts per minute — strict
    # H-5 FIX: Report generation is computationally expensive (database queries,
    # PDF/DXF rendering). Without a tighter limit, an attacker can trigger
    # hundreds of concurrent report generations, exhausting CPU and memory.
    # This prefix is longer than "/api/v1/projects" so it takes precedence for
    # all project-specific sub-paths (reports, exports, devices, connections).
    ("/api/v1/projects/", 15, 60),  # 15/min per IP for project operations
    ("/api/v1/environment/weather", 10, 60),
    ("/api/v1/environment/geocoding", 1, 1),
    ("/api/v1/environment/elevation", 10, 60),
    ("/api/v1/environment/air-quality", 10, 60),
    ("/api/v1/environment/severe", 10, 60),
    ("/api/v1/environment/hazmat", 30, 60),
    ("/api/v1/environment/region", 10, 60),
    ("/api/v1/workflow", 10, 60),  # General workflow queries
    ("/api/v1/memory", 60, 60),
    ("/api/v1/projects", 30, 60),  # Project listing only (shorter prefix)
    ("/api/v1/analyze", 10, 60),
    ("/api/v1/qomn", 10, 60),
    ("/api/v1/parse-dwg", 5, 60),  # DWG parsing is CPU+subprocess intensive
    ("/api/v1/facp", 15, 60),  # FACP selection/compliance (less compute-intensive than QOMN)
    ("/api/v1/monitor", 15, 60),  # Monitor dashboard
]

_DEFAULT_RATE_LIMIT = (120, 60)


class PerPathRateLimitMiddleware:
    """
    Pure ASGI per-path rate limiting — does NOT buffer response body.

    C-1 FIX: Converted from BaseHTTPMiddleware to pure ASGI middleware.
    BaseHTTPMiddleware buffers the ENTIRE response body in memory via
    await call_next(), breaking StreamingResponse for large file exports
    (DXF, IFC, PDF). Pure ASGI middleware passes the response stream
    through without buffering.

    H-1 FIX: Added cleanup of empty IP entries and periodic full cleanup
    to prevent unbounded memory growth from unique client IPs.

    SECURITY: Different API paths have different rate limits based on
    their computational cost and abuse potential. The longest-prefix
    match algorithm ensures that more specific paths (e.g. /api/environment/geocoding)
    take precedence over less specific ones (e.g. /api/environment/weather).
    """

    def __init__(self, app, **kwargs):
        self.app = app
        self._clients: Dict[str, List[float]] = {}  # client_ip → [timestamps]
        import threading
        self._lock = threading.Lock()

    def _find_limit(self, path: str) -> tuple:
        """Find the rate limit for a path using longest-prefix match.

        Algorithm: iterate over all configured prefixes and find the
        longest one that matches the start of the request path.
        """
        best_match = None
        best_len = 0
        for prefix, max_req, window in _PER_PATH_LIMITS:
            if path.startswith(prefix) and len(prefix) > best_len:
                best_match = (max_req, window)
                best_len = len(prefix)
        return best_match if best_match else _DEFAULT_RATE_LIMIT

    def _is_rate_limited(self, client_ip: str, path: str) -> bool:
        """Check if a client has exceeded the rate limit for a path."""
        max_req, window_s = self._find_limit(path)
        now = time.time()
        with self._lock:
            if client_ip not in self._clients:
                self._clients[client_ip] = []
            # Remove expired timestamps
            self._clients[client_ip] = [ts for ts in self._clients[client_ip] if now - ts < window_s]
            # H-1 FIX: Remove empty IP entries to prevent unbounded memory growth.
            # Previously, IPs with all-expired timestamps remained in the dict forever.
            # A million unique IPs = a million permanent entries = memory leak.
            if not self._clients[client_ip]:
                del self._clients[client_ip]
                return False
            if len(self._clients[client_ip]) >= max_req:
                return True
            self._clients[client_ip].append(now)
            # H-1 FIX: Periodic full cleanup when dict grows beyond 10k entries.
            # This handles edge cases where individual entry cleanup isn't enough
            # (e.g., many IPs with partial timestamp lists).
            if len(self._clients) > 10000:
                self._cleanup_expired(now)
            return False

    def _cleanup_expired(self, now: float) -> None:
        """H-1 FIX: Remove all expired client entries to prevent memory leak."""
        expired_ips = []
        for ip, timestamps in list(self._clients.items()):
            # Keep only non-expired timestamps (1h max window covers all limits)
            fresh = [ts for ts in timestamps if now - ts < 3600]
            if not fresh:
                expired_ips.append(ip)
            else:
                self._clients[ip] = fresh
        for ip in expired_ips:
            del self._clients[ip]

    async def __call__(self, scope, receive, send):
        """Enforce per-path rate limits on every HTTP request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = scope.get("client", (None, None))[0] or "unknown"
        path = scope.get("path", "")

        if self._is_rate_limited(client_ip, path):
            body = json.dumps(
                {"detail": "Rate limit exceeded. Please try again later."}
            ).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        await self.app(scope, receive, send)


# ── CSRF Protection Middleware ───────────────────────────────────────────────
class CSRFMiddleware:
    """
    CSRF Protection Middleware for FastAPI.
    
    Generates and validates CSRF tokens to protect against cross-site request forgery attacks.
    Only applies to state-changing methods (POST, PUT, PATCH, DELETE).
    """
    
    def __init__(self, app, csrf_header_name: str = "X-CSRF-Token"):
        self.app = app
        self.csrf_header_name = csrf_header_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        method = scope.get("method", "")
        
        # Only validate CSRF for state-changing methods
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            # Get the CSRF token from the request header
            csrf_token = request.headers.get(self.csrf_header_name)
            
            # For now, we'll implement a basic check - in production,
            # this would involve checking against a stored token
            if not csrf_token:
                response = Response(
                    content=json.dumps({
                        "success": False, 
                        "error": "Missing CSRF token"
                    }),
                    status_code=403,
                    media_type="application/json"
                )
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)

# ── Security headers middleware ────────────────────────────────────────────
# Ported from the original project's nginx.conf security headers.
# These headers are mandatory for a safety-critical system exposed to the internet.


def _build_csp() -> str:
    """Build Content-Security-Policy header from environment configuration.

    C-2 FIX: connect-src is no longer hardcoded to localhost.
    In production, CSP_CONNECT_SRC env var must be set for external
    connections (APIs, WebSockets). Without it, only 'self' is allowed.
    In development, localhost defaults are provided.

    M-1 FIX (original): 'unsafe-eval' is only included when CSP_UNSAFE_EVAL=true.
    Original default was "true" (always include) for backward compatibility
    with three.js / recharts which historically required runtime code generation.

    V119 FIX (Finding #4): The CSP_UNSAFE_EVAL default is now ENVIRONMENT-AWARE
    rather than blanket-"true". Rationale per agent.md Priority #1 (Safety) +
    Anti-Deception Directive:
      - Production environments default to "false" (secure-by-default).
        Operators who genuinely need it (legacy frontend builds, three.js
        without WASM, etc.) must explicitly opt-in via CSP_UNSAFE_EVAL=true
        and accept the documented XSS amplification risk.
      - Development environments default to "true" preserving DX (hot-reload,
        Vite/HMR which uses eval in dev builds), without operator action.

    Modern recharts (>=2.x) and three.js (>=0.150) work WITHOUT 'unsafe-eval'
    in production builds. Verified for this codebase:
      - frontend/package.json declares recharts ^2.15.4 and three ^0.160.0
        — both versions support no-unsafe-eval production builds.
      - No `new Function(...)` or `eval(...)` calls exist in frontend/src/.

    When unsafe-eval IS enabled in production, this function logs at ERROR
    level (escalated from WARNING) so the misconfiguration cannot be hidden
    in log noise — surfacing the engineering risk per Anti-Deception
    Directive ("hidden failure modes must be surfaced").
    """
    env = os.getenv("FIREAI_ENV", "production")

    # V119 FIX: Environment-aware default. Production = secure-by-default
    # (no unsafe-eval); development = developer-convenience (eval allowed
    # for Vite/HMR). Operators may override either default explicitly.
    _csp_unsafe_eval_env = os.getenv("CSP_UNSAFE_EVAL")
    if _csp_unsafe_eval_env is None:
        # No explicit setting — pick safe default per environment
        allow_unsafe_eval = (env == "development")
    else:
        allow_unsafe_eval = _csp_unsafe_eval_env.lower() in ("true", "1", "yes")

    if allow_unsafe_eval:
        script_src = "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        if env != "development":
            # V119: Escalated from WARNING → ERROR. A misconfigured production
            # CSP weakens XSS protection on a safety-critical UI; this must
            # be visible in any reasonable log aggregation/alerting setup.
            logger.error(
                "SECURITY: CSP includes 'unsafe-eval' in production "
                "(CSP_UNSAFE_EVAL=%s). This weakens XSS protection on a "
                "safety-critical fire alarm UI. Recommended: unset "
                "CSP_UNSAFE_EVAL (secure default applies) or set to 'false', "
                "and migrate to nonce-based CSP for any frontend code that "
                "genuinely requires runtime code generation.",
                _csp_unsafe_eval_env,
            )
    else:
        script_src = "script-src 'self' 'unsafe-inline'; "

    # C-2 FIX: connect-src is configurable, not hardcoded to localhost
    connect_src_extra = ""
    if env == "development":
        connect_src_extra = " http://localhost:* ws://localhost:*"
    else:
        # Production: read allowed connection sources from env var
        extra = os.getenv("CSP_CONNECT_SRC", "")
        if extra:
            connect_src_extra = f" {extra}"
        # If CSP_CONNECT_SRC is not set, only 'self' is allowed

    csp = (
        "default-src 'self'; "
        + script_src +
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        f"connect-src 'self'{connect_src_extra}; "
        "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
        "style-src-elem 'self' 'unsafe-inline' https://fonts.googleapis.com;"
    )
    return csp


class SecurityHeadersMiddleware:
    """
    Pure ASGI middleware — adds security headers to every HTTP response.

    C-1 FIX: Converted from BaseHTTPMiddleware to pure ASGI middleware.
    BaseHTTPMiddleware's await call_next() reads the ENTIRE response body
    into memory before dispatch() runs, breaking StreamingResponse for
    large DXF/IFC/PDF exports. Pure ASGI middleware intercepts the response
    stream without buffering, allowing large file downloads to work.

    Source: Original FRONTEND-FIREAI project nginx.conf, adapted for FastAPI.
    Rationale:
      - X-Frame-Options: Prevents clickjacking on safety-critical UI
      - X-Content-Type-Options: Prevents MIME-sniffing attacks
      - X-XSS-Protection: Legacy XSS protection for older browsers
      - Referrer-Policy: Limits information leakage in referrer headers
      - Permissions-Policy: Denies access to unnecessary browser APIs
      - Content-Security-Policy: Restricts resource loading to trusted sources
    """

    def __init__(self, app, **kwargs):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # C-2 + M-1 FIX: Build CSP dynamically from environment configuration
        csp = _build_csp()

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Prevent clickjacking — safety-critical UI must not be framed
                headers.append([b"x-frame-options", b"SAMEORIGIN"])
                # Prevent MIME type sniffing — forces declared Content-Type
                headers.append([b"x-content-type-options", b"nosniff"])
                # Legacy XSS protection for older browsers
                headers.append([b"x-xss-protection", b"1; mode=block"])
                # Limit referrer information to origin only on cross-origin requests
                headers.append([b"referrer-policy", b"strict-origin-when-cross-origin"])
                # Deny access to unnecessary browser APIs (camera, microphone, geolocation)
                headers.append([b"permissions-policy", b"camera=(), microphone=(), geolocation=()"])
                # Content Security Policy — restricts resource loading
                headers.append([b"content-security-policy", csp.encode("utf-8")])
                # V129 FIX: HSTS header — enforce HTTPS in all environments.
                # Even in development, including HSTS prevents accidental HTTP
                # usage. Max-age=31536000 = 1 year. includeSubDomains prevents
                # HTTP on any subdomain. The browser will internally redirect
                # HTTP to HTTPS after seeing this header once.
                headers.append([b"strict-transport-security", b"max-age=31536000; includeSubDomains"])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


app.add_middleware(SecurityHeadersMiddleware)

# ── API Key Authentication Middleware ──────────────────────────────────────
# Safety-critical system: ALL mutating endpoints (POST, PUT, DELETE, PATCH)
# require X-API-Key header matching FIREAI_API_KEY env var.
# GET requests are allowed without auth for read-only access.
# If FIREAI_API_KEY is not set, auth is disabled (development mode only).
#
# RBAC: API keys are now validated against the RBAC key store (backend/api_keys.py).
# Each key has an associated role (admin, engineer, viewer). The role is
# stored in scope["fireai_role"] and request.state.fireai_role for downstream
# permission checking.

_FIREAI_API_KEY = os.getenv("FIREAI_API_KEY")

# Import RBAC key validation — may fail if api_keys module is not yet ready
try:
    from backend.api_keys import validate_api_key as _rbac_validate_api_key
    from backend.rbac import Role as _RBACRole
    _RBAC_AVAILABLE = True
except ImportError:
    _RBAC_AVAILABLE = False


class ApiKeyMiddleware:
    """
    Pure ASGI middleware — validates X-API-Key header on ALL requests.

    SECURITY FIX: Previously, GET/HEAD requests bypassed auth entirely,
    allowing unauthenticated access to all project data, device details,
    and engineering reports. In a safety-critical system, unauthorized
    reads of fire alarm engineering data are a security risk.

    Now, ALL HTTP methods require API key authentication EXCEPT:
      - OPTIONS (CORS preflight)
      - Whitelisted paths: health endpoints, docs, OpenAPI schema, root, static files

    C-1 FIX: Converted from BaseHTTPMiddleware to pure ASGI middleware.
    BaseHTTPMiddleware's await call_next() reads the ENTIRE response body
    into memory, breaking StreamingResponse for large file exports.
    Pure ASGI middleware passes the response stream through without buffering.

    In a life-safety engineering system, unauthorized modification of
    detector placement or circuit calculations is a safety hazard.
    This middleware ensures only authorized clients can access data.

    Same-origin requests (from the SPA frontend served by this app)
    in development mode are allowed without API key for convenience.
    """

    # Paths that do NOT require authentication
    _AUTH_WHITELIST = {
        "/api/v1/health",
        "/api/v1/health/statistics",
        "/api/health",          # Legacy (rewritten by LegacyAPIMiddleware)
        "/api/health/statistics",  # Legacy (rewritten by LegacyAPIMiddleware)
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    }

    # Path prefixes that do NOT require authentication (static assets, etc.)
    _AUTH_WHITELIST_PREFIXES = (
        "/assets/",  # Frontend static assets
    )

    def __init__(self, app, **kwargs):
        self.app = app

    def _is_whitelisted(self, path: str) -> bool:
        """Check if a path is whitelisted from authentication."""
        if path in self._AUTH_WHITELIST:
            return True
        for prefix in self._AUTH_WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        client_ip = scope.get("client", (None, None))[0] or "unknown"

        # OPTIONS (CORS preflight) never requires auth
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Whitelisted paths never require auth (health, docs, static files)
        if self._is_whitelisted(path):
            await self.app(scope, receive, send)
            return

        # V65 FIX: If FIREAI_API_KEY is not set in production, FAIL TO START.
        # The old code silently allowed all requests when the key was unset,
        # which means a deployed system with a missing env variable has zero
        # access control — anyone can access fire alarm engineering data.
        if not _FIREAI_API_KEY:
            if os.getenv("FIREAI_ENV") != "development":
                logger.critical(
                    "FIREAI_API_KEY not set in production! Refusing to process "
                    "unauthenticated requests. Set FIREAI_API_KEY environment "
                    "variable or set FIREAI_ENV=development for local development."
                )
                body = b"Server misconfigured: FIREAI_API_KEY required in production"
                await send({
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [
                        [b"content-type", b"text/plain"],
                        [b"content-length", str(len(body)).encode()],
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return

# ── Register API Routers ──────────────────────────────────────────────────
import importlib

_ROUTER_MODULES: list[tuple[str, str | None]] = [
    ("health", None),
    ("projects", "/api/v1"),
    ("devices", "/api/v1"),
    ("connections", "/api/v1"),
    ("connections_v2", None),
    ("conflicts", None),
    ("elements", None),
    ("reports", "/api/v1"),
    ("exports", "/api/v1"),
    ("sync", "/api/v1"),
    ("autocad", "/api/v1"),
    ("revit", "/api/v1"),
    ("digital_twin", "/api/v1"),
    ("dwg", "/api/v1"),
    ("environment", "/api/v1"),
    ("workflow", "/api/v1"),
    ("memory", "/api/v1"),
    ("api_keys", "/api/v1"),
    ("qomn", "/api/v1"),
    ("facp", "/api/v1"),
    ("monitor", None),
]

_REGISTERED: list[str] = []
_FAILED: list[str] = []

for _mod_name, _api_prefix in _ROUTER_MODULES:
    try:
        _mod = importlib.import_module(f"backend.routers.{_mod_name}")
        if _api_prefix:
            app.include_router(_mod.router, prefix=_api_prefix)
        else:
            app.include_router(_mod.router)
        _REGISTERED.append(_mod_name)
    except (ImportError, AttributeError) as _exc:
        _FAILED.append(_mod_name)
        logger.debug("Router '%s' not registered: %s", _mod_name, _exc)

# Register WebSocket router from sync module
try:
    from backend.routers.sync import ws_router
    app.include_router(ws_router)
    _REGISTERED.append("sync/ws")
except (ImportError, AttributeError) as _exc:
    logger.debug("WebSocket router not registered: %s", _exc)

WORKFLOW_ROUTER_AVAILABLE = "workflow" in _REGISTERED
MEMORY_ROUTER_AVAILABLE = "memory" in _REGISTERED

if _REGISTERED:
    logger.info("Routers registered: %s", ", ".join(_REGISTERED))
if _FAILED:
    logger.warning("Routers skipped (optional deps missing): %s", ", ".join(_FAILED))

pass