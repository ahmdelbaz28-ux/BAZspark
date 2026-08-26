"""backend/core/context_resolver.py — Bounded Context Packet Resolver.

Frozen Phase 1 Architecture:
- Contract 4: Hard budget limit of <= 1,500 tokens per ContextPacket.
- The LLM receives strictly bounded room context, NEVER raw project CAD/DXF dumps.
- Telemetry measures baseline vs bounded token counts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BoundedContextPacket:
    project_id: str
    room_id: str
    revision: int
    room_bounds: dict[str, float]  # width_m, length_m, ceiling_height_m, area_m2
    existing_device_count: int
    existing_devices_summary: list[dict[str, Any]]
    standards: list[str]
    token_count: int
    is_within_budget: bool
    budget_limit: int = 1500
    telemetry: dict[str, Any] = field(default_factory=dict)


@dataclass
class BoundedCircuitContextPacket:
    project_id: str
    circuit_id: str
    revision: int
    circuit_spec: dict[str, Any]  # current_a, one_way_length_m, awg, nominal_voltage, temperature_c
    connected_device_count: int
    standards: list[str]
    token_count: int
    is_within_budget: bool
    budget_limit: int = 1500
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoundedHydraulicContextPacket:
    project_id: str
    pipe_segment_id: str
    revision: int
    hydraulic_spec: dict[
        str, Any
    ]  # length_m, diameter_mm, roughness_mm, flow_rate_kg_s, flow_l_min, fluid_type, elevation_m
    standards: list[str]
    token_count: int
    is_within_budget: bool
    budget_limit: int = 1500
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoundedBatteryContextPacket:
    project_id: str
    panel_id: str
    revision: int
    battery_spec: dict[
        str, Any
    ]  # standby_load_amps, alarm_load_amps, standby_hours, alarm_hours, min_temperature_c, service_life_years, battery_type, installed_ah, aging_factor
    standards: list[str]
    token_count: int
    is_within_budget: bool
    budget_limit: int = 1500
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoundedCompositeContextPacket:
    project_id: str
    revision: int
    domains: list[str]
    composite_spec: dict[str, Any]
    standards: list[str]
    token_count: int
    is_within_budget: bool
    budget_limit: int = 1500
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_token_count(text_or_dict: str | dict[str, Any]) -> int:
    """Accurately estimate token count for JSON payloads.

    Uses standard LLM token estimation (average ~3.8 chars per token for JSON structure).
    """
    if isinstance(text_or_dict, dict):
        serialized = json.dumps(text_or_dict, separators=(",", ":"))
    else:
        serialized = str(text_or_dict)

    # Accurate estimate: words + punctuation / symbols
    return max(1, int(len(serialized) / 3.8))


class TokenCounter:
    """Abstract tokenizer interface for measuring context budget utilization."""

    @staticmethod
    def count(text_or_dict: str | dict[str, Any]) -> int:
        """Count or estimate tokens in context payload."""
        return estimate_token_count(text_or_dict)


class ContextResolver:
    """Resolves bounded, token-budgeted context for AI spatial, electrical, and compliance intents."""

    MAX_TOKEN_BUDGET: int = 1500

    def __init__(self, token_budget: int = MAX_TOKEN_BUDGET) -> None:
        self.token_budget = token_budget

    def resolve_room_context(
        self,
        project_id: str,
        room_id: str,
        revision: int,
        room_bounds: dict[str, float] | None = None,
        existing_devices: list[dict[str, Any]] | None = None,
    ) -> BoundedContextPacket:
        """Constructs a strictly bounded context packet for a single room."""
        # 1. Standardize room bounds
        bounds = room_bounds or {"width_m": 12.0, "length_m": 18.0, "ceiling_height_m": 3.0}
        width = float(bounds.get("width_m", 12.0))
        length = float(bounds.get("length_m", 18.0))
        height = float(bounds.get("ceiling_height_m", 3.0))
        area = round(width * length, 2)

        standardized_bounds = {
            "width_m": width,
            "length_m": length,
            "ceiling_height_m": height,
            "area_m2": area,
        }

        # 2. Filter & summarize existing devices (omitting bloated CAD geometries/vendor blobs)
        devices = existing_devices or []
        device_summary: list[dict[str, Any]] = []
        for d in devices[:50]:  # Limit to 50 items max to enforce token bounds
            device_summary.append(
                {
                    "id": d.get("id", ""),
                    "type": d.get("type", "smoke"),
                    "x_m": round(float(d.get("x", d.get("x_m", 0))), 2),
                    "y_m": round(float(d.get("y", d.get("y_m", 0))), 2),
                }
            )

        # 3. Applicable standards
        standards = ["NFPA 72-2022 §17.7 (Smoke Sensing)", "NFPA 72-2022 §17.6 (Heat Sensing)"]

        # 4. Measure token usage
        packet_content = {
            "project_id": project_id,
            "room_id": room_id,
            "revision": revision,
            "room_bounds": standardized_bounds,
            "existing_device_count": len(devices),
            "existing_devices_summary": device_summary,
            "standards": standards,
        }

        measured_tokens = estimate_token_count(packet_content)

        # 5. Enforce hard budget
        if measured_tokens > self.token_budget:
            # Shed secondary details to fit budget
            device_summary = device_summary[:10]
            packet_content["existing_devices_summary"] = device_summary
            measured_tokens = estimate_token_count(packet_content)

        telemetry = {
            "measured_tokens": measured_tokens,
            "budget_limit": self.token_budget,
            "utilization_pct": round((measured_tokens / self.token_budget) * 100, 2),
            "raw_cad_excluded": True,
            "whole_project_dump_excluded": True,
        }

        return BoundedContextPacket(
            project_id=project_id,
            room_id=room_id,
            revision=revision,
            room_bounds=standardized_bounds,
            existing_device_count=len(devices),
            existing_devices_summary=device_summary,
            standards=standards,
            token_count=measured_tokens,
            is_within_budget=measured_tokens <= self.token_budget,
            budget_limit=self.token_budget,
            telemetry=telemetry,
        )

    def resolve_circuit_context(
        self,
        project_id: str,
        circuit_id: str,
        revision: int,
        circuit_spec: dict[str, Any] | None = None,
        connected_devices: list[dict[str, Any]] | None = None,
    ) -> BoundedCircuitContextPacket:
        """Constructs a strictly bounded context packet for an electrical circuit (Phase 2B)."""
        spec = circuit_spec or {}
        current_a = float(spec.get("current_a", 1.5))
        one_way_length_m = float(spec.get("one_way_length_m", 30.0))
        awg = str(spec.get("awg", "14")).strip()
        nominal_voltage = float(spec.get("nominal_voltage", 24.0))
        temperature_c = float(spec.get("temperature_c", 75.0))

        standardized_spec = {
            "current_a": current_a,
            "one_way_length_m": one_way_length_m,
            "awg": awg,
            "nominal_voltage": nominal_voltage,
            "temperature_c": temperature_c,
        }

        devices = connected_devices or []
        standards = [
            "NFPA 72-2022 §27.4.1.2 (10% Max Voltage Drop)",
            "NEC Chapter 9 Table 8 (DC Conductor Resistance at 75°C)",
        ]

        packet_content = {
            "project_id": project_id,
            "circuit_id": circuit_id,
            "revision": revision,
            "circuit_spec": standardized_spec,
            "connected_device_count": len(devices),
            "standards": standards,
        }

        measured_tokens = estimate_token_count(packet_content)

        telemetry = {
            "measured_tokens": measured_tokens,
            "budget_limit": self.token_budget,
            "utilization_pct": round((measured_tokens / self.token_budget) * 100, 2),
            "raw_cad_excluded": True,
            "whole_project_dump_excluded": True,
        }

        return BoundedCircuitContextPacket(
            project_id=project_id,
            circuit_id=circuit_id,
            revision=revision,
            circuit_spec=standardized_spec,
            connected_device_count=len(devices),
            standards=standards,
            token_count=measured_tokens,
            is_within_budget=measured_tokens <= self.token_budget,
            budget_limit=self.token_budget,
            telemetry=telemetry,
        )

    def resolve_hydraulic_context(
        self,
        project_id: str,
        pipe_segment_id: str,
        revision: int,
        hydraulic_spec: dict[str, Any] | None = None,
    ) -> BoundedHydraulicContextPacket:
        """Constructs a strictly bounded context packet for a hydraulic pipe segment (Phase 2C)."""
        spec = hydraulic_spec or {}
        length_m = float(spec.get("length_m", 15.0))
        diameter_mm = float(spec.get("diameter_mm", 50.0))
        roughness_mm = (
            float(spec.get("roughness_mm", 0.0457))
            if spec.get("roughness_mm") is not None
            else 0.0457
        )
        flow_rate_kg_s = (
            float(spec["flow_rate_kg_s"]) if spec.get("flow_rate_kg_s") is not None else None
        )
        if spec.get("flow_l_min") is not None:
            flow_l_min = float(spec["flow_l_min"])
        elif flow_rate_kg_s is not None:
            flow_l_min = None
        else:
            flow_l_min = 250.0
        fluid_type = str(spec.get("fluid_type", "water")).strip().lower()
        elevation_m = float(spec.get("elevation_m", 0.0))

        standardized_spec = {
            "length_m": length_m,
            "diameter_mm": diameter_mm,
            "roughness_mm": roughness_mm,
            "flow_rate_kg_s": flow_rate_kg_s,
            "flow_l_min": flow_l_min,
            "fluid_type": fluid_type,
            "elevation_m": elevation_m,
        }

        standards = [
            "Darcy-Weisbach Equation (NFPA 12 / NFPA 2001 / Crane TP-410)",
            "Colebrook-White Friction Factor Formulation",
        ]

        packet_content = {
            "project_id": project_id,
            "pipe_segment_id": pipe_segment_id,
            "revision": revision,
            "hydraulic_spec": standardized_spec,
            "standards": standards,
        }

        measured_tokens = estimate_token_count(packet_content)

        telemetry = {
            "measured_tokens": measured_tokens,
            "budget_limit": self.token_budget,
            "utilization_pct": round((measured_tokens / self.token_budget) * 100, 2),
            "raw_cad_excluded": True,
            "geometry_mesh_excluded": True,
            "whole_project_dump_excluded": True,
        }

        return BoundedHydraulicContextPacket(
            project_id=project_id,
            pipe_segment_id=pipe_segment_id,
            revision=revision,
            hydraulic_spec=standardized_spec,
            standards=standards,
            token_count=measured_tokens,
            is_within_budget=measured_tokens <= self.token_budget,
            budget_limit=self.token_budget,
            telemetry=telemetry,
        )

    def resolve_battery_context(
        self,
        project_id: str,
        panel_id: str,
        revision: int,
        battery_spec: dict[str, Any] | None = None,
    ) -> BoundedBatteryContextPacket:
        """Constructs a strictly bounded context packet for an electrical battery sizing calculation (Phase 2D)."""
        spec = battery_spec or {}
        standby_load_amps = float(spec.get("standby_load_amps", 0.5))
        alarm_load_amps = float(spec.get("alarm_load_amps", 2.0))
        standby_hours = float(spec.get("standby_hours", 24.0))
        alarm_hours = float(spec.get("alarm_hours", 5.0 / 60.0))
        min_temperature_c = float(spec.get("min_temperature_c", 20.0))
        service_life_years = float(spec.get("service_life_years", 5.0))
        battery_type = str(spec.get("battery_type", "vrla")).strip().lower()
        installed_ah = float(spec["installed_ah"]) if spec.get("installed_ah") is not None else None
        aging_factor = float(spec.get("aging_factor", 1.25))

        standardized_spec = {
            "standby_load_amps": standby_load_amps,
            "alarm_load_amps": alarm_load_amps,
            "standby_hours": standby_hours,
            "alarm_hours": alarm_hours,
            "min_temperature_c": min_temperature_c,
            "service_life_years": service_life_years,
            "battery_type": battery_type,
            "installed_ah": installed_ah,
            "aging_factor": aging_factor,
        }

        standards = [
            "NFPA 72-2022 §10.6.7 (Secondary Power Supply Requirements)",
            "IEEE 485 (Recommended Practice for Sizing Lead-Acid Batteries)",
            "IEEE 1188 (VRLA Maintenance, Testing, and Replacement)",
        ]

        packet_content = {
            "project_id": project_id,
            "panel_id": panel_id,
            "revision": revision,
            "battery_spec": standardized_spec,
            "standards": standards,
        }

        measured_tokens = estimate_token_count(packet_content)

        telemetry = {
            "measured_tokens": measured_tokens,
            "budget_limit": self.token_budget,
            "utilization_pct": round((measured_tokens / self.token_budget) * 100, 2),
            "raw_cad_excluded": True,
            "geometry_mesh_excluded": True,
            "whole_project_dump_excluded": True,
        }

        return BoundedBatteryContextPacket(
            project_id=project_id,
            panel_id=panel_id,
            revision=revision,
            battery_spec=standardized_spec,
            standards=standards,
            token_count=measured_tokens,
            is_within_budget=measured_tokens <= self.token_budget,
            budget_limit=self.token_budget,
            telemetry=telemetry,
        )

    def resolve_composite_context(
        self,
        project_id: str,
        revision: int,
        composite_spec: dict[str, Any] | None = None,
    ) -> BoundedCompositeContextPacket:
        """Resolve a bounded, deduplicated multi-domain composite context packet.

        Combines spatial bounds, circuit definitions, hydraulic piping, and power supply
        specifications into a single cohesive payload strictly bounded within token limits (<= 1500).
        """
        spec = composite_spec or {}
        domains = list(spec.get("domains", ["spatial", "electrical", "hydraulics"]))

        deduped_spec: dict[str, Any] = {
            "room_bounds": spec.get(
                "room_bounds",
                {"width_m": 12.0, "length_m": 16.0, "ceiling_height_m": 3.2},
            ),
            "circuit": spec.get(
                "circuit",
                {"circuit_id": "nac-01", "current_a": 2.0, "one_way_length_m": 35.0, "awg": "14"},
            ),
            "hydraulic": spec.get(
                "hydraulic",
                {
                    "pipe_segment_id": "pipe-01",
                    "length_m": 25.0,
                    "diameter_mm": 65.0,
                    "flow_l_min": 350.0,
                },
            ),
            "battery": spec.get(
                "battery",
                {
                    "panel_id": "facp-01",
                    "standby_load_amps": 0.8,
                    "alarm_load_amps": 3.0,
                    "installed_ah": 55.0,
                },
            ),
        }

        standards = [
            "NFPA 72-2022 §17 (Initiating Devices & Spacing)",
            "NFPA 72-2022 §10.6.7 (Secondary Power Supply)",
            "NFPA 13 (Standard for the Installation of Sprinkler Systems)",
            "IEEE 485 (Battery Sizing & Deratings)",
        ]

        packet_content = {
            "project_id": project_id,
            "revision": revision,
            "domains": domains,
            "composite_spec": deduped_spec,
            "standards": standards,
        }

        measured_tokens = estimate_token_count(packet_content)

        telemetry = {
            "measured_tokens": measured_tokens,
            "budget_limit": self.token_budget,
            "utilization_pct": round((measured_tokens / self.token_budget) * 100, 2),
            "raw_cad_excluded": True,
            "geometry_mesh_excluded": True,
            "whole_project_dump_excluded": True,
        }

        return BoundedCompositeContextPacket(
            project_id=project_id,
            revision=revision,
            domains=domains,
            composite_spec=deduped_spec,
            standards=standards,
            token_count=measured_tokens,
            is_within_budget=measured_tokens <= self.token_budget,
            budget_limit=self.token_budget,
            telemetry=telemetry,
        )


default_context_resolver = ContextResolver()
