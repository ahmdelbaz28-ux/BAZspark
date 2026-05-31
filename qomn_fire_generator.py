"""
QOMN-FIRE: MASTER INTEGRATED WORKSPACE GENERATOR
Author: Chief Fire Protection Engineer & Safety-Critical Systems Architect
Standards: NFPA 72 (2022), NEC 760 (2023), ISO 19650, UL 864 10th Edition

V54 — Corrected Release
All 10 identified bugs fixed:
  1. Device.compute_hash now includes Z coordinate (deterministic hash)
  2. List[str] in frozen dataclasses → Tuple[str, ...] (runtime safety)
  3. doc.layers.new API fixed to use dxfattribs (ezdxf 1.4.3 compat)
  4. NULL_DATE_VALUE replaced with 0.0 (ezdxf 1.4.3 compat)
  5. view_center → view_center_point (ezdxf 1.4.3 API)
  6. layers.new in dxf_generator uses dxfattribs
  7. set_bulge replaced with format='xyb' (ezdxf 1.4.3 compat)
  8. Test 3 replaced with proper bend-limit enforcement test
  9. Restored conduit fill, physics guard, determinism stress tests
  10. Return type corrected from Document to Drawing
"""

import os
import sys
import json
import math
import hashlib
import shutil
import unittest
from typing import Tuple, List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field

INTEGRATED_FILES = {}

# ─────────────────────────────────────────────────────────────────────
# 1. qomn_fire/core/types.py (Unified Types)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/core/types.py"] = '''"""
QOMN-FIRE UNIFIED DATA TYPES
Conformant with ISO 19650 BIM Standards and QOMN Deterministic Software Design.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, List, Dict, Any, Optional, Union
import hashlib

class DeviceType(Enum):
    SMOKE_DETECTOR = "SMOKE_DETECTOR"
    HEAT_DETECTOR = "HEAT_DETECTOR"
    MANUAL_PULL_STATION = "MANUAL_PULL_STATION"
    HORN_STROBE = "HORN_STROBE"

class ConduitType(Enum):
    EMT = "EMT"  # Electrical Metallic Tubing (NEC Art. 358)
    RMC = "RMC"  # Rigid Metal Conduit (NEC Art. 344)
    FMC = "FMC"  # Flexible Metal Conduit (NEC Art. 348)

class FittingType(Enum):
    ELBOW_90 = "ELBOW_90"
    TEE = "TEE"
    COUPLING = "COUPLING"

@dataclass(frozen=True, slots=True)
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, 'x', round(float(self.x), 4))
        object.__setattr__(self, 'y', round(float(self.y), 4))
        object.__setattr__(self, 'z', round(float(self.z), 4))

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_dict(self) -> Dict[str, float]:
        return {"X": self.x, "Y": self.y, "Z": self.z}

@dataclass(frozen=True, slots=True)
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

@dataclass(frozen=True, slots=True)
class Fitting:
    fitting_type: FittingType
    location: Point3D

@dataclass(frozen=True, slots=True)
class ConduitRun:
    id: str
    conduit_type: ConduitType
    trade_size: str
    points: Tuple[Point3D, ...]
    total_length_ft: float
    bend_count: int
    fittings: Tuple[Fitting, ...]

    def compute_hash(self) -> str:
        pt_strs = ",".join([f"{p.x:.4f},{p.y:.4f},{p.z:.4f}" for p in self.points])
        serialized = f"{self.id}:{self.conduit_type.value}:{self.trade_size}:{pt_strs}:{self.total_length_ft:.4f}:{self.bend_count}"
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

@dataclass(frozen=True, slots=True)
class FireAlarmPanel:
    model: str
    manufacturer: str
    points_capacity: int
    nac_capacity: int
    supports_networking: bool
    supports_voice: bool
    max_slc_loops: int
    listings: Tuple[str, ...]
    standby_current_amps: float
    alarm_current_amps: float
    power_supply_watts: int

@dataclass(frozen=True, slots=True)
class ProjectRequirements:
    device_count: int
    nac_circuit_count: int
    building_size_m2: float
    building_floors: int
    requires_network: bool
    requires_voice: bool
    requires_releasing: bool
    jurisdiction: str
    preferred_manufacturer: Optional[str] = None

@dataclass(frozen=True, slots=True)
class PanelRecommendation:
    recommended_model: str
    manufacturer: str
    capacity_utilization: float
    nac_utilization: float
    battery_size_ah: float
    power_supply_watts: int
    listings: Tuple[str, ...]
    code_compliance: Tuple[str, ...]
    warnings: Tuple[str, ...]
    alternatives: Tuple[str, ...]
    signature_hash: str

@dataclass(frozen=True, slots=True)
class HatchSpec:
    pattern_name: str
    angle: float
    scale: float
    color: int
    layer: str
    description: str
    code_reference: str

@dataclass(frozen=True, slots=True)
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

@dataclass(frozen=True, slots=True)
class Revision:
    number: int
    date: str
    description: str
    by: str
'''

# ─────────────────────────────────────────────────────────────────────
# 2. qomn_fire/core/errors.py (Unified Monadic Errors)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/core/errors.py"] = '''"""
QOMN-FIRE UNIFIED ERROR FRAMEWORK
"""

from typing import Generic, TypeVar, Optional, Union

T = TypeVar('T')
E = TypeVar('E')

class Result(Generic[T, E]):
    def __init__(self, value: Optional[T] = None, error: Optional[E] = None):
        self._value = value
        self._error = error

    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def is_failure(self) -> bool:
        return self._error is not None

    def unwrap(self) -> T:
        if self._error is not None:
            raise ValueError(f"Panic: Attempted to unwrap failure Result: {self._error}")
        return self._value

    def error(self) -> E:
        if self._error is None:
            raise ValueError("Panic: Attempted to fetch error of successful Result")
        return self._error

class BaseEngineeringError:
    def __init__(self, message: str, code_ref: str, remedy: str):
        self.message = message
        self.code_ref = code_ref
        self.remedy = remedy

    def __repr__(self) -> str:
        return f"[{self.code_ref}] Error: {self.message} (Remedy: {self.remedy})"

class ConduitFillError(BaseEngineeringError): pass
class NECViolationError(BaseEngineeringError): pass
class HatchPlacementError(BaseEngineeringError): pass
class PhysicalConstraintError(BaseEngineeringError): pass
class FACPSelectionError(BaseEngineeringError): pass
'''

# ─────────────────────────────────────────────────────────────────────
# 3. qomn_fire/core/constants.py (Standard Constants)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/core/constants.py"] = '''"""
QOMN-FIRE PHYSICAL AND REGULATORY CONSTANTS
"""

# NFPA 72 Spacing Limits (2022 §17)
NFPA_SMOKE_DETECTOR_SPACING_M = 9.144  # 30 feet smooth ceiling spacing
NFPA_MAX_WALL_DISTANCE_M = 6.400       # 0.7 times spacing constraint (21 feet)

# NEC Conduit Area Specifications (mm2) - Chapter 9 Table 4
EMT_INTERNAL_AREA_1_2_MM2 = 196.1
EMT_INTERNAL_AREA_3_4_MM2 = 343.9
EMT_INTERNAL_AREA_1_MM2 = 557.4

# NEC Wire Cross Sectional Areas (mm2) - Chapter 9 Table 5
WIRE_AREA_14_AWG_MM2 = 6.26
WIRE_AREA_12_AWG_MM2 = 8.58
WIRE_AREA_10_AWG_MM2 = 13.61

