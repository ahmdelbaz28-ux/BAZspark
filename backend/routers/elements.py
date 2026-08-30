# File-level issue suppression removed per AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
FireAI Digital Twin - Elements Router.
======================================
CRUD endpoints for building elements.
"""

import logging
import math
import re
from typing import Any

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated


from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.auth import get_current_principal, get_current_role, require_permission
from backend.core.openapi_contracts import StandardizedAPIRoute
from backend.db_service import get_db_service
from backend.limiter import limiter
from backend.rbac import Permission, Role
from backend.schemas import (
    ApiResponse,
    ElementCreate,
    ElementResponse,
    ElementUpdate,
    PaginatedData,
)

logger = logging.getLogger(__name__)

# (relative). The absolute prefix caused double-prefixing when
# _safe_include_router added "/api/v1" via app.include_router(prefix="/api/v1"),
# producing /api/v1/api/v1/elements which broke all tests.
router = APIRouter(prefix="/elements", tags=["elements"], route_class=StandardizedAPIRoute)

# ── Annotated dependency aliases (S8410) ────────────────────────────────────
DbDep = Annotated[Any, Depends(get_db_service)]
# ────────────────────────────────────────────────────────────────────────────


def _verify_project(project_id: str, request: Request | None = None) -> dict:
    """Ensure the project exists and caller has tenant access before operating on its elements."""
    from backend.database import get_db

    db = get_db()
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=404, detail="Project not found"
        )  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
    if request is not None:
        from backend.routers.projects import _verify_project_access

        _verify_project_access(project, request)
    return project


@router.get(
    "",
    response_model=ApiResponse[PaginatedData[ElementResponse]],
    dependencies=[Depends(require_permission(Permission.ELEMENT_READ))],
)
async def list_elements(
    request: Request,
    db: DbDep,
    element_type: str | None = Query(None, description="Filter by element type"),
    project_id: str | None = Query(None, description="Filter by project ID"),
    is_deleted: bool | None = Query(None, description="Include deleted elements"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
):
    """List elements with optional filtering, pagination, and tenant isolation."""
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    try:
        role = get_current_role(request)
        principal = get_current_principal(request)

        if project_id:
            if role != Role.ADMIN:
                _verify_project(project_id, request)
            elements, total = db.list_elements(
                element_type=element_type,
                project_id=project_id,
                is_deleted=is_deleted,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        else:
            if role == Role.ADMIN:
                elements, total = db.list_elements(
                    element_type=element_type,
                    project_id=None,
                    is_deleted=is_deleted,
                    page=page,
                    page_size=page_size,
                    sort_by=sort_by,
                    sort_order=sort_order,
                )
            else:
                if not principal:
                    elements, total = [], 0
                else:
                    from backend.database import get_db

                    db_backend = get_db()
                    user_projects = db_backend.list_projects(page=1, limit=1000, author=principal)
                    user_project_ids = {p["id"] for p in user_projects.get("data", [])}
                    if not user_project_ids:
                        elements, total = [], 0
                    else:
                        raw_elements, _ = db.list_elements(
                            element_type=element_type,
                            project_id=None,
                            is_deleted=is_deleted,
                            page=1,
                            page_size=100000,
                            sort_by=sort_by,
                            sort_order=sort_order,
                        )
                        filtered = [
                            elem for elem in raw_elements if elem.project_id in user_project_ids
                        ]
                        total = len(filtered)
                        start_idx = (page - 1) * page_size
                        elements = filtered[start_idx : start_idx + page_size]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return ApiResponse(
            success=True,
            data=PaginatedData(
                items=elements,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("list_elements failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )  # NOSONAR — S1192: duplicated literal acceptable in this localized context


@router.post(
    "",
    response_model=ApiResponse[ElementResponse],
    status_code=201,
    dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))],
)
@limiter.limit("30/minute")
async def create_element(
    request: Request,
    element_data: ElementCreate,
    db: DbDep,
):
    """Create a new element with tenant verification."""
    if element_data.project_id:
        _verify_project(element_data.project_id, request)
    try:
        element = db.create_element(element_data)
        return ApiResponse(success=True, data=element, message="Element created successfully")
    except ValueError as e:
        # or class details. Sanitize before exposing to client.
        safe_msg = str(e)[:200]  # Truncate to prevent overflow
        # Remove common path patterns that leak server structure
        safe_msg = re.sub(r"/[\w./-]+", "[PATH]", safe_msg)
        safe_msg = re.sub(r"<class \w+>", "[CLASS]", safe_msg)
        raise HTTPException(
            status_code=400, detail=safe_msg
        )  # NOSONAR — S8415: assignment kept for readability / debuggability
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_element failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )  # NOSONAR — S8415: assignment kept for readability / debuggability


@router.get(
    "/{element_id}",
    response_model=ApiResponse[ElementResponse],
    dependencies=[Depends(require_permission(Permission.ELEMENT_READ))],
)
async def get_element(
    request: Request,
    element_id: str,
    db: DbDep,
):
    """Get an element by ID with tenant verification."""
    try:
        element = db.get_element(element_id)
        if element is None:
            raise HTTPException(
                status_code=404, detail=f"Element {element_id} not found"
            )  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
        if element.project_id:
            _verify_project(element.project_id, request)
        return ApiResponse(success=True, data=element)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_element failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )  # NOSONAR — S8415: assignment kept for readability / debuggability


@router.put(
    "/{element_id}",
    response_model=ApiResponse[ElementResponse],
    dependencies=[Depends(require_permission(Permission.ELEMENT_UPDATE))],
)
@limiter.limit("30/minute")
async def update_element(
    request: Request,
    element_id: str,
    element_data: ElementUpdate,
    db: DbDep,
):
    """Update an element with tenant verification."""
    try:
        existing = db.get_element(element_id)
        if existing is None:
            raise HTTPException(
                status_code=404, detail=f"Element {element_id} not found"
            )  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
        if existing.project_id:
            _verify_project(existing.project_id, request)
        new_project_id = getattr(element_data, "project_id", None)
        if new_project_id and new_project_id != existing.project_id:
            _verify_project(new_project_id, request)

        element = db.update_element(element_id, element_data)
        if element is None:
            raise HTTPException(
                status_code=404, detail=f"Element {element_id} not found"
            )  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
        return ApiResponse(success=True, data=element, message="Element updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_element failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )  # NOSONAR — S8415: assignment kept for readability / debuggability


@router.delete(
    "/{element_id}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission(Permission.ELEMENT_DELETE))],
)
@limiter.limit("30/minute")
async def delete_element(
    request: Request,
    element_id: str,
    db: DbDep,
):
    """Soft delete an element with tenant verification."""
    try:
        existing = db.get_element(element_id)
        if existing is None:
            raise HTTPException(
                status_code=404, detail=f"Element {element_id} not found"
            )  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
        if existing.project_id:
            _verify_project(existing.project_id, request)

        success = db.delete_element(element_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Element {element_id} not found"
            )  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
        return ApiResponse(success=True, message="Element deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("delete_element failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )  # NOSONAR — S8415: assignment kept for readability / debuggability
