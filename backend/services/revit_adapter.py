"""Revit Adapter Layer

This module provides a thin abstraction over the Revit API (or its simulation)
used by `RevitService`. By delegating all direct Revit calls to this adapter,
the service logic becomes easier to test and maintain, and we gain a clear seam
for future refactoring.

The adapter follows the domain vocabulary from the `improve-codebase-architecture`
skill: **adapter** = hypothetical seam separating higher-level service logic from
low-level Revit interactions.

DEDUP NOTE (Phase 5):
  This module is NOT a duplicate of revit_integration/adapters/revit_adapter.py.
  They serve different purposes:
    - backend/services/revit_adapter.py       → Backend service adapter (RevitAdapter)
      for RevitService, handles simulation/API mode, wall creation, level/type lookups.
    - revit_integration/adapters/revit_adapter.py → ETAP integration adapters
      (IRevitAdapter, RevitElementAdapter, ETAPDataAdapter, IFCAdapter, GeoJSONAdapter)
      for converting Revit elements to DTOs and ETAP-compatible formats.
  Do NOT merge them.
"""

from typing import Any, Dict, List, Optional


class RevitAdapter:
    """Adapter exposing Revit operations.

    In *simulation* mode the methods return deterministic dummy values.
    In *API* mode (Windows + pythonnet) they forward calls to the real Revit
    objects. The adapter abstracts the import of `Autodesk.Revit.DB` so that
    the rest of the codebase never imports it directly.
    """

    def __init__(self, mode: str = "simulation") -> None:
        """Create the adapter.

        Parameters
        ----------
        mode: str, optional
            "api" - attempt real Revit connection (requires pythonnet).
            "simulation" - safe fallback that generates placeholder data.
        """
        self.mode = mode.lower()
        self._revit_doc = None
        if self.mode == "api":
            self._connect_api()

    # ---------------------------------------------------------------------
    # Internal connection handling
    # ---------------------------------------------------------------------
    def _connect_api(self) -> None:
        """Attempt to load the Revit document via pythonnet.

        If the import fails we gracefully fall back to simulation mode.
        """
        try:
            import clr  # type: ignore

            clr.AddReference("RevitAPI")
            from Autodesk.Revit.DB import Document  # type: ignore

            self._revit_doc = Document()
        except Exception as e:
            import logging

            logging.getLogger(__name__).debug("Revit API connection failed: %s", e, exc_info=True)
            self.mode = "simulation"
            self._revit_doc = None

    # ---------------------------------------------------------------------
    # Public API - wall operations (example)
    # ---------------------------------------------------------------------
    def create_wall(self, start_point: List[float], end_point: List[float]) -> Dict[str, Any]:
        """Create a wall and return its identifier.

        In simulation mode a UUID is generated; in API mode the real Revit
        Wall.Create call would be invoked (omitted here for safety).
        """
        if self.mode == "simulation":
            import uuid

            wall_id = str(uuid.uuid4())
            return {
                "id": wall_id,
                "type": "Wall",
                "start": start_point,
                "end": end_point,
                "simulation": True,
            }
        try:
            # In API mode, Revit wall creation logic would go here
            return {
                "id": "<real-wall-id>",
                "type": "Wall",
                "start": start_point,
                "end": end_point,
                "simulation": False,
                "note": "Real Revit wall creation not implemented in adapter stub",
            }
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Failed to create wall via Revit API")
            raise

    def get_level_by_name(self, name: str) -> Optional[Any]:
        """Return a Revit Level object or ``None``.

        Simulation returns ``None`` because levels are not modelled there.
        """
        if self.mode == "simulation":
            return None
        try:
            from Autodesk.Revit.DB import FilteredElementCollector, Level  # type: ignore

            collector = FilteredElementCollector(self._revit_doc)
            collector.OfClass(Level)
            for level in collector:
                if level.Name == name:
                    return level
        except Exception:
            import logging

            logging.getLogger(__name__).debug("Adapter get_level_by_name error", exc_info=True)
        return None

    def get_wall_type_id(self, wall_type_name: str) -> Optional[Any]:
        """Return the ElementId of a WallType matching ``wall_type_name``.

        In simulation mode returns ``None``.
        """
        if self.mode == "simulation":
            return None
        try:
            from Autodesk.Revit.DB import FilteredElementCollector, WallType  # type: ignore

            collector = FilteredElementCollector(self._revit_doc)
            collector.OfClass(WallType)
            for wt in collector:
                if wt.Name == wall_type_name:
                    return wt.Id
        except Exception:
            import logging

            logging.getLogger(__name__).debug("Adapter get_wall_type_id error", exc_info=True)
        return None


# End of RevitAdapter