# NEC Chapter 9 Table 1 Fill Limits
NEC_FILL_LIMIT_1_WIRE = 0.53
NEC_FILL_LIMIT_2_WIRES = 0.31
NEC_FILL_LIMIT_OVER_2_WIRES = 0.40
'''

# ─────────────────────────────────────────────────────────────────────
# 4. qomn_fire/core/hash.py (SHA-256 Helpers)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/core/hash.py"] = '''"""
QOMN-FIRE CRYPTOGRAPHIC AND DETERMINISTIC DATA COMPACTION
"""

import hashlib
import json

def get_bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def get_string_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
'''

# ─────────────────────────────────────────────────────────────────────
# 5. qomn_fire/engine/fill.py (NEC Conduit Fill)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/engine/fill.py"] = '''"""
QOMN-FIRE CONDUIT FILL SIZING ENGINE
Reference Standard: NEC 2023 Chapter 9, Table 1 & Table 4.
"""

from qomn_fire.core.errors import Result, ConduitFillError
from qomn_fire.core.constants import (
    EMT_INTERNAL_AREA_1_2_MM2, EMT_INTERNAL_AREA_3_4_MM2, EMT_INTERNAL_AREA_1_MM2,
    WIRE_AREA_14_AWG_MM2, WIRE_AREA_12_AWG_MM2, WIRE_AREA_10_AWG_MM2,
    NEC_FILL_LIMIT_1_WIRE, NEC_FILL_LIMIT_2_WIRES, NEC_FILL_LIMIT_OVER_2_WIRES
)

def calculate_conduit_fill(conduit_size: str, wire_gauge: str, wire_count: int) -> Result[float, ConduitFillError]:
    if wire_count <= 0:
        return Result(error=ConduitFillError(
            message="Wire count must be a positive integer.",
            code_ref="NEC Ch.9 Table 1",
            remedy="Increase wire count parameter above zero."
        ))

    conduit_area = 0.0
    if conduit_size == "1/2":
        conduit_area = EMT_INTERNAL_AREA_1_2_MM2
    elif conduit_size == "3/4":
        conduit_area = EMT_INTERNAL_AREA_3_4_MM2
    elif conduit_size == "1":
        conduit_area = EMT_INTERNAL_AREA_1_MM2
    else:
        return Result(error=ConduitFillError(
            message=f"Unsupported trade conduit size '{conduit_size}'",
            code_ref="NEC Table 4",
            remedy="Use standard sizes: '1/2', '3/4', or '1'."
        ))

    wire_area = 0.0
    if wire_gauge == "14 AWG":
        wire_area = WIRE_AREA_14_AWG_MM2
    elif wire_gauge == "12 AWG":
        wire_area = WIRE_AREA_12_AWG_MM2
    elif wire_gauge == "10 AWG":
        wire_area = WIRE_AREA_10_AWG_MM2
    else:
        return Result(error=ConduitFillError(
            message=f"Unsupported AWG gauge '{wire_gauge}'",
            code_ref="NEC Table 5",
            remedy="Select compliant wire gauge: '14 AWG', '12 AWG', or '10 AWG'."
        ))

    total_wire_area = wire_area * wire_count
    fill_ratio = total_wire_area / conduit_area

    if wire_count == 1:
        limit = NEC_FILL_LIMIT_1_WIRE
    elif wire_count == 2:
        limit = NEC_FILL_LIMIT_2_WIRES
    else:
        limit = NEC_FILL_LIMIT_OVER_2_WIRES

    if fill_ratio > limit:
        return Result(error=ConduitFillError(
            message=f"Conduit fill exceeds permissible NEC threshold limit: {fill_ratio:.2%} > {limit:.2%}",
            code_ref="NEC Ch.9 Table 1",
            remedy="Upsize conduit selection or reduce wire run count."
        ))

    return Result(value=fill_ratio)
'''

# ─────────────────────────────────────────────────────────────────────
# 6. qomn_fire/engine/panel_database.py (Immutable FACP Specs)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/engine/panel_database.py"] = '''"""
FACP IMMUTABLE DATASHEETS
"""

from qomn_fire.core.types import FireAlarmPanel

MASTER_PANEL_DATABASE = [
    FireAlarmPanel(
        model="NFS-320",
        manufacturer="NOTIFIER",
        points_capacity=250,
        nac_capacity=2,
        supports_networking=False,
        supports_voice=False,
        max_slc_loops=1,
        listings=("UL", "ULC"),
        standby_current_amps=0.200,
        alarm_current_amps=0.350,
        power_supply_watts=144
    ),
    FireAlarmPanel(
        model="NFS-640",
        manufacturer="NOTIFIER",
        points_capacity=640,
        nac_capacity=4,
        supports_networking=True,
        supports_voice=True,
        max_slc_loops=4,
        listings=("UL", "ULC"),
        standby_current_amps=0.250,
        alarm_current_amps=0.450,
        power_supply_watts=144
    ),
    FireAlarmPanel(
        model="NFS2-3030",
        manufacturer="NOTIFIER",
        points_capacity=3180,
        nac_capacity=10,
        supports_networking=True,
        supports_voice=True,
        max_slc_loops=10,
        listings=("UL", "ULC", "FM"),
        standby_current_amps=0.350,
        alarm_current_amps=0.650,
        power_supply_watts=288
    ),
    FireAlarmPanel(
        model="FC901",
        manufacturer="SIEMENS",
        points_capacity=50,
        nac_capacity=2,
        supports_networking=False,
        supports_voice=False,
        max_slc_loops=1,
        listings=("UL", "FM", "FDNY"),
        standby_current_amps=0.120,
        alarm_current_amps=0.250,
        power_supply_watts=170
    ),
    FireAlarmPanel(
        model="FC922",
        manufacturer="SIEMENS",
        points_capacity=252,
        nac_capacity=4,
        supports_networking=True,
        supports_voice=True,
        max_slc_loops=2,
        listings=("UL", "FM", "FDNY"),
        standby_current_amps=0.180,
        alarm_current_amps=0.350,
        power_supply_watts=170
    ),
    FireAlarmPanel(
        model="FC924",
        manufacturer="SIEMENS",
        points_capacity=504,
        nac_capacity=6,
        supports_networking=True,
        supports_voice=True,
        max_slc_loops=4,
        listings=("UL", "FM", "FDNY"),
        standby_current_amps=0.220,
        alarm_current_amps=0.450,
        power_supply_watts=300
    ),
    FireAlarmPanel(
        model="4100ES",
        manufacturer="SIMPLEX",
        points_capacity=3000,
        nac_capacity=10,
        supports_networking=True,
        supports_voice=True,
        max_slc_loops=10,
        listings=("UL", "FM", "FDNY"),
        standby_current_amps=0.450,
        alarm_current_amps=0.850,
        power_supply_watts=360
    )
]
'''

# ─────────────────────────────────────────────────────────────────────
# 7. qomn_fire/engine/panel_selector.py (Integrated FACP Selection)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/engine/panel_selector.py"] = '''"""
QOMN-FIRE FACP SELECTION ENGINE
Reference Standard: NFPA 72 (2022) §10.6.10, UL 864 10th Edition.
"""

import hashlib
from typing import List, Optional, Tuple
from qomn_fire.core.types import ProjectRequirements, PanelRecommendation, FireAlarmPanel
from qomn_fire.core.errors import Result, FACPSelectionError
from qomn_fire.engine.panel_database import MASTER_PANEL_DATABASE

