"""
backend/app.py — FastAPI Application Entry Point
===============================================

Core FastAPI application with all CAD/BIM integration routes.
Implements the complete backend for AutoCAD/Revit/Digital Twin system.

ARCHITECTURE:
- FastAPI app with CORS middleware
- Rate limiting with SlowAPI
- All CAD/BIM integration routes
- Health check endpoints
- Error handlers for CAD connection issues

USAGE:
    uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
"""

import os
import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import our CAD/BIM integration routers
from backend.routers import autocad, revit, digital_twin

# Import rate limiter from centralized module (avoids circular import)
from backend.limiter import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Reduce noise from third-party libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


# ============================================================================
# CONTENT SECURITY POLICY (CSP) BUILDER
# ============================================================================
# V119 FIX (Finding #4): Production default for CSP_UNSAFE_EVAL is now
# "false" (secure-by-default). Development default remains "true" for DX.
# SAFETY: A safety-critical fire alarm engineering UI must not be vulnerable
# to XSS amplification via 'unsafe-eval'. Modern frontend libraries
# (recharts >=2.x, three.js >=0.150) work without it in production builds.

def _build_csp() -> str:
    """Build a Content-Security-Policy header value.

    Environment-aware:
      - FIREAI_ENV=production (default): 'unsafe-eval' is OFF unless explicitly enabled.
      - FIREAI_ENV=development:           'unsafe-eval' is ON  unless explicitly disabled.

    Operators may override either default by setting CSP_UNSAFE_EVAL=true|false.

    Production + unsafe-eval=on is logged at ERROR level (V119 escalation)
    so the misconfiguration cannot hide in log noise.
    """
    # Truthy values that enable unsafe-eval (backward compatible with pre-V119).
    # Defined INSIDE the function so the function is fully self-contained and
    # can be exec'd in isolation by tests/test_csp_security.py.
    _truthy = {"true", "1", "yes"}

    env = os.getenv("FIREAI_ENV", "production").lower()
    is_dev = env == "development"

    # Resolve CSP_UNSAFE_EVAL with environment-aware default.
    unsafe_eval_raw = os.getenv("CSP_UNSAFE_EVAL")
    if unsafe_eval_raw is not None:
        unsafe_eval = unsafe_eval_raw.strip().lower() in _truthy
    else:
        unsafe_eval = is_dev  # dev: True, prod: False

    # V119: escalate to ERROR when production keeps unsafe-eval on.
    if unsafe_eval and not is_dev:
        logger.error(
            "CSP 'unsafe-eval' ENABLED in production (FIREAI_ENV=%s). "
            "This is a security risk for a safety-critical UI - "
            "set CSP_UNSAFE_EVAL=false to disable.",
            env,
        )

    script_src = "'self' 'unsafe-inline'" + (" 'unsafe-eval'" if unsafe_eval else "")
    style_src = "'self' 'unsafe-inline'"
    img_src = "'self' data: blob:"

    # connect-src: development allows localhost (Vite HMR / websockets);
    # production uses CSP_CONNECT_SRC env var if provided, else 'self'.
    if is_dev:
        connect_src = "'self' http://localhost:* ws://localhost:* http://127.0.0.1:* ws://127.0.0.1:*"
        custom_connect = os.getenv("CSP_CONNECT_SRC")
        if custom_connect:
            connect_src += f" {custom_connect}"
    else:
        custom_connect = os.getenv("CSP_CONNECT_SRC")
        connect_src = "'self'" + (f" {custom_connect}" if custom_connect else "")

    parts = [
        "default-src 'self'",
        f"script-src {script_src}",
        f"style-src {style_src}",
        f"img-src {img_src}",
        f"connect-src {connect_src}",
        "font-src 'self' data:",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(parts)

# ── In-memory cache with expiration support ────────────────────────────────
_cache: dict[str, dict] = {}


def get_cache():
    """Get cache instance. Returns in-memory dict if Redis unavailable."""
    return _cache


async def cache_get(key: str):
    """Get value from cache. Returns None if expired or missing."""
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.time() > entry.get("expire", 0):
        _cache.pop(key, None)  # Remove expired entry
        return None
    return entry["value"]


async def cache_set(key: str, value: str, expire: int = 300):
    """Set value in cache with expiration in seconds."""
    _cache[key] = {"value": value, "expire": time.time() + expire}


async def cache_delete(key: str):
    """Delete key from cache."""
    _cache.pop(key, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Used for startup and shutdown tasks.
    """
    logger.info("Starting CAD/BIM Integration Platform...")
    yield
    logger.info("Shutting down CAD/BIM Integration Platform...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="CAD/BIM Integration Platform",
    description="""
## API Overview

Complete platform for **AutoCAD** and **Revit** integration with **Digital Twin** capabilities.

### Features

- **AutoCAD Integration**: Connect to AutoCAD, read/write DWG files, create/draw entities
- **Revit Integration**: Connect to Revit, read/write RVT files, create/modify elements
- **Bidirectional Conversion**: Convert between AutoCAD and Revit formats
- **Digital Twin Engine**: Central conversion hub with semantic mapping
- **Version Management**: Track and rollback conversion history

### Authentication

All endpoints require API key authentication via `X-API-Key` header.

### Rate Limiting

| Endpoint Type | Limit |
|---------------|-------|
| Health/Read | 1000/minute |
| Standard | 100/minute |
| Write/Upload | 50/minute |
| Heavy Operations | 10/minute |
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add rate limiter state
app.state.limiter = limiter

# Add rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS middleware — FIX #1: Restrict origins from environment ────────────
# Previously allow_origins=["*"] with allow_credentials=True was a security
# vulnerability. Now reads allowed origins from CORS_ALLOWED_ORIGINS env var.
ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "X-Correlation-ID"],
)

