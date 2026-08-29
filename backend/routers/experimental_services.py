"""
backend/routers/experimental_services.py — V270 FIX (audit "5 orphan services").

The audit flagged OCR, Scan-to-BIM, and Speckle services as orphans:
they existed in backend/services/ but had no router exposure and no
frontend caller. (Uptime and Region services were also flagged but the
audit was mistaken — both are already wired through monitor.py and
environment.py respectively. That's documented in the worklog.)

This router exposes the three genuinely-orphan services as experimental
endpoints under /api/v1/experimental/*. They are:

  • POST /api/v1/experimental/ocr/process         — OCR a PDF/image
  • POST /api/v1/experimental/scan-to-bim/process  — OCR → BIM room extraction
  • POST /api/v1/experimental/speckle/push         — Push elements to a Speckle stream
  • POST /api/v1/experimental/speckle/receive      — Receive elements from a Speckle stream
  • GET  /api/v1/experimental/features             — List all experimental services + status

DESIGN NOTES
------------
• All endpoints require SYSTEM_CONFIG permission (admin role). These are
  experimental services — restricting to admin prevents accidental use
  by engineers in production.

• File uploads use UploadFile (PDF/PNG/JPG). Files are written to a
  temporary path, processed, then deleted. No persistent storage.

• Responses include the service name, status, and full payload. On error,
  the response returns a generic 4xx/5xx message (e.g. "OCR processing
  failed. Check server logs for details.") and the full exception is
  logged server-side via logger.exception(). This is the V271 fix for
  CodeQL py/stack-trace-exposure — previously {exc} was interpolated
  into the detail, which could leak internal paths, DB URLs, or
  credential fragments from the underlying library.

• The /features endpoint lets the frontend list all experimental
  services in a single call, with their availability status.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.core.openapi_contracts import StandardizedAPIRoute
from backend.rbac import Permission, Role
from backend.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experimental", tags=["experimental-services"], route_class=StandardizedAPIRoute)

SystemConfigRole = Annotated[Role, Depends(require_permission(Permission.SYSTEM_CONFIG))]


def _write_temp_file(suffix: str, content: bytes) -> str:
    """Write *content* to a named temp file and return its path.

    Called via ``await asyncio.to_thread(_write_temp_file, ...)`` so the
    synchronous file I/O does not block the async event loop (S7493).
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        return tmp.name


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────


from urllib.parse import urlsplit

from pydantic import field_validator

from backend.integrations._ssrf_guard import SSRFError, validate_host_for_user_input


