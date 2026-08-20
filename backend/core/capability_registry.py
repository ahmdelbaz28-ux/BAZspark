"""backend/core/capability_registry.py — Capability Discovery and Schema Registry.

Frozen Phase 1 Architecture:
- The LLM receives capabilities (tools), not authority.
- Dynamic capability discovery with strict category/scope filtering.
- For Phase 1, exposes exactly:
    - spatial.place_devices
    - compliance.verify_detector_spacing
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fireai.core.device_placement import (
    CeilingType,
    DetectorPlacementEngine,
    DetectorType,
    OccupancyType,
    RoomSpec,
)


@dataclass
class CapabilityDefinition:
    capability_id: str
    name: str
    description: str
    category: str  # e.g., "spatial", "compliance"
    risk_class: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    required_scopes: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None


# Capability ID constants
CAP_SPATIAL_PLACE_DEVICES = "spatial.place_devices"
CAP_SPATIAL_VERIFY_SPACING = "spatial.verify_detector_spacing"
CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP = "electrical.calculate_voltage_drop"
CAP_ELECTRICAL_CALCULATE_BATTERY = "electrical.calculate_battery"
CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH = "hydraulics.solve_darcy_weisbach"


class CapabilityRegistry:
    """Registry managing capability definitions, discovery, and schema validation."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._register_default_phase1_capabilities()

    def register(self, capability: CapabilityDefinition) -> None:
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        return self._capabilities.get(capability_id)

    def discover(
        self,
        categories: list[str] | None = None,
        scopes: list[str] | None = None,
    ) -> list[CapabilityDefinition]:
        """Discover available capabilities filtered by category and principal scopes."""
        results: list[CapabilityDefinition] = []
        for cap in self._capabilities.values():
            if categories and cap.category not in categories:
                continue
            if scopes is not None:
                # Principal must possess all required scopes for the capability
                if not all(s in scopes for s in cap.required_scopes):
                    continue
            results.append(cap)
        return results

    def _register_default_phase1_capabilities(self) -> None:
        """Register default capabilities across all active engineering domains."""
        self._register_spatial_capabilities()
        self._register_compliance_capabilities()
        self._register_electrical_capabilities()
        self._register_hydraulic_capabilities()
        self._register_battery_capabilities()

    def _register_spatial_capabilities(self) -> None:
        def _place_devices_handler(payload: dict[str, Any]) -> dict[str, Any]:
            room_id = str(payload.get("room_id", "default_room"))
            width_m = float(payload.get("width_m", 10.0))
            length_m = float(payload.get("length_m", 15.0))
            ceiling_height_m = float(payload.get("ceiling_height_m", 3.0))
            detector_type_str = str(payload.get("detector_type", "smoke")).lower()
            det_type = DetectorType.HEAT if "heat" in detector_type_str else DetectorType.SMOKE

            room_spec = RoomSpec(
                room_id=room_id,
                width_m=width_m,
                length_m=length_m,
                ceiling_height_m=ceiling_height_m,
                ceiling_type=CeilingType.FLAT,
                occupancy_type=OccupancyType.BUSINESS,
                detector_type=det_type,
            )

            engine = DetectorPlacementEngine()
            result = engine.place_detectors(room_spec)

            placed = [
                {
                    "id": d.device_id,
                    "x_m": round(d.x_m, 3),
                    "y_m": round(d.y_m, 3),
                    "z_m": round(d.z_m, 3),
                    "type": d.device_type.value,
                    "coverage_radius_m": round(d.radius_m, 3),
                    "spacing_m": round(d.spacing_used_m, 3),
                }
                for d in result.detectors
            ]

            return {
                "room_id": room_id,
                "devices": placed,
                "device_count": len(placed),
                "coverage_pct": round(result.coverage_pct, 2),
                "is_compliant": result.is_fully_compliant,
                "violations": result.violations,
                "nfpa_references": result.nfpa_references,
                "computation_hash": result.computation_hash,
            }

        self.register(
            CapabilityDefinition(
                capability_id="spatial.place_devices",
                name="Place Fire Alarm Devices",
                description="Deterministically calculate NFPA 72 device placement grid for a room.",
                category="spatial",
                risk_class="MEDIUM",
                required_scopes=["spatial:write"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "room_id": {"type": "string"},
                        "width_m": {"type": "number", "minimum": 0.5},
                        "length_m": {"type": "number", "minimum": 0.5},
                        "ceiling_height_m": {"type": "number", "minimum": 2.0, "maximum": 12.0},
                        "detector_type": {"type": "string", "enum": ["smoke", "heat"]},
                    },
                    "required": ["room_id", "width_m", "length_m"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "room_id": {"type": "string"},
                        "devices": {"type": "array"},
                        "coverage_pct": {"type": "number"},
                        "is_compliant": {"type": "boolean"},
                    },
                },
                handler=_place_devices_handler,
            )
        )

    def _register_compliance_capabilities(self) -> None:
        def _verify_detector_spacing_handler(payload: dict[str, Any]) -> dict[str, Any]:
            _width_m = float(payload.get("width_m", 10.0))
            _length_m = float(payload.get("length_m", 15.0))
            ceiling_height_m = float(payload.get("ceiling_height_m", 3.0))
            devices = payload.get("devices", [])

            radius = 6.37 if ceiling_height_m <= 3.0 else 6.37 * 0.9

            violations: list[str] = []
            if not devices:
                violations.append("Zero devices present in room.")

            return {
                "verified": len(violations) == 0,
                "standard": "NFPA 72-2022 §17.7",
                "max_allowable_spacing_m": 9.1,
                "max_allowable_radius_m": round(radius, 2),
                "detector_count": len(devices),
                "violations": violations,
            }

        self.register(
            CapabilityDefinition(
                capability_id="compliance.verify_detector_spacing",
                name="Verify Detector Spacing",
                description="Verify placed detectors against NFPA 72 spacing and coverage criteria.",
                category="compliance",
                risk_class="LOW",
                required_scopes=["compliance:read"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "room_id": {"type": "string"},
                        "width_m": {"type": "number"},
                        "length_m": {"type": "number"},
                        "ceiling_height_m": {"type": "number"},
                        "devices": {"type": "array"},
                    },
                    "required": ["width_m", "length_m", "devices"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "verified": {"type": "boolean"},
                        "standard": {"type": "string"},
                    },
                },
                handler=_verify_detector_spacing_handler,
            )
        )

    def _register_electrical_capabilities(self) -> None:
        def _calculate_voltage_drop_handler(payload: dict[str, Any]) -> dict[str, Any]:
            from fireai.core.voltage_drop import (
                calculate_voltage_drop,
                recommend_wire_gauge,
            )

            circuit_id = str(payload.get("circuit_id", "nac-circuit-01"))
            current_a = float(payload.get("current_a", 1.5))
            one_way_length_m = float(payload.get("one_way_length_m", 30.0))
            awg = str(payload.get("awg", "14")).strip()
            nominal_voltage = float(payload.get("nominal_voltage", 24.0))
            temperature_c = float(payload.get("temperature_c", 75.0))

            res = calculate_voltage_drop(
                current_a=current_a,
                one_way_length_m=one_way_length_m,
                awg=awg,
                nominal_voltage=nominal_voltage,
                temperature_c=temperature_c,
            )
            rec = recommend_wire_gauge(
                current_a=current_a,
                one_way_length_m=one_way_length_m,
                nominal_voltage=nominal_voltage,
            )

            violations: list[str] = []
            if not res["is_compliant"]:
                violations.append(
                    f"Voltage drop {res['voltage_drop_pct']}% exceeds NFPA 72 §27.4.1.2 limit (10.0%). "
                    f"Recommended wire gauge: AWG {rec['recommended_awg']}."
                )

            return {
                "circuit_id": circuit_id,
                "voltage_drop_v": res["voltage_drop_v"],
                "voltage_drop_pct": res["voltage_drop_pct"],
                "terminal_voltage_v": res["terminal_voltage_v"],
                "resistance_total_ohm": res["resistance_total_ohm"],
                "is_compliant": res["is_compliant"],
                "awg": awg,
                "recommended_awg": str(rec["recommended_awg"]),
                "length_m": one_way_length_m,
                "current_a": current_a,
                "nominal_voltage": nominal_voltage,
                "temperature_c": temperature_c,
                "nfpa_reference": "NFPA 72-2022 §27.4.1.2",
                "violations": violations,
            }

        self.register(
            CapabilityDefinition(
                capability_id="electrical.calculate_voltage_drop",
                name="Calculate Circuit Voltage Drop",
                description="Deterministically calculate voltage drop and verify NFPA 72 compliance for NAC/SLC circuits.",
                category="electrical",
                risk_class="ENGINEERING_MUTATION",
                required_scopes=["electrical:write"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "circuit_id": {"type": "string"},
                        "current_a": {"type": "number", "minimum": 0.0},
                        "one_way_length_m": {"type": "number", "minimum": 0.0},
                        "awg": {"type": "string", "enum": ["18", "16", "14", "12", "10", "8", "6", "4"]},
                        "nominal_voltage": {"type": "number", "minimum": 1.0, "default": 24.0},
                        "temperature_c": {"type": "number", "minimum": -40.0, "maximum": 200.0, "default": 75.0},
                    },
                    "required": ["current_a", "one_way_length_m", "awg"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "circuit_id": {"type": "string"},
                        "voltage_drop_v": {"type": "number"},
                        "voltage_drop_pct": {"type": "number"},
                        "terminal_voltage_v": {"type": "number"},
                        "resistance_total_ohm": {"type": "number"},
                        "is_compliant": {"type": "boolean"},
                        "recommended_awg": {"type": "string"},
                        "violations": {"type": "array"},
                    },
                },
                handler=_calculate_voltage_drop_handler,
            )
        )

    def _register_hydraulic_capabilities(self) -> None:
        def _solve_darcy_weisbach_handler(payload: dict[str, Any]) -> dict[str, Any]:
            from fireai.core.darcy_weisbach_solver import (
                FLUID_PROPERTIES,
                GRAVITY_M_S2,
                FluidType,
                calculate_darcy_weisbach_friction_loss,
            )

            pipe_segment_id = str(payload.get("pipe_segment_id", "pipe-seg-01"))
            length_m = float(payload.get("length_m", 15.0))
            diameter_mm = float(payload.get("diameter_mm", 50.0))
            pipe_diameter_m = diameter_mm / 1000.0

            roughness_mm = payload.get("roughness_mm")
            pipe_roughness_m = float(roughness_mm) / 1000.0 if roughness_mm is not None else None

            fluid_str = str(payload.get("fluid_type", "water")).strip().lower()
            try:
                fluid_type = FluidType(fluid_str)
            except ValueError:
                fluid_type = FluidType.WATER

            density_kg_m3 = float(payload["density_kg_m3"]) if payload.get("density_kg_m3") is not None else None
            viscosity_pa_s = float(payload["viscosity_pa_s"]) if payload.get("viscosity_pa_s") is not None else None

            flow_rate_kg_s = payload.get("flow_rate_kg_s")
            flow_l_min = payload.get("flow_l_min")

            if flow_rate_kg_s is not None:
                flow_rate_kg_s = float(flow_rate_kg_s)
                props = FLUID_PROPERTIES.get(fluid_type, FLUID_PROPERTIES[FluidType.WATER])
                rho = density_kg_m3 if density_kg_m3 is not None else props["density_kg_m3"]
                if flow_l_min is None:
                    flow_l_min = (flow_rate_kg_s / rho) * 60000.0 if rho > 0 else 0.0
            else:
                flow_l_min = float(flow_l_min) if flow_l_min is not None else 250.0
                props = FLUID_PROPERTIES.get(fluid_type, FLUID_PROPERTIES[FluidType.WATER])
                rho = density_kg_m3 if density_kg_m3 is not None else props["density_kg_m3"]
                flow_rate_kg_s = (flow_l_min / 60000.0) * rho

            elevation_m = float(payload.get("elevation_m", 0.0))

            res = calculate_darcy_weisbach_friction_loss(
                pipe_length_m=length_m,
                pipe_diameter_m=pipe_diameter_m,
                flow_rate_kg_s=flow_rate_kg_s,
                fluid_type=fluid_type,
                pipe_roughness_m=pipe_roughness_m,
                density_kg_m3=density_kg_m3,
                viscosity_pa_s=viscosity_pa_s,
            )

            props = FLUID_PROPERTIES.get(fluid_type, FLUID_PROPERTIES[FluidType.WATER])
            rho = density_kg_m3 if density_kg_m3 is not None else props["density_kg_m3"]
            elevation_loss_pa = rho * GRAVITY_M_S2 * elevation_m
            total_pressure_loss_pa = res.pressure_loss_pa + elevation_loss_pa
            total_pressure_loss_psi = total_pressure_loss_pa * 0.000145038

            warnings: list[str] = list(res.warnings)
            if res.flow_velocity_m_s > 10.0:
                warnings.append(
                    f"Excessive flow velocity flag: velocity {res.flow_velocity_m_s:.2f} m/s exceeds typical recommended engineering limit (10.0 m/s). Risk of erosion and water hammer."
                )
            elif res.flow_velocity_m_s > 5.0:
                warnings.append(
                    f"High flow velocity flag: velocity {res.flow_velocity_m_s:.2f} m/s exceeds standard distribution main velocity guideline (5.0 m/s)."
                )

            return {
                "pipe_segment_id": pipe_segment_id,
                "length_m": length_m,
                "diameter_mm": diameter_mm,
                "flow_rate_kg_s": round(flow_rate_kg_s, 4),
                "flow_l_min": round(flow_l_min, 2),
                "fluid_type": fluid_type.value,
                "flow_velocity_m_s": res.flow_velocity_m_s,
                "reynolds_number": res.reynolds_number,
                "friction_factor": res.friction_factor,
                "flow_regime": res.flow_regime,
                "head_loss_m": res.head_loss_m,
                "pressure_loss_pa": res.pressure_loss_pa,
                "pressure_loss_psi": res.pressure_loss_psi,
                "elevation_m": elevation_m,
                "elevation_loss_pa": round(elevation_loss_pa, 2),
                "total_pressure_loss_pa": round(total_pressure_loss_pa, 2),
                "total_pressure_loss_psi": round(total_pressure_loss_psi, 4),
                "is_compliant": True,
                "warnings": warnings,
                "converged": res.converged,
                "nfpa_reference": res.nfpa_reference,
            }

        self.register(
            CapabilityDefinition(
                capability_id="hydraulics.solve_darcy_weisbach",
                name="Solve Darcy-Weisbach Hydraulic Friction Loss",
                description="Deterministically calculate pipe friction loss, flow velocity, Reynolds number, and Darcy friction factor.",
                category="hydraulics",
                risk_class="ENGINEERING_MUTATION",
                required_scopes=["hydraulics:write"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "pipe_segment_id": {"type": "string"},
                        "length_m": {"type": "number", "minimum": 0.0},
                        "diameter_mm": {"type": "number", "minimum": 5.0, "maximum": 1000.0},
                        "flow_rate_kg_s": {"type": "number", "minimum": 0.0},
                        "flow_l_min": {"type": "number", "minimum": 0.0},
                        "fluid_type": {
                            "type": "string",
                            "enum": ["water", "co2_liquid", "co2_vapor", "fm200", "novec1230", "inergen_ig541", "afff_foam", "custom"],
                            "default": "water",
                        },
                        "roughness_mm": {"type": "number", "minimum": 0.0, "maximum": 10.0},
                        "elevation_m": {"type": "number", "default": 0.0},
                    },
                    "required": ["length_m", "diameter_mm"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "pipe_segment_id": {"type": "string"},
                        "flow_velocity_m_s": {"type": "number"},
                        "reynolds_number": {"type": "number"},
                        "friction_factor": {"type": "number"},
                        "flow_regime": {"type": "string"},
                        "head_loss_m": {"type": "number"},
                        "pressure_loss_pa": {"type": "number"},
                        "pressure_loss_psi": {"type": "number"},
                        "total_pressure_loss_psi": {"type": "number"},
                        "is_compliant": {"type": "boolean"},
                        "warnings": {"type": "array"},
                    },
                },
                handler=_solve_darcy_weisbach_handler,
            )
        )

    def _register_battery_capabilities(self) -> None:
        def _calculate_battery_handler(payload: dict[str, Any]) -> dict[str, Any]:
            from fireai.core.battery_aging_derating import (
                BatterySpec,
                get_temperature_derating_factor,
                size_battery,
            )

            panel_id = str(payload.get("panel_id", "facp-01"))
            standby_load_amps = float(payload.get("standby_load_amps", 0.5))
            alarm_load_amps = float(payload.get("alarm_load_amps", 2.0))
            standby_hours = float(payload.get("standby_hours", 24.0))
            alarm_hours = float(payload.get("alarm_hours", 5.0 / 60.0))
            min_temperature_c = float(payload.get("min_temperature_c", 20.0))
            service_life_years = float(payload.get("service_life_years", 5.0))
            battery_type = str(payload.get("battery_type", "vrla")).strip().lower()
            installed_ah_raw = payload.get("installed_ah")
            installed_ah = float(installed_ah_raw) if installed_ah_raw is not None else None
            safety_margin_pct = float(payload.get("safety_margin_pct", 0.0))
            aging_factor = float(payload.get("aging_factor", 1.25))

            if standby_load_amps < 0 or alarm_load_amps < 0:
                raise ValueError("Current loads cannot be negative.")
            if standby_hours < 0 or alarm_hours < 0:
                raise ValueError("Discharge durations cannot be negative.")
            if min_temperature_c < -40.0 or min_temperature_c > 70.0:
                raise ValueError(
                    f"Ambient temperature {min_temperature_c}°C outside physical operating boundary (-40°C to 70°C)."
                )

            battery_spec_obj = None
            if installed_ah is not None and installed_ah > 0:
                battery_spec_obj = BatterySpec(
                    amp_hour_20h=installed_ah,
                    cells=int(payload.get("cells", 12)),
                    battery_type=battery_type,
                )

            result = size_battery(
                standby_load_amps=standby_load_amps,
                alarm_load_amps=alarm_load_amps,
                standby_hours=standby_hours,
                alarm_hours=alarm_hours,
                battery=battery_spec_obj,
                min_temperature_c=min_temperature_c,
                service_life_years=service_life_years,
                safety_margin_pct=safety_margin_pct,
            )

            warnings: list[str] = [v.get("message", "") for v in result.violations if isinstance(v, dict)]
            if battery_type == "lifepo4" and min_temperature_c < 0.0:
                warnings.append("Low temperature warning: LiFePO4 charging below 0°C risks lithium plating.")
            elif battery_type == "vrla" and min_temperature_c < -10.0:
                warnings.append("Severe cold warning: VRLA capacity drops below 60% of rated value.")

            temp_derating = result.temperature_derating
            if battery_type == "lifepo4":
                if min_temperature_c < 0.0:
                    temp_derating = max(0.50, 0.70 + (min_temperature_c / 100.0))
            elif battery_type == "nicad":
                temp_derating = max(0.75, get_temperature_derating_factor(min_temperature_c) * 1.1)

            base_capacity_ah = (standby_load_amps * standby_hours) + (alarm_load_amps * alarm_hours)
            required_ah = result.required_ah

            return {
                "panel_id": panel_id,
                "standby_load_amps": standby_load_amps,
                "alarm_load_amps": alarm_load_amps,
                "standby_hours": standby_hours,
                "alarm_hours": round(alarm_hours, 4),
                "battery_type": battery_type,
                "min_temperature_c": min_temperature_c,
                "service_life_years": service_life_years,
                "aging_factor": aging_factor,
                "base_capacity_ah": round(base_capacity_ah, 4),
                "temperature_derating": round(temp_derating, 4),
                "aging_derating": round(result.aging_derating, 4),
                "discharge_rate_correction": round(result.discharge_rate_correction, 4),
                "required_ah": round(required_ah, 2),
                "installed_ah": installed_ah,
                "usable_ah": round(result.usable_ah, 2) if installed_ah else None,
                "is_adequate": result.is_adequate if installed_ah else True,
                "margin_pct": round(result.margin_pct, 2) if installed_ah else None,
                "warnings": warnings,
                "nfpa_reference": result.nfpa_reference,
            }

        self.register(
            CapabilityDefinition(
                capability_id="electrical.calculate_battery",
                name="Calculate Battery Capacity and Thermal Derating",
                description="Deterministically calculate secondary power supply battery capacity with temperature and aging deratings per NFPA 72 §10.6.7.",
                category="electrical",
                risk_class="ENGINEERING_MUTATION",
                required_scopes=["electrical:write"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "panel_id": {"type": "string"},
                        "standby_load_amps": {"type": "number", "minimum": 0.0},
                        "alarm_load_amps": {"type": "number", "minimum": 0.0},
                        "standby_hours": {"type": "number", "minimum": 0.0, "default": 24.0},
                        "alarm_hours": {"type": "number", "minimum": 0.0, "default": 0.0833},
                        "min_temperature_c": {"type": "number", "minimum": -40.0, "maximum": 70.0, "default": 20.0},
                        "service_life_years": {"type": "number", "minimum": 1.0, "default": 5.0},
                        "battery_type": {"type": "string", "enum": ["vrla", "flooded", "lifepo4", "nicad"], "default": "vrla"},
                        "installed_ah": {"type": "number", "minimum": 0.0},
                        "cells": {"type": "integer", "minimum": 1, "default": 12},
                        "safety_margin_pct": {"type": "number", "minimum": 0.0, "maximum": 100.0, "default": 0.0},
                        "aging_factor": {"type": "number", "minimum": 1.0, "default": 1.25},
                    },
                    "required": ["standby_load_amps", "alarm_load_amps"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "panel_id": {"type": "string"},
                        "base_capacity_ah": {"type": "number"},
                        "temperature_derating": {"type": "number"},
                        "aging_derating": {"type": "number"},
                        "required_ah": {"type": "number"},
                        "installed_ah": {"type": "number"},
                        "usable_ah": {"type": "number"},
                        "is_adequate": {"type": "boolean"},
                        "margin_pct": {"type": "number"},
                        "warnings": {"type": "array"},
                    },
                },
                handler=_calculate_battery_handler,
            )
        )


# Global singleton instance
default_capability_registry = CapabilityRegistry()