# Include our CAD/BIM integration routers
# FIX #35: Removed redundant prefix from app.include_router since each
# router already defines its own prefix (e.g., prefix="/autocad").
app.include_router(autocad.router, prefix="/api/v1", tags=["AutoCAD-v1"])
app.include_router(revit.router, prefix="/api/v1", tags=["Revit-v1"])
app.include_router(digital_twin.router, prefix="/api/v1", tags=["Digital-Twin-v1"])

# Health endpoints (no version prefix - always available)
@app.get("/api/v1/health", tags=["Health-v1"])
async def health_check_v1():
    """Health check endpoint for API v1."""
    return {
        "status": "healthy",
        "service": "CAD/BIM Integration Platform",
        "version": "1.0.0",
        "api_version": "v1"
    }

@app.get("/api/v2/health", tags=["Health-v2"])
async def health_check_v2():
    """Health check endpoint for API v2."""
    return {
        "status": "healthy",
        "service": "CAD/BIM Integration Platform",
        "version": "1.0.0",
        "api_version": "v2",
        "features": ["rate_limiting", "enhanced_caching", "streaming"]
    }

# Legacy health endpoint (deprecated)
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint (deprecated - use /api/v1/health)."""
    return {
        "status": "healthy",
        "service": "CAD/BIM Integration Platform",
        "version": "1.0.0",
        "deprecated": True,
        "suggestion": "Use /api/v1/health or /api/v2/health"
    }

# ── Error handlers ──────────────────────────────────────────────────────────
# FIX #2: Return JSONResponse (not HTTPException) and never expose str(exc)
# to the client. In a fire-safety system, internal exception messages can
# leak file paths, DB connection strings, and variable names.
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler — logs full traceback, returns safe message."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "success": False}
    )


# ═══════════════════════════════════════════════════════════════════════════
# CACHE MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/cache/clear", tags=["Cache"])
async def clear_cache():
    """Clear all cached data.

    FIX #3: Count items BEFORE clearing so the response is accurate.
    Previously _cache.clear() ran before len(_cache), always returning 0.
    """
    count = len(_cache)
    _cache.clear()
    return {"message": "Cache cleared", "items_cleared": count}


@app.get("/api/v1/cache/stats", tags=["Cache"])
async def cache_stats():
    """Get cache statistics.

    FIX #4: Also cleans up expired entries during stats check to prevent
    unbounded memory growth from expired-but-not-removed cache entries.
    """
    # Clean expired entries
    now = time.time()
    expired_keys = [k for k, v in _cache.items() if v.get("expire", 0) <= now]
    for k in expired_keys:
        _cache.pop(k, None)

    active_keys = sum(1 for v in _cache.values() if v.get("expire", 0) > now)
    return {
        "total_keys": len(_cache),
        "active_keys": active_keys,
        "expired_keys_cleaned": len(expired_keys),
        "cache_type": "in-memory"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
