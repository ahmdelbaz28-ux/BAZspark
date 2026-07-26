from __future__ import annotations
import logging
import threading
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.services.autocad_service import AutoCADService
from backend.services.revit_service import RevitService

logger = logging.getLogger(__name__)

class CADElement(BaseModel):
    id: str = Field(..., description="Unique element/entity identifier or handle")
    provider: str = Field(..., description="Provider: autocad or revit")
    type: str = Field(..., description="Type of element (e.g. Wall, Line, Circle)")
    layer: Optional[str] = Field(None, description="Layer or category of the element")
    color: Optional[int] = Field(None, description="Color code if applicable")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom parameters or geometries")


class CADGateway:
    """
    Unified CAD/BIM Integration Engine.
    Exposes a unified interface for connection, status checking, reading,
    writing, and drawing operations, routing them to AutoCAD or Revit.
    """
    _instance: Optional[CADGateway] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> CADGateway:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._autocad_service = AutoCADService()
        self._revit_service = RevitService()
        self._initialized = True
        logger.info("CADGateway initialized.")

    def get_service(self, provider: str) -> Any:
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            return self._autocad_service
        elif provider_lower == "revit":
            return self._revit_service
        else:
            raise ValueError(f"Unknown CAD provider: {provider}")

    def connect(self, provider: str, **kwargs: Any) -> bool:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            visible = kwargs.get("visible", True)
            force_new = kwargs.get("force_new", False)
            return service.connect(visible=visible, force_new=force_new)
        elif provider_lower == "revit":
            method = kwargs.get("method", "simulation")
            return service.connect(method=method)
        return False

    def disconnect(self, provider: str) -> bool:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            service.connected = False
            service.simulation_mode = False
            return True
        elif provider_lower == "revit":
            service.disconnect()
            return True
        return False

    def get_status(self, provider: str) -> Dict[str, Any]:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            return {
                "connected": service.connected,
                "simulation_mode": getattr(service, "simulation_mode", False),
                "details": {"app": "AutoCAD", "has_api": True}
            }
        elif provider_lower == "revit":
            return {
                "connected": service.connected,
                "connection_method": service.connection_method,
                "simulation_mode": service.simulation_mode
            }
        return {"connected": False}

    def read_drawing(self, provider: str, filepath: str) -> List[CADElement]:
        service = self.get_service(provider)
        elements = []
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            result = service.read_dwg(filepath)
            if result.get("success", False):
                entities = result.get("entities", [])
                for ent in entities:
                    handle = ent.get("handle") or ent.get("Handle") or ""
                    obj_name = ent.get("object_name") or ent.get("ObjectName") or "Unknown"
                    layer = ent.get("layer") or ent.get("Layer") or "0"
                    color = ent.get("color") or ent.get("Color") or 0
                    elements.append(CADElement(
                        id=handle,
                        provider="autocad",
                        type=obj_name,
                        layer=layer,
                        color=color,
                        properties=ent
                    ))
        elif provider_lower == "revit":
            revit_elements = service.extract_element_data()
            for elem in revit_elements:
                elem_id = elem.get("id") or elem.get("Id") or ""
                name = elem.get("name") or elem.get("Name") or "Element"
                cat = elem.get("category") or elem.get("Category") or ""
                elements.append(CADElement(
                    id=str(elem_id),
                    provider="revit",
                    type=name,
                    layer=cat,
                    properties=elem
                ))
        return elements

    def write_drawing(self, provider: str, filepath: str, elements: List[CADElement]) -> bool:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            entities = []
            for elem in elements:
                entities.append({
                    "Handle": elem.id,
                    "ObjectName": elem.type,
                    "Layer": elem.layer or "0",
                    "Color": elem.color or 0
                })
            return service.write_dwg(filepath, entities)
        elif provider_lower == "revit":
            logger.info("Writing %d elements to Revit file %s (Simulation)", len(elements), filepath)
            return True
        return False

    def draw_line(self, provider: str, start_point: List[float], end_point: List[float], layer: str = "0", color: int = 256) -> str:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            return service.draw_line(start_point, end_point, layer, color)
        elif provider_lower == "revit":
            return service.create_wall(start_point, end_point)
        return ""

    def draw_polyline(self, provider: str, vertices: List[List[float]], layer: str = "0", color: int = 256, closed: bool = False) -> str:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            return service.draw_polyline(vertices, layer, color, closed)
        elif provider_lower == "revit":
            return service.create_floor(vertices)
        return ""

    def draw_circle(self, provider: str, center: List[float], radius: float, layer: str = "0", color: int = 256) -> str:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            return service.draw_circle(center, radius, layer, color)
        elif provider_lower == "revit":
            return service.create_column(center, "Round Column")
        return ""

    def draw_text(self, provider: str, text: str, insertion_point: List[float], height: float = 0.2, layer: str = "0", color: int = 256) -> str:
        service = self.get_service(provider)
        provider_lower = provider.lower()
        if provider_lower == "autocad":
            return service.draw_text(text, insertion_point, height, layer, color)
        elif provider_lower == "revit":
            return service.create_family_instance(text, "TextNote", insertion_point)
        return ""
