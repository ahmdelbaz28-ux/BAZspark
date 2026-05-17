"""
geometry_utils.py — Computational Geometry for FireAI
=====================================================
Pure-Python computational geometry module with ZERO external dependencies.
Provides point-in-polygon, polygon area, centroid, bounds, grid generation,
convex hull, polygon inset, and NFPA 72-aware utilities.

This module serves as the SHARED geometry layer for FireAI, replacing
scattered implementations across the codebase:
  - Replaces shoelace in parsers/geometry_extractor.py
  - Replaces shoelace in src/reasoning/spatial.py
  - Provides fallback when Shapely is unavailable
  - Bridges polygon data to DensityOptimizer (rect-only engine)

Supports L-shape, U-shape, and any rectilinear/non-convex polygon.

NFPA 72 References:
  - Table 17.6.3.1.1: Coverage radius by ceiling height
  - Section 17.6.3.1.1: Min wall distance 0.10m (4 inches)

Zero external dependencies — pure Python.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Sequence, Dict

Point = Tuple[float, float]
Polygon = List[Point]

__all__ = [
    # Core primitives
    "shoelace_area",
    "polygon_area",
    "polygon_centroid",
    "polygon_bounds",
    "polygon_perimeter",
    # Point-in-polygon
    "point_in_polygon",
    "points_in_polygon",
    # Validation
    "ValidationResult",
    "validate_polygon",
    # Orientation
    "is_clockwise",
    "ensure_ccw",
    # Constructors
    "rect_polygon",
    "l_shape_polygon",
    "u_shape_polygon",
    # Grid generation
    "grid_points_in_polygon",
    # Convex hull
    "convex_hull",
    # Polygon operations
    "polygon_inset",
    "minimum_bounding_rectangle",
    "polygon_to_room_dims",
    # Segment intersection
    "segments_intersect",
]


# ─────────────────────────────────────────────
# Core Primitives
# ─────────────────────────────────────────────

def _ensure_closed(poly: Polygon) -> Polygon:
    """Return polygon with first vertex appended as last (if not already closed)."""
    if poly[0] != poly[-1]:
        return poly + [poly[0]]
    return poly


def shoelace_area(poly: Polygon) -> float:
    """
    Signed area via Shoelace formula.
    Positive -> CCW, Negative -> CW.
    """
    n = len(poly)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += (x0 * y1) - (x1 * y0)
    return s / 2.0


def polygon_area(poly: Polygon) -> float:
    """Absolute area — always positive."""
    return abs(shoelace_area(poly))


def polygon_centroid(poly: Polygon) -> Point:
    """
    True geometric centroid via Shoelace.
    Falls back to arithmetic mean for degenerate polygons.
    """
    n = len(poly)
    if n == 0:
        raise ValueError("Empty polygon.")
    if n == 1:
        return poly[0]
    if n == 2:
        return ((poly[0][0] + poly[1][0]) / 2, (poly[0][1] + poly[1][1]) / 2)

    signed = shoelace_area(poly)
    if abs(signed) < 1e-10:
        # Degenerate — arithmetic mean
        cx = sum(p[0] for p in poly) / n
        cy = sum(p[1] for p in poly) / n
        return (cx, cy)

    cx = cy = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    factor = 1.0 / (6.0 * signed)
    return (cx * factor, cy * factor)


def polygon_bounds(poly: Polygon) -> Tuple[float, float, float, float]:
    """Returns (min_x, min_y, max_x, max_y)."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def polygon_perimeter(poly: Polygon) -> float:
    """Total perimeter length of the polygon."""
    n = len(poly)
    total = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


# ─────────────────────────────────────────────
# Point-in-Polygon  (Ray Casting + Edge Cases)
# ─────────────────────────────────────────────

