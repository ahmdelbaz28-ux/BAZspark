"""
backend/services/autocad_service.py

Minimal AutoCAD integration service implementation intended to satisfy
compile-time checks and provide the method surface used by
backend/routers/autocad.py.

On Windows with pywin32 installed, COM calls can be implemented in the future.
For now, behavior is simulation-stubbed so the module is syntactically valid.
"""

from __future__ import annotations

import logging
import os
import platform
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Keep COM imports optional to avoid hard failures on non-Windows dev/CI.
try:
    if IS_WINDOWS:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore

        HAS_AUTOCAD_API = True
    else:
        pythoncom = None  # type: ignore
        win32com = None  # type: ignore
        HAS_AUTOCAD_API = False
except ImportError:
    pythoncom = None  # type: ignore
    win32com = None  # type: ignore
    HAS_AUTOCAD_API = False


class AutoCADService:
    def __init__(self) -> None:
        self.connected: bool = False
        self.acad_app: Any = None
        self.acad_doc: Any = None
        self.acad_util: Any = None
        self._sim_entities: Dict[str, Dict[str, Any]] = {}

    def connect(self) -> bool:
        """
        Connect to AutoCAD.

        Returns:
            bool: True if connected, False otherwise
        """
        # Simulation fallback (no COM) for non-Windows or missing pywin32.
        if not HAS_AUTOCAD_API:
            self.connected = False
            return False

        try:
            assert pythoncom is not None
            assert win32com is not None
            pythoncom.CoInitialize()

            try:
                self.acad_app = win32com.client.GetActiveObject("AutoCAD.Application")
            except Exception:
                self.acad_app = win32com.client.Dispatch("AutoCAD.Application")

            # Best-effort document handle; may not exist depending on AutoCAD state.
            self.acad_doc = getattr(self.acad_app, "ActiveDocument", None)
            self.acad_util = getattr(self.acad_doc, "Utility", None) if self.acad_doc else None

            self.connected = True
            return True
        except Exception as e:
            logger.error("Error connecting to AutoCAD: %s", e)
            self.connected = False
            return False

    def disconnect(self) -> bool:
        try:
            self.acad_app = None
            self.acad_doc = None
            self.acad_util = None
            self.connected = False
            if HAS_AUTOCAD_API and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error("Error disconnecting from AutoCAD: %s", e)
            return False

    def initialize(self) -> bool:
        return self.connect()

    def read_dwg(self, filepath: str) -> Dict[str, Any]:
        if not self.connected:
            return {
                "success": False,
                "error": "AutoCAD service not connected.",
                "entities": [],
                "count": 0,
            }
        if not os.path.exists(filepath):
            return {
                "success": False,
                "error": f"DWG file not found: {filepath}",
                "entities": [],
                "count": 0,
            }
        # Stub response for compile-time.
        return {"success": True, "entities": [], "count": 0, "source_file": filepath}

    def write_dwg(self, filepath: str, entities: List[Dict[str, Any]]) -> bool:
        if not self.connected:
            return False
        # Stub: just ensure the directory exists.
        output_dir = os.path.dirname(filepath)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        return True

    def draw_line(
        self,
        start_point: List[float],
        end_point: List[float],
        layer: str = "0",
        color: int = 0,
    ) -> Optional[Any]:
        if not self.connected:
            return None
        return {
            "type": "LINE",
            "start": start_point,
            "end": end_point,
            "layer": layer,
            "color": color,
        }

    def draw_polyline(
        self,
        vertices: List[List[float]],
        layer: str = "0",
        color: int = 0,
        closed: bool = False,
    ) -> Optional[Any]:
        if not self.connected:
            return None
        return {
            "type": "LWPOLYLINE",
            "vertices": vertices,
            "layer": layer,
            "color": color,
            "closed": closed,
        }

    def draw_circle(
        self,
        center: List[float],
        radius: float,
        layer: str = "0",
        color: int = 0,
    ) -> Optional[Any]:
        if not self.connected:
            return None
        return {
            "type": "CIRCLE",
            "center": center,
            "radius": radius,
            "layer": layer,
            "color": color,
        }

    def draw_text(
        self,
        text: str,
        insertion_point: List[float],
        height: float = 0.2,
        layer: str = "0",
        color: int = 0,
    ) -> Optional[Any]:
        if not self.connected:
            return None
        return {
            "type": "TEXT",
            "text": text,
            "at": insertion_point,
            "height": height,
            "layer": layer,
            "color": color,
        }

    def get_document_info(self) -> Dict[str, Any]:
        if not self.connected or not self.acad_doc:
            return {}
        return {
            "name": getattr(self.acad_doc, "Name", None),
            "path": getattr(self.acad_doc, "Path", None),
        }

    def save(self, filepath: str) -> bool:
        if not self.connected or not self.acad_doc:
            return False

        output_dir = os.path.dirname(filepath)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Best-effort COM save; if it fails, return False.
        try:
            self.acad_doc.SaveAs(filepath)
            return True
        except Exception as e:
            logger.error("Error saving document: %s", e)
            return False

    def delete_entity(self, handle: str) -> bool:
        # Simulation mode: delete from in-memory store.
        if not self.connected or not self.acad_doc:
            return self._sim_entities.pop(handle, None) is not None

        try:
            ent = self.acad_doc.HandleToObject(handle)
            if ent is None:
                return False
            ent.Delete()
            return True
        except Exception as e:
            logger.error("Error deleting entity %s: %s", handle, e)
            return False

    def modify_entity(self, handle: str, properties: Dict[str, Any]) -> bool:
        # Simulation mode: update in-memory store.
        if not self.connected or not self.acad_doc:
            self._sim_entities.setdefault(handle, {}).update(properties)
            return True

        try:
            ent = self.acad_doc.HandleToObject(handle)
            if ent is None:
                return False

            # Best-effort property assignment.
            if "layer" in properties:
                ent.Layer = properties["layer"]
            if "color" in properties:
                ent.Color = properties["color"]
            return True
        except Exception as e:
            logger.error("Error modifying entity %s: %s", handle, e)
            return False
