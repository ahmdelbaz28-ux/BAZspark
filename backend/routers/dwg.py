"""
backend/routers/dwg.py — DWG/DXF file parsing endpoint.

Provides a single endpoint for uploading a DWG or DXF file and
receiving structured parsing results (room count, errors, etc.).

SAFETY: Input path validation is delegated to parsers._path_security
via DWGParser.parse(). The temp file is cleaned up after every request.

STRESS-TEST FIX #5 (DWG DoS):
  - Added explicit auth dependency (require PROJECT_CREATE permission).
  - Added rate limit (10/minute per IP — parsing is CPU-intensive).
  - Streamed chunks DIRECTLY to disk via aiofiles (no in-memory accumulation).
  - Tightened size limit to 50 MB (was 100 MB).
"""

import logging
import os
import tempfile
from typing import Any

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from backend.auth import require_permission
from backend.core.openapi_contracts import StandardizedAPIRoute
from backend.rbac import Permission

try:
    from backend.limiter import limiter

    _HAS_LIMITER = True
except ImportError:
    _HAS_LIMITER = False
    limiter = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parse-dwg", tags=["dwg"], route_class=StandardizedAPIRoute)

_DWG_ALLOWED_EXTENSIONS = frozenset({".dwg", ".dxf"})
_MAX_DWG_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
_CHUNK_SIZE = 1024 * 1024  # 1 MB per read

# Auth dependency for the parse endpoint
_AUTH = [Depends(require_permission(Permission.PROJECT_CREATE))]


def _validate_dwg_extension(filename: str | None) -> str:
    """Validate file extension for DWG/DXF uploads."""
    if not filename:
        raise HTTPException(status_code=400, detail="No file provided")

    safe_filename = os.path.basename(filename)
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in _DWG_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(_DWG_ALLOWED_EXTENSIONS))}",
        )
    return ext


async def _stream_upload_to_disk(file: UploadFile, ext: str) -> str:
    """Stream incoming upload directly to a temporary file on disk using async I/O."""
    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="fireai_dwg_upload_")
    os.close(fd)  # Close raw descriptor; write via async aiofiles

    file_size = 0
    empty = True

    try:
        async with aiofiles.open(temp_path, "wb") as out_f:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                empty = False
                file_size += len(chunk)
                if file_size > _MAX_DWG_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {_MAX_DWG_SIZE_BYTES // (1024 * 1024)} MB). "
                        "Upload a smaller file or split the drawing.",
                    )
                await out_f.write(chunk)
            await out_f.flush()

        if empty:
            raise HTTPException(
                status_code=422,
                detail={"success": False, "error": "Empty file uploaded"},
            )
        return temp_path
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        raise


def _format_parse_response(result: Any, filename: str | None) -> dict[str, Any] | JSONResponse:
    """Format DWGParser result into standardized HTTP response."""
    if not result.success:
        detail = {
            "success": False,
            "source": filename,
            "errors": result.errors,
            "warnings": result.warnings,
            "room_count": result.room_count,
            "conversion_time_s": result.conversion_time_s,
        }
        if result.errors and any("SECURITY" in e for e in result.errors):
            status_code = 400
        elif result.errors and any("not found" in e for e in result.errors):
            status_code = 404
        else:
            status_code = 422
        return JSONResponse(status_code=status_code, content=detail)

    return {
        "success": True,
        "source": filename,
        "room_count": result.room_count,
        "conversion_time_s": result.conversion_time_s,
        "errors": result.errors,
        "warnings": result.warnings,
    }


async def _parse_dwg_impl(request: Request, file: UploadFile):
    """
    Upload a DWG or DXF file for parsing.

    Returns structured parsing results including room count, conversion
    time, and any errors/warnings. On validation failure, returns a
    400-level error with details.
    """
    ext = _validate_dwg_extension(file.filename)
    temp_path = ""
    try:
        temp_path = await _stream_upload_to_disk(file, ext)

        try:
            from parsers.dwg_parser import DWGParser
        except ImportError as import_err:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": f"DWG parser module unavailable: {import_err}",
                    "hint": "Ensure all parser dependencies are installed (ezdxf, pymupdf).",
                },
            )

        parser = DWGParser()
        result = parser.parse(temp_path)
        return _format_parse_response(result, file.filename)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("DWG parse request failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Internal error: {type(exc).__name__}",
            },
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as exc:
                logger.debug("Temp file cleanup failed: %s", exc)


if _HAS_LIMITER:

    @limiter.limit("10/minute")
    async def _rate_limited_parse_dwg(request: Request, file: UploadFile = File(...)):
        """Rate-limited wrapper for DWG parse endpoint."""
        return await _parse_dwg_impl(request, file)

    _rate_limited_parse_dwg.__annotations__["file"] = UploadFile

    router.add_api_route(
        "",
        _rate_limited_parse_dwg,
        methods=["POST"],
        dependencies=_AUTH,
        name="parse_dwg",
    )
else:
    router.add_api_route(
        "",
        _parse_dwg_impl,
        methods=["POST"],
        dependencies=_AUTH,
        name="parse_dwg",
    )

# Public alias for backward compatibility (tests/test_dwg_router.py)
parse_dwg = _parse_dwg_impl
