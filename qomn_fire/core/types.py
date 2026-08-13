"""
QOMN-FIRE UNIFIED DATA TYPES
Conformant with ISO 19650 BIM Standards and QOMN Deterministic Software Design.
Extended with building model types for IFC/DXF parsing pipeline.
"""

import hashlib
from dataclasses import dataclass

from fireai.core.base_types import (
    ConduitType,
    DeviceType,
    FittingType,
    Point3D,
)


@dataclass(frozen=True)
class Wall:
    """Structural wall element extracted from IFC/DXF parsing."""

    id: str
    start: Point3D
    end: Point3D
    height_m: float
    thickness_m: float


@dataclass(frozen=True)
class Opening:
    """Door or window opening in a wall."""

    id: str
    opening_type: str  # "DOOR" or "WINDOW"
    location: Point3D
    width_m: float
    height_m: float


@dataclass(frozen=True)
class Room:
    """Enclosed room/space with boundary polygon."""

    id: str
    name: str
    boundary: tuple[Point3D, ...]
    area_m2: float
    height_m: float
    has_placeholder_boundary: bool = False


@dataclass(frozen=True)
class Building:
    """Top-level building model containing all parsed geometric elements."""

    file_hash: str
    format_detected: str
    version_detected: str
    units: str  # Expected "METERS"
    walls: tuple[Wall, ...]
    rooms: tuple[Room, ...]
    openings: tuple[Opening, ...]
    has_fallback_geometry: bool = False

    def compute_hash(self) -> str:
        room_data = ";".join(
            f"{r.id}:{r.area_m2:.4f}:{r.height_m:.4f}:{len(r.boundary)}:"
            + "|".join(f"{p.x:.2f},{p.y:.2f},{p.z:.2f}" for p in r.boundary)
            for r in self.rooms
        )
        wall_data = ";".join(
            f"{w.id}:{w.start.x:.4f},{w.start.y:.4f}:{w.end.x:.4f},{w.end.y:.4f}:{w.height_m:.4f}:{w.thickness_m:.4f}"
            for w in self.walls
        )
        opening_data = ";".join(
            f"{o.id}:{o.opening_type}:{o.location.x:.2f},{o.location.y:.2f}:{o.width_m:.4f}:{o.height_m:.4f}"
            for o in self.openings
        )
        serialized = (
            f"{self.file_hash}:{self.format_detected}:{self.version_detected}:{self.units}:"
            f"WALLS[{wall_data}]:ROOMS[{room_data}]:OPENINGS[{opening_data}]:"
            f"{self.has_fallback_geometry}"
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Device:
    id: str
    device_type: DeviceType
    location: Point3D
    elevation_ft: float
    circuit: str
    zone: str

    def compute_hash(self) -> str:
        serialized = f"{self.id}:{self.device_type.value}:{self.location.x:.4f},{self.location.y:.4f},{self.location.z:.4f}:{self.elevation_ft}:{self.circuit}:{self.zone}"
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Fitting:
    fitting_type: FittingType
    location: Point3D


@dataclass(frozen=True)
class ConduitRun:
    id: str
    conduit_type: ConduitType
    trade_size: str
    points: tuple[Point3D, ...]
    total_length_ft: float
    bend_count: int
    bend_degrees: int
    fittings: tuple[Fitting, ...]

    def compute_hash(self) -> str:
        pt_strs = ",".join([f"{p.x:.4f},{p.y:.4f},{p.z:.4f}" for p in self.points])
        serialized = f"{self.id}:{self.conduit_type.value}:{self.trade_size}:{pt_strs}:{self.total_length_ft:.4f}:{self.bend_count}:{self.bend_degrees}"
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HatchSpec:
    pattern_name: str
    angle: float
    scale: float
    color: int
    layer: str
    description: str
    code_reference: str


@dataclass(frozen=True)
class TitleBlock:
    project_name: str
    drawing_number: str
    sheet_title: str
    scale: str
    date: str
    designer: str
    checker: str
    pe_stamp: str
    client: str
    address: str


@dataclass(frozen=True)
class Revision:
    number: int
    date: str
    description: str
    by: str
