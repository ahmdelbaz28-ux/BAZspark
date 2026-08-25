# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
backend/routers/workflow.py — Workflow API endpoints for FireAI.

Provides REST API for the LangGraph-based workflow engine:
  - POST /api/workflow/start     — Start a new analysis workflow
  - GET  /api/workflow/{id}/status — Get workflow status
  - POST /api/workflow/{id}/approve — Approve at human review gate
  - POST /api/workflow/{id}/reject  — Reject at human review gate
  - GET  /api/workflow/{id}/audit   — Get full audit trail

LIFE-SAFETY NOTE:
  - Approval endpoints require X-API-Key (same as all mutating endpoints)
  - Every action is logged with timestamp and reviewer identity
  - Rejected workflows do NOT generate reports (fail-safe)
  - Audit trails are append-only (no deletion or modification)
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from backend.auth import get_current_principal, require_permission
from backend.core.agent_run_orchestrator import (
    InvalidRunStateError,
    RunNotFoundError,
    RunPermissionError,
    StaleApprovalError,
    default_agent_run_orchestrator,
)
from backend.core.agent_run_store import (
    ApprovalAlreadyDecidedError,
    PendingApprovalNotFoundError,
)
from backend.limiter import limiter
from backend.rbac import Permission, Role
from backend.services.workflow_service import (
    get_workflow_service,
)


def _get_fireai_api_key():
    """Read FIREAI_API_KEY at runtime, not import time."""
    return os.getenv("FIREAI_API_KEY", "")


