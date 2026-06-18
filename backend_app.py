"""
backend_app.py - FireAI QOMN + Analyze API Application Entry Point
====================================================================
FastAPI application exposing:
  - QOMN-FIRE engineering kernel endpoints (under /api/qomn/...)
  - Analyze endpoints for project-level workflows (under /api/analyze/...
    and /api/projects/{project_id}/analyze/room)
  - Health endpoint (under /api/health)

DESIGN:
  - Loads the qomn_router from backend.routers.qomn
  - Loads the analyze_router and analyze_project_router from
    backend.routers.analyze (created in Phase 10)
  - Mounts all routers under /api prefix
  - Adds a RoleDevMiddleware that grants ADMIN role when
    FIREAI_ENV in {development, testing} so endpoints with
    require_permission(Permission.QOMN_EXECUTE) are callable
    in tests / dev. In production the middleware is a no-op and
    the real API-key middleware (deployed separately) sets the role.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.rbac import Role
from backend.routers.qomn import router as qomn_router
from backend.routers.analyze import (
    router as analyze_router,
    project_router as analyze_project_router,
)
from backend.routers.health import router as health_router

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Dev role middleware (V127)
# ----------------------------------------------------------------------------
class _RoleDevMiddleware(BaseHTTPMiddleware):
    """Grants ADMIN role in development / testing environments.

    In production this middleware is a no-op -- the real API-key
    middleware (deployed by the platform) is responsible for setting
    request.state.fireai_role based on the validated API key.
    """

    async def dispatch(self, request: Request, call_next):
        env = os.getenv("FIREAI_ENV", "production").lower()
        if env in ("development", "testing"):
            # Only set if not already set by an upstream middleware.
            if getattr(request.state, "fireai_role", None) is None:
                request.state.fireai_role = Role.ADMIN
        return await call_next(request)


# ----------------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------------
app = FastAPI(
    title="FireAI QOMN-FIRE API",
    description=(
        "QOMN-FIRE deterministic engineering kernel + project-level "
        "analyze endpoints. All calculations are NFPA 72-2022 / NEC 2023 "
        "compliant with cryptographic audit trail."
    ),
    version="1.0.0",
)

# CORS (permissive in dev, locked-down in production via env vars)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "X-Correlation-ID"],
)
app.add_middleware(_RoleDevMiddleware)


# ----------------------------------------------------------------------------
# Router registration (under /api prefix per Phase 10 spec)
# ----------------------------------------------------------------------------
app.include_router(health_router, prefix="/api")
app.include_router(qomn_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(analyze_project_router, prefix="/api")


# ----------------------------------------------------------------------------
# Root / fallback
# ----------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    return {"name": "FireAI QOMN-FIRE API", "version": "1.0.0",
            "docs": "/docs", "health": "/api/health"}


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler.

    Never leak internal exception text to clients -- fire-safety systems
    may have sensitive paths / connection strings in error messages.
    """
    logger.error("Unhandled exception on %s %s: %s",
                 request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "success": False},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
