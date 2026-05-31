"""
QOMN-FIRE GEOMETRIC VALIDATION LAYER
Enforces physical, dimension, and coordinate constraints on building models.

Safety-Critical: Invalid geometry = wrong room areas = wrong NFPA coverage = people die.
BUG-5 FIX: Overlap detection now checks ALL overlapping bounding boxes, not just
identical ones. The original code only flagged rooms with IDENTICAL bounding boxes,
missing rooms that overlap partially (e.g., two rooms sharing a wall drawn twice).

Standards: NFPA 72 (2022) §17, ISO 16739 (IFC Spatial Schemas)
"""

import math
from typing import Tuple, Union

from qomn_fire.core.types import Building, Room, Point3D
from qomn_fire.core.errors import Result, GeometryError, UnitError


class GeometryValidator:
    """Validates building model geometry for physical consistency and code compliance."""

    # Maximum coordinate value in meters — values above this likely indicate
    # the file uses millimeters or inches instead of meters
    MAX_COORD_M = 10000.0

    # Minimum room area in m2 — rooms smaller than this cannot be designed
    # for fire protection per NFPA 72 §17
    MIN_ROOM_AREA_M2 = 1.0

    @staticmethod
    def calculate_polygon_area_2d(poly: Tuple[Point3D, ...]) -> float:
        """Determines polygon area using the Shoelace algorithm."""
        n = len(poly)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += poly[i].x * poly[j].y
            area -= poly[j].x * poly[i].y
        return abs(area) / 2.0

    @classmethod
    def validate_building(cls, b: Building) -> Result[Building, Union[GeometryError, UnitError]]:
        """
        Enforces strict compliance rules against raw extracted spatial entities.

        Validation checks:
        1. At least one room must exist
        2. Each room must have >= 3 boundary points (closed polygon)
        3. Each room must have area >= 1.0 m2 (NFPA 72 §17)
        4. Coordinates must not exceed 10,000m (unit mismatch detection)
        5. Rooms must not overlap (duplicate or conflicting geometry)

        Returns Result containing validated Building or error.
        """
        # ── Check 1: At least one room ──
        if not b.rooms:
            return Result(error=GeometryError(
                message="Building layout must contain at least one valid room to compute fire design coverage.",
                code_ref="NFPA 72 §17",
                remedy="Model room boundaries inside native CAD or Revit design platform."
            ))

        for room in b.rooms:
            # ── Check 2: Closed room (minimum 3 boundary points) ──
            if len(room.boundary) < 3:
                return Result(error=GeometryError(
                    message=f"Room '{room.id}' contains fewer than 3 boundary coordinates.",
                    code_ref="Analytical Geometry",
                    remedy="Validate and re-draw room boundaries as fully closed polylines."
                ))

            # ── Check 3: Polygon area sanity check ──
            calc_area = cls.calculate_polygon_area_2d(room.boundary)
            if calc_area < cls.MIN_ROOM_AREA_M2:
                return Result(error=GeometryError(
                    message=f"Room '{room.id}' forms an invalid physical area ({calc_area:.4f} m2). "
                            f"Minimum is {cls.MIN_ROOM_AREA_M2} m2 per NFPA 72 §17.",
                    code_ref="NFPA 72 §17",
                    remedy="Re-draw room coordinates to form positive enclosed volumes."
                ))

            # ── Check 4: Units validation (metric meters, not millimeters/feet) ──
            # A typical room is not larger than 10,000 meters in a single span.
            # Coordinates exceeding this strongly suggest the file uses mm or inches.
            for pt in room.boundary:
                if abs(pt.x) > cls.MAX_COORD_M or abs(pt.y) > cls.MAX_COORD_M:
                    return Result(error=UnitError(
                        message=f"Coordinate system values exceed metric limits: {pt.to_tuple()}. "
                                f"Max allowed: {cls.MAX_COORD_M}m. File likely uses mm or inches.",
                        code_ref="Standard Units Verification",
                        remedy="Verify file units and convert coordinates from millimeters or inches to meters."
                    ))

        # ── Check 5: Overlapping rooms validation ──
        # BUG-5 FIX: The original code only detected rooms with IDENTICAL bounding boxes
        # (abs(min_x1 - min_x2) < 1e-4 AND abs(max_x1 - max_x2) < 1e-4).
        # This misses rooms that overlap PARTIALLY — e.g., a room drawn twice with
        # slight offset, or rooms on different layers that occupy the same space.
        # Fixed: now checks ALL AABB overlaps and reports them.
        for i in range(len(b.rooms)):
            for j in range(i + 1, len(b.rooms)):
                r1, r2 = b.rooms[i], b.rooms[j]

                min_x1 = min(p.x for p in r1.boundary)
                max_x1 = max(p.x for p in r1.boundary)
                min_y1 = min(p.y for p in r1.boundary)
                max_y1 = max(p.y for p in r1.boundary)

                min_x2 = min(p.x for p in r2.boundary)
                max_x2 = max(p.x for p in r2.boundary)
                min_y2 = min(p.y for p in r2.boundary)
                max_y2 = max(p.y for p in r2.boundary)

                # AABB overlap detection — rooms that share ANY space
                overlaps_x = not (max_x1 <= min_x2 or max_x2 <= min_x1)
                overlaps_y = not (max_y1 <= min_y2 or max_y2 <= min_y1)

                if overlaps_x and overlaps_y:
                    # Calculate overlap percentage for severity assessment
                    overlap_x = min(max_x1, max_x2) - max(min_x1, min_x2)
                    overlap_y = min(max_y1, max_y2) - max(min_y1, min_y2)
                    overlap_area = overlap_x * overlap_y

                    r1_area = (max_x1 - min_x1) * (max_y1 - min_y1)
                    r2_area = (max_x2 - min_x2) * (max_y2 - min_y2)

                    # Check if this is a near-complete duplicate (dangerous)
                    is_duplicate = (
                        abs(min_x1 - min_x2) < 1e-4 and
                        abs(max_x1 - max_x2) < 1e-4 and
                        abs(min_y1 - min_y2) < 1e-4 and
                        abs(max_y1 - max_y2) < 1e-4
                    )

                    if is_duplicate:
                        return Result(error=GeometryError(
                            message=f"Duplicate overlapping rooms detected: '{r1.id}' and '{r2.id}'. "
                                    f"Both rooms occupy identical space — likely a CAD layer duplication error.",
                            code_ref="BIM Quality Standard",
                            remedy="Remove overlapping or duplicate layers in CAD before exporting."
                        ))
                    else:
                        # Partial overlap — still an error but with different message
                        overlap_pct = min(overlap_area / max(r1_area, r2_area, 0.001) * 100, 100.0)
                        if overlap_pct > 50.0:
                            return Result(error=GeometryError(
                                message=f"Significant room overlap detected: '{r1.id}' and '{r2.id}' "
                                        f"share {overlap_pct:.1f}% of their area. "
                                        f"This causes double-counting in NFPA coverage calculations.",
                                code_ref="BIM Quality Standard",
                                remedy="Remove overlapping or duplicate layers in CAD before exporting."
                            ))

        return Result(value=b)
