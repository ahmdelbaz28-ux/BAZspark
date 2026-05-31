"""
QOMN-FIRE INTEGRATION ROUTING AND BOUNDARY PLACEMENTS
Reference Standard: NEC 760 spatial segregation compliance rules.

BUG-22 FIX: Boundary generation now handles diagonal (non-axis-aligned) segments.
The original code only generated boundary rectangles for horizontal and vertical
segments, ignoring diagonal segments entirely. This produced empty boundary lists
for routes with diagonal segments, causing hatch placement to fail silently.
Now uses perpendicular offset to generate boundaries for any segment orientation.
"""

import math
from typing import Tuple, List, Dict, Any, Union
import ezdxf
from qomn_fire.core.types import Point3D, ConduitType, ConduitRun, HatchSpec, Device
from qomn_fire.core.errors import Result, NECViolationError, HatchPlacementError
from qomn_fire.engine.routing import GridMap3D, astar_route_3d
from qomn_fire.drawing.hatch_engine import place_boundary_hatch

def route_conduit_and_hatch(
    grid_map: GridMap3D,
    doc: ezdxf.document.Drawing,
    start: Point3D,
    end: Point3D,
    conduit: ConduitType,
    conduit_id: str,
    spec: HatchSpec
) -> Result[Tuple[ConduitRun, Any], Union[NECViolationError, HatchPlacementError]]:
    route_res = astar_route_3d(grid_map, start, end, conduit, conduit_id)
    if route_res.is_failure:
        return Result(error=route_res.error())

    conduit_run = route_res.unwrap()
    pts = conduit_run.points

    boundary_points = []
    width_m = 0.20

    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i+1]
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        seg_len = math.sqrt(dx * dx + dy * dy)

        if seg_len < 1e-8:
            continue  # Skip zero-length segments

        # BUG-22 FIX: Use perpendicular offset for any segment orientation.
        # For a segment from P1 to P2 with direction (dx, dy), the perpendicular
        # unit vector is (-dy/len, dx/len). Offset the segment by width_m on
        # both sides to create a rectangular boundary around the conduit path.
        # This works for horizontal, vertical, AND diagonal segments.
        perp_x = -dy / seg_len * width_m
        perp_y = dx / seg_len * width_m

        boundary_points.extend([
            (round(p1.x + perp_x, 4), round(p1.y + perp_y, 4)),
            (round(p2.x + perp_x, 4), round(p2.y + perp_y, 4)),
            (round(p2.x - perp_x, 4), round(p2.y - perp_y, 4)),
            (round(p1.x - perp_x, 4), round(p1.y - perp_y, 4))
        ])

    unique_points = []
    for p in boundary_points:
        if p not in unique_points:
            unique_points.append(p)

    hatch_res = place_boundary_hatch(doc, unique_points, spec, conduit_id)
    if hatch_res.is_failure:
        return Result(error=hatch_res.error())

    msp = doc.modelspace()
    for i in range(len(pts) - 1):
        msp.add_line(
            pts[i].to_tuple()[:2],
            pts[i+1].to_tuple()[:2],
            dxfattribs={"layer": "A-FIRE-CABLES", "color": 2}
        )

    return Result(value=(conduit_run, hatch_res.unwrap()))
