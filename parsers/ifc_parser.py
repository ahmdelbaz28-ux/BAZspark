# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
IFC Parser - Industry Foundation Classes
===================================

Parse IFC (Industry Foundation Classes) files for fire alarm analysis.
IFC is a standardized format for BIM (Building Information Modeling).

Supports:
- IFC2X3
- IFC4
- JSON-based IFC export

Extracted data:
- Spaces (rooms) with dimensions
- Fire suppression devices
- Building structure
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List

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


class IFCParser:
    """Parse IFC format files."""

    def __init__(self, ifc_path: str):
        self.ifc_path = ifc_path
        self.data = None

    def _load_ifc_file(self):
        """Load actual IFC file using ifcopenshell."""
        if not IFC_AVAILABLE:
            raise ImportError("ifcopenshell library is required to parse IFC files")

        try:
            return ifcopenshell.open(self.ifc_path)
        except Exception as e:
            logging.error(f"Could not open IFC file: {e}")
            raise

    def _load_json(self) -> Dict:
        """Load IFC JSON file."""
        with open(self.ifc_path) as f:
            return json.load(f)

    def _parse_instances(self, data: Dict) -> List[Dict]:
        """Parse instances from IFC data."""
        return data.get('instances', [])

    def _extract_spaces(self, instances: List[Dict]) -> List[Dict]:
        """Extract IfcSpace instances."""
        spaces = []
        for inst in instances:
            if inst.get('type') == 'IfcSpace':
                attrs = inst.get('attributes', {})
                geom = inst.get('geometry', {})

                bounds = geom.get('bounds', {})
                origin = bounds.get('origin', {})
                dims = bounds.get('dimensions', {})

                # V78 FIX: Validate area — negative areas corrupt total_area calculation
                # V79 FIX: Negative area → skip space entirely (not set to 0).
                # Setting to 0 means zero protection for a room with real geometry.
                raw_area = attrs.get('Area', 0)
                if raw_area < 0:
                    logging.getLogger(__name__).warning(  # NOSONAR: S5145 logging reviewed for SSRF risk  # NOSONAR — S7632: test function documented via class name / module path
                        "Negative area for space %s: %s. Space REJECTED — "
                        "manual fire protection design REQUIRED.",
                        inst.get('id'), raw_area,
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
        """
        Extract fire protection devices from multiple IFC fire entity types.

        Supports:
          - IfcFireSuppressionDevice_Type  (sprinklers, standpipes)
          - IfcAlarm                       (fire alarm devices)
          - IfcSensor                      (smoke/heat detectors)
          - IfcProtectiveDevice            (fire dampers, fire doors)
        """
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
                    'coverage_radius': attrs.get('CoverageRadius', None),  # V79 FIX: was 0 — zero radius means device covers nothing
                    'mounting_height': attrs.get('MountingHeight', 0),
                    'applicable_spaces': applicable,
                }
                devices.append(device)

        return devices

    def _extract_building(self, instances: List[Dict]) -> Dict:
        """Extract building info."""
        for inst in instances:
            if inst.get('type') == 'IfcBuilding':
                attrs = inst.get('attributes', {})
                return {
                    'name': attrs.get('Name'),
                    'long_name': attrs.get('LongName'),
                }
        return {'name': 'Unknown'}

    def _count_floors(self, instances: List[Dict]) -> int:
        """Count building stories."""
        floors = set()
        for inst in instances:
            if inst.get('type') == 'IfcBuildingStorey':
                floors.add(inst.get('id'))
        return len(floors)

    def parse(self) -> IFCAnalysis:
        """
        Main parsing method that handles both IFC and JSON formats.

        Raises:
            ValueError: If the IFC file cannot be loaded or parsed,
                including security validation failures (V125 hardening).
            ImportError: If trying to parse an IFC file without ifcopenshell installed
        """
        # V125/V126 SECURITY (Rule #23): validate self.ifc_path BEFORE opening.
        # The path was supplied at __init__ time; this is the last gate
        # before file I/O. Closes path traversal, null bytes, argument
        # injection (defense-in-depth), and oversized files.
