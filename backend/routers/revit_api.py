"""
ETAP-AI-WORK Revit Integration API
=================================

REST API endpoints for Revit integration operations.

Principal Software Architect: Eng. Ahmed Elbaz
"""

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from backend.auth import require_permission
from backend.rbac import Permission

# ── Annotated type aliases (S8410) ────────────────────────────────────────────
UploadFileDep = Annotated[UploadFile, File(...)]
# ────────────────────────────────────────────────────────────────────────────

from revit_integration.aps.auth_service import APSAuthService
from revit_integration.aps.data_exchange import APSDataExchange
from revit_integration.dto.revit_dto import (
    ModelMetadataDTO,
    RevitElementDTO,
    RevitProjectDTO,
)
from revit_integration.services.revit_sync_service import RevitSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/revit-integration", tags=["Revit Integration"])

# Initialize services
# In a real implementation, these would be injected via DI container
aps_auth_service = APSAuthService(
    client_id=os.getenv("APS_CLIENT_ID", "dummy"),
    client_secret=os.getenv("APS_CLIENT_SECRET", "dummy"),
    redirect_uri=os.getenv("APS_REDIRECT_URI", "http://localhost:8000/callback"),
)
aps_data_exchange = APSDataExchange(aps_auth_service)
revit_sync_service = RevitSyncService(aps_data_exchange)


# Pydantic models for API
class RevitSyncRequest(BaseModel):
    """Request model for initiating Revit sync."""

    project_id: str
    incremental: bool = False
    force_full_sync: bool = False


class RevitSyncResponse(BaseModel):
    """Response model for Revit sync."""

    success: bool
    sync_id: str
    message: str
    elements_processed: int
    elements_successful: int
    elements_failed: int


class RevitUploadRequest(BaseModel):
    """Request model for uploading Revit file."""

    project_id: str
    filename: str


class RevitExportRequest(BaseModel):
    """Request model for exporting Revit data."""

    project_id: str
    format: str  # 'rvt', 'ifc', 'dwg', 'step', etc.
    include_electrical: bool = True
    include_structural: bool = True
    include_architectural: bool = True


class RevitStatusResponse(BaseModel):
    """Response model for Revit status."""

    project_id: str
    sync_status: str
    last_sync: datetime | None = None
    element_count: int
    electrical_elements: int
    next_sync: datetime | None = None
    connection_status: str


class RevitModelResponse(BaseModel):
    """Response model for Revit model data."""

    model_id: str
    project_name: str
    elements: list[RevitElementDTO]
    metadata: ModelMetadataDTO


class WebSocketMessage(BaseModel):
    """Model for WebSocket messages."""

    type: str
    data: dict[str, Any]


# Track active WebSocket connections
active_connections: dict[str, WebSocket] = {}


@router.post(
    "/upload",
    response_model=RevitSyncResponse,
    dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))],
)
async def upload_revit_model(project_id: str, file: UploadFileDep) -> RevitSyncResponse:
    """
    Upload a Revit model file for processing.

    Args:
        project_id: ID of the target project
        file: Revit file to upload (.rvt, .rfa, .rte)

    Returns:
        RevitSyncResponse: Upload and sync status
    """
    try:
        # Create temporary file to save upload
        suffix = os.path.splitext(file.filename or "")[1]
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        content = await file.read()
        await asyncio.to_thread(Path(temp_path).write_bytes, content)

        try:
            # In a real implementation, this would:
            # 1. Validate the Revit file
            # 2. Store it securely
            # 3. Initiate processing

            # For now, we'll simulate the process
            project_dto = RevitProjectDTO(
                project_id=project_id,
                project_name=f"Project_{project_id}",
                revit_file_path=temp_path,
                status="active",
            )

            # Start sync process
            sync_status = await revit_sync_service.sync_project(project_dto)

            response = RevitSyncResponse(
                success=True,
                sync_id=sync_status.sync_id,
                message=f"Successfully uploaded and started sync for {file.filename}",
                elements_processed=sync_status.processed_elements,
                elements_successful=sync_status.successful_elements,
                elements_failed=sync_status.failed_elements,
            )

            return response

        finally:
            # Clean up temporary file
            os.unlink(temp_path)

    except Exception:
        logger.exception("Error uploading Revit model")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.post(
    "/sync",
    response_model=RevitSyncResponse,
    dependencies=[Depends(require_permission(Permission.ELEMENT_CREATE))],
)
async def sync_revit_model(request: RevitSyncRequest) -> RevitSyncResponse:
    """
    Initiate synchronization of a Revit model.

    Args:
        request: Sync parameters

    Returns:
        RevitSyncResponse: Sync status
    """
    try:
        # Create project DTO
        project_dto = RevitProjectDTO(
            project_id=request.project_id,
            project_name=f"Project_{request.project_id}",
            status="active",
        )

        # Perform sync
        sync_status = await revit_sync_service.sync_project(project_dto)

        response = RevitSyncResponse(
            success=True,
            sync_id=sync_status.sync_id,
            message="Sync completed successfully",
            elements_processed=sync_status.processed_elements,
            elements_successful=sync_status.successful_elements,
            elements_failed=sync_status.failed_elements,
        )

        return response

    except Exception:
        logger.exception("Error syncing Revit model")
        raise HTTPException(status_code=500, detail="Sync failed")


