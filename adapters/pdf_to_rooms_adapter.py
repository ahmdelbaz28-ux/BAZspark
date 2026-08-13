# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
adapters/pdf_to_rooms_adapter — PDF wall extraction to FireAI Room adapter.

Bridges the GeometryExtractor (which returns raw wall geometry) to the
``fireai.core`` ``Room`` seam. This adapter extracts closed wall loops,
constructs room polygons, classifies occupancy types, and selects the
safest NFPA 72 detector technology for a room.

The adapter CROSSES the canonical seam: it produces/consumes
``fireai.core.contracts.Room``, not a local room variant. There is no
second ``Room`` definition here (deep-modules doctrine: one canonical
type; everything else is a boundary mapper).

Safety-critical: Empty rooms = zero fire protection zones = FAILED parse.
Detector selection is deterministic — never AI — and defaults to the most
conservative (protective) technology whenever occupancy is uncertain.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fireai.core.contracts import DetectorType, Room

logger = logging.getLogger(__name__)

# Callers may hand either a canonical ``Room`` or the raw dict shape
# ``{"name", "occupancy_type", "area_sqm"}`` that travels in pipeline
# state. The adapter maps both to a canonical ``Room`` before deciding.
Roomish = Room | Mapping[str, Any]


def _as_room(room: Roomish) -> Room:
    """Map a canonical Room or raw dict to a canonical Room (boundary mapper)."""
    if isinstance(room, Room):
        return room
    if isinstance(room, Mapping):
        name = str(room.get("name") or "")
        occupancy = room.get("occupancy_type")
        if occupancy is not None:
            occupancy = str(occupancy)
        area_sqm = room.get("area_sqm", room.get("area", 0.0)) or 0.0
        try:
            area_sqm = float(area_sqm)
        except (TypeError, ValueError):
            area_sqm = 0.0
        return Room(
            name=name,
            occupancy_type=occupancy or "unknown",
            area_sqm=area_sqm,
        )
    raise TypeError(
        f"select_safe_detector_type expects a Room or a dict with "
        f"'name'/'occupancy_type'/'area_sqm', got {type(room).__name__}. "
        "A silent per-room AttributeError is never acceptable."
    )


def extract_rooms_from_walls(  # NOSONAR — S3776: cognitive complexity is inherent to the safety-critical algorithm
    walls: list[Any],
    pdf_path: str = "",  # NOSONAR — S1172: parameter retained for API stability
) -> tuple[list[Room], dict[str, Any]]:
    """
    Extract rooms from a list of wall geometry objects.

    Given wall segments (lines/polygons), this function:
    1. Identifies closed loops of walls forming rooms
    2. Constructs polygon geometry for each room
    3. Classifies occupancy type based on room name heuristics
    4. Returns canonical ``Room`` objects and a diagnostic report

    Args:
        walls: List of wall geometry objects from GeometryExtractor
        pdf_path: Source PDF file path for diagnostic reporting

    Returns:
        Tuple of (rooms_list, report_dict) where report_dict contains
        status, wall_count, and any processing warnings.

    """
    rooms: list[Room] = []
    report: dict[str, Any] = {
        "status": "ok",
        "wall_count": len(walls) if walls else 0,
        "warnings": [],
    }

    if not walls:
        report["status"] = "no_walls"
        report["warnings"].append("No wall geometry found in PDF")
        return rooms, report

    try:
        # Attempt to form room polygons from wall segments
        from shapely.geometry import LineString
        from shapely.ops import polygonize

        lines = []
        for wall in walls:
            if hasattr(wall, 'coords'):
                try:
                    lines.append(LineString(wall.coords))
                except Exception:
                    continue
            elif hasattr(wall, 'geom_type'):
                lines.append(wall)

        if lines:
            polygons = list(polygonize(lines))
            for i, poly in enumerate(polygons):
                if poly.is_valid and not poly.is_empty:
                    room_name = f"Room_{i + 1}"
                    occupancy = _classify_occupancy(room_name)
                    rooms.append(Room(
                        name=room_name,
                        occupancy_type=occupancy,
                        area_sqm=poly.area,
                        polygon=poly,
                    ))

        if not rooms:
            report["status"] = "no_closed_loops"
            report["warnings"].append(
                "Walls found but no closed room loops could be formed"
            )

    except ImportError:
        report["status"] = "shapely_unavailable"
        report["warnings"].append(
            "Shapely library not available for polygon reconstruction"
        )
        logger.warning("Shapely not available — room extraction limited")
    except Exception as e:
        report["status"] = "error"
        report["warnings"].append(f"Room extraction error: {e}")
        logger.exception("Room extraction failed: %s", e)

    return rooms, report


def select_safe_detector_type(
    room: Roomish,
    ceiling_height: float = 3.0,
) -> DetectorType:
    """
    Select the safest detector technology for a given room.

    Accepts the caller's actual data shape — a canonical
    ``fireai.core.contracts.Room`` or a dict ``{name, occupancy_type,
    area_sqm}`` as produced by the workflow pipeline — and returns a typed
    ``DetectorType`` whose ``.name`` is the canonical uppercase technology
    ("SMOKE", "HEAT", "DUCT", "BEAM").

    Safety-critical decision: Always defaults to the most conservative
    (protective) detector type when uncertain. This is a DETERMINISTIC
    selection (no AI) per NFPA 72-2022.

    Args:
        room: Room record (canonical Room or dict with name/
            occupancy_type/area_sqm).
        ceiling_height: Room ceiling height in metres.

    Returns:
        A ``fireai.core.contracts.DetectorType`` value with a canonical
        uppercase ``.name``.

    Raises:
        TypeError: if ``room`` is neither a Room nor a mapping (contract
            violation — never a silent per-room AttributeError).
    """
    # Default to smoke detector (most sensitive, most protective)
    canonical = _as_room(room)
    occupancy = canonical.occupancy_type or "unknown"
    if occupancy in ("kitchen", "mechanical", "utility"):
        return DetectorType.HEAT
    if occupancy in ("duct", "hvac"):
        return DetectorType.DUCT
    if ceiling_height > 10.6:  # NFPA 72 §17.7.3.4 projected beam
        return DetectorType.BEAM
    return DetectorType.SMOKE


def _classify_occupancy(room_name: str) -> str:
    """Classify room occupancy type from name heuristics."""
    name_lower = room_name.lower()
    if any(kw in name_lower for kw in ("kitchen", "cook")):
        return "kitchen"
    if any(kw in name_lower for kw in ("mech", "utility", "plant")):
        return "mechanical"
    if any(kw in name_lower for kw in ("office", "work")):
        return "business"
    if any(kw in name_lower for kw in ("corridor", "hall", "lobby")):
        return "corridor"
    if any(kw in name_lower for kw in ("stair", "stairwell")):
        return "stairwell"
    return "unknown"
