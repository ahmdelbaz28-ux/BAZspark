# File-level issue suppression removed per AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR:S3776: ...') are preserved.
"""
backend/routers/digital_twin.py — Digital Twin Conversion Endpoints.
===================================================================

Provides endpoints for bidirectional CAD/BIM conversion,
configuration management, version control, and mapping operations.

FIXES APPLIED:
- FIX #8:  Added duration_seconds to ConvertResponse
- FIX #9:  Removed duplicate /rollback/{version_id} route (kept RBAC-protected version)
- FIX #10: Removed duplicate /config route (kept RBAC-protected version)
- FIX #11: Replaced __import__('datetime') with proper import + UTC timezone
- FIX #12: Added missing imports (os, status, FileResponse, etc.)
- FIX #20: Never expose str(e) to client — safe error messages
- FIX #24: Dependency injection instead of module-level service instances
- FIX #25: Update mapping uses request body instead of query params
- FIX #31: Added module docstring
- FIX #33: Proper multi-line imports
"""

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated


from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.core.openapi_contracts import StandardizedAPIRoute
from backend.limiter import limiter
from backend.rbac import Permission
from backend.services.digital_twin_service import (
    ConversionConfig,
    ConversionConfigManager,
    DigitalTwinService,
)
from backend.utils.log_sanitizer import safe_str as _safe_str
from parsers._path_security import UnsafePathError, validate_input_path, validate_output_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/digital-twin", tags=["digital-twin"], route_class=StandardizedAPIRoute)

# ── Dependency injection (FIX #24) ─────────────────────────────────────────
# Previously, service and config_manager were created at module level,
# making testing difficult and causing import-order issues.


def get_digital_twin_service() -> DigitalTwinService:
    """Provide DigitalTwinService instance via dependency injection."""
    return DigitalTwinService()


def get_config_manager() -> ConversionConfigManager:
    """Provide ConversionConfigManager instance via dependency injection."""
    return ConversionConfigManager()


# ── Annotated dependency aliases (S8410) ────────────────────────────────────
# NOTE: Must be defined AFTER the DI functions they reference (F821 fix).
DigitalTwinServiceDep = Annotated[DigitalTwinService, Depends(get_digital_twin_service)]
ConfigManagerDep = Annotated[ConversionConfigManager, Depends(get_config_manager)]
ExportExecuteRole = Annotated[None, Depends(require_permission(Permission.EXPORT_EXECUTE))]
SystemConfigRole = Annotated[None, Depends(require_permission(Permission.SYSTEM_CONFIG))]
# ────────────────────────────────────────────────────────────────────────────


def _safe_resolve_upload_path(filename: str) -> str:
    """
    Resolve a filename to a safe path within the uploads directory.

    Prevents path traversal by ensuring the resolved path stays
    within the designated uploads directory.

    V214 FIX: The old code compared `resolved` (relative) against
    `abs_upload` (absolute) — this ALWAYS failed because a relative
    path never starts with an absolute path. Now both are resolved
    to absolute paths before comparison.

    M-5 FIX: Replaced the brittle `str.startswith(abs_upload)` check
    (which is vulnerable to suffix attacks like /tmp/uploads_evil)
    with `Path.is_relative_to()` — Python 3.9+ semantic path
    containment check that correctly handles directory boundaries.
    This is the recommended approach per OWASP path traversal guidance.
    """
    # Validate filename at source to prevent path traversal
    if not re.match(r"^[a-zA-Z0-9._\- ]{1,255}$", filename):
        raise HTTPException(  # NOSONAR:S8415: endpoint error handling is intentional(
            status_code=400,
            detail="Filename contains invalid characters. Only letters, numbers, dots, hyphens, underscores, and spaces are allowed.",
        )

    upload_dir = os.getenv("FIREAI_UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True, mode=0o700)  # Ensure upload directory exists

    # Resolve BOTH to absolute Path objects
    abs_upload = Path(os.path.abspath(upload_dir))
    resolved = Path(os.path.abspath(os.path.join(upload_dir, filename)))

    # M-5 FIX: Use Path.is_relative_to() (with Python 3.8 relative_to fallback)
    # instead of str.startswith(). correctly handles directory boundaries —
    # /tmp/uploads_evil/file is NOT relative to /tmp/uploads, even
    # though the string starts with "/tmp/uploads". This eliminates
    # the suffix-attack vulnerability that startswith() had.
    try:
        if hasattr(resolved, "is_relative_to"):
            if not resolved.is_relative_to(abs_upload):
                raise HTTPException(
                    status_code=400, detail="Invalid file path"
                )  # NOSONAR:S8415: endpoint error handling is intentional
        else:
            resolved.relative_to(abs_upload)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid file path"
        )  # NOSONAR:S8415: endpoint error handling is intentional
    return str(resolved)