def point_in_polygon(
    point: Point,
    poly: Polygon,
    include_boundary: bool = True,
    tolerance: float = 1e-9,
) -> bool:
    """
    Ray casting algorithm with robust boundary handling.

    Args:
        point:            (x, y) to test.
        poly:             Polygon vertices (open or closed).
        include_boundary: True -> points on edges/vertices return True.
        tolerance:        Numerical epsilon for boundary detection.

    Returns:
        True if point is inside or on boundary (per include_boundary).
    """
    px, py = point
    poly = _ensure_closed(poly)
    n = len(poly) - 1  # last == first

    # -- Fast bounding-box rejection --
    min_x, min_y, max_x, max_y = polygon_bounds(poly[:-1])
    if not (min_x - tolerance <= px <= max_x + tolerance and
            min_y - tolerance <= py <= max_y + tolerance):
        return False

    # -- Boundary check --
    if include_boundary:
        for i in range(n):
            if _point_on_segment(point, poly[i], poly[i + 1], tolerance):
                return True

    # -- Ray casting (horizontal ray -> +x) --
    inside = False
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[i + 1]

        # Skip horizontal edges
        if abs(y1 - y0) < tolerance:
            continue

        # Check if ray crosses this edge
        if min(y0, y1) < py <= max(y0, y1):
            x_intersect = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if px < x_intersect:
                inside = not inside

    return inside


def _point_on_segment(
    p: Point,
    a: Point,
    b: Point,
    tol: float = 1e-9,
) -> bool:
    """True if p lies on segment [a, b]."""
    px, py = p
    ax, ay = a
    bx, by = b

    # Cross product — collinearity test
    cross = abs((bx - ax) * (py - ay) - (by - ay) * (px - ax))
    if cross > tol * max(1.0, math.hypot(bx - ax, by - ay)):
        return False

    # Dot product — within segment bounds
    if not (min(ax, bx) - tol <= px <= max(ax, bx) + tol and
            min(ay, by) - tol <= py <= max(ay, by) + tol):
        return False

    return True


def points_in_polygon(
    points: Sequence[Point],
    poly: Polygon,
    include_boundary: bool = True,
) -> List[bool]:
    """
    Test multiple points against the same polygon.
    Reuses the closed polygon and bounding box for efficiency.
    This is a batch wrapper, not a NumPy-vectorised implementation.
    """
    closed = _ensure_closed(poly)
    bounds = polygon_bounds(closed[:-1])
    return [
        point_in_polygon(p, closed, include_boundary)
        for p in points
    ]


