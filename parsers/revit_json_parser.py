"""
RevitJSON Parser - Autodesk Revit Project Export
===========================================

Parse Revit project exports (JSON format).

Supports:
- Revit 2024+ JSON export
- Multi-level buildings
- Fire alarm device families
- Spatial data (rooms/spaces)
- Parameters and settings
"""

import json
from dataclasses import dataclass


@dataclass
class RevitProject:
    """Parsed Revit project."""

    name: str
    version: str
    units: str
    levels: list[dict]
    categories: list[str]
    families: dict[str, list[str]]
    parameters: dict


class RevitJSONParser:
    """Parse Revit JSON exports."""

    def __init__(self, json_path: str):
        self.json_path = json_path
        self.data = None

    def _load_json(self) -> dict:
        """Load JSON file."""
        from parsers._path_security import validate_file_size, validate_input_path
        safe_path = validate_input_path(self.json_path, parser_name='revit_json')
        validate_file_size(
            safe_path,
            max_size_bytes=200 * 1024 * 1024,
            parser_name='revit_json',
        )
        with open(self.json_path) as f:
            return json.load(f)

    def parse(self) -> RevitProject | None:
        """Parse Revit JSON."""
        try:
            if self.data is None:
                self.data = self._load_json()
        except Exception:
            return None

        info = self.data.get('project_info', {})

        return RevitProject(
            name=info.get('name', 'Unknown'),
            version=info.get('version', 'Unknown'),
            units=info.get('units', 'metric'),
            levels=self.data.get('levels', []),
            categories=self.data.get('categories', []),
            families=self.data.get('families', {}),
            parameters=self.data.get('parameters', {}),
        )

    def get_level_count(self) -> int:
        """Get number of levels."""
        if self.data:
            return len(self.data.get('levels', []))
        return 0

    def get_fire_alarm_families(self) -> list[str]:
        """Get fire alarm device families."""
        if self.data:
            families = self.data.get('families', {})
            fa_families = []
            for device_type, variants in families.items():
                if device_type in ['SmokeDetector', 'HeatDetector', 'PullStation', 'HornStrobe']:
                    fa_families.extend(variants)
            return fa_families
        return []

    def get_parameters(self) -> dict:
        """Get project parameters."""
        if self.data:
            return self.data.get('parameters', {})
        return {}


def parse_revit_json(json_path: str) -> RevitProject | None:
    """Convenience function."""
    parser = RevitJSONParser(json_path)
    return parser.parse()
