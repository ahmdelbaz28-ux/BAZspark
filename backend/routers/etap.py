# File-level suppression comment removed per audit guide (V143 hardening).
# Per-line justified suppressions are preserved.
"""
backend/routers/etap.py — ETAP Integration REST API.
=====================================================

Endpoints:
    POST /api/v1/integrations/etap/connect          — Test ETAP connection
    POST /api/v1/integrations/etap/disconnect       — Disconnect from ETAP
    GET  /api/v1/integrations/etap/status           — Get integration status
    GET  /api/v1/integrations/etap/projects         — List ETAP projects
    POST /api/v1/integrations/etap/export           — Export to ETAP
    POST /api/v1/integrations/etap/import           — Import from ETAP
    GET  /api/v1/integrations/etap/logs             — Get sync logs
    POST /api/v1/integrations/etap/settings         — Create/update settings
    GET  /api/v1/integrations/etap/settings         — Get settings
    DELETE /api/v1/integrations/etap/settings       — Delete settings
"""
import logging
from typing import List, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated



from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.auth import require_permission
from backend.integrations.etap_schemas import (
    EtapConnectionSettings,
    EtapConnectionTestResponse,
    EtapExportRequest,
    EtapImportRequest,
    EtapProjectInfo,
    EtapSettingsResponse,
    EtapSettingsUpdate,
    EtapSyncLogResponse,
)
from backend.integrations.etap_service import EtapService
from backend.rbac import Permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/etap", tags=["ETAP Integration"])

_ETAP_NOT_CONFIGURED = "ETAP integration not configured"
_PROJECT_ID_DESCRIPTION = "Project ID"


def get_etap_service(request: Request):
    """Dependency to get ETAP service instance."""
    db = request.app.state.db
    return EtapService(db)


# ── Annotated dependency aliases (S8410) ────────────────────────────────────
# NOTE: Must be defined AFTER the DI function it references (F821 fix).
EtapServiceDep = Annotated[EtapService, Depends(get_etap_service)]
# ────────────────────────────────────────────────────────────────────────────


# ─── Connection Endpoints ────────────────────────────────────────────────────


@router.post("/connect", dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))])
async def connect_to_etap(
    request: Request,
    settings: EtapConnectionSettings,
    service: EtapServiceDep,
) -> EtapConnectionTestResponse:
    """
    Test connection to ETAP server.

    Requires INTEGRATION_MANAGE permission.
    """
    project_id = request.query_params.get("project_id", "default")
    result = service.test_connection(project_id)
    return EtapConnectionTestResponse(**result)


@router.post(
    "/disconnect",
    responses={
        404: {"description": _ETAP_NOT_CONFIGURED},
    },
    dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))],
)
async def disconnect(
    request: Request,
    service: EtapServiceDep,
) -> dict:
    """Disconnect from ETAP (disable integration)."""
    project_id = request.query_params.get("project_id", "default")
    existing = service.get_settings(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=_ETAP_NOT_CONFIGURED)

    service.update_settings(project_id, EtapSettingsUpdate(enabled=False))
    return {"message": "Disconnected successfully", "enabled": False}


@router.get("/status", dependencies=[Depends(require_permission(Permission.INTEGRATION_READ))])
async def get_status(
    service: EtapServiceDep,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
) -> dict:
    """Get ETAP integration status for a project."""
    return service.get_status(project_id)


# ─── Projects Endpoints ──────────────────────────────────────────────────────


@router.get("/projects", dependencies=[Depends(require_permission(Permission.INTEGRATION_READ))])
async def list_etap_projects(
    service: EtapServiceDep,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
) -> List[EtapProjectInfo]:
    """List available ETAP projects."""
    projects = service.list_etap_projects(project_id)
    return [EtapProjectInfo(**p) for p in projects]


@router.get("/projects/local", dependencies=[Depends(require_permission(Permission.INTEGRATION_READ))])
async def list_local_projects(
    service: EtapServiceDep,
) -> List[dict]:
    """List local BAZSPARK projects."""
    return service.list_local_projects()


# ─── Export/Import Endpoints ─────────────────────────────────────────────────