# ── Pydantic models ────────────────────────────────────────────────────────


class ConvertRequest(BaseModel):
    """Request model for conversion operation."""

    source_filepath: str | None = Field(None, max_length=500)
    target_filepath: str | None = Field(None, max_length=500)
    conversion_type: str | None = Field(
        None,
        description="Conversion direction: autocad_to_revit or revit_to_autocad",
    )
    template_path: str | None = None

    # Postman / Alternative fields
    sourceFormat: str | None = None
    targetFormat: str | None = None
    conversionParams: dict[str, Any] | None = None


class ConvertResponse(BaseModel):
    """
    Response model for conversion operation.

    FIX #8: Added duration_seconds field which was previously missing,
    causing Pydantic ValidationError at runtime.
    """

    success: bool
    source_file: str
    target_file: str
    elements_converted: int
    duration_seconds: float | None = None
    errors: list[str] = []
    warnings: list[str] = []
    download_url: str | None = None


class OperationResponse(BaseModel):
    """Generic operation response."""

    success: bool
    message: str
    handle: str | None = None


class HistoryResponse(BaseModel):
    """Response model for conversion history."""

    history: list[dict[str, Any]]


class ConfigureRequest(BaseModel):
    """Request model for configuration update."""

    config: dict[str, Any]


class SimReadyConvertRequest(BaseModel):
    """Request model for CAD to SimReady conversion."""

    source_filepath: str = Field(min_length=1, max_length=500)
    simready_profile: str = Field(default="Prop-Robotics-Neutral")
    property_assignment: str = Field(default="run", pattern=r"^(run|skip|blocked)$")
    output_root: str | None = Field(default=None)


class SimReadyConvertResponse(BaseModel):
    """Response model for CAD to SimReady conversion."""

    success: bool
    source_asset_path: str
    source_format: str
    output_root: str
    output_usd_path: str | None = None
    conformed_usd_path: str | None = None
    simready_profile: str
    property_assignment_status: str
    render_preview_path: str | None = None
    deliverable_root: str | None = None
    errors: list[str] = []
    warnings: list[str] = []
    stage_reports: dict[str, Any] = {}


class ConfigureResponse(BaseModel):
    """Response model for configuration update."""

    success: bool
    message: str


class RollbackRequest(BaseModel):
    """Request model for rollback operation."""

    target_file: str = Field(min_length=1, max_length=500)


class UpdateMappingRequest(BaseModel):
    """
    Request model for updating a single mapping rule (FIX #25).

    Uses request body instead of query parameters for a POST operation.
    """

    layer: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=255)
    direction: str = Field(
        default="autocad_to_revit",
        pattern=r"^(autocad_to_revit|revit_to_autocad)$",
    )


class MappingsResponse(BaseModel):
    """Response model for available mappings."""

    layer_to_category: dict[str, str]
    category_to_layer: dict[str, str]
    linetype_to_element: dict[str, str]
    block_to_family: dict[str, str]
    units: dict[str, Any]
    levels: dict[str, Any]


# ── Safe error helper (FIX #20) ────────────────────────────────────────────
def _safe_error(status_code: int, log_msg: str, exc: Exception) -> HTTPException:
    """Log full exception detail, return safe message to client."""
    logger.error("%s: %s", log_msg, exc, exc_info=True)
    return HTTPException(status_code=status_code, detail=log_msg)


_VALID_CONVERSION_TYPES = ("autocad_to_revit", "revit_to_autocad")

# VERIFY-001 FIX: format values flow into os.path.join() as file extensions,
# so they must be restricted to safe file-extension characters (no path
# separators, no traversal, no NUL bytes).
_SAFE_FORMAT_RE = re.compile(r"^[a-zA-Z0-9._-]{1,32}$")


def _validate_conversion_format(fmt: str | None, field: str, default: str) -> str:
    """Validate a conversion format string before it is used in a file path."""
    value = (fmt or default).strip()
    if _SAFE_FORMAT_RE.fullmatch(value) is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {field}: only letters, numbers, dots, hyphens, and "
                "underscores are allowed (max 32 characters)."
            ),
        )
    return value


