"""backend/routers/export_router.py — API v2 Unified Export Endpoints.

Safety-Critical Phase 4 Router:
- REST API v2 endpoints for export planning, mapping/loss preview, execution, and artifact download.
- Full integration with AgentRunOrchestrator for durable, policy-governed export lifecycles.
- OCC-governed revision verification and artifact validation.
- Rate limiting and RBAC permission checks.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.core.agent_run_orchestrator import default_agent_run_orchestrator
from backend.core.capability_registry import (
    CAP_EXPORT_EXECUTE_EXPORT,
    CAP_EXPORT_PLAN_EXPORT,
)
from backend.core.command_bus import AuthenticatedPrincipal
from backend.core.export_orchestrator import (
    FORMAT_MIME_TYPES,
    ArtifactValidationError,
    ExportExecutionError,
    ProjectNotFoundError,
    ProjectRevisionChangedError,
    StagedArtifactNotFoundError,
    UnsupportedExportFormatError,
    default_export_orchestrator,
)
from backend.limiter import limiter
from backend.rbac import Permission

logger = logging.getLogger("fireai.routers.export")

router = APIRouter(prefix="/export", tags=["export-v2"])

# Permissions
ExportReadRole = Annotated[None, Depends(require_permission(Permission.EXPORT_READ))]
ExportExecuteRole = Annotated[None, Depends(require_permission(Permission.EXPORT_EXECUTE))]


# ── Request / Response Models ───────────────────────────────────────────────


class PlanExportRequest(BaseModel):
    project_id: str = Field("", description="Target project ID")
    target_format: str = Field(
        ..., description="Target format: dxf, revit, ifc, xlsx, csv, json, pdf"
    )
    options: dict[str, Any] = Field(default_factory=dict, description="Export options")


class ExecuteExportRequest(BaseModel):
    project_id: str = Field("", description="Target project ID")
    expected_revision: int = Field(
        ..., description="Expected project revision for OCC verification"
    )
    target_format: str = Field(
        ..., description="Target format: dxf, revit, ifc, xlsx, csv, json, pdf"
    )
    options: dict[str, Any] = Field(default_factory=dict, description="Execution options")


class CreateExportRunRequest(BaseModel):
    project_id: str = Field("", description="Target project ID")
    target_format: str = Field(
        ..., description="Target format: dxf, revit, ifc, xlsx, csv, json, pdf"
    )
    approval_mode: str = Field("AUTO", description="AUTO or STEP_BY_STEP")
    options: dict[str, Any] = Field(default_factory=dict, description="Export options")


# ── Helper for Principal Extraction ─────────────────────────────────────────


def _get_principal(request: Request, current_user: Any = None) -> AuthenticatedPrincipal:
    user_id = "anonymous"
    email = "anonymous@bazspark.io"
    role = "viewer"
    scopes = ["export:read", "project:read"]

    if current_user:
        if isinstance(current_user, dict):
            user_id = current_user.get("sub", current_user.get("user_id", "user-01"))
            email = current_user.get("email", "user@bazspark.io")
            role = current_user.get("role", "engineer")
        else:
            user_id = getattr(current_user, "user_id", getattr(current_user, "id", "user-01"))
            email = getattr(current_user, "email", "user@bazspark.io")
            role = getattr(current_user, "role", "engineer")

    # In engineering workflows, grant default read/export scopes for authenticated users
    scopes = ["export:read", "export:write", "project:read", "project:write", "spatial:read"]

    return AuthenticatedPrincipal(
        user_id=str(user_id),
        email=str(email),
        role=str(role),
        scopes=scopes,
        is_authenticated=True,
    )


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/plan")
@limiter.limit("60/minute")
async def plan_export(
    request: Request,
    req: PlanExportRequest,
    _: None = Depends(require_permission(Permission.EXPORT_READ)),
) -> dict[str, Any]:
    """Generate a deterministic export plan with loss / mapping impact analysis."""
    principal = _get_principal(request)
    try:
        plan = default_export_orchestrator.plan_export(
            project_id=req.project_id,
            target_format=req.target_format,
            principal=principal,
            options=req.options,
        )
        return {
            "success": True,
            "plan": plan.to_dict(),
        }
    except UnsupportedExportFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Failed to plan export: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "PLAN_EXPORT_FAILED", "message": "Failed to create export plan."},
        ) from exc


@router.post("/execute")
@limiter.limit("30/minute")
async def execute_export(
    request: Request,
    req: ExecuteExportRequest,
    _: None = Depends(require_permission(Permission.EXPORT_READ)),
) -> dict[str, Any]:
    """Directly execute deterministic export with OCC revision check and artifact validation."""
    principal = _get_principal(request)
    try:
        result = default_export_orchestrator.execute_export(
            project_id=req.project_id,
            expected_revision=req.expected_revision,
            target_format=req.target_format,
            principal=principal,
            options=req.options,
        )
        return {
            "success": True,
            "result": result.to_dict(),
        }
    except UnsupportedExportFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except ProjectRevisionChangedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except (ArtifactValidationError, ExportExecutionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Export execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "EXPORT_EXECUTION_FAILED", "message": str(exc)},
        ) from exc


@router.post("/run")
@limiter.limit("20/minute")
async def create_export_run(
    request: Request,
    req: CreateExportRunRequest,
    _: None = Depends(require_permission(Permission.EXPORT_READ)),
) -> dict[str, Any]:
    """Launch a server-authoritative AgentRun lifecycle for the export pipeline."""
    principal = _get_principal(request)
    try:
        # Pre-plan to obtain current revision & policy
        plan = default_export_orchestrator.plan_export(
            project_id=req.project_id,
            target_format=req.target_format,
            principal=principal,
            options=req.options,
        )

        steps = [
            {
                "step_id": "step-1-plan-export",
                "capability_id": CAP_EXPORT_PLAN_EXPORT,
                "description": f"Analyze mapping and plan {req.target_format.upper()} export for '{req.project_id}'",
                "payload": {
                    "project_id": req.project_id,
                    "target_format": req.target_format,
                    "options": req.options,
                },
            },
            {
                "step_id": "step-2-execute-export",
                "capability_id": CAP_EXPORT_EXECUTE_EXPORT,
                "description": f"Generate and validate {req.target_format.upper()} artifact with OCC check",
                "payload": {
                    "project_id": req.project_id,
                    "expected_revision": plan.expected_revision,
                    "target_format": req.target_format,
                    "options": req.options,
                },
            },
        ]

        run = default_agent_run_orchestrator.start_run(
            principal,
            project_id=req.project_id,
            steps=steps,
            approval_mode=req.approval_mode,
        )

        return {
            "success": True,
            "run": {
                "runId": run.run_id,
                "status": run.status.value,
                "currentStep": run.current_step,
                "completedSteps": list(run.completed_steps),
                "pendingApprovalId": run.pending_approval_id,
                "projectId": run.project_id,
                "approvalMode": run.approval_mode.value,
                "plan": plan.to_dict(),
            },
        }
    except UnsupportedExportFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Failed to start export agent run: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "errorCode": "AGENT_RUN_FAILED",
                "message": "Could not initiate export workflow run.",
            },
        ) from exc


@router.get("/artifacts/{artifact_id}")
async def get_artifact_metadata(
    artifact_id: str,
    _: None = Depends(require_permission(Permission.EXPORT_READ)),
) -> dict[str, Any]:
    """Retrieve metadata and validation status for an export artifact."""
    try:
        record = default_export_orchestrator.get_artifact(artifact_id)
        return {
            "success": True,
            "artifact": record.to_dict(),
        }
    except StagedArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    _: None = Depends(require_permission(Permission.EXPORT_READ)),
) -> StreamingResponse:
    """Stream exported engineering artifact file with format-specific media type."""
    try:
        record = default_export_orchestrator.get_artifact(artifact_id)
        file_path = Path(record.artifact_path)
        if not file_path.exists():
            raise StagedArtifactNotFoundError("Artifact file on disk no longer exists.")

        content = file_path.read_bytes()
        media_type = FORMAT_MIME_TYPES.get(record.target_format.lower(), "application/octet-stream")

        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{record.filename}"',
                "X-Artifact-SHA256": record.sha256_hash,
                "X-Artifact-Revision": str(record.revision),
            },
        )
    except StagedArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Artifact download failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "DOWNLOAD_FAILED", "message": "Failed to stream export artifact."},
        ) from exc