def verify_api_key_dep(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """Verify API key from X-API-Key header."""
    _api_key = _get_fireai_api_key()
    if _api_key and (not x_api_key or not hmac.compare_digest(x_api_key, _api_key)):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API key")


logger = logging.getLogger(__name__)


# ── Path Traversal Defense-in-Depth (V113) ─────────────────────────────────
# SECURITY: file_path comes from user-controlled query string.
# Without validation, an attacker can read ANY file on the server:
#   ?file_path=../../../../etc/passwd
#   ?file_path=/etc/shadow
# The service layer (workflow_service.py:node_initialize) also validates,
# but defense-in-depth requires BOTH layers reject traversal.
# Per agent.md Priority 1 (Safety): a compromised FireAI system produces
# fake compliance reports = catastrophic loss of life.

ALLOWED_DATA_DIRS = os.environ.get(
    "FIREAI_DATA_DIRS",
    "/tmp/fireai_uploads:/data:/uploads",  # NOSONAR
).split(":")

ALLOWED_FILE_EXTENSIONS = frozenset({".dxf", ".dwg", ".pdf", ".ifc", ".rvt"})


def _validate_file_path(file_path: str) -> str:
    """
    Validate file_path against path traversal and extension whitelist.

    SECURITY: This is the FIRST line of defense at the router layer.
    The service layer (node_initialize) provides a SECOND check.
    Both are required — defense-in-depth per agent.md Priority 1 (Safety).
    """
    # Null byte injection (e.g., "file.pdf\x00.sh")
    if "\x00" in file_path:
        raise ValueError("Invalid file path: null byte detected")

    # Extension whitelist — only BIM/CAD file types
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise ValueError(
            f"File extension '{ext}' not allowed. Permitted: {sorted(ALLOWED_FILE_EXTENSIONS)}"
        )

    # Path traversal check — resolve and verify within allowed dirs
    real_path = os.path.realpath(file_path)
    parent_dir = os.path.dirname(real_path)
    is_allowed = False
    for allowed_dir in ALLOWED_DATA_DIRS:
        if not allowed_dir:
            continue
        allowed_real = os.path.realpath(allowed_dir)
        if (
            real_path == allowed_real
            or real_path.startswith(allowed_real + os.sep)
            or parent_dir == allowed_real
            or parent_dir.startswith(allowed_real + os.sep)
        ):
            is_allowed = True
            break

    if not is_allowed:
        raise ValueError(
            f"Path traversal blocked: '{file_path}' resolves outside "
            f"allowed directories. Per security policy, file access is "
            f"restricted to designated data directories."
        )

    return real_path


router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.get("/status", dependencies=[Depends(require_permission(Permission.WORKFLOW_READ))])
async def get_workflow_engine_status():
    """
    Get overall workflow engine status.

    Returns summary counts of workflows by status, plus service health.
    Does not require authentication (read-only monitoring endpoint).
    """
    svc = get_workflow_service()

    # Count workflows by status from the in-memory store
    status_counts = {}
    for _wf_id, wf_data in svc._workflows.items():
        state = wf_data.get("state", {})
        wf_status = state.get("status", "UNKNOWN")
        status_counts[wf_status] = status_counts.get(wf_status, 0) + 1

    langgraph_available = getattr(svc, "_langgraph_available", False)
    initialized = getattr(svc, "is_initialized", False)

    from backend.response import success

    return success(
        {
            "engine": {
                "initialized": initialized,
                "langgraph_available": langgraph_available,
                "status": "operational" if initialized and langgraph_available else "degraded",
            },
            "workflows": {
                "total": len(svc._workflows),
                "by_status": status_counts,
            },
        }
    )


@router.post(
    "/start",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
    responses={
        400: {"description": "Invalid file path or unpermitted directory"},
        403: {"description": "Human review bypass forbidden in production"},
    },
)
@limiter.limit("10/minute")
async def start_workflow(
    request: Request,
    file_path: str = Query(  # NOSONAR - python:S8410
        ...,
        min_length=1,
        max_length=1000,
        description="Path to DWG/PDF/DXF file to analyze",
    ),
    latitude: float | None = Query(  # NOSONAR - python:S8410
        None,
        ge=-90,
        le=90,
        description="Building latitude for environmental context",
    ),
    longitude: float | None = Query(  # NOSONAR - python:S8410
        None,
        ge=-180,
        le=180,
        description="Building longitude for environmental context",
    ),
    skip_human_review: bool = Query(  # NOSONAR - python:S8410
        False,
        description="Skip human review gate (DEVELOPMENT ONLY — never use in production)",
    ),
):
    """
    Start a new FireAI NFPA 72 analysis workflow.

    The workflow follows this state machine:
      Upload → Parse → Validate → NFPA Analysis → Conflict Detection
        → [Human Review Gate] → Generate Report

    If critical issues are found (unknown rooms, missing detectors),
    the workflow pauses at the Human Review Gate and must be
    explicitly approved or rejected before proceeding.

    LIFE-SAFETY: skip_human_review=True should NEVER be used in production.
    It bypasses the PE review gate required by NFPA 72.
    """
    try:
        _validate_file_path(file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if skip_human_review:
        # NFPA 72 requires PE review for all fire alarm designs.
        # Allowing this in production is a direct violation of NFPA 72.
        env = os.getenv("FIREAI_ENV", os.getenv("NODE_ENV", "production")).lower()
        if env not in ("development", "dev", "test", "testing"):
            raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
                status_code=403,
                detail=(
                    "skip_human_review=True is FORBIDDEN in production. "
                    "NFPA 72 requires Professional Engineer review for all "
                    "fire alarm designs. Set FIREAI_ENV=development to enable."
                ),
            )
        logger.warning(  # NOSONAR
            f"⚠️ DEVELOPMENT ONLY: Human review gate BYPASSED for {file_path}. "
            f"This is acceptable for development/testing ONLY. "
            f"NFPA 72 requires PE review for all fire alarm designs."
        )

    svc = get_workflow_service()
    result = await svc.start_workflow(
        file_path=file_path,
        latitude=latitude,
        longitude=longitude,
        skip_human_review=skip_human_review,
    )

    return {
        "success": True,
        "data": result,
    }


@router.get(
    "/{workflow_id}/status", dependencies=[Depends(require_permission(Permission.WORKFLOW_READ))]
)
async def get_workflow_status(
    workflow_id: str,
):
    """
    Get the current status of a workflow.

    Returns workflow status, review requirements, and summary statistics.
    Does NOT include the full report (use /audit for full details).
    """
    svc = get_workflow_service()
    result = await svc.get_workflow_status(workflow_id)

    if result is None:
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    return {
        "success": True,
        "data": result,
    }


@router.post(
    "/{workflow_id}/approve", dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))]
)
@limiter.limit("30/minute")
async def approve_workflow(
    request: Request,
    workflow_id: str,
    reviewer_comments: str | None = Query(  # NOSONAR - python:S8410
        None,
        max_length=2000,
        description="Reviewer comments (optional but recommended)",
    ),
):
    """
    Approve a workflow at the human review gate.

    After approval, the workflow resumes and generates the final report.
    The approval is logged with timestamp and comments in the audit trail.

    LIFE-SAFETY: Only a qualified Fire Protection Engineer (FPE) should
    approve a fire alarm design. This endpoint requires X-API-Key.
    """
    svc = get_workflow_service()
    result = await svc.approve_workflow(
        workflow_id=workflow_id,
        reviewer_comments=reviewer_comments,
    )

    if result is None:
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    if "error" in result:
        # CodeQL: py/stack-trace-exposure — sanitize error before returning to client
        err_msg = str(result["error"])[:200]
        if "Traceback" in err_msg or 'File "' in err_msg:
            err_msg = "Internal workflow error (details sanitized)"
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=400,
            detail=err_msg,  # lgtm[py/stack-trace-exposure] — sanitized above
        )

    return {
        "success": True,
        "data": result,
    }