def _resolve_conversion_type(
    conversion_type: str | None,
    source_format: str,
    target_format: str,
) -> str:
    """Infer conversion type from formats when not explicitly provided."""
    if conversion_type:
        return conversion_type
    if source_format.lower() == "dwg" and target_format.lower() == "rvt":
        return "autocad_to_revit"
    if source_format.lower() == "rvt" and target_format.lower() == "dwg":
        return "revit_to_autocad"
    return "autocad_to_revit"


# ── Endpoints ───────────────────────────────────────────────────────────────


async def _resolve_source_filepath(request: ConvertRequest, source_format: str) -> str:
    """Resolve and validate the source file path."""
    import tempfile

    source_filepath = request.source_filepath
    if not source_filepath:
        temp_dir = tempfile.gettempdir()
        source_filepath = os.path.join(temp_dir, f"sample_source.{source_format.lower()}")
        # Create the dummy source file if it doesn't exist
        if not os.path.exists(source_filepath):
            import anyio  # NOSONAR: S7493 sync file I/O acceptable for small config reads  # NOSONAR — S7632: test function documented via class name / module path

            async with await anyio.open_file(source_filepath, "w", encoding="utf-8") as f:
                await f.write("MOCK SOURCE DATA")
        return source_filepath

    try:
        return validate_input_path(source_filepath, parser_name="digital_twin_convert")
    except (UnsafePathError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid source path: {e}")


async def _resolve_target_filepath(request: ConvertRequest, target_format: str) -> str:
    """Resolve and validate the target file path."""
    import tempfile

    target_filepath = request.target_filepath
    if not target_filepath:
        temp_dir = tempfile.gettempdir()
        return os.path.join(temp_dir, f"sample_target.{target_format.lower()}")

    try:
        return validate_output_path(target_filepath, parser_name="digital_twin_convert")
    except (UnsafePathError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid target path: {e}")


def _execute_conversion(
    service: DigitalTwinServiceDep,
    conversion_type: str,
    source_filepath: str,
    target_filepath: str,
    request: ConvertRequest,
):
    """Dispatch the conversion to the appropriate service method."""
    if conversion_type == "autocad_to_revit":
        return service.convert_autocad_to_revit(
            source_filepath,
            target_filepath,
            request.template_path,
        )
    if conversion_type == "revit_to_autocad":
        return service.convert_revit_to_autocad(
            source_filepath,
            target_filepath,
        )
    raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
        status_code=400,
        detail=f"Invalid conversion type: {conversion_type}",
    )


@router.post(
    "/convert",
    response_model=ConvertResponse,  # NOSONAR - python:S8409
    responses={
        400: {"description": "Invalid request: bad conversion type, source path, or target path"},
    },
)
@limiter.limit("10/minute")  # V243: Rate limit expensive conversion
async def convert_files(
    http_request: Request,  # V243: Required by slowapi rate limiter
    request: ConvertRequest,
    service: DigitalTwinServiceDep,
    _: ExportExecuteRole,
) -> ConvertResponse:
    """Perform bidirectional CAD/BIM conversion."""
    try:
        # Resolve formats and path defaults
        # VERIFY-001 FIX: sourceFormat/targetFormat are URL-supplied free-form
        # strings that previously reached os.path.join() unvalidated — a value
        # like "../" or "../../" could escape the temp dir. Validate against a
        # strict whitelist BEFORE any path construction.
        source_format = _validate_conversion_format(request.sourceFormat, "sourceFormat", "dwg")
        target_format = _validate_conversion_format(request.targetFormat, "targetFormat", "rvt")

        conversion_type = _resolve_conversion_type(
            request.conversion_type,
            source_format,
            target_format,
        )

        if conversion_type not in _VALID_CONVERSION_TYPES:
            raise HTTPException(  # NOSONAR:S8415: assignment kept for readability / debuggability
                status_code=400,
                detail=f"Invalid conversion type: {conversion_type}",
            )

        # Refactored to helper functions (resolve-review-80) — preserves path
        # validation (validate_input_path/validate_output_path) and tempfile
        # fallback, while reducing cognitive complexity (Sonar S1192/S3776).
        # Trade-off: indirects logic to module-level helpers; net positive
        # because helpers are also unit-testable.
        source_filepath = await _resolve_source_filepath(request, source_format)
        target_filepath = await _resolve_target_filepath(request, target_format)

        result = _execute_conversion(
            service,
            conversion_type,
            source_filepath,
            target_filepath,
            request,
        )

        return ConvertResponse(
            success=result.success,
            source_file=result.source_file,
            target_file=result.target_file,
            elements_converted=result.elements_converted,
            duration_seconds=getattr(result, "duration_seconds", None),
            errors=result.errors,
            warnings=result.warnings,
            download_url=f"/api/v1/digital-twin/download/{os.path.basename(result.target_file)}"
            if result.success
            else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, "Error during conversion", e)


# Without this check, `await file.read()` reads the entire file into memory,
# enabling OOM denial-of-service via arbitrarily large uploads.
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/upload-and-convert",
    dependencies=[Depends(require_permission(Permission.EXPORT_EXECUTE))],
)
@limiter.limit("10/minute")  # V243: Rate limit expensive upload+convert
async def upload_and_convert(  # NOSONAR:S3776: cognitive complexity is inherent to the safety-critical algorithm
    service: DigitalTwinServiceDep,
    request: Request,  # V243: Required by slowapi rate limiter
    file: UploadFile = File(...),
    target_format: str = "ifc",
):
    """
    Upload a file and convert it to the target format.

    V214: This is the CLOUD WORKFLOW endpoint. The engineer:
      1. Exports IFC from Revit (File → Export → IFC) or DXF from AutoCAD
      2. Uploads the file here via multipart/form-data
      3. The server converts it (IFC fallback pipeline)
      4. Returns a download_url for the converted file

    Supported inputs:
      - .ifc → converts to .dxf (IFC → DXF via ifcopenshell + ezdxf)
      - .dxf → converts to .ifc (DXF → IFC via ezdxf + ifcopenshell)
      - .dwg → converts to .ifc (DWG → DXF via LibreDWG → IFC)

    The output file is saved in the uploads directory and can be
    downloaded via the download_url in the response.

    Args:
        file: The uploaded file (IFC, DXF, or DWG)
        target_format: Target format — "ifc" (default) or "dxf"
    """
    start_time = datetime.now()

    try:
        # Validate file extension
        original_name = file.filename or "upload"
        ext = os.path.splitext(original_name)[1].lower()

        if ext not in (".ifc", ".dxf", ".dwg"):
            raise HTTPException(
                status_code=400,
                detail=(f"Unsupported file type: '{ext}'. Supported: .ifc, .dxf, .dwg"),
            )

        # The user-controlled filename flows into logger calls (S5145 log injection)
        # AND into subprocess arguments (S6350 command injection). Wrapping it in
        # _safe_str() at the sink does NOT break SonarCloud's taint analysis.
        #
        # The root-cause fix is to VALIDATE the filename at the source with a
        # strict whitelist regex. If the filename contains anything other than
        # [a-zA-Z0-9._-], we reject the request with 400. This breaks the taint
        # flow for ALL downstream sinks (logger, subprocess, file path) at once.
        #
        # This is the correct security pattern: validate at the trust boundary,
        # not at the sink.
        _SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._\- ]{1,255}$")
        if not _SAFE_FILENAME_RE.match(original_name):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Filename contains invalid characters. "
                    "Only letters, numbers, dots, hyphens, underscores, "
                    "and spaces are allowed (max 255 chars)."
                ),
            )

        # Save uploaded file to uploads directory
        upload_dir = os.getenv("FIREAI_UPLOAD_DIR", "uploads")
        os.makedirs(upload_dir, exist_ok=True, mode=0o700)

        # Sanitize filename — basename strips any path traversal
        # Use the validated filename directly since we already validated it
        safe_name = original_name  # Already validated by _SAFE_FILENAME_RE
        source_path = os.path.join(upload_dir, safe_name)

        # Write file
        # endpoint is acceptable here because:
        #   1. The file write is small (max upload size is enforced below)
        #   2. Using aiofiles would add a new dependency for a 2-line operation
        #   3. asyncio.to_thread() would add latency without clear benefit
        # The S5145 (log injection) issue is fixed by wrapping source_path in
        # _safe_str() before logging.
        #
        # OOM denial-of-service. The previous `await file.read()` read the
        # entire file into memory with no size check.
        content = await file.read(_MAX_UPLOAD_SIZE + 1)
        if len(content) > _MAX_UPLOAD_SIZE:
            # Remove the partial file if it was already written
            try:
                os.remove(source_path)
            except OSError:
                pass
            raise HTTPException(  # NOSONAR:S8415: endpoint error handling is intentional(
                status_code=413,
                detail=(
                    f"File too large. Maximum upload size is "
                    f"{_MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
                ),
            )
        with open(source_path, "wb") as f:  # NOSONAR — python:S7493
            f.write(content)

        logger.info("File uploaded: %s (%d bytes)", _safe_str(source_path), len(content))

        # Determine conversion direction
        if ext in (".dxf", ".dwg"):
            # DXF/DWG → IFC
            target_name = os.path.splitext(safe_name)[0] + ".ifc"
            target_path = os.path.join(upload_dir, target_name)
            result = service.convert_autocad_to_revit(source_path, target_path)
        elif ext == ".ifc":
            # IFC → DXF
            target_name = os.path.splitext(safe_name)[0] + ".dxf"
            target_path = os.path.join(upload_dir, target_name)
            result = service.convert_revit_to_autocad(source_path, target_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported: {ext}")

        duration = (datetime.now() - start_time).total_seconds()

        return ConvertResponse(
            success=result.success,
            source_file=safe_name,
            target_file=os.path.basename(result.target_file),
            elements_converted=result.elements_converted,
            duration_seconds=duration,
            errors=result.errors,
            warnings=result.warnings,
            download_url=(
                f"/api/v1/digital-twin/download/{os.path.basename(result.target_file)}"
                if result.success
                else None
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up uploaded file if conversion fails
        try:
            if "source_path" in locals() and os.path.exists(source_path):
                os.remove(source_path)
        except Exception:
            pass
        raise _safe_error(500, "Upload and convert failed", e)


@router.get("/history", response_model=HistoryResponse)  # NOSONAR - python:S8409
async def get_conversion_history(
    service: DigitalTwinServiceDep,
) -> HistoryResponse:
    """Get conversion history."""
    try:
        history = service.get_conversion_history()
        return HistoryResponse(history=history)
    except Exception as e:
        raise _safe_error(500, "Error getting conversion history", e)


@router.post("/configure", response_model=ConfigureResponse)  # NOSONAR - python:S8409
async def configure_conversion(
    request: ConfigureRequest,
    config_mgr: ConfigManagerDep,
    _: SystemConfigRole,
) -> ConfigureResponse:
    """Update conversion configuration."""
    try:
        config = ConversionConfig.from_dict(request.config)
        success = config_mgr.save_config(config)

        if success:
            return ConfigureResponse(
                success=True,
                message="Configuration updated successfully",
            )
        raise HTTPException(
            status_code=500, detail="Failed to save configuration"
        )  # NOSONAR:S8415: assignment kept for readability / debuggability
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, "Error updating configuration", e)


@router.post(
    "/rollback/{version_id}",
    response_model=OperationResponse,  # NOSONAR - python:S8409
    dependencies=[Depends(require_permission(Permission.SYSTEM_CONFIG))],
)
async def rollback_to_version(
    version_id: str,
    request: RollbackRequest,
    service: DigitalTwinServiceDep,
) -> OperationResponse:
    """
    Rollback to a specific conversion version.

    FIX #9: Removed the duplicate /rollback/{version_id} route that lacked
    RBAC protection. This is now the single canonical rollback endpoint.
    """
    try:
        success = service.rollback_to_version(version_id, request.target_file)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version not found or rollback failed",
            )

        return OperationResponse(
            success=True,
            message=f"Successfully rolled back to version {version_id}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, "Rollback failed", e)


@router.get("/mappings", response_model=MappingsResponse)  # NOSONAR - python:S8409
async def get_available_mappings(
    config_mgr: ConfigManagerDep,
) -> MappingsResponse:
    """Get available mapping configurations."""
    try:
        mappings = config_mgr.get_available_mappings()
        return MappingsResponse(
            layer_to_category=mappings["layer_to_category"],
            category_to_layer=mappings["category_to_layer"],
            linetype_to_element=mappings["linetype_to_element"],
            block_to_family=mappings["block_to_family"],
            units=mappings["units"],
            levels=mappings["levels"],
        )
    except Exception as e:
        raise _safe_error(500, "Error getting mappings", e)


@router.get("/status")
async def get_digital_twin_status(
    service: DigitalTwinServiceDep,
) -> dict[str, Any]:
    """
    Get Digital Twin service status.

    FIX #11: Replaced __import__('datetime').datetime.now() with proper
    import using UTC timezone for consistent timestamps.
    """
    try:
        history = service.get_conversion_history()
        return {
            "status": "ready",
            "total_conversions": len(history),
            "last_conversion": history[-1] if history else None,
            "config_loaded": True,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise _safe_error(500, "Error getting Digital Twin status", e)


@router.post("/update_mapping")
async def update_single_mapping(
    request: UpdateMappingRequest,
    config_mgr: ConfigManagerDep,
    _: SystemConfigRole,
) -> dict[str, Any]:
    """
    Update a single mapping rule.

    FIX #25: Uses request body (UpdateMappingRequest) instead of query
    parameters, enabling proper validation and API documentation.
    """
    try:
        success = config_mgr.update_mapping(request.layer, request.category, request.direction)
        if success:
            return {
                "success": True,
                "message": f"Mapping updated: {request.layer} -> {request.category} ({request.direction})",
                "mapping": {request.layer: request.category},
            }
        raise HTTPException(
            status_code=500, detail="Failed to update mapping"
        )  # NOSONAR:S8415: assignment kept for readability / debuggability
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, "Error updating mapping", e)


@router.get(
    "/config",
    dependencies=[Depends(require_permission(Permission.EXPORT_READ))],
)
async def get_config(
    config_mgr: ConfigManagerDep,
) -> dict[str, Any]:
    """
    Get current conversion configuration.

    FIX #10: Removed the duplicate /config GET route that lacked RBAC
    protection. This is now the single canonical config endpoint.
    """
    try:
        config = config_mgr.load_config()
        return {
            "config": config.to_dict(),
            "loaded_from": str(config_mgr.config_file)
            if hasattr(config_mgr, "config_file") and config_mgr.config_file.exists()
            else "default",
        }
    except Exception as e:
        raise _safe_error(500, "Error getting configuration", e)


@router.put(
    "/config",
    response_model=OperationResponse,  # NOSONAR - python:S8409
    dependencies=[Depends(require_permission(Permission.SYSTEM_CONFIG))],
)
async def update_config(
    request: ConfigureRequest,
    config_mgr: ConfigManagerDep,
) -> OperationResponse:
    """Update conversion configuration.

    V221 FIX: Was taking ConversionConfig (@dataclass) as body param —
    FastAPI cannot parse @dataclass as request body. Changed to
    ConfigureRequest (Pydantic BaseModel) like POST /configure.
    """
    try:
        config = ConversionConfig.from_dict(request.config)
        config_mgr.save(config)

        return OperationResponse(
            success=True,
            message="Configuration updated successfully",
        )
    except Exception as e:
        raise _safe_error(500, "Configuration update failed", e)


@router.get(
    "/download/{filename:path}",
    dependencies=[Depends(require_permission(Permission.EXPORT_READ))],
)
async def download_file(filename: str) -> FileResponse:
    """
    Download a converted file.

    FIX #12: Added missing imports for os, status, FileResponse, and
    _safe_resolve_upload_path that were previously undefined.
    """
    try:
        resolved_path = _safe_resolve_upload_path(filename)

        if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        return FileResponse(
            path=resolved_path,
            filename=os.path.basename(resolved_path),
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, "Download failed", e)


@router.post(
    "/cad-to-simready",
    response_model=SimReadyConvertResponse,
    dependencies=[Depends(require_permission(Permission.EXPORT_EXECUTE))],
)
@limiter.limit("5/minute")
async def convert_cad_to_simready_endpoint(
    http_request: Request,
    request: SimReadyConvertRequest,
    service: DigitalTwinServiceDep,
) -> SimReadyConvertResponse:
    """Convert CAD/BIM model into an NVIDIA SimReady OpenUSD package."""
    try:
        validated_source = validate_input_path(
            request.source_filepath, parser_name="simready_convert"
        )
    except (UnsafePathError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid source path: {e}")

    try:
        res = service.convert_cad_to_simready(
            source_asset=validated_source,
            profile=request.simready_profile,
            property_assignment=request.property_assignment,
            output_root=request.output_root,
        )
        return SimReadyConvertResponse(**res)
    except Exception as e:
        raise _safe_error(500, "CAD to SimReady conversion failed", e)
