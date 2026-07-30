# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
IFC Parser - Industry Foundation Classes
===================================

Parse IFC (Industry Foundation Classes) files for fire alarm analysis.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List

from parsers._base import ParserBase
from parsers._path_security import (
    UnsafePathError,
)

_JSON_EXT = ".json"

try:
    import ifcopenshell
    import ifcopenshell.geom
    IFC_AVAILABLE = True
except ImportError:
    IFC_AVAILABLE = False
    logging.warning("ifcopenshell not available - IFC file parsing will be limited")


@dataclass
class IFCAnalysis:
    """Analysis result from IFC file."""

    building_name: str
    floors: int
    spaces: List[Dict]
    devices: List[Dict]
    total_area: float


class IFCParser(ParserBase):
    """Parse IFC format files."""

    allowed_extensions = {'.ifc'}
    max_file_size_bytes = int(os.getenv("FIREAI_IFC_MAX_FILE_SIZE_BYTES", 500 * 1024 * 1024))

    def __init__(self, ifc_path: str):
        self.ifc_path = ifc_path
        self.data = None

    def _load_ifc_file(self):
        if not IFC_AVAILABLE:
            raise ImportError("ifcopenshell library is required to parse IFC files")

        safe_path = self.validate_input(self.ifc_path)
        try:
            return ifcopenshell.open(safe_path)
        except Exception as e:
            logging.exception("Could not open IFC file: %s", e)
            raise

    def _load_json(self) -> Dict:
        safe_path = self.validate_input(self.ifc_path)
        with open(safe_path) as f:
            return json.load(f)

    def _parse_instances(self, data: Dict) -> List[Dict]:
        return data.get('instances', [])

    def _extract_spaces(self, instances: List[Dict]) -> List[Dict]:
        spaces = []
        for inst in instances:
            if inst.get('type') == 'IfcSpace':
                attrs = inst.get('attributes', {})
                geom = inst.get('geometry', {})

                bounds = geom.get('bounds', {})
                origin = bounds.get('origin', {})
                dims = bounds.get('dimensions', {})

                raw_area = attrs.get('Area', 0)
                if raw_area < 0:
                    logging.getLogger(__name__).warning(
                        "Negative area for space: %s. Space REJECTED — "
                        "manual fire protection design REQUIRED.",
                        raw_area,  # nosec: S5145 — numeric value only, not user-controlled text
                    )
                    continue

                space = {
                    'id': inst.get('id'),
                    'name': attrs.get('Name'),
                    'long_name': attrs.get('LongName'),
                    'area': raw_area,
                    'elevation': attrs.get('Elevation', 0),
                    'bounds': {
                        'x': origin.get('x', 0),
                        'y': origin.get('y', 0),
                        'z': origin.get('z', 0),
                        'width': dims.get('width', 0),
                        'length': dims.get('length', 0),
                        'height': dims.get('height', 0),
                    }
                }
                spaces.append(space)

        return spaces

    def _extract_devices(self, instances: List[Dict]) -> List[Dict]:
        _FIRE_ENTITY_TYPES = {
            'IfcFireSuppressionDevice_Type',
            'IfcAlarm',
            'IfcSensor',
            'IfcProtectiveDevice',
        }
        devices = []
        for inst in instances:
            if inst.get('type') in _FIRE_ENTITY_TYPES:
                attrs = inst.get('attributes', {})
                applicable = inst.get('applicable_to', [])

                device = {
                    'id': inst.get('id'),
                    'name': attrs.get('Name'),
                    'detector_type': attrs.get('DetectorType'),
                    'sensitivity': attrs.get('Sensitivity'),
                    'coverage_radius': attrs.get('CoverageRadius', None),
                    'mounting_height': attrs.get('MountingHeight', 0),
                    'applicable_spaces': applicable,
                }
                devices.append(device)

        return devices

    def _extract_building(self, instances: List[Dict]) -> Dict:
        for inst in instances:
            if inst.get('type') == 'IfcBuilding':
                attrs = inst.get('attributes', {})
                return {
                    'name': attrs.get('Name'),
                    'long_name': attrs.get('LongName'),
                }
        return {'name': 'Unknown'}

    def _count_floors(self, instances: List[Dict]) -> int:
        floors = set()
        for inst in instances:
            if inst.get('type') == 'IfcBuildingStorey':
                floors.add(inst.get('id'))
        return len(floors)

    def parse(self) -> IFCAnalysis:
        try:
            safe_path = self.validate_input(self.ifc_path)
        except UnsafePathError as e:
            raise ValueError(f"SECURITY: {e}") from e
        except FileNotFoundError as e:
            raise ValueError(f"File not found: {e}") from e

        self.ifc_path = str(safe_path)
        _, ext = os.path.splitext(self.ifc_path)
        ext = ext.lower()

        try:
            if ext == _JSON_EXT:
                data = self._load_json()
            else:
                if IFC_AVAILABLE:
                    data = self._load_ifc_file()
                else:
                    data = self._load_json()
        except Exception as e:
            raise ValueError(f"Failed to load IFC file: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Loaded IFC content is not a dictionary")

        instances = self._parse_instances(data)
        building = self._extract_building(instances)
        floors = self._count_floors(instances)
        spaces = self._extract_spaces(instances)
        devices = self._extract_devices(instances)
        total_area = sum(space.get("area", 0) for space in spaces)

        return IFCAnalysis(
            building_name=building.get("name", "Unknown"),
            floors=floors,
            spaces=spaces,
            devices=devices,
            total_area=total_area,
        )

    def to_standard_format(self, analysis: IFCAnalysis) -> dict:
        rooms = [
            {
                "id": space.get("id"),
                "name": space.get("name"),
                "area": space.get("area"),
            }
            for space in analysis.spaces
        ]

        devices = [
            {
                "id": dev.get("id"),
                "name": dev.get("name"),
                "type": dev.get("detector_type"),
            }
            for dev in analysis.devices
        ]

        walls = []
        for space in analysis.spaces:
            bounds = space.get("bounds", {})
            width = bounds.get("width", 0)
            length = bounds.get("length", 0)
            if width > 0 and length > 0:
                walls.append(
                    {
                        "space_id": space.get("id"),
                        "width": width,
                        "length": length,
                    }
                )

        return {
            "building_name": analysis.building_name,
            "floors": analysis.floors,
            "total_area": analysis.total_area,
            "rooms": rooms,
            "devices": devices,
            "walls": walls,
        }


def parse_ifc(ifc_path: str) -> IFCAnalysis:
    """Convenience wrapper around IFCParser."""
    return IFCParser(ifc_path).parse()