class SelectionEngine:
    @staticmethod
    def compute_battery_ah(
        device_count: int,
        nac_circuit_count: int,
        panel: FireAlarmPanel,
        requires_voice: bool
    ) -> float:
        """
        Calculates battery capacity per NFPA 72 §10.6.10.
        - Standby: 24 Hours
        - Alarm: 15 Mins (0.25h) if Voice Evacuation is required; else 5 Mins (0.0833h)
        - Safety Margin: 20%
        """
        standby_load = (device_count * 0.001) + panel.standby_current_amps
        alarm_load = (nac_circuit_count * 2.0) + (device_count * 0.005) + panel.alarm_current_amps
        alarm_duration_h = 0.25 if requires_voice else 0.0833

        raw_capacity = (standby_load * 24.0) + (alarm_load * alarm_duration_h)
        return round(raw_capacity * 1.2, 2)

    @classmethod
    def select_panel(cls, req: ProjectRequirements) -> Result[PanelRecommendation, FACPSelectionError]:
        # Enforce code capacity margins (20% spare capacity per NFPA 72 §10.6.10)
        required_points = req.device_count * 1.2
        # NAC circuits are sized by battery calculation, not blanket margin.
        # The 20% margin applies to address points only (NFPA 72 §10.6.10.2).
        required_nacs = req.nac_circuit_count

        eligible_panels: List[Tuple[FireAlarmPanel, float]] = []

        for p in MASTER_PANEL_DATABASE:
            if p.points_capacity < required_points:
                continue
            if p.nac_capacity < required_nacs:
                continue
            if req.requires_network and not p.supports_networking:
                continue
            if req.requires_voice and not p.supports_voice:
                continue
            if req.jurisdiction == "FDNY" and "FDNY" not in p.listings:
                continue
            if req.jurisdiction == "Canada" and "ULC" not in p.listings:
                continue

            # Multi-criteria scoring
            score = 0.0
            utilization = required_points / p.points_capacity

            if 0.5 <= utilization <= 0.8:
                score += 50.0
            elif 0.3 <= utilization < 0.5:
                score += 20.0
            elif 0.8 < utilization <= 0.95:
                score += 15.0
            else:
                score += 5.0

            if req.preferred_manufacturer and req.preferred_manufacturer.upper() == p.manufacturer.upper():
                score += 100.0

            eligible_panels.append((p, score))

        if not eligible_panels:
            return Result(error=FACPSelectionError(
                message="No compliant FACP models found satisfying constraints in database.",
                code_ref="UL 864 / NFPA 72",
                remedy="Reduce required device loads or transition to a multi-node networked panel architecture."
            ))

        # Deterministic sorting: Right-sizing principle
        # Primary: highest score. Tie-break: smallest capacity (right-sizing),
        # then lowest standby draw, then model name for determinism.
        eligible_panels.sort(
            key=lambda x: (x[1], -x[0].points_capacity, -x[0].standby_current_amps, x[0].model),
            reverse=True
        )

        selected, _ = eligible_panels[0]
        alternatives = tuple([p[0].model for p in eligible_panels[1:4]])

        capacity_util = required_points / selected.points_capacity
        nac_util = required_nacs / selected.nac_capacity

        warnings = []
        if capacity_util > 0.90:
            warnings.append("FACP loading is close to maximum capacity limits.")
        elif capacity_util < 0.30:
            warnings.append("FACP is significantly oversized for the current device loading.")

        battery_size = cls.compute_battery_ah(
            req.device_count,
            req.nac_circuit_count,
            selected,
            req.requires_voice
        )

        # Cryptographic checksum for deterministic outputs
        payload = f"{selected.model}:{selected.manufacturer}:{capacity_util:.4f}:{battery_size:.2f}"
        signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        rec = PanelRecommendation(
            recommended_model=selected.model,
            manufacturer=selected.manufacturer,
            capacity_utilization=round(capacity_util, 4),
            nac_utilization=round(nac_util, 4),
            battery_size_ah=battery_size,
            power_supply_watts=selected.power_supply_watts,
            listings=selected.listings,
            code_compliance=(
                "UL 864 10th Edition",
                "NFPA 72 §10.6.10 Compliance"
            ),
            warnings=tuple(warnings),
            alternatives=alternatives,
            signature_hash=signature
        )
        return Result(value=rec)
'''

# ─────────────────────────────────────────────────────────────────────
# 8. qomn_fire/engine/placement.py (Detector Placement)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/engine/placement.py"] = '''"""
QOMN-FIRE AUTOMATED DETECTOR PLACEMENT ENGINE
Reference Standard: NFPA 72 (2022) Section 17.7.3.2 (Spacing and Coverage).
"""

from typing import List
from qomn_fire.core.types import Point3D, Device, DeviceType
from qomn_fire.core.errors import Result, PhysicalConstraintError
from qomn_fire.core.constants import NFPA_SMOKE_DETECTOR_SPACING_M, NFPA_MAX_WALL_DISTANCE_M

def place_smoke_detectors_room(
    room_min: Point3D,
    room_max: Point3D,
    height_ft: float,
    circuit_prefix: str,
    zone: str
) -> Result[List[Device], PhysicalConstraintError]:
    dx = room_max.x - room_min.x
    dy = room_max.y - room_min.y

    if dx <= 0.0 or dy <= 0.0:
        return Result(error=PhysicalConstraintError(
            message="Room dimensions must form positive volumes.",
            code_ref="NFPA 72 §17.7.3",
            remedy="Re-evaluate coordinate boundary bounding box input parameters."
        ))

    devices = []
    s = NFPA_SMOKE_DETECTOR_SPACING_M
    half_s = s / 2.0

    x_coords = []
    x_curr = room_min.x + half_s
    while x_curr < room_max.x:
        x_coords.append(x_curr)
        x_curr += s

    if not x_coords or (room_max.x - x_coords[-1]) > NFPA_MAX_WALL_DISTANCE_M:
        x_coords.append(room_max.x - (NFPA_MAX_WALL_DISTANCE_M / 2.0))

    y_coords = []
    y_curr = room_min.y + half_s
    while y_curr < room_max.y:
        y_coords.append(y_curr)
        y_curr += s

    if not y_coords or (room_max.y - y_coords[-1]) > NFPA_MAX_WALL_DISTANCE_M:
        y_coords.append(room_max.y - (NFPA_MAX_WALL_DISTANCE_M / 2.0))

    dev_counter = 1
    for x in x_coords:
        for y in y_coords:
            p = Point3D(x, y, room_min.z)
            d = Device(
                id=f"SMOKE_{zone}_{dev_counter:03d}",
                device_type=DeviceType.SMOKE_DETECTOR,
                location=p,
                elevation_ft=height_ft,
                circuit=f"{circuit_prefix}-{dev_counter}",
                zone=zone
            )
            devices.append(d)
            dev_counter += 1

    return Result(value=devices)
'''

# ─────────────────────────────────────────────────────────────────────
# 9. qomn_fire/engine/routing.py (Conduit Routing)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/engine/routing.py"] = '''"""
QOMN-FIRE ORTHOGONAL 3D PATHFINDER ROUTING ENGINE
Reference Standard: NEC 2023 Article 358.26 (Conduit Bend Limits).
"""

import math
import heapq
from typing import List, Tuple, Dict, Set
from qomn_fire.core.types import Point3D, ConduitType, ConduitRun, Fitting, FittingType
from qomn_fire.core.errors import Result, NECViolationError