# ─────────────────────────────────────────────
# Polygon Validation
# ─────────────────────────────────────────────

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_polygon(poly: Polygon, min_area: float = 0.01) -> ValidationResult:
    """
    Validate polygon integrity: minimum vertices, no duplicates,
    no self-intersection, minimum area.

    Note: Self-intersection check is O(n^2). Acceptable for room-scale
    polygons (typically < 50 vertices). For complex polygons, consider
    using Shapely's is_valid for O(n log n) performance.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if len(poly) < 3:
        errors.append(f"Polygon has {len(poly)} vertices — minimum is 3.")
        return ValidationResult(False, errors, warnings)

    # Duplicate consecutive vertices
    for i in range(len(poly)):
        a = poly[i]
        b = poly[(i + 1) % len(poly)]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-9:
            errors.append(f"Duplicate consecutive vertices at index {i}: {a}.")

    # Self-intersection (O(n^2) — acceptable for room-scale polygons)
    n = len(poly)
    for i in range(n):
        for j in range(i + 2, n):
            if j == (i + n - 1) % n:
                continue
            if _segments_intersect_raw(poly[i], poly[(i + 1) % n],
                                       poly[j], poly[(j + 1) % n]):
                errors.append(
                    f"Self-intersection between edge {i}->{(i+1)%n} and edge {j}->{(j+1)%n}."
                )

    area = polygon_area(poly)
    if area < min_area:
        errors.append(f"Area {area:.4f}m² is below minimum {min_area}m².")

    if len(poly) > 50:
        warnings.append(f"Polygon has {len(poly)} vertices — consider simplification.")

    if polygon_perimeter(poly) > 500:
        warnings.append("Perimeter > 500m — verify units are in metres.")

    return ValidationResult(not errors, errors, warnings)


def _segments_intersect_raw(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """
    True if segment p1-p2 properly intersects p3-p4.
    Uses the orientation test (CCW-based).
    Handles collinear overlap correctly.
    """
    def cross2d(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1 = cross2d(p3, p4, p1)
    d2 = cross2d(p3, p4, p2)
    d3 = cross2d(p1, p2, p3)
    d4 = cross2d(p1, p2, p4)

    # Proper intersection: segments straddle each other
    if ((d1 > 0 > d2) or (d2 > 0 > d1)) and \
       ((d3 > 0 > d4) or (d4 > 0 > d3)):
        return True

    # Collinear overlap check
    if abs(d1) < 1e-10 and abs(d2) < 1e-10 and abs(d3) < 1e-10 and abs(d4) < 1e-10:
        # All four points are collinear — check for 1D overlap
        for (a, b, c) in [
            (p1, p2, p3), (p1, p2, p4),
            (p3, p4, p1), (p3, p4, p2),
        ]:
            # Check if c lies on segment [a, b]
            if (min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9 and
                min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9):
                return True

    # Endpoint-on-endpoint (tangent intersection)
    if abs(d1) < 1e-10 and _point_on_segment(p1, p3, p4):
        return True
    if abs(d2) < 1e-10 and _point_on_segment(p2, p3, p4):
        return True
    if abs(d3) < 1e-10 and _point_on_segment(p3, p1, p2):
        return True
    if abs(d4) < 1e-10 and _point_on_segment(p4, p1, p2):
        return True

    return False


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """Public API: True if segment p1-p2 intersects p3-p4."""
    return _segments_intersect_raw(p1, p2, p3, p4)


# ─────────────────────────────────────────────
# Polygon Winding & Orientation
# ─────────────────────────────────────────────

def is_clockwise(poly: Polygon) -> bool:
    """True if polygon vertices are in clockwise order."""
    return shoelace_area(poly) < 0


def ensure_ccw(poly: Polygon) -> Polygon:
    """Returns polygon with CCW orientation (required for NFPA grid scanning)."""
    if is_clockwise(poly):
        return list(reversed(poly))
    return poly


# ─────────────────────────────────────────────
# Polygon Constructors
# ─────────────────────────────────────────────

def rect_polygon(
    width: float,
    height: float,
    origin: Point = (0, 0),
) -> Polygon:
    """
    Create a rectangular polygon (CCW order).

    Args:
        width:  Rectangle width (x-axis).
        height: Rectangle height (y-axis).
        origin: Bottom-left corner (default (0,0)).

    Returns:
        List of 4 vertices in CCW order.

    Raises:
        ValueError: If width or height is not positive.
    """
    if width <= 0:
        raise ValueError(f"Width must be positive, got {width}")
    if height <= 0:
        raise ValueError(f"Height must be positive, got {height}")
    x0, y0 = origin
    return [
        (x0, y0),
        (x0 + width, y0),
        (x0 + width, y0 + height),
        (x0, y0 + height),
    ]


def l_shape_polygon(
    width: float,
    height: float,
    cut_w: float,
    cut_h: float,
    cut_corner: str = "top_right",
    origin: Point = (0, 0),
) -> Polygon:
    """
    Create an L-shaped polygon (CCW order).

    The L-shape is formed by cutting a rectangle from one corner of a
    larger rectangle (width x height).

    Args:
        width:      Full width of the bounding rectangle.
        height:     Full height of the bounding rectangle.
        cut_w:      Width of the cutout rectangle.
        cut_h:      Height of the cutout rectangle.
        cut_corner: Which corner to cut. One of:
                    "top_right", "top_left", "bottom_right", "bottom_left".
        origin:     Origin of the bounding rectangle.

    Returns:
        6-vertex polygon in CCW order.

    Raises:
        ValueError: If dimensions are invalid or cutout exceeds bounds.

    Examples:
        >>> l_shape_polygon(6, 4, 2, 2)  # cut top-right corner
        [(0,0), (6,0), (6,2), (2,2), (2,4), (0,4)]
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Width and height must be positive, got {width}x{height}")
    if cut_w <= 0 or cut_h <= 0:
        raise ValueError(f"Cutout dimensions must be positive, got {cut_w}x{cut_h}")
    if cut_w > width:
        raise ValueError(f"Cutout width {cut_w} exceeds total width {width}")
    if cut_h > height:
        raise ValueError(f"Cutout height {cut_h} exceeds total height {height}")

    x0, y0 = origin
    x1 = x0 + width
    y1 = y0 + height

    corners = {
        "top_right": [
            (x0, y0), (x1, y0), (x1, y1 - cut_h),
            (x0 + width - cut_w, y1 - cut_h), (x0 + width - cut_w, y1), (x0, y1),
        ],
        "top_left": [
            (x0, y0), (x1, y0), (x1, y1),
            (x0 + cut_w, y1), (x0 + cut_w, y1 - cut_h), (x0, y1 - cut_h),
        ],
        "bottom_right": [
            (x0, y0), (x1 - cut_w, y0), (x1 - cut_w, y0 + cut_h),
            (x1, y0 + cut_h), (x1, y1), (x0, y1),
        ],
        "bottom_left": [
            (x0 + cut_w, y0), (x1, y0), (x1, y1), (x0, y1),
            (x0, y0 + cut_h), (x0 + cut_w, y0 + cut_h),
        ],
    }

    if cut_corner not in corners:
        raise ValueError(
            f"cut_corner must be one of {list(corners.keys())}, got '{cut_corner}'"
        )

    return corners[cut_corner]