@router.post(
    "/{workflow_id}/reject", dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))]
)
@limiter.limit("30/minute")
async def reject_workflow(
    request: Request,
    workflow_id: str,
    reviewer_comments: str | None = Query(  # NOSONAR - python:S8410
        None,
        max_length=2000,
        description="Reviewer comments (required for rejection — explain why)",
    ),
):
    """
    Reject a workflow at the human review gate.

    Rejected workflows do NOT generate reports (fail-safe).
    The rejection is logged with timestamp and comments in the audit trail.

    The workflow must be restarted with corrected data.
    """
    svc = get_workflow_service()
    result = await svc.reject_workflow(
        workflow_id=workflow_id,
        reviewer_comments=reviewer_comments,
    )

    if result is None:
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    if "error" in result:
        # CodeQL: py/stack-trace-exposure — sanitize error before returning to client
        err_msg = str(result["error"])[:200]
        if "Traceback" in err_msg or 'File "' in err_msg:
            err_msg = "Internal workflow error (details sanitized)"
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=400,
            detail=err_msg,  # lgtm[py/stack-trace-exposure] — sanitized above
        )

    return {
        "success": True,
        "data": result,
    }


@router.get(
    "/{workflow_id}/audit", dependencies=[Depends(require_permission(Permission.WORKFLOW_READ))]
)
async def get_audit_trail(
    workflow_id: str,
):
    """
    Get the full audit trail for a workflow.

    Returns every state transition with:
    - Timestamp (ISO 8601 UTC)
    - From/to nodes
    - Evidence (what was verified at each step)
    - Status at time of transition

    This satisfies agent.md traceability requirements and
    provides the evidence chain for PE sign-off.
    """
    svc = get_workflow_service()
    result = await svc.get_audit_trail(workflow_id)

    if result is None:
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    return {
        "success": True,
        "data": {
            "workflow_id": workflow_id,
            "transition_count": len(result),
            "transitions": result,
        },
    }


# ── Durable Agent Run lifecycle endpoints (Phase 1) ─────────────────────────
#
# Server-authoritative REST surface for the persistent Agent Run lifecycle.
# All operations authenticate via the existing X-API-Key middleware chain and
# reuse the existing RBAC dependencies. Authorization against the run itself
# (owner-or-admin binding) is enforced server-side by the orchestrator.
#
# NOTE: These endpoints do NOT touch the FireAI LangGraph workflow service
# above; they expose the durable Agent Run store exclusively.


