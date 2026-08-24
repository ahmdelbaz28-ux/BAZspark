"""backend/routers/import_router.py — API v2 Unified Import Endpoints.

Safety-Critical Phase 3 Router:
- REST API v2 endpoints for file staging, inspection, planning, and execution.
- Integration with AgentRunOrchestrator for durable, policy-governed execution.
- Rate limiting and RBAC permission checks.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.core.agent_run_orchestrator import default_agent_run_orchestrator
from backend.core.capability_registry import (
    CAP_IMPORT_EXECUTE_IMPORT,
    CAP_IMPORT_INSPECT_FILE,
    CAP_IMPORT_PLAN_IMPORT,
)
from backend.core.command_bus import AuthenticatedPrincipal
from backend.core.import_orchestrator import (
    InvalidFileError,
    ProjectRevisionChangedError,
    ResourceLimitExceededError,
    StagedFileNotFoundError,
    UnsupportedFormatError,
    default_import_orchestrator,
)
from backend.limiter import limiter
from backend.rbac import Permission

logger = logging.getLogger("fireai.routers.import")

router = APIRouter(prefix="/import", tags=["import-v2"])

# Permissions
ImportReadRole = Annotated[None, Depends(require_permission(Permission.PROJECT_READ))]
ImportWriteRole = Annotated[None, Depends(require_permission(Permission.PROJECT_CREATE))]


# ── Request / Response Models ───────────────────────────────────────────────


class InspectRequest(BaseModel):
    file_id: str = Field(..., description="Staged file ID")


class PlanImportRequest(BaseModel):
    file_id: str = Field(..., description="Staged file ID")
    project_id: str = Field("default_project", description="Target project ID")
    options: dict[str, Any] = Field(default_factory=dict, description="Import options")


class ExecuteImportRequest(BaseModel):
    file_id: str = Field(..., description="Staged file ID")
    project_id: str = Field("default_project", description="Target project ID")
    expected_revision: int = Field(..., description="Expected project revision for OCC check")
    options: dict[str, Any] = Field(default_factory=dict, description="Execution options")


class CreateImportRunRequest(BaseModel):
    file_id: str = Field(..., description="Staged file ID")
    project_id: str = Field("default_project", description="Target project ID")
    approval_mode: str = Field("AUTO", description="AUTO or STEP_BY_STEP")
    options: dict[str, Any] = Field(default_factory=dict, description="Import options")


# ── Helper for Principal Extraction ─────────────────────────────────────────


def _get_principal(request: Request, current_user: Any = None) -> AuthenticatedPrincipal:
    user_id = "anonymous"
    email = "anonymous@bazspark.io"
    role = "viewer"
    scopes = ["import:read", "project:read"]

    if current_user:
        if isinstance(current_user, dict):
            user_id = current_user.get("sub", current_user.get("user_id", "user-01"))
            email = current_user.get("email", "user@bazspark.io")
            role = current_user.get("role", "engineer")
        else:
            user_id = getattr(current_user, "user_id", getattr(current_user, "id", "user-01"))
            email = getattr(current_user, "email", "user@bazspark.io")
            role = getattr(current_user, "role", "engineer")

    # In engineering workflows, grant default read/write scopes for authenticated users
    scopes = ["import:read", "import:write", "project:read", "project:write", "spatial:write"]

    return AuthenticatedPrincipal(
        user_id=str(user_id),
        email=str(email),
        role=str(role),
        scopes=scopes,
        is_authenticated=True,
    )


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/upload")
@limiter.limit("30/minute")
async def upload_and_stage_file(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_permission(Permission.PROJECT_READ)),
) -> dict[str, Any]:
    """Upload and stage a drawing / BIM file (.dwg, .dxf, .pdf, .ifc, .rvt, .xlsx, .csv)."""
    principal = _get_principal(request)
    try:
        content = await file.read()
        record = default_import_orchestrator.stage_file(
            content=content,
            filename=file.filename or "uploaded_drawing",
            principal=principal,
        )
        return {
            "success": True,
            "file": record.to_dict(),
        }
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except (InvalidFileError, ResourceLimitExceededError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("File upload failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "UPLOAD_FAILED", "message": "Failed to stage uploaded file."},
        ) from exc


@router.post("/inspect")
async def inspect_staged_file(
    request: Request,
    req: InspectRequest,
    _: None = Depends(require_permission(Permission.PROJECT_READ)),
) -> dict[str, Any]:
    """Inspect a staged file to extract rooms, devices, layers, and confidence."""
    principal = _get_principal(request)
    try:
        inspection = default_import_orchestrator.inspect_file(req.file_id, principal=principal)
        return {
            "success": True,
            "inspection": inspection,
        }
    except StagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Inspection failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "INSPECTION_FAILED", "message": "Failed to inspect staged file."},
        ) from exc


@router.post("/plan")
async def plan_import(
    request: Request,
    req: PlanImportRequest,
    _: None = Depends(require_permission(Permission.PROJECT_READ)),
) -> dict[str, Any]:
    """Build a deterministic import plan bound to target project revision."""
    principal = _get_principal(request)
    try:
        plan = default_import_orchestrator.plan_import(
            file_id=req.file_id,
            project_id=req.project_id,
            principal=principal,
            options=req.options,
        )
        return {
            "success": True,
            "plan": plan.to_dict(),
        }
    except StagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Planning failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "PLANNING_FAILED", "message": "Failed to create import plan."},
        ) from exc


@router.post("/execute")
async def execute_import(
    request: Request,
    req: ExecuteImportRequest,
    _: None = Depends(require_permission(Permission.PROJECT_CREATE)),
) -> dict[str, Any]:
    """Atomically execute import and commit entities to canonical project state."""
    principal = _get_principal(request)
    try:
        result = default_import_orchestrator.execute_import(
            file_id=req.file_id,
            project_id=req.project_id,
            expected_revision=req.expected_revision,
            principal=principal,
            options=req.options,
        )
        return {
            "success": True,
            "result": result.to_dict(),
        }
    except ProjectRevisionChangedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except StagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "EXECUTION_FAILED", "message": "Failed to execute import."},
        ) from exc


@router.post("/runs")
async def create_import_run(
    request: Request,
    req: CreateImportRunRequest,
    _: None = Depends(require_permission(Permission.PROJECT_CREATE)),
) -> dict[str, Any]:
    """Create a durable, policy-governed AgentRun for the import workflow."""
    principal = _get_principal(request)
    try:
        # Pre-verify staged file exists
        record = default_import_orchestrator.get_staged_file(req.file_id)
        current_rev = default_import_orchestrator._state_store.get_project_revision(req.project_id)

        steps = [
            {
                "step_id": "step-1-inspect",
                "capability_id": CAP_IMPORT_INSPECT_FILE,
                "payload": {"file_id": req.file_id},
                "description": f"Inspect {record.detected_format.upper()} drawing geometry and metadata",
            },
            {
                "step_id": "step-2-plan",
                "capability_id": CAP_IMPORT_PLAN_IMPORT,
                "payload": {
                    "file_id": req.file_id,
                    "project_id": req.project_id,
                    "options": req.options,
                },
                "description": "Construct deterministic import plan bound to canonical revision",
            },
            {
                "step_id": "step-3-execute",
                "capability_id": CAP_IMPORT_EXECUTE_IMPORT,
                "payload": {
                    "file_id": req.file_id,
                    "project_id": req.project_id,
                    "options": req.options,
                },
                "description": f"Commit parsed entities to canonical project state (Rev {current_rev} → {current_rev + 1})",
            },
        ]

        run = default_agent_run_orchestrator.start_run(
            principal=principal,
            project_id=req.project_id,
            steps=steps,
            approval_mode=req.approval_mode,
            plan={
                "intent": f"Import {record.detected_format.upper()} file '{record.sanitized_filename}'",
                "file_id": req.file_id,
                "target_project": req.project_id,
            },
        )

        return {
            "success": True,
            "run": {
                "runId": run.run_id,
                "projectId": run.project_id,
                "status": run.status.value,
                "approvalMode": run.approval_mode.value,
                "currentStep": run.current_step,
                "completedSteps": list(run.completed_steps),
                "pendingApprovalId": run.pending_approval_id,
            },
        }
    except StagedFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.error_code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.error("Create import run failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errorCode": "IMPORT_RUN_FAILED", "message": str(exc)},
        ) from exc