@router.post(
    "/export",
    responses={
        400: {"description": "Bad request — invalid export parameters"},
        500: {"description": "Export failed"},
    },
    dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))],
)
async def export_to_etap(
    export_request: EtapExportRequest,
    service: EtapServiceDep,
) -> dict:
    """
    Export local project data to ETAP.

    Requires INTEGRATION_MANAGE permission.
    """
    try:
        return service.export_to_etap(export_request.project_id, export_request)
    except ValueError as exc:
        logger.exception("ETAP export validation failed")
        raise HTTPException(status_code=400, detail="Export failed: invalid parameters") from exc
    except Exception as exc:
        logger.exception("ETAP export failed")
        raise HTTPException(status_code=500, detail="Export failed") from exc


@router.post(
    "/import",
    responses={
        400: {"description": "Bad request — invalid import parameters"},
        500: {"description": "Import failed"},
    },
    dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))],
)
async def import_from_etap(
    import_request: EtapImportRequest,
    service: EtapServiceDep,
) -> dict:
    """
    Import data from ETAP to local project.

    Requires INTEGRATION_MANAGE permission.
    """
    try:
        return service.import_from_etap(import_request.project_id, import_request)
    except ValueError as exc:
        logger.exception("ETAP import validation failed")
        raise HTTPException(status_code=400, detail="Import failed: invalid parameters") from exc
    except Exception as exc:
        logger.exception("ETAP import failed")
        raise HTTPException(status_code=500, detail="Import failed") from exc


# ─── Logs Endpoint ───────────────────────────────────────────────────────────


@router.get("/logs", dependencies=[Depends(require_permission(Permission.INTEGRATION_READ))])
async def get_logs(
    service: EtapServiceDep,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
) -> EtapSyncLogResponse:
    """Get sync logs for a project."""
    result = service.get_logs(project_id, page, page_size)
    return EtapSyncLogResponse(**result)


# ─── Settings Endpoints ──────────────────────────────────────────────────────


@router.post(
    "/settings",
    dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))],
)
async def create_settings(
    service: EtapServiceDep,
    settings: EtapConnectionSettings,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
) -> EtapSettingsResponse:
    """
    Create ETAP integration settings for a project.

    Requires INTEGRATION_MANAGE permission.
    """
    result = service.create_settings(project_id, settings)
    return EtapSettingsResponse(**result)


@router.get("/settings", dependencies=[Depends(require_permission(Permission.INTEGRATION_READ))])
async def get_settings(
    service: EtapServiceDep,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
) -> Optional[EtapSettingsResponse]:
    """Get ETAP settings for a project (no secrets returned)."""
    settings = service.get_settings(project_id)
    if not settings:
        return None
    # Return only non-sensitive fields
    safe_settings = {
        "id": settings["id"],
        "project_id": settings["project_id"],
        "host": settings["host"],
        "port": settings["port"],
        "username": settings["username"],
        "enabled": settings["enabled"],
        "last_sync": settings["last_sync"],
        "created_at": settings["created_at"],
        "updated_at": settings["updated_at"],
    }
    return EtapSettingsResponse(**safe_settings)


@router.put(
    "/settings",
    responses={
        404: {"description": _ETAP_NOT_CONFIGURED},
    },
    dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))],
)
async def update_settings(
    service: EtapServiceDep,
    update: EtapSettingsUpdate,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
) -> EtapSettingsResponse:
    """
    Update ETAP integration settings.

    Requires INTEGRATION_MANAGE permission.
    Password is optional — only update if provided.
    """
    updated = service.update_settings(project_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail=_ETAP_NOT_CONFIGURED)
    # Return only non-sensitive fields
    safe_settings = {
        "id": updated["id"],
        "project_id": updated["project_id"],
        "host": updated["host"],
        "port": updated["port"],
        "username": updated["username"],
        "enabled": updated["enabled"],
        "last_sync": updated["last_sync"],
        "created_at": updated["created_at"],
        "updated_at": updated["updated_at"],
    }
    return EtapSettingsResponse(**safe_settings)


@router.delete(
    "/settings",
    responses={
        404: {"description": _ETAP_NOT_CONFIGURED},
    },
    dependencies=[Depends(require_permission(Permission.INTEGRATION_MANAGE))],
)
async def delete_settings(
    service: EtapServiceDep,
    project_id: str = Query(..., description=_PROJECT_ID_DESCRIPTION),
) -> dict:
    """Delete ETAP integration settings."""
    deleted = service.delete_settings(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_ETAP_NOT_CONFIGURED)
    return {"message": "Settings deleted successfully"}
