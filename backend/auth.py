"""
Authentication and authorization dependencies for FastAPI.

Provides FastAPI dependencies for extracting the current user's role
from the request and enforcing permission checks on endpoints.

LAYER NOTE (Phase 5 dedup):
  This module is the FastAPI *dependency* layer for auth — it provides
  ``require_permission()`` and ``get_current_role()`` used by ~40 routers.
  It is NOT a duplicate of the other auth modules:
    - backend/auth.py               → FastAPI dependency layer (this file:
                                      require_permission, get_current_role, get_current_principal)
    - backend/routers/auth.py       → FastAPI router layer (login, logout, verify, me endpoints)
    - facp_distributed/security/auth.py → JWT-based auth for distributed FACP nodes
  Each serves a distinct layer. Do NOT merge.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from backend.rbac import Permission, Role, has_permission


def get_current_role(request: Request) -> Role:
    """
    Extract the current user's role from the request.

    The role is set by the ApiKeyMiddleware on request.state.fireai_role
    and also stored in request.scope["fireai_role"] as a fallback.

    If no role is found (e.g., whitelisted paths or development mode),
    defaults to VIEWER for safety (least privilege).
    """
    role: Role | None = getattr(request.state, "fireai_role", None)
    if role is not None:
        return role
    # Fallback: check for role in request scope (set by ASGI middleware)
    scope_role = request.scope.get("fireai_role")
    if scope_role is not None and isinstance(scope_role, Role):
        return scope_role
    # Default to VIEWER (least privilege) when no role is set
    return Role.VIEWER


def require_permission(permission: Permission):
    """
    FastAPI dependency factory that requires a specific permission.

    Usage:
        @router.post("", dependencies=[Depends(require_permission(Permission.PROJECT_CREATE))])
        async def create_project(...):
            ...

    Raises HTTP 403 Forbidden if the current role lacks the required permission.
    """

    def checker(request: Request) -> Role:
        role = get_current_role(request)
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission denied: {permission.value} required. "
                    f"Your role: {role.value}"
                ),
            )
        return role

    return checker


def get_current_principal(request: Request) -> str | None:
    """
    Extract the current credential's opaque principal id from the request.

    The principal is stamped by ApiKeyMiddleware (both the API-key path and
    the session-cookie path) as an opaque, stable, per-credential identifier
    used to scope user-owned resources (e.g. Mem0 memories).

    Returns None when the request is unauthenticated or the principal is
    absent (e.g. legacy middleware without the stamp).
    """
    principal: str | None = getattr(request.state, "fireai_principal", None)
    if principal is not None:
        return principal
    scope_principal = request.scope.get("fireai_principal")
    if isinstance(scope_principal, str) and scope_principal:
        return scope_principal
    return None
