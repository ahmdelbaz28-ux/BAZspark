"""
src/application/coverage_service.py
محرك فحص التغطية مع دعم العوارض (Beams)
"""
from typing import List
from src.core.models import Room, Device, Violation, ViolationSeverity, Point, Beam
from src.auto_placement import suggest_devices
import shapely.geometry as geom
import shapely.ops as ops
import math

class CoverageService:

    def __init__(self, beams: List[Beam] = None):
        self.beams = beams or []

    def check_coverage(self, room: Room, devices: List[Device] = None,
                       standard=None) -> List[Violation]:
        # (نفس منطق الاقتراح السابق)
        if devices is None:
            spacing = standard.get_max_spacing("SmokeDetector") if standard else 9.1
            devices = suggest_devices(room, spacing)

        violations = []
        if not devices:
            violations.append(Violation(
                violation_code="NO_DEVICES",
                severity=ViolationSeverity.CRITICAL,
                description_template="Room '{room_name}' has no devices.",
                params={"room_name": room.name}
            ))
            return violations

        try:
            room_poly = self._room_to_shapely(room)
        except Exception as e:
            violations.append(Violation(
                violation_code="INVALID_GEOMETRY",
                severity=ViolationSeverity.CRITICAL,
                description_template="Invalid geometry: {error}",
                params={"error": str(e)}
            ))
            return violations

        # دوائر التغطية المعدلة
        coverage_parts = []
        for device in devices:
            if not device.position:
                continue
            center = geom.Point(device.position.x, device.position.y)
            radius = device.coverage_radius
            if standard:
                try:
                    radius = standard.get_coverage_radius(device.device_type)
                except:
                    pass

            circle = center.buffer(radius)

            # ----- جديد: إزالة المناطق المحجوبة بالعوارض -----
            blocked_areas = []
            for beam in self.beams:
                if self._beam_blocks_room(beam, room):
                    # شعاع: خط من الكاشف إلى نهاية الغرفة عبر العارضة
                    beam_line = geom.LineString([
                        (beam.start.x, beam.start.y),
                        (beam.end.x, beam.end.y)
                    ])
                    # المنطقة التي تحجبها العارضة = دائرة نصف قطرها صغير حول خط العارضة
                    blocked_zone = beam_line.buffer(beam.depth * 2.0)
                    blocked_areas.append(blocked_zone)

            if blocked_areas:
                blocked_union = ops.unary_union(blocked_areas)
                circle = circle.difference(blocked_union)

            if not circle.is_empty:
                coverage_parts.append(circle)

        if not coverage_parts:
            violations.append(Violation(
                violation_code="NO_COVERAGE",
                severity=ViolationSeverity.CRITICAL,
                description_template="Room '{room_name}' has no effective coverage.",
                params={"room_name": room.name}
            ))
            return violations

        coverage_union = ops.unary_union(coverage_parts)
        uncovered = room_poly.difference(coverage_union)

        if not uncovered.is_empty and uncovered.area > 0.01:
            pct = (uncovered.area / room_poly.area) * 100.0
            violations.append(Violation(
                violation_code="UNCOVERED_AREA",
                severity=ViolationSeverity.CRITICAL,
                description_template=(
                    "Room '{room_name}' has {pct:.1f}% uncovered area "
                    "({area:.2f} m² out of {total:.2f} m²)."
                ),
                params={
                    "room_name": room.name,
                    "pct": pct,
                    "area": uncovered.area,
                    "total": room_poly.area
                }
            ))

        return violations

    def _beam_blocks_room(self, beam: Beam, room: Room) -> bool:
        """هل العارضة داخل الغرفة؟ (اختبار بسيط بالمسافة)"""
        if not room.polygon or not room.polygon.exterior:
            return False
        mid_x = (beam.start.x + beam.end.x) / 2.0
        mid_y = (beam.start.y + beam.end.y) / 2.0
        mid_point = Point(mid_x, mid_y)
        return room.polygon.is_point_inside(mid_point)

    def _room_to_shapely(self, room: Room) -> geom.Polygon:
        if room.polygon and room.polygon.exterior:
            coords = [(p.x, p.y) for p in room.polygon.exterior]
            return geom.Polygon(coords)
        raise ValueError("Room has no valid polygon")