class SpeckleOperationRequest(BaseModel):
    """Body for /speckle/push and /speckle/receive."""

    stream_id: str = Field(..., min_length=1, description="Speckle stream ID")
    server_url: str = Field(
        default="https://speckle.xyz",
        description="Speckle server URL (e.g. https://speckle.xyz)",
    )
    token: str = Field(..., min_length=1, description="Speckle API token")
    elements: list[dict[str, Any]] | None = Field(
        default=None,
        description="Elements to push (push only). Ignored for receive.",
    )

    @field_validator("server_url")
    @classmethod
    def _validate_server_url(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return "https://speckle.xyz"
        parts = urlsplit(v)
        if parts.scheme.lower() != "https":
            raise ValueError("server_url must use https scheme")
        if parts.username or parts.password:
            raise ValueError("server_url must not contain embedded credentials")
        if not parts.hostname:
            raise ValueError("server_url must include a valid hostname")
        try:
            validate_host_for_user_input(parts.hostname)
        except SSRFError as err:
            raise ValueError(f"SSRF validation failed: {err}") from err
        return v.rstrip("/")


class ExperimentalFeatureStatus(BaseModel):
    """Single experimental service status."""

    name: str
    description: str
    endpoint: str
    available: bool
    unavailable_reason: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/features")
async def list_experimental_features(_role: SystemConfigRole) -> dict[str, Any]:
    """
    List all experimental services and their availability.

    Returns a structured list — frontend uses this to render the
    "Experimental Features" admin page.
    """
    features: list[dict[str, Any]] = []

    # OCR
    try:
        from backend.services.ocr_service import OCRService  # noqa: F401

        features.append(
            ExperimentalFeatureStatus(
                name="OCR Service",
                description="Extract text and room names from scanned PDF/image drawings (Tesseract, eng+ara).",
                endpoint="POST /api/v1/experimental/ocr/process",
                available=True,
            ).model_dump()
        )
    except Exception as exc:
        features.append(
            ExperimentalFeatureStatus(
                name="OCR Service",
                description="Extract text and room names from scanned PDF/image drawings.",
                endpoint="POST /api/v1/experimental/ocr/process",
                available=False,
                unavailable_reason=str(exc),
            ).model_dump()
        )

    # Scan-to-BIM
    try:
        from backend.services.scan_to_bim import ScanToBIMService  # noqa: F401

        features.append(
            ExperimentalFeatureStatus(
                name="Scan-to-BIM Service",
                description="Convert scanned drawings to BIM room objects (OCR + room classification + IFC export).",
                endpoint="POST /api/v1/experimental/scan-to-bim/process",
                available=True,
            ).model_dump()
        )
    except Exception as exc:
        features.append(
            ExperimentalFeatureStatus(
                name="Scan-to-BIM Service",
                description="Convert scanned drawings to BIM room objects.",
                endpoint="POST /api/v1/experimental/scan-to-bim/process",
                available=False,
                unavailable_reason=str(exc),
            ).model_dump()
        )

    # Speckle
    try:
        from backend.services.speckle_service import SpeckleService  # noqa: F401

        features.append(
            ExperimentalFeatureStatus(
                name="Speckle Bridge",
                description="Push/receive BIM elements to/from a Speckle stream for interoperability.",
                endpoint="POST /api/v1/experimental/speckle/push",
                available=True,
            ).model_dump()
        )
    except Exception as exc:
        features.append(
            ExperimentalFeatureStatus(
                name="Speckle Bridge",
                description="Push/receive BIM elements to/from Speckle.",
                endpoint="POST /api/v1/experimental/speckle/push",
                available=False,
                unavailable_reason=str(exc),
            ).model_dump()
        )

    return success(data={"features": features, "count": len(features)})


@router.post("/ocr/process")
async def process_ocr(
    _role: SystemConfigRole,
    file: UploadFile = File(..., description="PDF or image file (PNG/JPG/TIFF)"),
    lang: str = Form("eng+ara", description="Tesseract language codes"),
) -> dict[str, Any]:
    """
    Run OCR on an uploaded file and return extracted text + room names.

    Files are processed from a temporary location and deleted after processing.
    """
    from backend.services.ocr_service import OCRService

    # V272 FIX: previously the upload-save block was OUTSIDE the try/finally,
    # so if file.read() raised (network blip, client disconnect), the temp
    # file was leaked on disk with no cleanup. Now the entire block is wrapped
    # in a try/finally so cleanup always runs.
    suffix = Path(file.filename or "").suffix or ".bin"
    tmp_path: str | None = None
    try:
        # S7493: use asyncio.to_thread to avoid blocking the event loop
        # with synchronous tempfile I/O.
        content = await file.read()
        tmp_path = await asyncio.to_thread(_write_temp_file, suffix, content)

        svc = OCRService()
        result = svc.process_file(tmp_path, lang=lang)
        return success(data={"service": "ocr", "filename": file.filename, "result": result})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        # V271 FIX (CodeQL py/stack-trace-exposure): previously we exposed
        # {exc} in the detail, which can leak internal paths, DB URLs, or
        # credential fragments from the underlying library. Now we log the
        # full exception server-side and return a generic message.
        logger.exception("OCR processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR processing failed. Check server logs for details.",
        )
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post("/scan-to-bim/process")
async def process_scan_to_bim(
    _role: SystemConfigRole,
    file: UploadFile = File(..., description="PDF or image file with floor plan"),
    lang: str = Form("eng+ara", description="Tesseract language codes"),
) -> dict[str, Any]:
    """
    Run Scan-to-BIM on an uploaded floor plan: OCR → room extraction →
    classification → validation. Returns BIM rooms with areas and types.
    """
    from backend.services.ocr_service import OCRService
    from backend.services.scan_to_bim import ScanToBIMService

    # V272 FIX: wrap upload-save + processing in a single try/finally so
    # the temp file is cleaned up even if file.read() raises mid-upload.
    suffix = Path(file.filename or "").suffix or ".bin"
    tmp_path: str | None = None
    try:
        # S7493: use asyncio.to_thread to avoid blocking the event loop
        # with synchronous tempfile I/O.
        content = await file.read()
        tmp_path = await asyncio.to_thread(_write_temp_file, suffix, content)

        ocr = OCRService()
        svc = ScanToBIMService(ocr_service_instance=ocr)
        result = svc.process_scan(tmp_path, lang=lang)
        # Convert dataclass-like result to dict for JSON serialization
        payload: dict[str, Any] = {
            "service": "scan-to-bim",
            "filename": file.filename,
            "rooms": [
                r.__dict__ if hasattr(r, "__dict__") else r
                for r in (getattr(result, "rooms", []) or [])
            ],
            "summary": {
                "total_rooms": getattr(result, "total_rooms", 0),
                "valid_rooms": getattr(result, "valid_rooms", 0),
                "total_area_m2": getattr(result, "total_area_m2", 0.0),
                "avg_confidence": getattr(result, "avg_confidence", 0.0),
            },
        }
        return success(data=payload)
    except Exception:
        # V271 FIX (CodeQL py/stack-trace-exposure): do not expose {exc}.
        logger.exception("Scan-to-BIM processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scan-to-BIM processing failed. Check server logs for details.",
        )
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post("/speckle/push")
async def speckle_push(body: SpeckleOperationRequest, _role: SystemConfigRole) -> dict[str, Any]:
    """Push a list of BIM elements to a Speckle stream."""
    from backend.services.speckle_service import SpeckleService

    if not body.elements:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="elements list is required for push",
        )
    try:
        svc = SpeckleService()
        result = svc.push_to_speckle(
            stream_id=body.stream_id,
            server_url=body.server_url,
            token=body.token,
            elements=body.elements,
        )
        return success(data={"service": "speckle-push", "result": result})
    except Exception as exc:
        # V271 FIX (CodeQL py/stack-trace-exposure): do not expose {exc}.
        logger.exception("Speckle push failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Speckle push failed. Check server logs and Speckle service status.",
        ) from exc


@router.post("/speckle/receive")
async def speckle_receive(body: SpeckleOperationRequest, _role: SystemConfigRole) -> dict[str, Any]:
    """Receive elements from a Speckle stream."""
    from backend.services.speckle_service import SpeckleService

    try:
        svc = SpeckleService()
        result = svc.receive_from_speckle(
            stream_id=body.stream_id,
            server_url=body.server_url,
            token=body.token,
        )
        return success(data={"service": "speckle-receive", "result": result})
    except Exception as exc:
        # V271 FIX (CodeQL py/stack-trace-exposure): do not expose {exc}.
        logger.exception("Speckle receive failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Speckle receive failed. Check server logs and Speckle service status.",
        ) from exc