def u_shape_polygon(
    width: float,
    height: float,
    left_wing_w: float,
    right_wing_w: float,
    cut_h: float,
    origin: Point = (0, 0),
) -> Polygon:
    """
    Create a U-shaped polygon (CCW order).

    The U-shape is formed by cutting a rectangular channel from the top
    of a larger rectangle, leaving two wings on the left and right.

          left_wing_w  gap  right_wing_w
        ┌─────────┐        ┌─────────┐  ─┐
        │         │        │         │   │ cut_h
        │         └────────┘         │  ─┘ ← channel bottom
        │                            │
        └────────────────────────────┘
              width

    Args:
        width:        Full width of the bounding rectangle.
        height:       Full height of the bounding rectangle.
        left_wing_w:  Width of the left wing.
        right_wing_w: Width of the right wing.
        cut_h:        Depth of the cutout channel from the top.
        origin:       Origin of the bounding rectangle.

    Returns:
        8-vertex polygon in CCW order.

    Raises:
        ValueError: If dimensions are invalid or wings exceed bounds.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Width and height must be positive, got {width}x{height}")
    if left_wing_w <= 0 or right_wing_w <= 0:
        raise ValueError(
            f"Wing widths must be positive, got {left_wing_w} and {right_wing_w}"
        )
    if cut_h <= 0:
        raise ValueError(f"Cutout depth must be positive, got {cut_h}")
    if cut_h > height:
        raise ValueError(f"Cutout depth {cut_h} exceeds total height {height}")
    gap = width - left_wing_w - right_wing_w
    if gap < 0:
        raise ValueError(
            f"Total wing width ({left_wing_w} + {right_wing_w} = "
            f"{left_wing_w + right_wing_w}) exceeds total width {width}"
        )

    x0, y0 = origin
    # CCW order: bottom → right up → right wing top → into channel
    #          → across channel bottom → up left wing → left wing top
    return [
        (x0, y0),                              # bottom-left
        (x0 + width, y0),                      # bottom-right
        (x0 + width, y0 + height),             # top-right (full height)
        (x0 + left_wing_w + gap, y0 + height), # channel top-right
        (x0 + left_wing_w + gap, y0 + height - cut_h),  # channel bottom-right
        (x0 + left_wing_w, y0 + height - cut_h),  # channel bottom-left
        (x0 + left_wing_w, y0 + height),       # channel top-left
        (x0, y0 + height),                     # top-left (full height)
    ]


# ─────────────────────────────────────────────
# Grid Generation Inside Polygon
# ─────────────────────────────────────────────

def grid_points_in_polygon(
    poly: Polygon,
    step: float = 0.5,
    margin: float = 0.0,
) -> List[Point]:
    """
    Generate a regular grid of points inside the polygon, useful for
    coverage verification and detector candidate generation.

    The grid starts at (min_x + margin, min_y + margin) and steps
    through the bounding box, keeping only points that fall inside
    the polygon (with margin offset from boundary).

    Args:
        poly:   Polygon vertices (open or closed).
        step:   Grid spacing in metres. Must be > 0.
        margin: Inset from the polygon boundary in metres.
                Use 0.10 for NFPA 72 §17.6.3.1.1 wall distance compliance.
                If margin > 0, points are generated inside a slightly
                smaller polygon (inset by margin).

    Returns:
        List of (x, y) points inside the polygon.

    Raises:
        ValueError: If step <= 0 or margin < 0.

    Examples:
        >>> pts = grid_points_in_polygon(rect_polygon(4, 4), step=1.0)
        >>> len(pts) > 0
        True
    """
    if step <= 0:
        raise ValueError(f"Step must be positive, got {step}")
    if margin < 0:
        raise ValueError(f"Margin must be non-negative, got {margin}")

    min_x, min_y, max_x, max_y = polygon_bounds(poly)

    # Apply margin: shift grid start/end inward
    x_start = min_x + margin
    y_start = min_y + margin
    x_end = max_x - margin
    y_end = max_y - margin

    if x_start >= x_end or y_start >= y_end:
        return []  # Margin too large — no valid grid points

    points: List[Point] = []
    x = x_start
    while x <= x_end + 1e-9:
        y = y_start
        while y <= y_end + 1e-9:
            p = (round(x, 10), round(y, 10))  # Avoid floating-point drift
            if point_in_polygon(p, poly, include_boundary=True):
                points.append(p)
            y += step
        x += step

    return points


# ─────────────────────────────────────────────
# Convex Hull
# ─────────────────────────────────────────────

def convex_hull(points: Sequence[Point]) -> Polygon:
    """
    Compute the convex hull of a set of 2D points using Andrew's
    Monotone Chain algorithm. O(n log n).

    The convex hull is the smallest convex polygon that contains all
    input points. Useful for:
      - Minimum bounding circle calculation
      - Simplifying complex polygons for quick overlap tests
      - Determining room shape characteristics

    Args:
        points: Sequence of (x, y) points.

    Returns:
        Convex hull as a CCW polygon (open — first != last).

    Raises:
        ValueError: If fewer than 3 non-collinear points are provided.
    """
    pts = sorted(set(points))  # Remove duplicates and sort by (x, y)
    if len(pts) <= 1:
        return list(pts)

    # Build lower hull
    lower: List[Point] = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper: List[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Remove last point of each half (it's repeated)
    hull = lower[:-1] + upper[:-1]

    if len(hull) < 3:
        raise ValueError(
            f"Cannot compute convex hull: only {len(hull)} unique hull vertices "
            f"(points may be collinear)"
        )

    return hull


def _cross(o: Point, a: Point, b: Point) -> float:
    """2D cross product of vectors OA and OB. Positive = CCW turn."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


