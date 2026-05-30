"""
FireAI RVT Parser - Revit .rvt file parser
==========================================
INTEGRATION: Uses DDC (DataDrivenConstruction) CLI converter when installed.
FALLBACK: Placeholder mode when DDC not available (requires Revit API otherwise).

DDC Installation (Linux):
    curl -sS https://pkg.datadrivenconstruction.io/setup.sh | sudo bash
    sudo apt install ddc-rvtconverter

Reference: https://github.com/datadrivenconstruction/cad2data-Revit-IFC-DWG-DGN
"""

import logging
from typing import List, Optional

try:
    from core.models import UniversalElement  # type: ignore[import-not-found]
except ModuleNotFoundError:
    # core.models not present in all deployment configurations
    # Define minimal stub so the parser module loads without errors
    class UniversalElement:  # type: ignore[no-redef]
        def __init__(self, element_id="", element_type="", name="", source_file="", metadata=None):
            self.element_id = element_id
            self.element_type = element_type
            self.name = name
            self.source_file = source_file
            self.metadata = metadata or {}

logger = logging.getLogger(__name__)


class RVTParser:
    """
    Parser for Revit .rvt files.

    Uses DDCAdapter (ddc-rvtconverter CLI) when installed.
    Falls back to placeholder mode with warning if DDC not available.
    """

    def __init__(self, converter_dir: Optional[str] = None):
        """
        Args:
            converter_dir: Optional path to DDC .exe directory (Windows only).
                          On Linux, uses ddc-rvtconverter from apt.
        """
        self._converter_dir = converter_dir
        self._ddc = None
        try:
            from parsers.ddc_adapter import DDCAdapter
            self._ddc = DDCAdapter(converter_dir=converter_dir)
            if self._ddc.is_available(".rvt"):
                logger.info("RVTParser: DDC converter available — full Revit parsing enabled")
            else:
                logger.info("RVTParser: DDC converter not installed — placeholder mode")
                self._ddc = None
        except ImportError:
            logger.debug("RVTParser: ddc_adapter not importable — placeholder mode")

    def parse_rvt(self, rvt_path: str) -> List[UniversalElement]:
        """
        Parse a Revit .rvt file and return UniversalElements.

        If DDC converter is available, converts .rvt → XLSX and extracts elements.
        Otherwise, logs a warning and returns empty list.
        """
        if self._ddc is not None:
            try:
                from parsers.ddc_adapter import DDCNotAvailableError
                result = self._ddc.convert(rvt_path, export_mode="standard")
                if result.success:
                    return self._to_universal_elements(result.elements, rvt_path)
                else:
                    logger.error(f"DDC RVT conversion failed: {result.errors}")
                    return []
            except Exception as e:
                logger.error(f"RVT parse error: {e}", exc_info=True)
                return []

        logger.warning(
            f"RVT parsing: placeholder mode. Install ddc-rvtconverter for full parsing. "
            f"File: {rvt_path}"
        )
        return []

    def _to_universal_elements(
        self, ddc_elements: List[dict], source_file: str
    ) -> List[UniversalElement]:
        """Convert DDC XLSX row dicts to UniversalElement objects."""
        elements = []
        for row in ddc_elements:
            try:
                el = UniversalElement(
                    element_id=str(row.get("Id", row.get("Element ID", ""))),
                    element_type=str(row.get("Category", "Unknown")),
                    name=str(row.get("Name", row.get("Type Name", ""))),
                    source_file=source_file,
                    metadata=row,
                )
                elements.append(el)
            except Exception as e:
                logger.debug(f"DDC element conversion skipped: {e}")
        return elements

    def _convert_revit_element(self, element, rvt_path: str) -> Optional[UniversalElement]:
        """Convert a Revit element (requires Revit API — not available in headless mode)."""
        return None

    def _convert_revit_wall(self, wall_element, rvt_path: str) -> Optional[UniversalElement]:
        """Convert a Revit wall element (requires Revit API)."""
        return None

    def _convert_revit_door(self, door_element, rvt_path: str) -> Optional[UniversalElement]:
        """Convert a Revit door element (requires Revit API)."""
        return None

    def _convert_revit_room(self, room_element, rvt_path: str) -> Optional[UniversalElement]:
        """Convert a Revit room element (requires Revit API)."""
        return None