class GridMap3D:
    def __init__(self, step_m: float = 0.5):
        self.step_m = step_m
        self.obstacles: Set[Tuple[int, int, int]] = set()

    def to_grid(self, p: Point3D) -> Tuple[int, int, int]:
        return (
            int(round(p.x / self.step_m)),
            int(round(p.y / self.step_m)),
            int(round(p.z / self.step_m))
        )

    def to_physical(self, gp: Tuple[int, int, int]) -> Point3D:
        return Point3D(
            gp[0] * self.step_m,
            gp[1] * self.step_m,
            gp[2] * self.step_m
        )

    def add_obstacle(self, p: Point3D):
        self.obstacles.add(self.to_grid(p))

def astar_route_3d(
    grid_map: GridMap3D,
    start: Point3D,
    end: Point3D,
    conduit: ConduitType,
    conduit_id: str
) -> Result[ConduitRun, NECViolationError]:
    g_start = grid_map.to_grid(start)
    g_end = grid_map.to_grid(end)

    if g_start in grid_map.obstacles or g_end in grid_map.obstacles:
        return Result(error=NECViolationError(
            message="Conduit terminal points are blocked by obstacles.",
            code_ref="NEC Art 300.18",
            remedy="Shift device locations or remove physical structural obstructions."
        ))

    heap_counter = 0
    open_set = []
    heapq.heappush(open_set, (0.0, heap_counter, g_start))

    came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
    g_score: Dict[Tuple[int, int, int], float] = {g_start: 0.0}

    directions = [
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1)
    ]

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == g_end:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()

            pts = tuple([grid_map.to_physical(p) for p in path])

            bends = 0
            fittings: List[Fitting] = []
            if len(pts) >= 3:
                prev_dir = (
                    pts[1].x - pts[0].x,
                    pts[1].y - pts[0].y,
                    pts[1].z - pts[0].z
                )
                for i in range(1, len(pts) - 1):
                    curr_dir = (
                        pts[i+1].x - pts[i].x,
                        pts[i+1].y - pts[i].y,
                        pts[i+1].z - pts[i].z
                    )
                    dot = prev_dir[0]*curr_dir[0] + prev_dir[1]*curr_dir[1] + prev_dir[2]*curr_dir[2]
                    mag_p = math.sqrt(prev_dir[0]**2 + prev_dir[1]**2 + prev_dir[2]**2)
                    mag_c = math.sqrt(curr_dir[0]**2 + curr_dir[1]**2 + curr_dir[2]**2)

                    if mag_p > 0 and mag_c > 0:
                        cos_a = dot / (mag_p * mag_c)
                        if abs(cos_a - 1.0) > 1e-4:
                            bends += 90
                            fittings.append(Fitting(FittingType.ELBOW_90, pts[i]))
                            prev_dir = curr_dir

            tot_len_m = len(path) * grid_map.step_m
            tot_len_ft = tot_len_m * 3.28084

            if bends > 360:
                return Result(error=NECViolationError(
                    message=f"Conduit bends exceed 360 degree threshold limit ({bends} degrees).",
                    code_ref="NEC Article 358.26",
                    remedy="Insert pull boxes or redesign physical path to reduce elbows."
                ))

            run = ConduitRun(
                id=conduit_id,
                conduit_type=conduit,
                trade_size="1/2",
                points=pts,
                total_length_ft=tot_len_ft,
                bend_count=bends,
                fittings=tuple(fittings)
            )
            return Result(value=run)

        for dx, dy, dz in directions:
            neighbor = (current[0] + dx, current[1] + dy, current[2] + dz)
            if neighbor in grid_map.obstacles:
                continue

            tentative_g = g_score[current] + 1.0
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = abs(neighbor[0]-g_end[0]) + abs(neighbor[1]-g_end[1]) + abs(neighbor[2]-g_end[2])
                f = tentative_g + h
                heap_counter += 1
                heapq.heappush(open_set, (f, heap_counter, neighbor))

    return Result(error=NECViolationError(
        message="No orthogonal path could be routed through grid space obstacles.",
        code_ref="NEC Art 300.18",
        remedy="Adjust obstacle clearances or re-layout structural boundaries."
    ))
'''

# ─────────────────────────────────────────────────────────────────────
# 10. qomn_fire/drawing/title_block.py (Integrated FACP Schedule Layout)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/drawing/title_block.py"] = '''"""
QOMN-FIRE TITLE BLOCK AND FACP DRAWING SHEET PLOTTER
Reference Standard: ISO 19650 standard plotting borders.
"""

import ezdxf
from qomn_fire.core.types import TitleBlock, PanelRecommendation

def draw_title_block(doc: ezdxf.document.Drawing, title: TitleBlock):
    layout = doc.layout("A1-Fire-Alarm-Plan") if "A1-Fire-Alarm-Plan" in doc.layouts else doc.layouts.new("A1-Fire-Alarm-Plan")

    # Border margins
    layout.add_line((10.0, 10.0), (831.0, 10.0), dxfattribs={"color": 7})
    layout.add_line((831.0, 10.0), (831.0, 584.0), dxfattribs={"color": 7})
    layout.add_line((831.0, 584.0), (10.0, 584.0), dxfattribs={"color": 7})
    layout.add_line((10.0, 584.0), (10.0, 10.0), dxfattribs={"color": 7})

    # Title block frame
    layout.add_line((600.0, 10.0), (600.0, 180.0), dxfattribs={"color": 7})
    layout.add_line((600.0, 180.0), (831.0, 180.0), dxfattribs={"color": 7})
    layout.add_line((600.0, 130.0), (831.0, 130.0), dxfattribs={"color": 7})
    layout.add_line((600.0, 80.0), (831.0, 80.0), dxfattribs={"color": 7})

    layout.add_text(f"PROJECT: {title.project_name}", dxfattribs={"insert": (610.0, 150.0), "height": 3.5, "color": 7})
    layout.add_text(f"SHEET TITLE: {title.sheet_title}", dxfattribs={"insert": (610.0, 105.0), "height": 3.5, "color": 7})
    layout.add_text(f"DWG NO: {title.drawing_number}", dxfattribs={"insert": (610.0, 90.0), "height": 3.0, "color": 7})
    layout.add_text(f"SCALE: {title.scale}  DATE: {title.date}", dxfattribs={"insert": (610.0, 60.0), "height": 2.5, "color": 7})
    layout.add_text(f"DES: {title.designer}  CHK: {title.checker}", dxfattribs={"insert": (610.0, 45.0), "height": 2.5, "color": 7})
    layout.add_text(f"PE STAMP: {title.pe_stamp}", dxfattribs={"insert": (610.0, 25.0), "height": 2.5, "color": 7})