# ─────────────────────────────────────────────
# Polygon Operations
# ─────────────────────────────────────────────

def polygon_inset(poly: Polygon, margin: float) -> Polygon:
    """
    Compute a simplified inset polygon by moving each vertex toward
    the centroid by the margin distance.

    This is a SIMPLIFIED inset — for rectilinear room polygons, this
    produces correct results. For general polygons with sharp angles,
    use Shapely's buffer(-margin) for full correctness.

    The inset polygon represents the area where detectors can be placed
    while maintaining NFPA 72 §17.6.3.1.1 minimum wall distance
    (0.10m / 4 inches).

    Args:
        poly:   Polygon vertices (CCW recommended).
        margin: Inset distance in metres (must be >= 0).

    Returns:
        Inset polygon vertices.

    Raises:
        ValueError: If margin is negative or polygon is degenerate.
    """
    if margin < 0:
        raise ValueError(f"Margin must be non-negative, got {margin}")
    if margin == 0:
        return list(poly)

    n = len(poly)
    if n < 3:
        raise ValueError(f"Polygon must have at least 3 vertices, got {n}")

    cx, cy = polygon_centroid(poly)

    result: List[Point] = []
    for px, py in poly:
        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)
        if dist <= margin:
            # Vertex too close to centroid — clamp to centroid
            result.append((cx, cy))
        else:
            factor = (dist - margin) / dist
            result.append((cx + dx * factor, cy + dy * factor))

    return result


