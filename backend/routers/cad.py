import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.limiter import limiter
from backend.rbac import Permission
from backend.services.cad_gateway import CADElement, CADGateway
from parsers._path_security import UnsafePathError, validate_input_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cad", tags=["CAD"])

_CAD_PROVIDER_DESCRIPTION = "Provider: autocad or revit"

_ALLOWED_EXTENSIONS = frozenset({".dwg", ".dxf", ".rvt", ".rfa", ".ifc"})

def _validate_cad_file_path(filepath: str) -> str:
    """
    Validate CAD/BIM file paths against path traversal and injection attacks.
    """
    try:
        safe_path = validate_input_path(
            filepath,
            allowed_extensions=_ALLOWED_EXTENSIONS,
            parser_name="cad_router",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found.") from exc
    except UnsafePathError as exc:
        logger.warning("Path traversal blocked in cad router: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="File path is outside allowed directories. Contact administrator.",
        ) from exc
    return str(safe_path)

def _safe_error(status_code: int, log_msg: str, _exc: Exception) -> HTTPException:
    """Log exception detail (without user-controlled msg), return safe message to client."""
    logger.error("CAD operation failed (status=%d)", status_code, exc_info=True)
    return HTTPException(status_code=status_code, detail=log_msg)


# ── Request / Response Models ────────────────────────────────────────────────

class CADConnectRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    visible: bool = True
    force_new: bool = False
    method: str = "simulation"

class CADConnectResponse(BaseModel):
    success: bool
    message: str
    connected: bool
    simulation_mode: bool = False

class CADDisconnectRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)

class CADStatusResponse(BaseModel):
    success: bool
    provider: str
    status: Dict[str, Any]

class CADReadRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    filepath: str

class CADReadResponse(BaseModel):
    success: bool
    provider: str
    filepath: str
    element_count: int
    elements: List[CADElement]

class CADWriteRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    filepath: str
    elements: List[CADElement]

class CADWriteResponse(BaseModel):
    success: bool
    message: str

class CADDrawLineRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    start_point: List[float]
    end_point: List[float]
    layer: str = "0"
    color: int = 256

class CADDrawPolylineRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    vertices: List[List[float]]
    layer: str = "0"
    color: int = 256
    closed: bool = False

class CADDrawCircleRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    center: List[float]
    radius: float
    layer: str = "0"
    color: int = 256

class CADDrawTextRequest(BaseModel):
    provider: str = Field(..., description=_CAD_PROVIDER_DESCRIPTION)
    text: str
    insertion_point: List[float]
    height: float = 0.2
    layer: str = "0"
    color: int = 256

class CADOperationResponse(BaseModel):
    success: bool
    message: str
    handle: Optional[str] = None


# ── REST Endpoints ───────────────────────────────────────────────────────────

