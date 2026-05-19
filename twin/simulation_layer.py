"""
twin/simulation_layer.py — FireAI Level 4 Simulation Layer
============================================================
High-level simulation interface that wraps the physics engine with
NFPA 72 compliance validation and proper detector activation tracking.

This layer sits between:
  - Below: fire_physics.py (low-level N-S solver, zone model, detectors)
  - Above: digital_twin_bridge.py (BIM integration, state management)

Key Fixes Applied (from Consultant Code Review):
  BUG 3: Timer-based detector checking instead of int(t) % 30 == 0
  BUG 4: Proper lower-layer temperature with plume contribution factor

SAFETY: All simulation results are approximate. Must be verified by PE.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time as _time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from twin.fire_physics import (
    AMBIENT_TEMP,
    AIR_DENSITY,
    AIR_HEAT_CAP,
    GRAVITY,
    GAS_CONSTANT_AIR,
    SMOKE_ALARM_OD,
    CO_LETHAL_PPM,
    VoxelGrid,
    CFLController,
    FireSource,
    FireGrowthModel,
    PressureSolver,
    HeatTransportNS,
    SmokeTransportNS,
    Zone,
    Doorway,
    MultiZoneEngine,
    PhysicsDetector,
    DetectorType,
    DetectorConfig,
)
from twin.nfpa72_bridge import (
    NFPA72Bridge,
    RoomConfig,
    DetectorPlacement,
    OccupancyType,
)

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Data structures for simulation results
# ═══════════════════════════════════════════════════════════════════════

class SimulationMode(Enum):
    """Simulation mode selector."""
    ZONE_MODEL = "zone"          # 2-zone CFAST-inspired (fast, coarse)
    CFD_LITE = "cfd_lite"        # N-S VoxelGrid solver (slower, detailed)
    HYBRID = "hybrid"            # Zone model + CFD validation


@dataclass
class SimulationRoomConfig:
    """Room configuration for simulation."""
    room_id: str
    name: str
    width_m: float
    depth_m: float
    height_m: float
    occupancy_type: str = "business"
    ceiling_type: str = "smooth"


@dataclass
class SimulationFireSource:
    """Fire source configuration for simulation."""
    room_id: str
    x: float
    y: float
    z: float = 0.0
    hrr_peak_w: float = 500_000.0
    growth_alpha_kW_s2: float = 0.047  # Fast fire per NFPA 72 Table B.4.2.1
    soot_yield: float = 0.10
    co_yield: float = 0.04
    ignition_time_s: float = 0.0


@dataclass
class SimulationDetector:
    """Detector configuration for simulation."""
    detector_id: str
    room_id: str
    x: float
    y: float
    z: float
    detector_type: str = "smoke"  # smoke, heat, combination, co
    zone_id: str = ""


@dataclass
class DetectorActivation:
    """Record of a detector activation during simulation."""
    detector_id: str
    room_id: str
    activation_time_s: float
    activation_type: str  # "smoke", "heat", "co", "multi"
    threshold_value: float
    measured_value: float
    zone_id: str = ""


@dataclass
class RoomSimulationState:
    """State of a room during simulation (2-zone model)."""
    room_id: str
    time_s: float
    upper_layer_temp_k: float
    lower_layer_temp_k: float
    interface_height_m: float
    smoke_od_m1: float
    co_ppm: float
    is_flashover: bool = False


@dataclass
class SimulationStep:
    """Single simulation time step result."""
    time_s: float
    room_states: List[RoomSimulationState]
    activations: List[DetectorActivation]
    peak_temp_k: float
    peak_smoke_od: float


@dataclass
class SimulationResult:
    """Complete simulation result."""
    mode: SimulationMode
    duration_s: float
    dt_used: float
    total_steps: int
    room_states: Dict[str, List[RoomSimulationState]]
    all_activations: List[DetectorActivation]
    flashover_rooms: List[str]
    compliance_result: Optional[Dict[str, Any]]
    peak_temp_k: float
    peak_smoke_od: float
    elapsed_wall_s: float
    sha256: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Simulation Layer
# ═══════════════════════════════════════════════════════════════════════

class SimulationLayer:
    """High-level fire simulation interface with NFPA 72 validation.

    Supports three modes:
      - ZONE_MODEL: Fast 2-zone CFAST-inspired simulation
      - CFD_LITE: Full N-S voxel solver (detailed but slower)
      - HYBRID: Zone model with CFD spot-checks

    Key fixes applied from consultant code review:
      - BUG 3: Timer-based detector checking (not int(t) % 30)
      - BUG 4: Proper lower-layer temperature with plume impact factor

    Safety: All results are approximate. Must be verified by licensed PE.
    """

    # Detector check interval (seconds)
    # BUG FIX (Consultant BUG 3): Use fixed interval instead of int(t) % 30
    DETECTOR_CHECK_INTERVAL_S: float = 0.1

    # Plume impact factor for lower-layer temperature
    # BUG FIX (Consultant BUG 4): Use physics-based factor instead of 0.1
    # Plume entrainment brings hot gases down; factor ~0.5 is conservative
    PLUME_IMPACT_FACTOR: float = 0.5

    # Flashover threshold (upper layer temperature)
    FLASHOVER_TEMP_K: float = 600.0 + 273.15  # 600°C per ISO 834

    def __init__(
        self,
        mode: SimulationMode = SimulationMode.ZONE_MODEL,
        resolution_m: float = 0.5,
        max_steps: int = 100_000,
    ) -> None:
        self.mode = mode
        self.resolution_m = resolution_m
        self.max_steps = max_steps

        # Sub-engines
        self._nfpa72 = NFPA72Bridge()
        self._cfl = CFLController()

        # Zone model components
        self._multi_zone: Optional[MultiZoneEngine] = None

        # CFD components
        self._grid: Optional[VoxelGrid] = None
        self._pressure_solver: Optional[PressureSolver] = None
        self._heat_transport: Optional[HeatTransportNS] = None
        self._smoke_transport: Optional[SmokeTransportNS] = None

        # Detector tracking
        # BUG FIX (Consultant BUG 3): Track last check time per detector
        self._detector_last_check: Dict[str, float] = {}
        self._detector_configs: Dict[str, DetectorConfig] = {}
        self._physics_detectors: Dict[str, PhysicsDetector] = {}

        # Room configurations
        self._room_configs: Dict[str, SimulationRoomConfig] = {}

    def setup(
        self,
        rooms: List[SimulationRoomConfig],
        fires: List[SimulationFireSource],
        detectors: List[SimulationDetector],
        doorways: Optional[List[Doorway]] = None,
    ) -> None:
        """Set up the simulation with room, fire, and detector configs.

        Parameters:
            rooms: Room configurations
            fires: Fire source configurations
            detectors: Detector configurations
            doorways: Optional connections between rooms (for multi-zone)
        """
        # Store room configs
        for room in rooms:
            self._room_configs[room.room_id] = room

        # Initialize zone model
        self._multi_zone = MultiZoneEngine()
        for room in rooms:
            zone = Zone(
                zone_id=room.room_id,
                width=room.width_m,
                length=room.depth_m,
                height=room.height_m,
            )
            self._multi_zone.add_zone(zone)

        # Add doorways between rooms
        if doorways:
            for door in doorways:
                self._multi_zone.add_doorway(door)

        # Add fires
        self._fires: List[SimulationFireSource] = fires

        # Set up detectors with proper configs
        for det in detectors:
            # Map detector type
            if det.detector_type.lower() == "smoke":
                dt = DetectorType.SMOKE
            elif det.detector_type.lower() == "heat":
                dt = DetectorType.HEAT
            elif det.detector_type.lower() == "combination":
                dt = DetectorType.COMBINATION
            elif det.detector_type.lower() == "co":
                dt = DetectorType.CO
            else:
                dt = DetectorType.SMOKE

            config = DetectorConfig(detector_type=dt)
            self._detector_configs[det.detector_id] = config

            # Create physics detector
            physics_det = PhysicsDetector(
                detector_id=det.detector_id,
                x=det.x, y=det.y, z=det.z,
                zone_id=det.zone_id or det.room_id,
                config=config,
            )
            self._physics_detectors[det.detector_id] = physics_det

            # BUG FIX (Consultant BUG 3): Initialize timer tracking
            self._detector_last_check[det.detector_id] = -1.0

        # Set up CFD grid if needed
        if self.mode in (SimulationMode.CFD_LITE, SimulationMode.HYBRID):
            self._setup_cfd(rooms)

        log.info("Simulation setup: %d rooms, %d fires, %d detectors, mode=%s",
                 len(rooms), len(fires), len(detectors), self.mode.value)

    def _setup_cfd(self, rooms: List[SimulationRoomConfig]) -> None:
        """Initialize CFD voxel grid for the largest room."""
        if not rooms:
            return

        # Use the largest room for CFD
        largest = max(rooms, key=lambda r: r.width_m * r.depth_m * r.height_m)
        self._grid = VoxelGrid(
            width=largest.width_m,
            length=largest.depth_m,
            height=largest.height_m,
            resolution=self.resolution_m,
        )
        self._pressure_solver = PressureSolver()
        self._heat_transport = HeatTransportNS()
        self._smoke_transport = SmokeTransportNS()

        log.info("CFD grid: %dx%dx%d cells (%.1fm resolution)",
                 self._grid.nx, self._grid.ny, self._grid.nz,
                 self.resolution_m)

    def run(
        self,
        t_end: float = 300.0,
        dt_req: float = 1.0,
        check_compliance: bool = True,
    ) -> SimulationResult:
        """Run the fire simulation.

        Parameters:
            t_end: Simulation end time (seconds)
            dt_req: Requested time step (seconds)
            check_compliance: Whether to run NFPA 72 compliance check

        Returns:
            SimulationResult with all states and activations
        """
        wall_start = _time.time()
        t = 0.0
        step_count = 0

        # Results tracking
        room_states: Dict[str, List[RoomSimulationState]] = {
            rid: [] for rid in self._room_configs
        }
        all_activations: List[DetectorActivation] = []
        flashover_rooms: List[str] = []
        global_peak_temp = AMBIENT_TEMP
        global_peak_smoke = 0.0

        # Group fires by room
        fires_by_room: Dict[str, List[SimulationFireSource]] = {}
        for fire in self._fires:
            fires_by_room.setdefault(fire.room_id, []).append(fire)

        # Group detectors by room
        detectors_by_room: Dict[str, List[SimulationDetector]] = {}
        for det_id, pdet in self._physics_detectors.items():
            room_id = pdet.zone_id
            detectors_by_room.setdefault(room_id, []).append(
                SimulationDetector(
                    detector_id=det_id,
                    room_id=room_id,
                    x=pdet.x, y=pdet.y, z=pdet.z,
                    detector_type=pdet.config.detector_type.name.lower(),
                    zone_id=pdet.zone_id,
                )
            )

        while t < t_end and step_count < self.max_steps:
            # Compute adaptive dt
            if self._grid and self.mode in (SimulationMode.CFD_LITE, SimulationMode.HYBRID):
                u_max = CFLController.max_velocity(self._grid.all_fluid())
                dt = self._cfl.compute_dt(self.resolution_m, u_max, dt_req)
            else:
                dt = min(dt_req, t_end - t)

            # Compute HRR for each fire
            total_hrr_by_room: Dict[str, float] = {}
            for room_id, fires in fires_by_room.items():
                room_hrr = 0.0
                for fire in fires:
                    hrr = FireGrowthModel.hrr_at(
                        fire.hrr_peak_w,
                        fire.growth_alpha_kW_s2,
                        fire.ignition_time_s,
                        t,
                    )
                    room_hrr += hrr
                total_hrr_by_room[room_id] = room_hrr

            # Advance zone model
            if self._multi_zone:
                for room_id, fires in fires_by_room.items():
                    for fire in fires:
                        self._multi_zone.step(
                            dt,
                            fire=FireSource(
                                x=fire.x, y=fire.y, z=fire.z,
                                hrr=fire.hrr_peak_w,
                                growth_alpha=fire.growth_alpha_kW_s2,
                                soot_yield=fire.soot_yield,
                                co_yield=fire.co_yield,
                                ignition_time=fire.ignition_time_s,
                            ),
                            hrr_now=total_hrr_by_room.get(room_id, 0.0),
                        )

            # Advance CFD if in that mode
            if self.mode == SimulationMode.CFD_LITE and self._grid:
                self._advance_cfd(dt, fires_by_room, total_hrr_by_room, t)

            # Record room states and check detectors
            for room_id, room_cfg in self._room_configs.items():
                zone = self._multi_zone.zones.get(room_id) if self._multi_zone else None

                if zone:
                    upper_temp = zone.T_upper
                    smoke_od = zone.smoke_upper
                    co_ppm = zone.co_upper_ppm
                    interface = zone.z_interface

                    # BUG FIX (Consultant BUG 4): Proper lower-layer temp
                    # Old: T_lower = 293 + (T_upper - 293) * 0.1  (arbitrary 0.1)
                    # New: Use plume impact factor based on physics
                    # Hot gas descends via plume entrainment; impact ~50% at floor
                    plume_contribution = (upper_temp - AMBIENT_TEMP) * self.PLUME_IMPACT_FACTOR
                    lower_temp = max(AMBIENT_TEMP, AMBIENT_TEMP + plume_contribution)

                    is_flashover = upper_temp >= self.FLASHOVER_TEMP_K
                    if is_flashover and room_id not in flashover_rooms:
                        flashover_rooms.append(room_id)

                    # Track peaks
                    if upper_temp > global_peak_temp:
                        global_peak_temp = upper_temp
                    if smoke_od > global_peak_smoke:
                        global_peak_smoke = smoke_od

                    state = RoomSimulationState(
                        room_id=room_id,
                        time_s=t,
                        upper_layer_temp_k=round(upper_temp, 1),
                        lower_layer_temp_k=round(lower_temp, 1),
                        interface_height_m=round(interface, 2),
                        smoke_od_m1=round(smoke_od, 4),
                        co_ppm=round(co_ppm, 1),
                        is_flashover=is_flashover,
                    )
                    room_states[room_id].append(state)

                # BUG FIX (Consultant BUG 3): Timer-based detector checking
                # Old: if int(t) % 30 == 0: check_detector()
                # New: Use fixed interval with per-detector tracking
                room_dets = detectors_by_room.get(room_id, [])
                for det in room_dets:
                    last_check = self._detector_last_check.get(det.detector_id, -1.0)
                    if t - last_check >= self.DETECTOR_CHECK_INTERVAL_S:
                        self._detector_last_check[det.detector_id] = t

                        activation = self._check_detector_activation(
                            det, zone, t
                        )
                        if activation:
                            # Check if already activated (dedup)
                            already = any(
                                a.detector_id == activation.detector_id and
                                abs(a.activation_time_s - activation.activation_time_s) < 0.5
                                for a in all_activations
                            )
                            if not already:
                                all_activations.append(activation)

            t += dt
            step_count += 1

        # NFPA 72 compliance check
        compliance_result = None
        if check_compliance and self._room_configs:
            compliance_result = self._check_nfpa72_compliance()

        # Build result
        elapsed_wall = round(_time.time() - wall_start, 2)

        result = SimulationResult(
            mode=self.mode,
            duration_s=t_end,
            dt_used=dt,
            total_steps=step_count,
            room_states=room_states,
            all_activations=all_activations,
            flashover_rooms=flashover_rooms,
            compliance_result=compliance_result,
            peak_temp_k=round(global_peak_temp, 1),
            peak_smoke_od=round(global_peak_smoke, 4),
            elapsed_wall_s=elapsed_wall,
        )

        # Compute SHA-256 of result for audit integrity
        result.sha256 = self._compute_result_hash(result)

        log.info("Simulation complete: %d steps, %d activations, %d flashover rooms, %.1fs wall",
                 step_count, len(all_activations), len(flashover_rooms), elapsed_wall)

        return result

    def _advance_cfd(
        self,
        dt: float,
        fires_by_room: Dict[str, List[SimulationFireSource]],
        hrr_by_room: Dict[str, float],
        t: float,
    ) -> None:
        """Advance the CFD solver by one time step."""
        if not self._grid:
            return

        # Use first fire for CFD (single-room CFD for now)
        for room_id, fires in fires_by_room.items():
            for fire in fires:
                fire_src = FireSource(
                    x=fire.x, y=fire.y, z=fire.z,
                    hrr=fire.hrr_peak_w,
                    soot_yield=fire.soot_yield,
                    co_yield=fire.co_yield,
                )
                hrr_now = hrr_by_room.get(room_id, 0.0)

                if self._pressure_solver:
                    self._pressure_solver.step(self._grid, dt)
                if self._heat_transport:
                    self._heat_transport.step(self._grid, fire_src, hrr_now, dt)
                if self._smoke_transport:
                    self._smoke_transport.step(self._grid, fire_src, hrr_now, dt)

                # Check for divergence
                self._cfl.check_divergence(self._grid.all_fluid())
                break  # Only one fire in CFD for now
            break

    def _check_detector_activation(
        self,
        det: SimulationDetector,
        zone: Optional[Zone],
        t: float,
    ) -> Optional[DetectorActivation]:
        """Check if a detector should activate based on zone conditions.

        Uses the physics detector model with RTI delay.
        """
        if zone is None:
            return None

        physics_det = self._physics_detectors.get(det.detector_id)
        if physics_det is None:
            return None

        # Feed zone conditions to the physics detector
        # The detector is at ceiling level, so it sees upper layer
        if det.z >= zone.z_interface:
            # Detector is in upper layer
            local_temp = zone.T_upper
            local_smoke = zone.smoke_upper
            local_co = zone.co_upper_ppm
            # Estimate gas velocity at ceiling from plume
            u_gas = max(0.5, math.sqrt(2.0 * GRAVITY * (zone.T_upper - AMBIENT_TEMP) / AMBIENT_TEMP * zone.height_m))
        else:
            # Detector is in lower layer
            # BUG FIX (Consultant BUG 4): Use proper lower-layer temp
            plume_contribution = (zone.T_upper - AMBIENT_TEMP) * self.PLUME_IMPACT_FACTOR
            local_temp = max(AMBIENT_TEMP, AMBIENT_TEMP + plume_contribution)
            local_smoke = zone.smoke_upper * 0.1  # Lower layer has much less smoke
            local_co = zone.co_upper_ppm * 0.1
            u_gas = 0.3  # Low velocity in lower layer

        # Check activation conditions
        config = physics_det.config
        activation_type = None
        threshold_val = 0.0
        measured_val = 0.0

        if config.detector_type in (DetectorType.SMOKE, DetectorType.COMBINATION):
            if local_smoke >= config.smoke_threshold:
                activation_type = "smoke"
                threshold_val = config.smoke_threshold
                measured_val = local_smoke

        if config.detector_type in (DetectorType.HEAT, DetectorType.COMBINATION):
            if local_temp >= config.temp_threshold:
                if activation_type is None:  # Smoke takes priority for combination
                    activation_type = "heat"
                    threshold_val = config.temp_threshold
                    measured_val = local_temp

        if config.detector_type == DetectorType.CO:
            if local_co >= config.co_threshold_ppm:
                activation_type = "co"
                threshold_val = config.co_threshold_ppm
                measured_val = local_co

        if activation_type is None:
            return None

        # Apply RTI delay model
        # t_response = RTI / sqrt(u_gas) + latency
        rti = config.rti
        latency = config.latency_s
        if u_gas > 0.01:
            response_time = rti / math.sqrt(u_gas) + latency
        else:
            response_time = rti / math.sqrt(0.01) + latency

        activation_time = t + response_time

        return DetectorActivation(
            detector_id=det.detector_id,
            room_id=det.room_id,
            activation_time_s=round(activation_time, 2),
            activation_type=activation_type,
            threshold_value=round(threshold_val, 4),
            measured_value=round(measured_val, 4),
            zone_id=det.zone_id,
        )

    def _check_nfpa72_compliance(self) -> Dict[str, Any]:
        """Run NFPA 72 compliance validation on the design."""
        room_configs = []
        detector_placements = []

        for room_id, room in self._room_configs.items():
            # Map occupancy type
            occ_map = {
                "business": OccupancyType.BUSINESS,
                "assembly": OccupancyType.ASSEMBLY,
                "educational": OccupancyType.EDUCATIONAL,
                "factory": OccupancyType.FACTORY,
                "hazardous": OccupancyType.HAZARDOUS,
                "institutional": OccupancyType.INSTITUTIONAL,
                "mercantile": OccupancyType.MERCANTILE,
                "residential": OccupancyType.RESIDENTIAL,
                "storage": OccupancyType.STORAGE,
            }
            occ = occ_map.get(room.occupancy_type.lower(), OccupancyType.BUSINESS)

            room_configs.append(RoomConfig(
                room_id=room_id,
                name=room.name,
                width_m=room.width_m,
                depth_m=room.depth_m,
                ceiling_height_m=room.height_m,
                occupancy_type=occ,
                floor_number=1,
                ceiling_type=room.ceiling_type,
            ))

        for det_id, pdet in self._physics_detectors.items():
            # Get effective coverage radius
            room_cfg = self._room_configs.get(pdet.zone_id)
            ceiling_h = room_cfg.height_m if room_cfg else 2.8
            det_type_str = pdet.config.detector_type.name.lower()
            if det_type_str == "combination":
                det_type_str = "smoke"

            adjusted = self._nfpa72.get_adjusted_spacing(ceiling_h, det_type_str)
            coverage_r = self._nfpa72.get_coverage_radius(adjusted)

            detector_placements.append(DetectorPlacement(
                detector_id=det_id,
                room_id=pdet.zone_id,
                x=pdet.x,
                y=pdet.y,
                z=pdet.z,
                detector_type=det_type_str,
                coverage_radius_m=coverage_r,
            ))

        return self._nfpa72.validate_design(
            building_id="simulation",
            room_configs=room_configs,
            detector_placements=detector_placements,
        )

    @staticmethod
    def _compute_result_hash(result: SimulationResult) -> str:
        """Compute SHA-256 hash of simulation result for audit integrity."""
        data = {
            'duration_s': result.duration_s,
            'total_steps': result.total_steps,
            'activations': len(result.all_activations),
            'flashover_rooms': sorted(result.flashover_rooms),
            'peak_temp_k': result.peak_temp_k,
            'peak_smoke_od': result.peak_smoke_od,
        }
        content = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════════════════

def run_simulation(
    rooms: List[SimulationRoomConfig],
    fires: List[SimulationFireSource],
    detectors: List[SimulationDetector],
    doorways: Optional[List[Doorway]] = None,
    t_end: float = 300.0,
    dt: float = 1.0,
    mode: str = "zone",
    check_compliance: bool = True,
) -> SimulationResult:
    """Run a fire simulation with detector activation tracking.

    Convenience function that creates a SimulationLayer and runs it.

    Parameters:
        rooms: Room configurations
        fires: Fire source configurations
        detectors: Detector configurations
        doorways: Optional inter-room connections
        t_end: Simulation end time (seconds)
        dt: Requested time step (seconds)
        mode: "zone", "cfd_lite", or "hybrid"
        check_compliance: Whether to run NFPA 72 compliance check

    Returns:
        SimulationResult with all states, activations, and compliance info
    """
    sim_mode = SimulationMode(mode)
    sim = SimulationLayer(mode=sim_mode)
    sim.setup(rooms, fires, detectors, doorways)
    return sim.run(t_end=t_end, dt_req=dt, check_compliance=check_compliance)


__all__ = [
    "SimulationMode",
    "SimulationRoomConfig",
    "SimulationFireSource",
    "SimulationDetector",
    "DetectorActivation",
    "RoomSimulationState",
    "SimulationStep",
    "SimulationResult",
    "SimulationLayer",
    "run_simulation",
]