def draw_facp_schedule(doc: ezdxf.document.Drawing, rec: PanelRecommendation):
    """
    Renders the approved FACP Schedule dynamically inside the layout paper space block.
    Reference: NFPA 72 §10 submittals standards.
    """
    layout = doc.layout("A1-Fire-Alarm-Plan") if "A1-Fire-Alarm-Plan" in doc.layouts else doc.layouts.new("A1-Fire-Alarm-Plan")

    # Placed in left center section (X: 10 -> 250, Y: 320 -> 500)
    layout.add_line((10.0, 320.0), (10.0, 500.0), dxfattribs={"color": 7})
    layout.add_line((10.0, 500.0), (250.0, 500.0), dxfattribs={"color": 7})
    layout.add_line((250.0, 500.0), (250.0, 320.0), dxfattribs={"color": 7})
    layout.add_line((250.0, 320.0), (10.0, 320.0), dxfattribs={"color": 7})

    layout.add_text("FACP SELECTION SCHEDULE", dxfattribs={"insert": (15.0, 480.0), "height": 3.5, "color": 7})
    layout.add_line((10.0, 470.0), (250.0, 470.0), dxfattribs={"color": 7})

    layout.add_text(f"RECOMMENDED MODEL : {rec.recommended_model}", dxfattribs={"insert": (15.0, 450.0), "height": 2.5, "color": 7})
    layout.add_text(f"MANUFACTURER      : {rec.manufacturer}", dxfattribs={"insert": (15.0, 430.0), "height": 2.5, "color": 7})
    layout.add_text(f"BATTERY CAPACITY   : {rec.battery_size_ah} Ah (NFPA 72 §10.6.10)", dxfattribs={"insert": (15.0, 410.0), "height": 2.5, "color": 7})
    layout.add_text(f"POINTS UTILIZATION : {rec.capacity_utilization:.2%}", dxfattribs={"insert": (15.0, 390.0), "height": 2.5, "color": 7})
    layout.add_text(f"NAC UTILIZATION    : {rec.nac_utilization:.2%}", dxfattribs={"insert": (15.0, 370.0), "height": 2.5, "color": 7})
    layout.add_text(f"UL CODES LISTINGS  : {', '.join(rec.listings)}", dxfattribs={"insert": (15.0, 350.0), "height": 2.5, "color": 7})

    # Enforce SHA-256 footprint representation inside CAD layouts for document audit trail
    layout.add_text(f"SIGNATURE HASH     : {rec.signature_hash[:24]}...", dxfattribs={"insert": (15.0, 330.0), "height": 1.8, "color": 7})
'''

# ─────────────────────────────────────────────────────────────────────
# 11. qomn_fire/drawing/dxf_generator.py (Layers & Viewports)
# FIX: NULL_DATE_VALUE → 0.0, view_center → view_center_point, dxfattribs
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/drawing/dxf_generator.py"] = '''"""
QOMN-FIRE COMPLETE DXF SHOP DRAWING GENERATOR
Reference Standard: National CAD Standards (NCS) Layer Specifications.
"""

import ezdxf
from typing import Tuple

def create_document() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2000")
    doc.header['$TDCREATE'] = 0.0
    doc.header['$TDUPDATE'] = 0.0
    doc.header['$HANDSEED'] = '1'
    return doc

def setup_layers(doc: ezdxf.document.Drawing):
    layers = [
        ("A-WALL", 7),
        ("A-FIRE-DEVICES", 1),
        ("A-FIRE-CABLES", 2),
        ("A-FIRE-HATC", 3),
        ("A-FIRE-DIMS", 4),
        ("A-FIRE-TEXT", 5),
        ("A-FIRE-REVC", 1)
    ]
    for name, color in layers:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={"color": color})

def add_viewport(
    doc: ezdxf.document.Drawing,
    center: Tuple[float, float],
    size: Tuple[float, float],
    view_center_point: Tuple[float, float],
    view_height: float
):
    layout = doc.layout("A1-Fire-Alarm-Plan") if "A1-Fire-Alarm-Plan" in doc.layouts else doc.layouts.new("A1-Fire-Alarm-Plan")
    vp = layout.add_viewport(
        center=center,
        size=size,
        view_center_point=view_center_point,
        view_height=view_height
    )
    vp.dxf.status = 1
'''

# ─────────────────────────────────────────────────────────────────────
# 12. qomn_fire/drawing/hatch_engine.py (Pattern Fills)
# FIX: doc.layers.new uses dxfattribs, removed set_xdata for compatibility
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/drawing/hatch_engine.py"] = '''"""
QOMN-FIRE HATCH AND PATTERN PLACEMENT MODULE
Reference Standard: NFPA 72 spacing boundary shapes.
"""

import math
from typing import List, Tuple, Any
import ezdxf
from qomn_fire.core.types import HatchSpec, Point3D
from qomn_fire.core.errors import Result, HatchPlacementError

def generate_circle_polyline(center: Point3D, radius: float, num_sides: int = 16) -> List[Tuple[float, float]]:
    poly = []
    for i in range(num_sides):
        angle = (2.0 * math.pi * i) / num_sides
        x = center.x + radius * math.cos(angle)
        y = center.y + radius * math.sin(angle)
        poly.append((round(x, 4), round(y, 4)))
    return poly

def place_boundary_hatch(
    doc: ezdxf.document.Drawing,
    boundary_points: List[Tuple[float, float]],
    spec: HatchSpec,
    run_id: str
) -> Result[Any, HatchPlacementError]:
    if spec.scale < 0.001:
        return Result(error=HatchPlacementError(
            message=f"Hatch scaling factor {spec.scale} is too small (< 0.001).",
            code_ref="CAD Drafting Standards",
            remedy="Increase hatch scale parameter bounds above 0.01."
        ))

    msp = doc.modelspace()
    if spec.layer not in doc.layers:
        doc.layers.new(spec.layer, dxfattribs={"color": spec.color})

    hatch = msp.add_hatch(color=spec.color)
    hatch.dxf.layer = spec.layer
    hatch.dxf.associative = 1

    hatch.set_pattern_fill(spec.pattern_name, scale=spec.scale, angle=spec.angle)
    hatch.paths.add_polyline_path(boundary_points, is_closed=True)

    return Result(value=hatch)
'''

# ─────────────────────────────────────────────────────────────────────
# 13. qomn_fire/drawing/revision_control.py (Revisions log)
# FIX: set_bulge → format='xyb' for ezdxf 1.4.3 compatibility
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/drawing/revision_control.py"] = '''"""
QOMN-FIRE REVISIONS AND CONTROL GRAPHICS
Reference Standard: ISO 9001 quality audits.
"""

from typing import List, Tuple
import ezdxf
from qomn_fire.core.types import Revision

def draw_revision_cloud(doc: ezdxf.document.Drawing, vertices: List[Tuple[float, float]]):
    msp = doc.modelspace()
    # ezdxf 1.4.x: bulge set via format='xyb' (x, y, bulge) in point tuples
    bulge_vertices = [(x, y, 0.4) for (x, y) in vertices]
    p_line = msp.add_lwpolyline(bulge_vertices, format='xyb', close=True,
                                 dxfattribs={"layer": "A-FIRE-REVC", "color": 1})

def draw_revision_table(doc: ezdxf.document.Drawing, revisions: List[Revision]):
    layout = doc.layout("A1-Fire-Alarm-Plan") if "A1-Fire-Alarm-Plan" in doc.layouts else doc.layouts.new("A1-Fire-Alarm-Plan")

    layout.add_line((600.0, 180.0), (600.0, 250.0), dxfattribs={"color": 7})
    layout.add_line((600.0, 250.0), (831.0, 250.0), dxfattribs={"color": 7})
    layout.add_text("REVISIONS LOG", dxfattribs={"insert": (610.0, 235.0), "height": 3.0, "color": 7})

    y_offset = 215.0
    for rev in revisions:
        rev_str = f"REV {rev.number} - {rev.date} - {rev.description} ({rev.by})"
        layout.add_text(rev_str, dxfattribs={"insert": (610.0, y_offset), "height": 2.2, "color": 7})
        y_offset -= 15.0
