"""backend/routers/capability_discovery.py — Read-only Authorized Capability Discovery HTTP Router.

BAZSPARK V2.2 Phase 2 Canonical Capability Discovery:
- Exposes GET discovery query over existing authentication middleware.
- Zero state mutation, zero new auth paths.
- Returns lean schema payload of authorized capabilities only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.auth import get_current_role
from backend.core.capability_registry import (
    VALID_CATEGORIES,
    VALID_EXECUTION_CHANNELS,
    default_capability_registry,
)
from backend.rbac import ROLE_PERMISSIONS, Role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capabilities", tags=["Capability Discovery"])


@router.get("", response_model=dict[str, Any])
async def discover_capabilities(
    request: Request,
    execution_channel: str | None = Query(
        default=None, description="Optional execution channel filter (e.g. sync, async, websocket)"
    ),
    category: str | None = Query(
        default=None, description="Optional capability category filter (e.g. spatial, electrical, export)"
    ),
) -> dict[str, Any]:
    """
    Discover authorized capabilities for the authenticated principal.

    Fail-closed validation on filter parameters.
    Returns lean schema metadata for capabilities where the principal possesses
    all required scopes.
    """
    # 1. Fail-closed query filter validation
    if category is not None and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category filter '{category}'. Must be one of {sorted(VALID_CATEGORIES)}.",
        )
    if execution_channel is not None and execution_channel not in VALID_EXECUTION_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid execution_channel filter '{execution_channel}'. Must be one of {sorted(VALID_EXECUTION_CHANNELS)}.",
        )

    # 2. Extract principal role and granted scopes from existing auth context
    role = get_current_role(request)
    is_admin = role == Role.ADMIN

    # Check if custom scopes are stamped on request.state (e.g. from token/session)
    custom_scopes = getattr(request.state, "fireai_scopes", None)
    if custom_scopes is not None and isinstance(custom_scopes, (list, set)):
        granted_scopes = [str(s) for s in custom_scopes]
    else:
        # Default to permissions associated with the validated role
        role_perms = ROLE_PERMISSIONS.get(role, set())
        granted_scopes = [p.value for p in role_perms]

    # 3. Query registry for authorized capabilities
    try:
        caps = default_capability_registry.discover_authorized(
            scopes=granted_scopes,
            is_admin=is_admin,
            execution_channel=execution_channel,
            category=category,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    return {
        "success": True,
        "count": len(caps),
        "capabilities": caps,
    }