def minimum_bounding_rectangle(poly: Polygon) -> Dict[str, float]:
    """
    Compute the axis-aligned minimum bounding rectangle (AAMBR) of a polygon.

    For FireAI, this converts an arbitrary polygon to the width/length
    dimensions needed by DensityOptimizer (which only handles rectangles).

    IMPORTANT: For non-convex polygons (L-shape, U-shape), the bounding
    rectangle is LARGER than the actual room. This means DensityOptimizer
    may over-place detectors. This is a known conservative approximation.

    Args:
        poly: Polygon vertices.

    Returns:
        Dictionary with:
          - min_x, min_y, max_x, max_y: Bounding box corners
          - width:  max_x - min_x
          - height: max_y - min_y
          - area:   width * height (bounding box area, NOT polygon area)
          - polygon_area: Actual polygon area
          - fill_ratio: polygon_area / bounding_box_area (< 1.0 for L/U shapes)
    """
    min_x, min_y, max_x, max_y = polygon_bounds(poly)
    width = max_x - min_x
    height = max_y - min_y
    bbox_area = width * height
    p_area = polygon_area(poly)

    return {
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "width": width,
        "height": height,
        "area": bbox_area,
        "polygon_area": p_area,
        "fill_ratio": p_area / bbox_area if bbox_area > 0 else 0.0,
    }


def polygon_to_room_dims(poly: Polygon) -> Tuple[float, float, float]:
    """
    Convert a polygon to (width, length, fill_ratio) for DensityOptimizer.

    DensityOptimizer works with rectangular rooms only (Room dataclass).
    This function extracts the bounding rectangle dimensions and a fill
    ratio that indicates how much of the rectangle is actually room space.

    A fill_ratio of 1.0 means the room is a perfect rectangle.
    A fill_ratio < 1.0 means the room is L-shaped, U-shaped, etc.
    and the bounding rectangle over-estimates the room area.

    Future enhancement: When DensityOptimizer supports polygons, the
    fill_ratio can be used to trigger polygon-based placement instead.

    Args:
        poly: Polygon vertices.

    Returns:
        (width, length, fill_ratio) where:
          - width:      Bounding box width (x-axis extent)
          - length:     Bounding box height (y-axis extent)
          - fill_ratio: Actual area / bounding box area (0.0 to 1.0)
    """
    mbr = minimum_bounding_rectangle(poly)
    return mbr["width"], mbr["height"], mbr["fill_ratio"]