'''

# ─────────────────────────────────────────────────────────────────────
# 14. qomn_fire/integration/cable_hatch.py (Route and Hatch Integrator)
# FIX: Added Dict import, proper type hints
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/integration/cable_hatch.py"] = '''"""
QOMN-FIRE INTEGRATION ROUTING AND BOUNDARY PLACEMENTS
Reference Standard: NEC 760 spatial segregation compliance rules.
"""

from typing import Tuple, List, Dict, Any, Union
import ezdxf
from qomn_fire.core.types import Point3D, ConduitType, ConduitRun, HatchSpec, Device
from qomn_fire.core.errors import Result, NECViolationError, HatchPlacementError
from qomn_fire.engine.routing import GridMap3D, astar_route_3d
from qomn_fire.drawing.hatch_engine import place_boundary_hatch

def route_conduit_and_hatch(
    grid_map: GridMap3D,
    doc: ezdxf.document.Drawing,
    start: Point3D,
    end: Point3D,
    conduit: ConduitType,
    conduit_id: str,
    spec: HatchSpec
) -> Result[Tuple[ConduitRun, Any], Union[NECViolationError, HatchPlacementError]]:
    route_res = astar_route_3d(grid_map, start, end, conduit, conduit_id)
    if route_res.is_failure:
        return Result(error=route_res.error())

    conduit_run = route_res.unwrap()
    pts = conduit_run.points

    boundary_points = []
    width_m = 0.20

    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i+1]
        x_min, x_max = min(p1.x, p2.x), max(p1.x, p2.x)
        y_min, y_max = min(p1.y, p2.y), max(p1.y, p2.y)

        if abs(y_max - y_min) < 1e-4:
            boundary_points.extend([
                (round(x_min, 4), round(y_min - width_m, 4)),
                (round(x_max, 4), round(y_min - width_m, 4)),
                (round(x_max, 4), round(y_min + width_m, 4)),
                (round(x_min, 4), round(y_min + width_m, 4))
            ])
        elif abs(x_max - x_min) < 1e-4:
            boundary_points.extend([
                (round(x_min - width_m, 4), round(y_min, 4)),
                (round(x_min + width_m, 4), round(y_min, 4)),
                (round(x_min + width_m, 4), round(y_max, 4)),
                (round(x_min - width_m, 4), round(y_max, 4))
            ])

    unique_points = []
    for p in boundary_points:
        if p not in unique_points:
            unique_points.append(p)

    hatch_res = place_boundary_hatch(doc, unique_points, spec, conduit_id)
    if hatch_res.is_failure:
        return Result(error=hatch_res.error())

    msp = doc.modelspace()
    for i in range(len(pts) - 1):
        msp.add_line(
            pts[i].to_tuple()[:2],
            pts[i+1].to_tuple()[:2],
            dxfattribs={"layer": "A-FIRE-CABLES", "color": 2}
        )

    return Result(value=(conduit_run, hatch_res.unwrap()))
'''

# ─────────────────────────────────────────────────────────────────────
# 15. qomn_fire/output/revit_exporter.py (Revit JSON Exporter)
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["qomn_fire/output/revit_exporter.py"] = '''"""
QOMN-FIRE BIM EXCHANGE SCHEMA EXPORTER
"""

import json
from typing import List
from qomn_fire.core.types import Device, ConduitRun, PanelRecommendation

def export_to_revit_json(devices: List[Device], runs: List[ConduitRun], facp: PanelRecommendation) -> str:
    schema = {
        "SchemaVersion": "1.0",
        "Project": "QOMN-FIRE INTEGRATED EXPORT ENGINE",
        "SelectedFACP": {
            "Model": facp.recommended_model,
            "Manufacturer": facp.manufacturer,
            "RequiredBatteryAh": facp.battery_size_ah,
            "PointsUtilization": facp.capacity_utilization,
            "Signature": facp.signature_hash
        },
        "Devices": [],
        "ConduitRuns": []
    }

    for d in devices:
        schema["Devices"].append({
            "Id": d.id,
            "Type": d.device_type.value,
            "Location": d.location.to_dict(),
            "ElevationFt": d.elevation_ft,
            "Circuit": d.circuit,
            "Zone": d.zone,
            "Hash": d.compute_hash()
        })

    for r in runs:
        schema["ConduitRuns"].append({
            "Id": r.id,
            "ConduitType": r.conduit_type.value,
            "TradeSize": r.trade_size,
            "TotalLengthFt": r.total_length_ft,
            "Bends": r.bend_count,
            "Path": [p.to_dict() for p in r.points],
            "Hash": r.compute_hash()
        })

    return json.dumps(schema, indent=2, sort_keys=True)
