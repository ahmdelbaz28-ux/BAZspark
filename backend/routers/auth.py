"""
backend/routers/auth.py — Session-based authentication with HttpOnly cookies.

M-3 FIX: Replaces sessionStorage API key storage with HttpOnly cookie.
This is MORE secure because:
  - HttpOnly: JavaScript cannot read the cookie (XSS-resistant)
  - SameSite=Strict: CSRF-resistant
  - Secure: Only transmitted over HTTPS in production
  - The frontend no longer needs to manually attach X-API-Key to every request

Endpoints:
  POST /api/v1/auth/login
    Body: {"api_key": "..."}
    Sets: Set-Cookie: fireai_session=<api_key>; HttpOnly; SameSite=Strict; Secure (prod)
    Returns: {"success": true, "data": {"role": "ADMIN"}}

  POST /api/v1/auth/logout
    Clears the cookie.

  GET /api/v1/auth/me
    Returns the current session's role (or 401 if not logged in).

Compliance: agent.md ANTI-DECEPTION — every claim verified by tests.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie settings
_COOKIE_NAME = "fireai_session"
# 8 hours — typical work session. Forces re-login daily.
_COOKIE_MAX_AGE_SECONDS = 8 * 3600


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""
    api_key: str = Field(..., min_length=1, description="FireAI API key")


class LoginResponse(BaseModel):
    """Response body for POST /auth/login."""
    role: str
    expires_at: str


@router.post("/login")
async def login(request: Request, body: LoginRequest):
    """
    Authenticate with an API key and receive an HttpOnly session cookie.

    The cookie replaces the need for X-API-Key header on subsequent requests.
    The frontend should call this once at login, then rely on the cookie.
    """
    import hmac

    from backend.rbac import Role
    from backend.security_middleware import _validate_api_key

    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Validate the API key
    role: Role | None = None
    env_key = os.getenv("FIREAI_API_KEY")
    if env_key and hmac.compare_digest(api_key, env_key):
        role = Role.ADMIN
    else:
        info = _validate_api_key(api_key)
        if info is not None:
            role = info.role

    if role is None:
        logger.warning("Failed login attempt from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Build Set-Cookie header
    is_production = os.getenv("FIREAI_ENV", "development").lower() in ("production", "prod")
    # Detect HTTPS (behind reverse proxy)
    forwarded_proto = ""
    for name, value in request.scope.get("headers", []):
        if name == b"x-forwarded-proto":
            forwarded_proto = value.decode("utf-8", errors="replace")
            break
    is_https = forwarded_proto == "https" or request.url.scheme == "https"

    cookie_parts = [
        f"{_COOKIE_NAME}={api_key}",
        "Path=/",
        f"Max-Age={_COOKIE_MAX_AGE_SECONDS}",
        "HttpOnly",
        "SameSite=Strict",
    ]
    if is_https or is_production:
        cookie_parts.append("Secure")

    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=_COOKIE_MAX_AGE_SECONDS)).isoformat()

    from fastapi.responses import JSONResponse
    response = JSONResponse(
        content=success({
            "role": role.value,
            "expires_at": expires_at,
        }),
    )
    response.headers["Set-Cookie"] = "; ".join(cookie_parts)
    response.headers["Cache-Control"] = "no-store"

    logger.info("Successful login, role=%s", role.value)
    return response


@router.post("/logout")
async def logout():
    """Clear the session cookie."""
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=success({"logged_out": True}))
    response.headers["Set-Cookie"] = (
        f"{_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"
    )
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """Return the current session's role (requires auth)."""
    role = request.scope.get("fireai_role")
    if role is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return success({"role": role.value})