@router.get(
    "/model/{model_id}",
    response_model=RevitModelResponse,
    dependencies=[Depends(require_permission(Permission.ELEMENT_READ))],
)
async def get_revit_model(model_id: str) -> RevitModelResponse:
    """
    Retrieve a specific Revit model.

    Args:
        model_id: ID of the model to retrieve

    Returns:
        RevitModelResponse: Model data and metadata
    """
    try:
        # In a real implementation, this would fetch model data from storage
        # For now, we'll simulate the response

        # Create mock model data
        mock_elements = [
            RevitElementDTO(
                id=f"ele_{i}",
                name=f"Element_{i}",
                category="Electrical Equipment"
                if i % 3 == 0
                else "Rooms"
                if i % 3 == 1
                else "Cable Tray",
                family="Generic",
                type="Default",
                parameters={"Power": 100 + i, "Voltage": 480},
                location={"x": float(i), "y": float(i * 2), "z": 0.0} if i % 2 == 0 else None,
            )
            for i in range(10)  # Simulate 10 elements
        ]

        metadata = ModelMetadataDTO(
            model_id=model_id,
            project_name=f"Project_{model_id}",
            revit_version="2024",
            model_units="Imperial",
            total_elements=10,
            electrical_elements=4,
            geometry_elements=6,
            file_size=1024000,  # 1MB
            created_date=datetime.now(),
            modified_date=datetime.now(),
            author="Mock Author",
            organization="Mock Organization",
            description="Mock Revit Model",
        )

        response = RevitModelResponse(
            model_id=model_id,
            project_name=f"Project_{model_id}",
            elements=mock_elements,
            metadata=metadata,
        )

        return response

    except Exception:
        logger.exception("Error retrieving Revit model")
        raise HTTPException(status_code=500, detail="Model retrieval failed")


@router.post(
    "/export",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permission(Permission.EXPORT_READ))],
)
async def export_revit_data(request: RevitExportRequest) -> dict[str, Any]:
    """
    Export Revit data in various formats.

    Args:
        request: Export parameters

    Returns:
        dict: Export status and file information
    """
    try:
        # In a real implementation, this would:
        # 1. Gather elements based on request parameters
        # 2. Convert to requested format
        # 3. Generate file

        # For now, we'll simulate the export
        export_filename = f"export_{request.project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{request.format}"

        response = {
            "success": True,
            "filename": export_filename,
            "format": request.format,
            "export_type": "simulation",
            "message": f"Export job started for project {request.project_id}",
            "estimated_completion": (datetime.now().timestamp() + 30),  # 30 seconds
        }

        return response

    except Exception:
        logger.exception("Error exporting Revit data")
        raise HTTPException(status_code=500, detail="Export failed")


@router.get(
    "/status",
    response_model=RevitStatusResponse,
    dependencies=[Depends(require_permission(Permission.ELEMENT_READ))],
)
async def get_revit_status(project_id: str) -> RevitStatusResponse:
    """
    Get the synchronization status of a Revit project.

    Args:
        project_id: ID of the project

    Returns:
        RevitStatusResponse: Status information
    """
    try:
        # In a real implementation, this would query the database for project status
        # For now, we'll simulate the status

        response = RevitStatusResponse(
            project_id=project_id,
            sync_status="up_to_date",
            last_sync=datetime.now(),
            element_count=150,
            electrical_elements=50,
            next_sync=datetime.now().replace(hour=datetime.now().hour + 1),
            connection_status="connected",
        )

        return response

    except Exception:
        logger.exception("Error getting Revit status")
        raise HTTPException(status_code=500, detail="Status retrieval failed")


