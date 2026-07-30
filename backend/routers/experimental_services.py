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

• Responses include the service name, status, and full payload. Errors
  return structured JSON with the underlying exception message — these
  are experimental services, so exposing error details helps debugging.

• The /features endpoint lets the frontend list all experimental
  services in a single call, with their availability status.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.rbac import Permission, Role
from backend.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experimental", tags=["experimental-services"])

SystemConfigRole = Annotated[Role, Depends(require_permission(Permission.SYSTEM_CONFIG))]


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────


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

    # Save upload to temp file
    suffix = Path(file.filename or "").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        svc = OCRService()
        result = svc.process_file(tmp_path, lang=lang)
        return success(data={"service": "ocr", "filename": file.filename, "result": result})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("OCR processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR processing failed: {exc}",
        ) from exc
    finally:
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

    suffix = Path(file.filename or "").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ocr = OCRService()
        svc = ScanToBIMService(ocr_service_instance=ocr)
        result = svc.process_scan(tmp_path, lang=lang)
        # Convert dataclass-like result to dict for JSON serialization
        payload: dict[str, Any] = {
            "service": "scan-to-bim",
            "filename": file.filename,
            "rooms": [r.__dict__ if hasattr(r, "__dict__") else r for r in (getattr(result, "rooms", []) or [])],
            "summary": {
                "total_rooms": getattr(result, "total_rooms", 0),
                "valid_rooms": getattr(result, "valid_rooms", 0),
                "total_area_m2": getattr(result, "total_area_m2", 0.0),
                "avg_confidence": getattr(result, "avg_confidence", 0.0),
            },
        }
        return success(data=payload)
    except Exception as exc:
        logger.exception("Scan-to-BIM processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan-to-BIM processing failed: {exc}",
        ) from exc
    finally:
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
        logger.exception("Speckle push failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Speckle push failed: {exc}",
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
        logger.exception("Speckle receive failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Speckle receive failed: {exc}",
        ) from exc
