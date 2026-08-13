"""
ETAP-AI-WORK Revit Integration DTOs
===================================

Data Transfer Objects for Revit integration.
Defines standardized contracts between Revit and ETAP systems.

Principal Software Architect: Eng. Ahmed Elbaz
"""
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RevitElementDTO(BaseModel):
    """
    Data Transfer Object for Revit elements.
    Represents individual elements from Revit models.
    """
    id: str = Field(..., description="Unique identifier for the element")
    name: str = Field(..., description="Display name of the element")
    category: str = Field(..., description="Revit category of the element")
    family: str = Field("", description="Family name of the element")
    type: str = Field("", description="type name of the element")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Element parameters")
    location: dict[str, float] | None = Field(None, description="XYZ coordinates of the element")
    geometry: dict[str, Any] | None = Field(None, description="Geometric representation")
    level: str | None = Field(None, description="Building level/phase")
    workset: str | None = Field(None, description="Workset assignment")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last update timestamp")


class ElectricalAssetDTO(BaseModel):
    """
    Data Transfer Object for electrical assets extracted from Revit.
    Maps Revit electrical elements to ETAP electrical model.
    """
    element_id: str = Field(..., description="Original Revit element ID")
    asset_type: str = Field(..., description="type of electrical asset")
    name: str = Field(..., description="Asset name")
    voltage_rating: float | None = Field(None, description="Voltage rating in volts")
    power_rating: float | None = Field(None, description="Power rating in watts/kVA")
    manufacturer: str | None = Field(None, description="Manufacturer name")
    model: str | None = Field(None, description="Model number")
    serial_number: str | None = Field(None, description="Serial number")
    capacity: float | None = Field(None, description="Capacity rating")
    connections: list[str] = Field(default_factory=list, description="Connected element IDs")
    location_coordinates: dict[str, float] | None = Field(None, description="GIS coordinates")
    electrical_parameters: dict[str, Any] = Field(default_factory=dict, description="Electrical parameters")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Creation timestamp")


class SyncStatusDTO(BaseModel):
    """
    Data Transfer Object for synchronization status.
    Tracks the progress and outcome of sync operations.
    """
    sync_id: str = Field(..., description="Unique sync operation ID")
    project_id: str = Field(..., description="Associated project ID")
    status: str = Field(..., description="Current sync status")
    progress: float = Field(0.0, description="Progress percentage (0.0-100.0)")
    total_elements: int = Field(0, description="Total elements to sync")
    processed_elements: int = Field(0, description="Elements processed")
    successful_elements: int = Field(0, description="Successfully synced elements")
    failed_elements: int = Field(0, description="Failed elements count")
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Sync start time")
    end_time: datetime | None = Field(None, description="Sync completion time")
    error_details: dict[str, str] | None = Field(None, description="Error details if any")
    message: str | None = Field(None, description="Status message")


class ModelMetadataDTO(BaseModel):
    """
    Data Transfer Object for Revit model metadata.
    Contains information about the model structure and properties.
    """
    model_id: str = Field(..., description="Unique model identifier")
    project_name: str = Field(..., description="Project name from Revit")
    project_number: str | None = Field(None, description="Project number")
    revit_version: str = Field(..., description="Revit version used")
    model_units: str = Field(..., description="Model units (metric/imperial)")
    total_elements: int = Field(0, description="Total number of elements in model")
    electrical_elements: int = Field(0, description="Number of electrical elements")
    geometry_elements: int = Field(0, description="Number of geometry elements")
    file_size: int = Field(0, description="Model file size in bytes")
    created_date: datetime | None = Field(None, description="Model creation date")
    modified_date: datetime | None = Field(None, description="Model last modified date")
    author: str | None = Field(None, description="Model author")
    organization: str | None = Field(None, description="Organization name")
    description: str | None = Field(None, description="Model description")
    geographic_location: dict[str, float] | None = Field(None, description="Geographic coordinates")


class RevitProjectDTO(BaseModel):
    """
    Data Transfer Object for Revit project management.
    Manages project lifecycle within the ETAP integration.
    """
    project_id: str = Field(..., description="Unique project identifier")
    project_name: str = Field(..., description="Project name")
    revit_file_path: str | None = Field(None, description="Path to Revit file")
    aps_project_id: str | None = Field(None, description="APS project identifier")
    sync_enabled: bool = Field(True, description="Whether auto-sync is enabled")
    last_sync: datetime | None = Field(None, description="Last sync timestamp")
    next_sync: datetime | None = Field(None, description="Next scheduled sync")
    sync_interval: int = Field(3600, description="Sync interval in seconds")
    status: str = Field("active", description="Project status")
    owner: str | None = Field(None, description="Project owner")
    permissions: dict[str, bool] = Field(default_factory=dict, description="User permissions")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Project creation time")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Project update time")


class RevitSyncLogDTO(BaseModel):
    """
    Data Transfer Object for Revit synchronization logs.
    Records all sync operations for audit and troubleshooting.
    """
    log_id: str = Field(..., description="Unique log entry identifier")
    sync_id: str = Field(..., description="Associated sync operation ID")
    project_id: str = Field(..., description="Associated project ID")
    operation_type: str = Field(..., description="type of sync operation")
    element_id: str | None = Field(None, description="Affected element ID")
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Log message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Log timestamp")
    duration_ms: int | None = Field(None, description="Operation duration in milliseconds")
    user_id: str | None = Field(None, description="User who initiated sync")
    client_ip: str | None = Field(None, description="Client IP address")
