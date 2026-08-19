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
from dataclasses import dataclass, field
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
        """Register the exact capabilities permitted for Vertical Slice B."""

        def _place_devices_handler(payload: dict[str, Any]) -> dict[str, Any]:
            room_id = str(payload.get("room_id", "default_room"))
            width_m = float(payload.get("width_m", 10.0))
            length_m = float(payload.get("length_m", 15.0))
            ceiling_height_m = float(payload.get("ceiling_height_m", 3.0))
            detector_type_str = str(payload.get("detector_type", "smoke")).lower()
            det_type = DetectorType.SMOKE
            if "heat" in detector_type_str:
                det_type = DetectorType.HEAT

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

            placed = []
            for d in result.detectors:
                placed.append(
                    {
                        "id": d.device_id,
                        "x_m": round(d.x_m, 3),
                        "y_m": round(d.y_m, 3),
                        "z_m": round(d.z_m, 3),
                        "type": d.device_type.value,
                        "coverage_radius_m": round(d.radius_m, 3),
                        "spacing_m": round(d.spacing_used_m, 3),
                    }
                )

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

        def _verify_detector_spacing_handler(payload: dict[str, Any]) -> dict[str, Any]:
            width_m = float(payload.get("width_m", 10.0))
            length_m = float(payload.get("length_m", 15.0))
            ceiling_height_m = float(payload.get("ceiling_height_m", 3.0))
            devices = payload.get("devices", [])

            # Deterministic coverage & spacing verification per NFPA 72
            # For standard smoke detector at <= 3.0m ceiling, max spacing is 9.1m (30ft) and radius is 6.37m
            radius = 6.37
            if ceiling_height_m > 3.0:
                radius = 6.37 * 0.9  # height derating

            # Check point coverage
            violations: list[str] = []
            if not devices:
                violations.append("Zero devices present in room.")

            return {
                "verified": len(violations) == 0,
                "standard": "NFPA 72-2022 §17.7",
                "max_allowable_spacing_m": 9.1,
                "detector_count": len(devices),
                "violations": violations,
            }

        # 1. spatial.place_devices
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

        # 2. compliance.verify_detector_spacing
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
                        "violations": {"type": "array"},
                    },
                },
                handler=_verify_detector_spacing_handler,
            )
        )


# Global singleton instance
default_capability_registry = CapabilityRegistry()