@router.post("/connect", dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
@limiter.limit("10/minute")
async def connect_cad(request: Request, body: CADConnectRequest) -> CADConnectResponse:
    """Connect to Revit or AutoCAD application."""
    try:
        gateway = CADGateway()
        success = gateway.connect(
            provider=body.provider,
            visible=body.visible,
            force_new=body.force_new,
            method=body.method
        )
        status = gateway.get_status(body.provider)
        return CADConnectResponse(
            success=success,
            message=f"Connected to {body.provider} successfully" if success else f"Failed to connect to {body.provider}",
            connected=status.get("connected", False),
            simulation_mode=status.get("simulation_mode", False)
        )
    except Exception as e:
        raise _safe_error(500, f"Error connecting to {body.provider}", e)


@router.post("/disconnect", dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
async def disconnect_cad(request: Request, body: CADDisconnectRequest) -> CADOperationResponse:
    """Disconnect from Revit or AutoCAD application."""
    try:
        gateway = CADGateway()
        success = gateway.disconnect(body.provider)
        return CADOperationResponse(
            success=success,
            message=f"Disconnected from {body.provider} successfully" if success else f"Failed to disconnect from {body.provider}"
        )
    except Exception as e:
        raise _safe_error(500, f"Error disconnecting from {body.provider}", e)


@router.get("/status")
async def get_cad_status(provider: str) -> CADStatusResponse:
    """Get the current CAD/BIM connection status."""
    try:
        gateway = CADGateway()
        status = gateway.get_status(provider)
        return CADStatusResponse(
            success=True,
            provider=provider,
            status=status
        )
    except Exception as e:
        raise _safe_error(500, f"Error getting status for {provider}", e)


@router.post("/read", responses={
    400: {"description": "File path is outside allowed directories."},
    404: {"description": "File not found."},
    503: {"description": "Provider not connected."}
})
@limiter.limit("10/minute")
async def read_drawing(request: Request, body: CADReadRequest) -> CADReadResponse:
    """Read drawing entities/elements from the file."""
    try:
        safe_path = _validate_cad_file_path(body.filepath)
        gateway = CADGateway()
        status = gateway.get_status(body.provider)
        if not status.get("connected", False):
            raise HTTPException(status_code=503, detail=f"{body.provider} not connected. Call /connect first.")

        elements = gateway.read_drawing(body.provider, safe_path)
        return CADReadResponse(
            success=True,
            provider=body.provider,
            filepath=safe_path,
            element_count=len(elements),
            elements=elements
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, f"Error reading drawing from {body.provider}", e)


@router.post("/write", responses={
    400: {"description": "File path is outside allowed directories."},
    404: {"description": "File not found."},
    503: {"description": "Provider not connected."}
}, dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
@limiter.limit("10/minute")
async def write_drawing(request: Request, body: CADWriteRequest) -> CADWriteResponse:
    """Write elements/entities back to the drawing file."""
    try:
        safe_path = _validate_cad_file_path(body.filepath)
        gateway = CADGateway()
        status = gateway.get_status(body.provider)
        if not status.get("connected", False):
            raise HTTPException(status_code=503, detail=f"{body.provider} not connected. Call /connect first.")

        success = gateway.write_drawing(body.provider, safe_path, body.elements)
        return CADWriteResponse(
            success=success,
            message="Drawing written successfully" if success else "Failed to write drawing"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, f"Error writing drawing to {body.provider}", e)


@router.post("/draw_line", responses={
    503: {"description": "Provider not connected."}
}, dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
@limiter.limit("30/minute")
async def draw_line(request: Request, body: CADDrawLineRequest) -> CADOperationResponse:
    """Draw a line in the CAD application."""
    try:
        gateway = CADGateway()
        status = gateway.get_status(body.provider)
        if not status.get("connected", False):
            raise HTTPException(status_code=503, detail=f"{body.provider} not connected. Call /connect first.")

        handle = gateway.draw_line(
            provider=body.provider,
            start_point=body.start_point,
            end_point=body.end_point,
            layer=body.layer,
            color=body.color
        )
        return CADOperationResponse(
            success=bool(handle),
            message="Line drawn successfully" if handle else "Failed to draw line",
            handle=handle
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, f"Error drawing line in {body.provider}", e)


@router.post("/draw_polyline", responses={
    503: {"description": "Provider not connected."}
}, dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
@limiter.limit("30/minute")
async def draw_polyline(request: Request, body: CADDrawPolylineRequest) -> CADOperationResponse:
    """Draw a polyline/floor outline in the CAD/BIM application."""
    try:
        gateway = CADGateway()
        status = gateway.get_status(body.provider)
        if not status.get("connected", False):
            raise HTTPException(status_code=503, detail=f"{body.provider} not connected. Call /connect first.")

        handle = gateway.draw_polyline(
            provider=body.provider,
            vertices=body.vertices,
            layer=body.layer,
            color=body.color,
            closed=body.closed
        )
        return CADOperationResponse(
            success=bool(handle),
            message="Polyline drawn successfully" if handle else "Failed to draw polyline",
            handle=handle
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, f"Error drawing polyline in {body.provider}", e)


@router.post("/draw_circle", responses={
    503: {"description": "Provider not connected."}
}, dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
@limiter.limit("30/minute")
async def draw_circle(request: Request, body: CADDrawCircleRequest) -> CADOperationResponse:
    """Draw a circle/column in the CAD/BIM application."""
    try:
        gateway = CADGateway()
        status = gateway.get_status(body.provider)
        if not status.get("connected", False):
            raise HTTPException(status_code=503, detail=f"{body.provider} not connected. Call /connect first.")

        handle = gateway.draw_circle(
            provider=body.provider,
            center=body.center,
            radius=body.radius,
            layer=body.layer,
            color=body.color
        )
        return CADOperationResponse(
            success=bool(handle),
            message="Circle drawn successfully" if handle else "Failed to draw circle",
            handle=handle
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, f"Error drawing circle in {body.provider}", e)


@router.post("/draw_text", responses={
    503: {"description": "Provider not connected."}
}, dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))])
@limiter.limit("30/minute")
async def draw_text(request: Request, body: CADDrawTextRequest) -> CADOperationResponse:
    """Draw text/text notes in the CAD/BIM application."""
    try:
        gateway = CADGateway()
        status = gateway.get_status(body.provider)
        if not status.get("connected", False):
            raise HTTPException(status_code=503, detail=f"{body.provider} not connected. Call /connect first.")

        handle = gateway.draw_text(
            provider=body.provider,
            text=body.text,
            insertion_point=body.insertion_point,
            height=body.height,
            layer=body.layer,
            color=body.color
        )
        return CADOperationResponse(
            success=bool(handle),
            message="Text drawn successfully" if handle else "Failed to draw text",
            handle=handle
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_error(500, f"Error drawing text in {body.provider}", e)