def _validate_ws_origin(websocket: WebSocket) -> bool:
    """
    Validate WebSocket origin to prevent Cross-Site WebSocket Hijacking (CSWSH).

    Same-origin requests (SPA hosted on same server or localhost) are allowed.
    In production (FIREAI_ENV=production), missing Origin is rejected.
    """
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")
    is_dev_mode = os.getenv("FIREAI_ENV", "production").lower() not in ("production", "prod")

    if not origin:
        return bool(is_dev_mode)

    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    host_clean = host.lower()

    if scheme == "https":
        if netloc in (host_clean, "testserver"):
            return True
        cors_origins = os.getenv("CORS_ORIGINS", "")
        if cors_origins:
            allowed_list = [o.strip().lower() for o in cors_origins.split(",") if o.strip()]
            if origin.lower() in allowed_list:
                return True

    if is_dev_mode:
        dev_allowed_netlocs = {
            host_clean,
            "testserver",
            "localhost",
            "localhost:3000",
            "localhost:5173",
            "localhost:8000",
            "127.0.0.1",
            "127.0.0.1:3000",
            "127.0.0.1:5173",
            "127.0.0.1:8000",
        }
        if netloc in dev_allowed_netlocs:
            return True

    return False


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint for real-time Revit synchronization updates.

    Security:
      - Origin validation against allowed origins (CSWSH prevention).
      - Header-based API key authentication (X-API-Key).
    """
    # ── Origin check ────────────────────────────────────────────────────
    if not _validate_ws_origin(websocket):
        logger.warning(
            "Revit WebSocket rejected: invalid origin origin=%s client=%s",
            websocket.headers.get("origin", "missing"),
            websocket.client.host if websocket.client else "unknown",
        )
        await websocket.close(code=4001, reason="Unauthorized origin")
        return

    # Authenticate via header before accepting WebSocket connection
    from backend.api_keys import validate_api_key

    api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-Key")
    if not api_key:
        api_key = websocket.query_params.get("api_key")
        if api_key:
            logger.warning("Query parameter auth for WebSocket is deprecated; use X-API-Key header")

    principal = validate_api_key(api_key) if api_key else None
    if not principal:
        await websocket.close(code=4001, reason="Unauthorized: Valid API key required")
        return

    await websocket.accept()

    # Add to active connections
    connection_key = f"{project_id}_{websocket.client.host}:{websocket.client.port}"
    active_connections[connection_key] = websocket

    try:
        # Send initial connection message
        await websocket.send_text(
            WebSocketMessage(
                type="connection_established",
                data={
                    "project_id": project_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "message": f"Connected to project {project_id}",
                },
            ).model_dump_json()
        )

        # Listen for messages and handle sync updates
        while True:
            try:
                # In a real implementation, this would listen for sync updates
                # For now, we'll just keep the connection alive
                data = await websocket.receive_text()

                # Parse incoming message
                try:
                    message = WebSocketMessage.model_validate_json(data)

                    # Handle different message types
                    if message.type == "sync_request":
                        # Simulate starting a sync
                        await websocket.send_text(
                            WebSocketMessage(
                                type="sync_started",
                                data={
                                    "sync_id": f"sync_{project_id}_{int(datetime.now(UTC).timestamp())}",
                                    "project_id": project_id,
                                    "timestamp": datetime.now(UTC).isoformat(),
                                },
                            ).model_dump_json()
                        )

                        # Simulate sync progress
                        for progress in [25, 50, 75, 100]:
                            await websocket.send_text(
                                WebSocketMessage(
                                    type="sync_progress",
                                    data={
                                        "sync_id": f"sync_{project_id}_{int(datetime.now(UTC).timestamp())}",
                                        "progress": progress,
                                        "timestamp": datetime.now(UTC).isoformat(),
                                    },
                                ).model_dump_json()
                            )

                            await asyncio.sleep(1)  # Simulate processing

                        # Send completion
                        await websocket.send_text(
                            WebSocketMessage(
                                type="sync_completed",
                                data={
                                    "sync_id": f"sync_{project_id}_{int(datetime.now(UTC).timestamp())}",
                                    "project_id": project_id,
                                    "elements_processed": 100,
                                    "elements_successful": 98,
                                    "elements_failed": 2,
                                    "timestamp": datetime.now(UTC).isoformat(),
                                },
                            ).model_dump_json()
                        )

                    elif message.type == "ping":
                        await websocket.send_text(
                            WebSocketMessage(
                                type="pong", data={"timestamp": datetime.now(UTC).isoformat()}
                            ).model_dump_json()
                        )

                except Exception:
                    logger.exception("Error processing WebSocket message")
                    await websocket.send_text(
                        WebSocketMessage(
                            type="error",
                            data={
                                "error": "Internal error",
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        ).model_dump_json()
                    )

            except WebSocketDisconnect:
                break

    except Exception:
        logger.exception("WebSocket error")
    finally:
        # Remove from active connections
        active_connections.pop(connection_key, None)


# Utility functions
async def broadcast_to_project(project_id: str, message: WebSocketMessage):
    """
    Broadcast a message to all WebSocket connections for a project.

    Args:
        project_id: Project ID
        message: Message to broadcast
    """
    for conn_key, ws in list(active_connections.items()):
        if conn_key.startswith(project_id):
            try:
                await ws.send_text(message.model_dump_json())
            except Exception:
                logger.exception("Error broadcasting to connection")
                # Remove broken connection
                active_connections.pop(conn_key, None)