async def _to_thread(func, *args, **kwargs):
    if hasattr(asyncio, "to_thread"):
        return await asyncio.to_thread(func, *args, **kwargs)
    import functools

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


def _agent_run_http_error(exc: Exception) -> HTTPException:
    """Map orchestrator domain errors to HTTP status codes."""
    if isinstance(exc, (RunNotFoundError, PendingApprovalNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc)[:300])
    if isinstance(exc, RunPermissionError):
        return HTTPException(status_code=403, detail=str(exc)[:300])
    if isinstance(
        exc, (InvalidRunStateError, StaleApprovalError, ApprovalAlreadyDecidedError)
    ):
        return HTTPException(status_code=409, detail=str(exc)[:300])
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc)[:300])
    # CodeQL: py/stack-trace-exposure — sanitize unexpected errors
    return HTTPException(status_code=500, detail="Internal agent run error (details sanitized)")


def _run_caller_context(request: Request, role: Role) -> tuple[str, bool]:
    """Extract (caller_id, caller_is_admin) from the authenticated request."""
    caller_id = get_current_principal(request) or ""
    return caller_id, role == Role.ADMIN


@router.get(
    "/runs/{run_id}/status",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_READ))],
)
async def get_agent_run_status(run_id: str, request: Request):
    """Get persisted Agent Run status (durable across disconnects/restarts)."""
    role = require_permission(Permission.WORKFLOW_READ)(request)
    caller_id, is_admin = _run_caller_context(request, role)
    try:
        run = await asyncio.to_thread(
            default_agent_run_orchestrator.get_run_status, caller_id, run_id, is_admin
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc
    return {"success": True, "data": run.to_dict()}


@router.post(
    "/runs/{run_id}/resume",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
@limiter.limit("30/minute")
async def resume_agent_run(run_id: str, request: Request):
    """Resume a paused/interrupted Agent Run from its persisted position."""
    role = require_permission(Permission.WORKFLOW_MANAGE)(request)
    caller_id, is_admin = _run_caller_context(request, role)
    try:
        run = await asyncio.to_thread(
            default_agent_run_orchestrator.resume_run, caller_id, run_id, is_admin
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc
    return {"success": True, "data": run.to_dict()}


@router.post(
    "/runs/{run_id}/cancel",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
@limiter.limit("30/minute")
async def cancel_agent_run(run_id: str, request: Request):
    """Cancel an Agent Run server-side (terminal; pending approvals invalidated)."""
    role = require_permission(Permission.WORKFLOW_MANAGE)(request)
    caller_id, is_admin = _run_caller_context(request, role)
    try:
        run = await asyncio.to_thread(
            default_agent_run_orchestrator.cancel_run, caller_id, run_id, is_admin
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc
    return {"success": True, "data": run.to_dict()}


@router.post(
    "/runs/{run_id}/retry",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
@limiter.limit("30/minute")
async def retry_agent_run(run_id: str, request: Request):
    """Retry a FAILED Agent Run from its failed step (idempotency-safe)."""
    role = require_permission(Permission.WORKFLOW_MANAGE)(request)
    caller_id, is_admin = _run_caller_context(request, role)
    try:
        run = await asyncio.to_thread(
            default_agent_run_orchestrator.retry_run, caller_id, run_id, is_admin
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc
    return {"success": True, "data": run.to_dict()}


class AgentRunApprovalDecisionRequest(BaseModel):
    decision: str  # APPROVED | REJECTED
    reason: str | None = None


@router.post(
    "/runs/{run_id}/approvals/{approval_id}/decide",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
@limiter.limit("30/minute")
async def decide_agent_run_approval(
    run_id: str,
    approval_id: str,
    request: Request,
    body: AgentRunApprovalDecisionRequest,
):
    """Record an immutable approval decision for a pending Agent Run step."""
    decision = body.decision.strip().upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=400, detail="decision must be APPROVED or REJECTED"
        )
    role = require_permission(Permission.WORKFLOW_MANAGE)(request)
    caller_id, is_admin = _run_caller_context(request, role)
    try:
        run = await asyncio.to_thread(
            default_agent_run_orchestrator.decide_approval,
            caller_id,
            approval_id,
            decision,
            reason=(body.reason or "")[:2000],
            caller_is_admin=is_admin,
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc
    if run.run_id != run_id:
        raise HTTPException(
            status_code=409, detail="Approval does not belong to the specified run"
        )
    return {"success": True, "data": run.to_dict()}


def _reconcile_and_validate_execution_context(
    request: Request,
    project_id: str,
    model_id: str | None,
    entity_id: str | None,
    entity_type: str | None,
    expected_revision: int | None,
) -> dict:
    """
    Authoritative reconciliation of execution context (Gate 5 Blockers B, C, F).
    Validates:
    1. Authenticated principal has access to project_id
    2. model_id belongs to project_id (rejects forged/mismatched models)
    3. entity_id exists and belongs to project_id (zero bypasses: elem-*, mock-* forbidden unless in DB)
    4. entity/entity_type is compatible
    5. expected_revision matches canonical persistent OCC revision from project_revisions
    """
    from backend.database import get_db
    from backend.core.state_store import CommandStateStore
    from backend.routers.projects import _verify_project_access

    db = get_db()
    state_store = CommandStateStore(db)

    project = None
    if project_id:
        project = db.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        _verify_project_access(project, request)

        # 2. model_id belongs to project_id
        canonical_model_id = project.get("modelId") or f"dt-{project_id}"
        if model_id and model_id != canonical_model_id:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model_id}' does not belong to project '{project_id}'",
            )

        # 3. entity_id exists and belongs to project_id (strictly enforced, no prefix bypasses)
        if entity_id:
            dev = db.get_device(project_id, entity_id)
            if not dev:
                raise HTTPException(
                    status_code=400,
                    detail=f"Entity '{entity_id}' does not belong to project '{project_id}'",
                )

            # 4. entity/entity_type compatibility
            if entity_type:
                allowed_types = {"device", "element", "detector", "panel", "module", "circuit", "appliance"}
                dev_type = str(dev.get("type", "")).lower()
                dev_cat = str(dev.get("category", "")).lower()
                if entity_type.lower() not in allowed_types and entity_type.lower() != dev_type and entity_type.lower() != dev_cat:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Entity type '{entity_type}' is incompatible with entity '{entity_id}'",
                    )

        # 5. expected_revision matches canonical persistent revision
        canonical_rev = state_store.get_project_revision(project_id)
        if expected_revision is not None and expected_revision != canonical_rev:
            raise HTTPException(
                status_code=409,
                detail=f"OCC revision conflict: expected revision {expected_revision} but project '{project_id}' is at canonical revision {canonical_rev}",
            )
    elif entity_id:
        raise HTTPException(
            status_code=400,
            detail="project_id is required when entity_id is specified",
        )

    return {
        "project": project,
        "canonical_model_id": project.get("modelId") if project else "",
        "canonical_revision": state_store.get_project_revision(project_id) if project_id else 1,
    }


class PlanWorkflowRequest(BaseModel):
    prompt: str = ""
    project_id: str = ""
    model_id: str | None = None
    entity_id: str | None = None
    entity_type: str | None = None
    expected_revision: int | None = None
    composite_spec: dict | None = None
    approval_mode: str = "AUTO"
    governance_policy: dict | None = None


@router.post(
    "/runs/plan",
    dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))],
)
@limiter.limit("30/minute")
async def plan_autonomous_workflow(request: Request, body: PlanWorkflowRequest):
    """Synthesize a natural language or structured intent into a validated, policy-evaluated autonomous plan."""
    from backend.core.command_bus import AuthenticatedPrincipal
    from backend.core.workflow_planner import default_workflow_planner

    role = require_permission(Permission.CALCULATION_EXECUTE)(request)
    caller_id, _ = _run_caller_context(request, role)
    principal = AuthenticatedPrincipal(
        user_id=caller_id or "anonymous",
        email=f"{caller_id or 'anonymous'}@bazspark.com",
        role=role.value,
        scopes=["*"],
    )

    # Authoritative context reconciliation (Blockers B, C, F)
    _reconcile_and_validate_execution_context(
        request=request,
        project_id=body.project_id,
        model_id=body.model_id,
        entity_id=body.entity_id,
        entity_type=body.entity_type,
        expected_revision=body.expected_revision,
    )

    spec = dict(body.composite_spec or {})
    if body.model_id:
        spec["model_id"] = body.model_id
    if body.entity_id:
        spec["entity_id"] = body.entity_id
    if body.entity_type:
        spec["entity_type"] = body.entity_type

    try:
        plan = await _to_thread(
            default_workflow_planner.plan_workflow,
            prompt=body.prompt or "Autonomous engineering workflow",
            principal=principal,
            project_id=body.project_id,
            expected_revision=body.expected_revision,
            composite_spec=spec,
            approval_mode=body.approval_mode,
            governance_policy=body.governance_policy,
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc

    return {"success": True, "data": plan.to_dict()}


class StartPlannedWorkflowRequest(BaseModel):
    prompt: str = ""
    project_id: str = ""
    model_id: str | None = None
    entity_id: str | None = None
    entity_type: str | None = None
    expected_revision: int | None = None
    composite_spec: dict | None = None
    approval_mode: str = "AUTO"
    conversation_id: str = ""
    governance_policy: dict | None = None


@router.post(
    "/runs/start-plan",
    dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))],
)
@limiter.limit("30/minute")
async def start_planned_autonomous_workflow(
    request: Request, body: StartPlannedWorkflowRequest
):
    """Plan an autonomous workflow and immediately dispatch it to the durable AgentRunOrchestrator."""
    from backend.core.command_bus import AuthenticatedPrincipal
    from backend.core.workflow_planner import default_workflow_planner

    role = require_permission(Permission.CALCULATION_EXECUTE)(request)
    caller_id, _ = _run_caller_context(request, role)
    principal = AuthenticatedPrincipal(
        user_id=caller_id or "anonymous",
        email=f"{caller_id or 'anonymous'}@bazspark.com",
        role=role.value,
        scopes=["*"],
    )

    # Authoritative context reconciliation (Blockers B, C, F)
    _reconcile_and_validate_execution_context(
        request=request,
        project_id=body.project_id,
        model_id=body.model_id,
        entity_id=body.entity_id,
        entity_type=body.entity_type,
        expected_revision=body.expected_revision,
    )

    spec = dict(body.composite_spec or {})
    if body.model_id:
        spec["model_id"] = body.model_id
    if body.entity_id:
        spec["entity_id"] = body.entity_id
    if body.entity_type:
        spec["entity_type"] = body.entity_type

    try:
        plan = await _to_thread(
            default_workflow_planner.plan_workflow,
            prompt=body.prompt or "Autonomous engineering workflow",
            principal=principal,
            project_id=body.project_id,
            expected_revision=body.expected_revision,
            composite_spec=spec,
            approval_mode=body.approval_mode,
            governance_policy=body.governance_policy,
        )
        run = await _to_thread(
            default_workflow_planner.execute_plan,
            plan,
            principal=principal,
            approval_mode=body.approval_mode,
            conversation_id=body.conversation_id,
            governance_policy=body.governance_policy,
        )
    except Exception as exc:
        raise _agent_run_http_error(exc) from exc

    return {"success": True, "data": run.to_dict(), "plan": plan.to_dict()}

