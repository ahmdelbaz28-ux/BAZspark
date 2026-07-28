# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
dxf_parser.py — FireAI V5.1.0
CRITICAL SAFETY: Reads real DXF and produces valid Polygons only.
Any invalid geometry is rejected, never guessed.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List

import ezdxf
from ezdxf import recover
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid

from parsers._base import ParserBase

logger = logging.getLogger("fireai.dxf_parser")


@dataclass
class ParsedRoom:
    room_id: str
    polygon: Polygon
    source_layer: str
    area_m2: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.area_m2 = round(self.polygon.area, 3)


@dataclass
class DXFParseResult:
    source_file: str
    dxf_units: str
    scale_to_meters: float
    rooms: List[ParsedRoom] = field(default_factory=list)
    skipped_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def room_count(self) -> int:
        return len(self.rooms)

    @property
    def total_area_m2(self) -> float:
        return round(sum(r.area_m2 for r in self.rooms), 2)


class DXFParser(ParserBase):
    """CRITICAL: Never trust DXF geometry. Always validate."""

    allowed_extensions = {'.dxf'}

    MIN_ROOM_AREA_M2: float = 2.0
    MAX_ROOM_AREA_M2: float = 50_000.0

    INSUNITS_TO_METERS = {
        0: 1.0,
        1: 0.0254,
        2: 0.3048,
        3: 1609.344,
        4: 0.001,
        5: 0.01,
        6: 1.0,
        7: 1000.0,
        8: 2.54e-8,
    }

    def __init__(self, min_area: float = MIN_ROOM_AREA_M2, max_area: float = MAX_ROOM_AREA_M2):
        self.min_area = min_area
        self.max_area = max_area

    def parse(self, dxf_path: str) -> DXFParseResult:
        safe_path = self.validate_input(dxf_path)
        logger.info("Parsing DXF: %s", safe_path)

        try:
            doc = ezdxf.readfile(safe_path)
        except ezdxf.DXFStructureError:
            logger.warning("DXF corrupt — attempting recovery")
            doc, auditor = recover.readfile(safe_path)
            if auditor.has_errors:
                raise RuntimeError(f"DXF '{safe_path}' unrecoverable. Errors: {len(auditor.errors)}")

        units = self._detect_units(doc)

        if units not in self.INSUNITS_TO_METERS:
            raise ValueError(f"Unknown DXF units code: '{units}'")
        scale = self.INSUNITS_TO_METERS[units]

        msp = doc.modelspace()
        lines = self._extract_lines(msp, scale)
        polys = self._lines_to_valid_polygons(lines)

        rooms = []
        skipped = 0

        for i, poly in enumerate(polys):
            rid = f"ROOM_{i + 1:03d}"

            area = poly.area
            if not math.isfinite(area):
                logger.warning("%s: area is %s (NaN/Inf) — SKIPPED", rid, area)
                skipped += 1
                continue

            if area < self.min_area:
                skipped += 1
                continue
            if area > self.max_area:
                logger.warning("%s: area %sm² > max %sm² — SKIPPED (possible unit error)", rid, poly.area, self.max_area)
                skipped += 1
                continue

            rooms.append(
                ParsedRoom(
                    room_id=rid,
                    polygon=poly,
                    source_layer="A-WALL",
                    warnings=[],
                )
            )

        if not rooms:
            raise RuntimeError(f"No valid rooms in '{safe_path}'")

        return DXFParseResult(
            source_file=dxf_path,
            dxf_units=units,
            scale_to_meters=scale,
            rooms=rooms,
            skipped_count=skipped,
        )

    def _detect_units(self, doc) -> int:
        units = doc.header.get("$INSUNITS", 6)

        if units != 0:
            return units

        detected = self._detect_unit_heuristic(doc)
        if detected is not None:
            logger.info("Units auto-detected: %s", detected)
            return detected

        raise RuntimeError(
            "Cannot determine DXF units. INSUNITS=0 and coordinate analysis inconclusive. "
            "File may be corrupted or use non-standard units. "
            "CRITICAL: Cannot proceed - incorrect unit = incorrect coverage calculation."
        )

    def _detect_unit_heuristic(self, doc) -> int | None:
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union
        from shapely.validation import make_valid

        msp = doc.modelspace()

        candidates = [
            (1, "meters"),
            (0.001, "mm x 1000 -> m"),
            (0.01, "cm x 100 -> m"),
            (0.3048, "feet x 0.3048 -> m"),
        ]

        valid_scales = []

        for scale, unit_name in candidates:
            lines = []
            for ent in msp:
                if ent.dxftype() == "LINE":
                    s = (ent.dxf.start.x * scale, ent.dxf.start.y * scale)
                    e = (ent.dxf.end.x * scale, ent.dxf.end.y * scale)
                    if s != e:
                        lines.append(LineString([s, e]))
                elif ent.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                    try:
                        pts = [(p[0] * scale, p[1] * scale) for p in ent.get_points()]
                        if len(pts) >= 3 and ent.closed:
                            lines.append(LineString(pts))
                    except Exception as exc:
                        logger.debug("Polyline point extraction failed: %s", exc)

            if not lines:
                continue

            merged = unary_union(lines)
            raw_polys = polygonize(merged)

            valid_count = 0
            for p in raw_polys:
                if not p.is_valid:
                    p = make_valid(p)
                if p.is_valid and self.MIN_ROOM_AREA_M2 <= p.area <= self.MAX_ROOM_AREA_M2:
                    valid_count += 1

            if valid_count > 0:
                valid_scales.append((scale, unit_name, valid_count))

        if len(valid_scales) >= 1:
            valid_scales.sort(key=lambda x: -x[2])
            scale, name, count = valid_scales[0]
            logger.info("Unit detected: %s -> %s valid rooms", name, count)

            _SCALE_TO_UNIT = {0.001: 4, 0.01: 5, 0.3048: 2}
            return _SCALE_TO_UNIT.get(scale, 6)

        logger.error("No valid unit scale found")
        return None

    def _extract_lines(self, msp, scale: float) -> List:
        from shapely.geometry import LineString

        lines = []
        for ent in msp:
            if ent.dxftype() == "LINE":
                sx, sy = ent.dxf.start.x * scale, ent.dxf.start.y * scale
                ex, ey = ent.dxf.end.x * scale, ent.dxf.end.y * scale
                if not (math.isfinite(sx) and math.isfinite(sy) and math.isfinite(ex) and math.isfinite(ey)):
                    logger.warning("Skipping LINE with non-finite coordinates: start=(%s,%s) end=(%s,%s)", sx, sy, ex, ey)
                    continue
                s, e = (sx, sy), (ex, ey)
                if s != e:
                    lines.append(LineString([s, e]))
            elif ent.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                try:
                    raw_pts = [(p[0] * scale, p[1] * scale) for p in ent.get_points()]
                    if not all(math.isfinite(x) and math.isfinite(y) for x, y in raw_pts):
                        bad_count = sum(1 for x, y in raw_pts if not (math.isfinite(x) and math.isfinite(y)))
                        logger.warning(
                            "Polyline had %d non-finite vertices out of %d total. "
                            "Geometry would be corrupted by filtering — skipping this entity.",
                            bad_count, len(raw_pts),
                        )
                        continue
                    pts = raw_pts
                    if len(pts) >= 3 and ent.closed:
                        lines.append(LineString(pts))
                except Exception as e:
                    logger.debug("Polyline skip: %s", e)
            elif ent.dxftype() == "CIRCLE":
                try:
                    poly = self._circle_to_polygon(ent, scale)
                    if poly and poly.is_valid:
                        lines.append(poly.exterior)
                except Exception as e:
                    logger.debug("Circle skip: %s", e)
            elif ent.dxftype() == "ARC":
                try:
                    segments = self._arc_to_segments(ent, scale)
                    lines.extend(segments)
                except Exception as e:
                    logger.debug("Arc skip: %s", e)
            elif ent.dxftype() == "SPLINE":
                try:
                    segments = self._spline_to_segments(ent, scale)
                    lines.extend(segments)
                except Exception as e:
                    logger.debug("Spline skip: %s", e)
        return lines

    def _circle_to_polygon(self, entity, scale):
        c = Point(entity.dxf.center.x * scale, entity.dxf.center.y * scale)
        r = entity.dxf.radius * scale
        return c.buffer(r, quad_segs=36)

    def _arc_to_segments(self, entity, scale, num_points: int = 32):
        c = Point(entity.dxf.center.x * scale, entity.dxf.center.y * scale)
        r = entity.dxf.radius * scale

        start_angle = math.radians(entity.dxf.start_angle)
        end_angle = math.radians(entity.dxf.end_angle)

        if end_angle < start_angle:
            end_angle += 2 * math.pi

        total_angle = end_angle - start_angle
        step = total_angle / num_points

        points = []
        for i in range(num_points + 1):
            angle = start_angle + (i * step)
            x = c.x + r * math.cos(angle)
            y = c.y + r * math.sin(angle)
            points.append((x, y))

        if len(points) >= 2:
            from shapely.geometry import LineString

            ls = LineString(points)
            return [ls]
        return []

    def _spline_to_segments(self, entity, scale, num_segments: int = 64):
        try:
            ctrl_pts = entity.control_points
            if ctrl_pts is None or len(ctrl_pts) < 2:
                return []

            points = [(p.dxf.location.x * scale, p.dxf.location.y * scale) for p in ctrl_pts]

            if len(points) < 2:
                return []

            from shapely.geometry import LineString

            base_line = LineString(points)

            sampled_points = []
            for i in range(num_segments + 1):
                t = i / num_segments
                if t <= 1.0:
                    pt = base_line.interpolate(t, normalized=True)
                    sampled_points.append((pt.x, pt.y))

            segments = []
            for i in range(len(sampled_points) - 1):
                segments.append(LineString([sampled_points[i], sampled_points[i + 1]]))

            return segments
        except Exception as e:
            logger.debug("Spline conversion failed: %s", e)
            return []

    def _is_duplicate(self, poly1: Polygon, poly2: Polygon) -> bool:
        if not poly1.intersects(poly2):
            return False

        intersection = poly1.intersection(poly2)
        min_area = min(poly1.area, poly2.area)

        if min_area <= 0:
            return False

        overlap_ratio = intersection.area / min_area
        return overlap_ratio > 0.9

    def _remove_duplicates(self, polygons: List[Polygon]) -> List[Polygon]:
        if len(polygons) <= 1:
            return polygons

        unique = []
        for poly in polygons:
            is_dup = False
            for existing in unique:
                if self._is_duplicate(poly, existing):
                    is_dup = True
                    if poly.area > existing.area:
                        unique.remove(existing)
                        unique.append(poly)
                    break
            if not is_dup:
                unique.append(poly)

        return unique

    def _lines_to_valid_polygons(self, lines) -> List[Polygon]:
        if not lines:
            return []

        merged = unary_union(lines)
        raw_polys = list(polygonize(merged))

        valid_polys = self._remove_duplicates(raw_polys)

        valid = []
        for p in valid_polys:
            if not p.is_valid:
                p = make_valid(p)

            if isinstance(p, MultiPolygon):
                valid.extend([g for g in p.geoms if g.is_valid])
            elif isinstance(p, Polygon) and not p.is_empty:
                valid.append(p)

        valid.sort(key=lambda x: x.area, reverse=True)
        return valid
