# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
backend/routers/projects.py — Projects CRUD endpoints.

LIFE-SAFETY NOTE: Projects are the top-level container for all fire alarm
engineering data. Deletion cascades to all child devices, connections,
and reports.
"""

from __future__ import annotations

import io
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from backend.core.openapi_contracts import StandardizedAPIRoute
from fastapi.responses import StreamingResponse

from backend.auth import (
    get_current_principal,
    get_current_role,
    require_permission,
)
from backend.contract import validate_paginated, validate_project
from backend.database import get_db
from backend.limiter import limiter
from backend.models import (
    CreateProjectInput,
    UpdateProjectInput,
)
from backend.project_bridge import (
    sync_project_delete_to_udm,
    sync_project_to_udm,
    sync_project_update_to_udm,
)
from backend.rbac import Permission, Role
from backend.response import success

router = APIRouter(prefix="/projects", tags=["projects"], route_class=StandardizedAPIRoute)
_SORT_MAP = {
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    "name": "name",
    "status": "status",
    "author": "author",
}


def _normalize_sort(sort: str) -> str:
    """
    Convert camelCase sort fields to snake_case for database.

    SECURITY FIX (BUG-32): Strict whitelist — if the sort field isn't
    in _SORT_MAP, default to 'created_at'. Previously, raw user input
    with underscores passed through, creating an SQL injection vector
    if the database whitelist was ever bypassed.
    """
    return _SORT_MAP.get(sort, "created_at")


def _verify_project_access(project: dict, request: Request) -> None:
    """
    Verify caller has permission to access the project (BLK-01 Tenant Isolation).
    Fails closed with 404 (anti-enumeration).
    """
    role = get_current_role(request)
    if role == Role.ADMIN:
        return

    principal = get_current_principal(request)
    if not principal:
        raise HTTPException(status_code=404, detail="Project not found")

    author = project.get("author", "")
    if author != principal:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("", dependencies=[Depends(require_permission(Permission.PROJECT_READ))])
async def list_projects(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),  # NOSONAR - python:S8410
    limit: int = Query(20, ge=1, le=100, description="Items per page"),  # NOSONAR - python:S8410
    sort: str = Query("createdAt", description="Sort field"),  # NOSONAR - python:S8410
    order: str = Query("desc", description="Sort order (asc/desc)"),  # NOSONAR - python:S8410
    author: str | None = Query(None, description="Filter by author"),
):
    page_num = page if isinstance(page, int) else 1
    limit_num = limit if isinstance(limit, int) else 20
    sort_str = sort if isinstance(sort, str) else "createdAt"
    order_str = order if isinstance(order, str) and order in ("asc", "desc") else "desc"

    role = get_current_role(request)
    principal = get_current_principal(request)

    if role == Role.ADMIN:
        author_filter = author if isinstance(author, str) else None
    elif principal:
        author_filter = principal
    else:
        author_filter = "__unauthenticated_deny__"

    """List all projects with pagination and tenant isolation."""
    db = get_db()
    result = db.list_projects(
        page=page_num,
        limit=limit_num,
        sort=_normalize_sort(sort_str),
        order=order_str,
        author=author_filter,
    )
    validate_paginated(result, item_validator=validate_project)
    return success(result)


@router.post(
    "", status_code=201, dependencies=[Depends(require_permission(Permission.PROJECT_CREATE))]
)
@limiter.limit("30/minute")
async def create_project(request: Request, input_data: CreateProjectInput):
    """Create a new project scoped authoritatively to the current authenticated principal."""
    db = get_db()
    principal = get_current_principal(request)
    role = get_current_role(request)
    if principal:
        # Enforce authoritative ownership boundary: client cannot forge another principal's ownership
        if input_data.author and input_data.author != principal and role != Role.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Cannot create a project on behalf of another principal",
            )
        author = principal
    else:
        author = input_data.author or ""

    project_data = {
        "id": str(uuid.uuid4()),
        "name": input_data.name,
        "description": input_data.description or "",
        "author": author,
    }
    project = db.create_project(project_data)
    validate_project(project)

    # Sync to UDM (System B) — non-blocking, never raises
    try:
        sync_project_to_udm(project)
    except Exception:
        pass  # Bridge failures are logged internally, must not block

    return success(project)


@router.get(
    "/{project_id}",
    responses={404: {"description": "Project not found"}},
    dependencies=[Depends(require_permission(Permission.PROJECT_READ))],
)
async def get_project(request: Request, project_id: str):
    """Get a project by ID with tenant access verification."""
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail="Project not found"
        )  # NOSONAR — S1192: duplicated literal acceptable in this localized context
    _verify_project_access(project, request)
    validate_project(project)
    return success(project)


@router.put(
    "/{project_id}",
    responses={404: {"description": "Project not found"}},
    dependencies=[Depends(require_permission(Permission.PROJECT_UPDATE))],
)
@limiter.limit("30/minute")
async def update_project(request: Request, project_id: str, input_data: UpdateProjectInput):
    """Update an existing project with tenant access verification."""
    db = get_db()
    existing = db.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")
    _verify_project_access(existing, request)

    updates = input_data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    project = db.update_project(project_id, updates)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    validate_project(project)

    # Sync update to UDM (System B) — non-blocking, never raises
    try:
        sync_project_update_to_udm(project_id, updates)
    except Exception:
        pass  # Bridge failures are logged internally, must not block

    return success(project)


# ── Project Export Endpoints (DXF, Revit, IFC) ────────────────────────────────────────


@router.get(
    "/{project_id}/export/dxf",
    responses={404: {"description": "Project not found"}},
    dependencies=[Depends(require_permission(Permission.EXPORT_READ))],
)
async def export_project_dxf(request: Request, project_id: str) -> StreamingResponse:
    """Export a project as DXF (placeholder implementation)."""
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _verify_project_access(project, request)
    content = b"Mock DXF content for project " + project_id.encode()
    filename = f"{project.get('name', 'project')}_export.dxf"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{project_id}/export/revit",
    responses={404: {"description": "Project not found"}},
    dependencies=[Depends(require_permission(Permission.EXPORT_READ))],
)
async def export_project_revit(request: Request, project_id: str) -> StreamingResponse:
    """Export a project as Revit JSON (placeholder)."""
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _verify_project_access(project, request)
    data = {"project_id": project_id, "devices": [], "connections": [], "version": "1.0"}
    content = json.dumps(data).encode()
    filename = f"{project.get('name', 'project')}_export.json"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{project_id}/export/ifc",
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid IFC version"},
    },
    dependencies=[Depends(require_permission(Permission.EXPORT_READ))],
)
async def export_project_ifc(
    request: Request, project_id: str, version: str | None = None
) -> StreamingResponse:
    """Export a project as IFC (placeholder).
    Accepts optional version parameter; only known versions are allowed.
    """
    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _verify_project_access(project, request)
    # Validate version if provided
    allowed_versions = {"IFC2X3", "IFC4"}
    if version is not None and version not in allowed_versions:
        raise HTTPException(status_code=422, detail="Invalid IFC version")
    # Simple placeholder IFC content
    content = f"IFC placeholder for project {project_id}, version {version or 'default'}".encode()
    filename = f"{project.get('name', 'project')}_export.ifc"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/ifc",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/{project_id}",
    responses={404: {"description": "Project not found"}},
    dependencies=[Depends(require_permission(Permission.PROJECT_DELETE))],
)
@limiter.limit("30/minute")
async def delete_project(request: Request, project_id: str):
    """Delete a project and all its children with tenant verification."""
    db = get_db()
    existing = db.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")
    _verify_project_access(existing, request)

    deleted = db.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    # Sync deletion to UDM (System B) — non-blocking, never raises
    try:
        sync_project_delete_to_udm(project_id)
    except Exception:
        pass  # Bridge failures are logged internally, must not block

    return success(None, "Project deleted")