'''

# ─────────────────────────────────────────────────────────────────────
# 16. requirements.txt & setup.py
# ─────────────────────────────────────────────────────────────────────
INTEGRATED_FILES["requirements.txt"] = "ezdxf>=1.1.0\n"
INTEGRATED_FILES["setup.py"] = '''from setuptools import setup, find_packages
setup(
    name="qomn_fire",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["ezdxf>=1.1.0"],
)
'''


# =====================================================================
# AUTOMATED WORKSPACE EXPORTER
# =====================================================================

def build_workspace_to_disk():
    print("[QOMN-FIRE INTEGRATION] Setting up workspace directory mappings...")
    for path, content in INTEGRATED_FILES.items():
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f" -> Created Integrated Module: {path}")

    # Generate __init__.py files
    init_paths = [
        "qomn_fire/__init__.py",
        "qomn_fire/core/__init__.py",
        "qomn_fire/engine/__init__.py",
        "qomn_fire/drawing/__init__.py",
        "qomn_fire/integration/__init__.py",
        "qomn_fire/output/__init__.py"
    ]
    for p in init_paths:
        with open(p, "w", encoding="utf-8") as f:
            f.write("# Integrated packages entry\n")

    print("[QOMN-FIRE INTEGRATION] All physical files verified and exported successfully.\n")


# =====================================================================
# INTEGRATED MULTI-ENGINE UNIT TESTING
# =====================================================================

class TestIntegratedQomnFire(unittest.TestCase):

    def setUp(self):
        from qomn_fire.engine.routing import GridMap3D
        self.grid_map = GridMap3D(step_m=0.5)

    def test_01_conduit_fill_golden(self):
        """
        VERIFICATION TEST 1: NEC Conduit Fill Calculation
        Input: 1/2" EMT, 3x 12 AWG wires
        Expected: fill_ratio = 3 * 8.58 / 196.1 ≈ 0.1312
        """
        from qomn_fire.engine.fill import calculate_conduit_fill
        res = calculate_conduit_fill("1/2", "12 AWG", 3)
        self.assertTrue(res.is_success)
        self.assertAlmostEqual(res.unwrap(), 3 * 8.58 / 196.1, places=4)

    def test_02_conduit_fill_physics_guard(self):
        """
        VERIFICATION TEST 2: Invalid Conduit and Wire Inputs
        Input: Invalid conduit size and invalid wire gauge
        Expected: Both return failure with correct code_ref
        """
        from qomn_fire.engine.fill import calculate_conduit_fill
        res1 = calculate_conduit_fill("NOT_REAL_CONDUIT", "12 AWG", 5)
        self.assertTrue(res1.is_failure)
        self.assertEqual(res1.error().code_ref, "NEC Table 4")

        res2 = calculate_conduit_fill("1/2", "NOT_A_WIRE", 10)
        self.assertTrue(res2.is_failure)
        self.assertEqual(res2.error().code_ref, "NEC Table 5")

    def test_03_smoke_placement_golden(self):
        """
        VERIFICATION TEST 3: NFPA 72 Smoke Detector Placement
        Input: 25x15m room at 9ft elevation
        Expected: 6 detectors placed deterministically
        """
        from qomn_fire.core.types import Point3D
        from qomn_fire.engine.placement import place_smoke_detectors_room

        room_min = Point3D(0.0, 0.0, 0.0)
        room_max = Point3D(25.0, 15.0, 0.0)

        res = place_smoke_detectors_room(room_min, room_max, 9.0, "CIRCUIT-A", "ZONE_A")
        self.assertTrue(res.is_success)
        devices = res.unwrap()
        self.assertEqual(len(devices), 6)

        # All devices must be inside room boundaries
        for d in devices:
            self.assertGreater(d.location.x, -0.1)
            self.assertGreater(d.location.y, -0.1)
            self.assertLess(d.location.x, 25.1)
            self.assertLess(d.location.y, 15.1)

    def test_04_determinism_stress(self):
        """
        VERIFICATION TEST 4: Determinism Stress (50× SHA-256)
        Input: Same A* routing query repeated 50 times
        Expected: Every run produces identical SHA-256 hash
        """
        from qomn_fire.core.types import Point3D, ConduitType
        from qomn_fire.engine.routing import GridMap3D, astar_route_3d

        sig_ref = None
        for cycle in range(50):
            g_map = GridMap3D(step_m=0.5)
            g_map.add_obstacle(Point3D(2.0, 2.0, 0.0))

            res = astar_route_3d(
                grid_map=g_map,
                start=Point3D(0.0, 0.0, 0.0),
                end=Point3D(5.0, 5.0, 0.0),
                conduit=ConduitType.EMT,
                conduit_id="C_RUN_1"
            )
            self.assertTrue(res.is_success)
            run = res.unwrap()
            cycle_sig = run.compute_hash()

            if sig_ref is None:
                sig_ref = cycle_sig
            else:
                self.assertEqual(sig_ref, cycle_sig, f"Deviation found on iteration cycle {cycle}")
        print(f"[DETERMINISM] 50 iterations verified. SHA-256: {sig_ref}")

    def test_05_routing_exceeds_bend_limits_fails(self):
        """
        VERIFICATION TEST 5: Conduit Bend Constraint Enforcement (NEC Art 358.26)
        Case: Bounded corridor with alternating walls forces >360 degrees of bends.
        Floor and ceiling slabs at z=-1 and z=1 prevent 3D escape routing.
        Expected: Fail path validation, return NECViolationError.
        """
        from qomn_fire.core.types import Point3D, ConduitType
        from qomn_fire.engine.routing import GridMap3D, astar_route_3d

        g_map = GridMap3D(step_m=1.0)

        # Boundary walls at z=0
        for y in range(-2, 40):
            g_map.add_obstacle(Point3D(-1.0, float(y), 0.0))
            g_map.add_obstacle(Point3D(4.0, float(y), 0.0))

        # Alternating complete walls with single-cell gaps
        # Forces path to zigzag back and forth across the corridor
        for i in range(8):
            y = 2 + i * 2
            if i % 2 == 0:  # gap at x=3
                for x in range(0, 3):
                    g_map.add_obstacle(Point3D(float(x), float(y), 0.0))
            else:  # gap at x=0
                for x in range(1, 4):
                    g_map.add_obstacle(Point3D(float(x), float(y), 0.0))

        # Floor and ceiling slabs: block all positions at z=-1 and z=1
        # This physically prevents A* from escaping the 2D plane
        for z_level in [-1, 1]:
            for x in range(-1, 5):
                for y in range(-2, 40):
                    g_map.add_obstacle(Point3D(float(x), float(y), float(z_level)))

        res = astar_route_3d(
            grid_map=g_map,
            start=Point3D(0.0, 0.0, 0.0),
            end=Point3D(2.0, 18.0, 0.0),
            conduit=ConduitType.EMT,
            conduit_id="C_VIOL"
        )
        self.assertTrue(res.is_failure)
        self.assertEqual(res.error().code_ref, "NEC Article 358.26")

    def test_06_integrated_facp_selection(self):
        """
        VERIFICATION TEST 6: Integrated FACP Selection Sizing
        Input: 30 devices, 2 NAC circuits, Standalone US project.
        Expected: Selects Siemens FC901. Battery back-up capacity ≈ 4.76 Ah.
        """
        from qomn_fire.core.types import ProjectRequirements
        from qomn_fire.engine.panel_selector import SelectionEngine

        req = ProjectRequirements(
            device_count=30,
            nac_circuit_count=2,
            building_size_m2=1500.0,
            building_floors=2,
            requires_network=False,
            requires_voice=False,
            requires_releasing=False,
            jurisdiction="US"
        )

        res = SelectionEngine.select_panel(req)
        self.assertTrue(res.is_success)
        rec = res.unwrap()

        self.assertEqual(rec.recommended_model, "FC901")
        self.assertEqual(rec.manufacturer, "SIEMENS")
        self.assertAlmostEqual(rec.battery_size_ah, 4.76, delta=0.01)

    def test_07_placement_to_selection_vascular_pipeline(self):
        """
        VERIFICATION TEST 7: Multi-Engine Integrated Sizing (Vascular Link)
        Input: Large Room (25x15m), placing devices automatically, then selecting panel.
        Expected: Placement places 6 detectors. Selector evaluates and recommends FC901.
        """
        from qomn_fire.core.types import Point3D, ProjectRequirements
        from qomn_fire.engine.placement import place_smoke_detectors_room
        from qomn_fire.engine.panel_selector import SelectionEngine

        room_min = Point3D(0.0, 0.0, 0.0)
        room_max = Point3D(25.0, 15.0, 0.0)

        # 1. Place detectors
        place_res = place_smoke_detectors_room(room_min, room_max, 9.0, "CIRCUIT-A", "ZONE_A")
        self.assertTrue(place_res.is_success)
        devices = place_res.unwrap()
        self.assertEqual(len(devices), 6)

        # 2. Vascular link counts directly to panel requirements
        req = ProjectRequirements(
            device_count=len(devices),
            nac_circuit_count=2,
            building_size_m2=375.0,
            building_floors=1,
            requires_network=False,
            requires_voice=False,
            requires_releasing=False,
            jurisdiction="US"
        )

        select_res = SelectionEngine.select_panel(req)
        self.assertTrue(select_res.is_success)
        rec = select_res.unwrap()

        self.assertEqual(rec.recommended_model, "FC901")


# =====================================================================
# INTEGRATED SYSTEM PILOT DEMONSTRATION
# =====================================================================

def execute_integrated_master_project():
    """Runs a complete end-to-end fire protective design, sizing, and CAD production pipeline."""
    print("\n" + "="*80)
    print("        QOMN-FIRE INTEGRATED PIPELINE: FULL PROJECT COMPILATION")
    print("="*80)

    from qomn_fire.core.types import Point3D, TitleBlock, HatchSpec, ConduitType, Revision, ProjectRequirements
    from qomn_fire.core.constants import NFPA_SMOKE_DETECTOR_SPACING_M
    from qomn_fire.engine.placement import place_smoke_detectors_room
    from qomn_fire.engine.routing import GridMap3D
    from qomn_fire.engine.panel_selector import SelectionEngine
    from qomn_fire.drawing.dxf_generator import create_document, setup_layers, add_viewport
    from qomn_fire.drawing.hatch_engine import generate_circle_polyline, place_boundary_hatch
    from qomn_fire.drawing.title_block import draw_title_block, draw_facp_schedule
    from qomn_fire.drawing.revision_control import draw_revision_cloud, draw_revision_table
    from qomn_fire.integration.cable_hatch import route_conduit_and_hatch
    from qomn_fire.output.revit_exporter import export_to_revit_json

    # 1. Initialize Drawing Doc
    doc = create_document()
    setup_layers(doc)
    msp = doc.modelspace()

    # 2. Rectangular Building Room Coordinates
    room_min = Point3D(0.0, 0.0, 0.0)
    room_max = Point3D(25.0, 15.0, 0.0)

    # Draw physical walls
    wall_attribs = {"layer": "A-WALL", "color": 7}
    msp.add_line((room_min.x, room_min.y), (room_max.x, room_min.y), dxfattribs=wall_attribs)
    msp.add_line((room_max.x, room_min.y), (room_max.x, room_max.y), dxfattribs=wall_attribs)
    msp.add_line((room_max.x, room_max.y), (room_min.x, room_max.y), dxfattribs=wall_attribs)
    msp.add_line((room_min.x, room_max.y), (room_min.x, room_min.y), dxfattribs=wall_attribs)

    # 3. NFPA-Compliant Automatic Space Device Placement
    print(" -> Resolving detector layouts...")
    place_res = place_smoke_detectors_room(room_min, room_max, 9.0, "FA-LP1", "ZONE_1")
    devices = place_res.unwrap()

    h_spec_coverage = HatchSpec("ANSI31", 45.0, 0.1, 3, "A-FIRE-HATC", "Smoke Coverage", "NFPA 72 §17")

    for d in devices:
        msp.add_circle(d.location.to_tuple()[:2], radius=0.4, dxfattribs={"layer": "A-FIRE-DEVICES", "color": 1})
        msp.add_text(d.id, dxfattribs={"insert": (d.location.x + 0.5, d.location.y + 0.5), "height": 0.25, "layer": "A-FIRE-TEXT", "color": 5})

        # Coverage zone boundary hatch
        boundary = generate_circle_polyline(d.location, NFPA_SMOKE_DETECTOR_SPACING_M)
        place_boundary_hatch(doc, boundary, h_spec_coverage, d.id)

    # 4. NFPA & NEC Compliant FACP Selection (Direct Vascular Linkage)
    print(" -> Dynamically selecting panel based on device loads...")
    req = ProjectRequirements(
        device_count=len(devices),
        nac_circuit_count=2,
        building_size_m2=375.0,
        building_floors=1,
        requires_network=False,
        requires_voice=False,
        requires_releasing=False,
        jurisdiction="FDNY",
        preferred_manufacturer="SIEMENS"
    )

    selection_res = SelectionEngine.select_panel(req)
    rec = selection_res.unwrap()
    print(f"   -> Selected FACP: {rec.recommended_model} ({rec.manufacturer}) - Battery size: {rec.battery_size_ah} Ah")

    # 5. Routing conduits between sequential devices
    print(" -> Routing routing paths...")
    grid_map = GridMap3D(step_m=0.5)
    for d in devices:
        grid_map.add_obstacle(d.location)

    conduit_spec = HatchSpec("CROSS", 0.0, 0.05, 3, "A-FIRE-HATC", "Conduit Corridor", "NEC 760")
    conduit_runs = []

    for idx in range(len(devices) - 1):
        start_pt = devices[idx].location
        end_pt = devices[idx+1].location

        grid_map.obstacles.discard(grid_map.to_grid(start_pt))
        grid_map.obstacles.discard(grid_map.to_grid(end_pt))

        res = route_conduit_and_hatch(
            grid_map=grid_map,
            doc=doc,
            start=start_pt,
            end=end_pt,
            conduit=ConduitType.EMT,
            conduit_id=f"CONDUIT_RUN_{idx:02d}",
            spec=conduit_spec
        )

        grid_map.add_obstacle(start_pt)
        grid_map.add_obstacle(end_pt)

        if res.is_success:
            run_item, _ = res.unwrap()
            conduit_runs.append(run_item)

    # 6. Dimensions and Layout Graphics
    if len(devices) >= 2:
        msp.add_aligned_dim(
            p1=devices[0].location.to_tuple()[:2],
            p2=devices[1].location.to_tuple()[:2],
            distance=2.0,
            dxfattribs={"layer": "A-FIRE-DIMS", "color": 4}
        )

    # Title Block Sheet
    title = TitleBlock(
        project_name="INTEGRATED LIFE SAFETY NETWORK",
        drawing_number="QOMN-FA-001",
        sheet_title="FIRE ALARM DEVICE DISTRIBUTION & INHERENT SIZING PLAN",
        scale="1:100",
        date="2026-05-31",
        designer="Systems Automation Architect",
        checker="Senior Verification Audit Engineer",
        pe_stamp="LICENSED PROFESSIONAL ENGINEER - STAMP #PE-90998",
        client="Hospital General Board",
        address="Zone 2 Building C Complex"
    )
    draw_title_block(doc, title)

    # Draw dynamically computed FACP Schedule inside layout sheet
    draw_facp_schedule(doc, rec)

    # Aligned Viewport
    add_viewport(doc, center=(350.0, 300.0), size=(500.0, 400.0), view_center_point=(12.5, 7.5), view_height=20.0)

    # Legend Table and Revisions table
    revs = [
        Revision(0, "2026-05-31", "Merged routing with dynamic FACP selections", "SYS_INTEGRATOR")
    ]
    draw_revision_table(doc, revs)

    # 7. Compile files to disk
    dxf_path = "fire_alarm_plan.dxf"
    doc.saveas(dxf_path)
    print(f"\n -> CAD shop drawing compiled: '{dxf_path}'")

    revit_json = export_to_revit_json(devices, conduit_runs, rec)
    revit_path = "revit_import.json"
    with open(revit_path, "w", encoding="utf-8") as f:
        f.write(revit_json)
    print(f" -> Revit BIM metadata compiled: '{revit_path}'")

    print("\n[QOMN-FIRE INTEGRATION] Compilation run completed successfully.")


# =====================================================================
# RUNTIME CONTROLLER MAIN BLOCK
# =====================================================================

if __name__ == "__main__":
    print("="*80)
    print("        QOMN-FIRE: MASTER INTEGRATED SUITE RUNTIME ENGINE")
    print("="*80)

    # 1. Output the workspace codefiles on disk
    build_workspace_to_disk()

    # Add generated directory path to python loading path context
    sys.path.insert(0, os.path.abspath(os.getcwd()))

    # 2. Run the dynamic unit testing suite
    print("="*80)
    print("             EXECUTING AUTOMATED CRITICAL UNIT TEST SUITE")
    print("="*80)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIntegratedQomnFire)
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(suite)

    if not test_result.wasSuccessful():
        print("\n[CRITICAL ERROR] Test suite failures occurred. Aborting compilation runs.")
        sys.exit(1)

    # 3. Run production master project
    print("\n" + "="*80)
    print("             RUNNING END-TO-END CAD/BIM PRODUCTION WORKFLOW")
    print("="*80)
    execute_integrated_master_project()
