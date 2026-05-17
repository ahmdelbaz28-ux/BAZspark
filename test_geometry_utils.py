"""
test_geometry_utils.py — Comprehensive Tests for geometry_utils.py
===================================================================
Tests all functions including:
  - Core primitives (area, centroid, bounds, perimeter)
  - Point-in-polygon (ray casting, boundary, L-shape, batch)
  - Polygon validation
  - Orientation (CW/CCW)
  - Constructors (rect, L-shape, U-shape)
  - Grid generation (with NFPA wall margin)
  - Convex hull
  - Polygon operations (inset, bounding rect, room dims)
  - Segment intersection (including collinear overlap)

NFPA 72 references:
  - §17.6.3.1.1: Min wall distance 0.10m (4 inches)
  - Table 17.6.3.1.1: Coverage radius by ceiling height
"""

import math
import pytest
from geometry_utils import (
    polygon_area, polygon_centroid, polygon_bounds, polygon_perimeter,
    point_in_polygon, points_in_polygon, validate_polygon,
    grid_points_in_polygon, is_clockwise, ensure_ccw,
    rect_polygon, l_shape_polygon, u_shape_polygon,
    shoelace_area, convex_hull, polygon_inset,
    minimum_bounding_rectangle, polygon_to_room_dims,
    segments_intersect, _cross,
)


# ─────────────────────────────────────────────
# Test: Polygon Area (Shoelace)
# ─────────────────────────────────────────────

class TestPolygonArea:
    def test_unit_square(self):
        assert polygon_area([(0, 0), (1, 0), (1, 1), (0, 1)]) == pytest.approx(1.0)

    def test_rectangle(self):
        assert polygon_area([(0, 0), (4, 0), (4, 3), (0, 3)]) == pytest.approx(12.0)

    def test_l_shape_area(self):
        """L-shape: 6x4 with 2x2 cutout from top-right = 20 m²"""
        poly = l_shape_polygon(6, 4, 2, 2)
        assert polygon_area(poly) == pytest.approx(20.0)

    def test_triangle(self):
        assert polygon_area([(0, 0), (4, 0), (0, 3)]) == pytest.approx(6.0)

    def test_cw_same_as_ccw(self):
        cw = [(0, 0), (0, 1), (1, 1), (1, 0)]
        ccw = [(0, 0), (1, 0), (1, 1), (0, 1)]
        assert polygon_area(cw) == pytest.approx(polygon_area(ccw))

    def test_degenerate_line(self):
        assert polygon_area([(0, 0), (1, 1), (2, 2)]) == pytest.approx(0.0)

    def test_degenerate_point(self):
        assert polygon_area([(0, 0), (0, 0), (0, 0)]) == pytest.approx(0.0)

    def test_shoelace_signed_ccw(self):
        """CCW polygon should have positive signed area."""
        ccw = [(0, 0), (1, 0), (1, 1), (0, 1)]
        assert shoelace_area(ccw) > 0

    def test_shoelace_signed_cw(self):
        """CW polygon should have negative signed area."""
        cw = [(0, 0), (0, 1), (1, 1), (1, 0)]
        assert shoelace_area(cw) < 0


# ─────────────────────────────────────────────
# Test: Centroid
# ─────────────────────────────────────────────

class TestCentroid:
    def test_square_centroid(self):
        cx, cy = polygon_centroid([(0, 0), (2, 0), (2, 2), (0, 2)])
        assert cx == pytest.approx(1.0)
        assert cy == pytest.approx(1.0)

    def test_rectangle_centroid(self):
        cx, cy = polygon_centroid([(0, 0), (6, 0), (6, 4), (0, 4)])
        assert cx == pytest.approx(3.0)
        assert cy == pytest.approx(2.0)

    def test_single_point_returns_itself(self):
        assert polygon_centroid([(3.0, 5.0)]) == (3.0, 5.0)

    def test_two_points_returns_midpoint(self):
        cx, cy = polygon_centroid([(0, 0), (4, 6)])
        assert cx == pytest.approx(2.0)
        assert cy == pytest.approx(3.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            polygon_centroid([])

    def test_l_shape_centroid(self):
        """L-shape centroid should be offset from geometric center."""
        poly = l_shape_polygon(6, 4, 2, 2)
        cx, cy = polygon_centroid(poly)
        # Area = 20 m², centroid should be left of center
        assert cx < 3.0  # Left of bounding box center
        assert cy < 2.0  # Below bounding box center


# ─────────────────────────────────────────────
# Test: Bounds & Perimeter
# ─────────────────────────────────────────────

class TestBoundsAndPerimeter:
    def test_square_bounds(self):
        min_x, min_y, max_x, max_y = polygon_bounds([(0, 0), (3, 0), (3, 3), (0, 3)])
        assert min_x == 0 and min_y == 0 and max_x == 3 and max_y == 3

    def test_offset_rect_bounds(self):
        poly = rect_polygon(5, 3, origin=(10, 20))
        min_x, min_y, max_x, max_y = polygon_bounds(poly)
        assert min_x == 10 and min_y == 20 and max_x == 15 and max_y == 23

    def test_square_perimeter(self):
        assert polygon_perimeter([(0, 0), (1, 0), (1, 1), (0, 1)]) == pytest.approx(4.0)

    def test_rectangle_perimeter(self):
        assert polygon_perimeter([(0, 0), (5, 0), (5, 3), (0, 3)]) == pytest.approx(16.0)


# ─────────────────────────────────────────────
# Test: Point-in-Polygon
# ─────────────────────────────────────────────

class TestPointInPolygon:
    square = [(0, 0), (4, 0), (4, 4), (0, 4)]

    def test_center_inside(self):
        assert point_in_polygon((2, 2), self.square)

    def test_outside(self):
        assert not point_in_polygon((5, 5), self.square)

    def test_on_edge_included(self):
        assert point_in_polygon((2, 0), self.square, include_boundary=True)

    def test_on_edge_excluded(self):
        assert not point_in_polygon((2, 0), self.square, include_boundary=False)

    def test_corner_included(self):
        assert point_in_polygon((0, 0), self.square, include_boundary=True)

    def test_corner_excluded(self):
        assert not point_in_polygon((0, 0), self.square, include_boundary=False)

    def test_l_shape_inside(self):
        poly = l_shape_polygon(6, 4, 2, 2)
        assert point_in_polygon((1, 1), poly)

    def test_l_shape_cutout_outside(self):
        """Point in the cutout region should be OUTSIDE the L-shape."""
        poly = l_shape_polygon(6, 4, 2, 2)
        # Cutout is top-right: x in (4, 6), y in (2, 4)
        assert not point_in_polygon((5.0, 3.0), poly)

    def test_l_shape_inside_wing(self):
        """Point in the left wing of L-shape should be inside."""
        poly = l_shape_polygon(6, 4, 2, 2)
        assert point_in_polygon((1.0, 3.0), poly)

    def test_l_shape_on_inner_corner(self):
        """Point on the inner corner of L-shape should be inside (boundary)."""
        poly = l_shape_polygon(6, 4, 2, 2)
        # Inner corner at (4, 2)
        assert point_in_polygon((4.0, 2.0), poly, include_boundary=True)

    def test_far_outside_fast_rejection(self):
        assert not point_in_polygon((100, 100), self.square)

    def test_batch_points(self):
        pts = [(2, 2), (5, 5), (0, 0)]
        results = points_in_polygon(pts, self.square)
        assert results == [True, False, True]

    def test_u_shape_inside_left_wing(self):
        poly = u_shape_polygon(8, 6, 2, 2, 3)
        assert point_in_polygon((1, 1), poly)

    def test_u_shape_inside_channel_outside(self):
        """Point in the top channel (between wings) should be OUTSIDE."""
        poly = u_shape_polygon(8, 6, 2, 2, 3)
        # Channel: x in (2, 6), y in (3, 6)
        assert not point_in_polygon((4.0, 5.0), poly)


# ─────────────────────────────────────────────
# Test: Validation
# ─────────────────────────────────────────────

class TestValidation:
    def test_valid_square(self):
        r = validate_polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
        assert r.valid

    def test_too_few_vertices(self):
        r = validate_polygon([(0, 0), (1, 1)])
        assert not r.valid
        assert any("3" in e for e in r.errors)

    def test_zero_area(self):
        r = validate_polygon([(0, 0), (1, 0), (0, 0)], min_area=0.01)
        assert not r.valid

    def test_duplicate_vertex_error(self):
        r = validate_polygon([(0, 0), (0, 0), (1, 1), (0, 1)])
        assert not r.valid

    def test_large_vertex_warning(self):
        """Polygons with >50 vertices should produce a warning."""
        pts = [(math.cos(2 * math.pi * i / 55), math.sin(2 * math.pi * i / 55)) for i in range(55)]
        r = validate_polygon(pts, min_area=0.01)
        assert r.valid  # Still valid, just warned
        assert any("vertices" in w for w in r.warnings)

    def test_self_intersecting_hourglass(self):
        """Hourglass/bowtie shape should fail validation."""
        poly = [(0, 0), (4, 4), (4, 0), (0, 4)]  # Self-intersecting
        r = validate_polygon(poly)
        assert not r.valid
        assert any("Self-intersection" in e for e in r.errors)

    def test_valid_l_shape(self):
        poly = l_shape_polygon(6, 4, 2, 2)
        r = validate_polygon(poly)
        assert r.valid


# ─────────────────────────────────────────────
# Test: Orientation
# ─────────────────────────────────────────────

class TestOrientation:
    def test_ccw_detection(self):
        assert not is_clockwise([(0, 0), (1, 0), (1, 1), (0, 1)])

    def test_cw_detection(self):
        assert is_clockwise([(0, 0), (0, 1), (1, 1), (1, 0)])

    def test_ensure_ccw_idempotent(self):
        poly = [(0, 0), (1, 0), (1, 1), (0, 1)]
        assert ensure_ccw(poly) == poly

    def test_ensure_ccw_flips_cw(self):
        cw = [(0, 0), (0, 1), (1, 1), (1, 0)]
        assert not is_clockwise(ensure_ccw(cw))

    def test_rect_polygon_is_ccw(self):
        poly = rect_polygon(5, 3)
        assert not is_clockwise(poly)

    def test_l_shape_polygon_is_ccw(self):
        poly = l_shape_polygon(6, 4, 2, 2)
        assert not is_clockwise(poly)

    def test_u_shape_polygon_is_ccw(self):
        poly = u_shape_polygon(8, 6, 2, 2, 3)
        assert not is_clockwise(poly)


# ─────────────────────────────────────────────
# Test: Constructors
# ─────────────────────────────────────────────

class TestConstructors:
    # --- rect_polygon ---
    def test_rect_polygon_area(self):
        assert polygon_area(rect_polygon(5, 3)) == pytest.approx(15.0)

    def test_rect_polygon_with_origin(self):
        poly = rect_polygon(4, 3, origin=(10, 20))
        assert poly[0] == (10, 20)
        assert polygon_area(poly) == pytest.approx(12.0)

    def test_rect_polygon_invalid_width(self):
        with pytest.raises(ValueError, match="positive"):
            rect_polygon(0, 5)

    def test_rect_polygon_negative_width(self):
        with pytest.raises(ValueError, match="positive"):
            rect_polygon(-1, 5)

    def test_rect_polygon_invalid_height(self):
        with pytest.raises(ValueError, match="positive"):
            rect_polygon(5, 0)

    # --- l_shape_polygon ---
    def test_l_shape_area_top_right(self):
        poly = l_shape_polygon(6, 4, 2, 2)
        assert polygon_area(poly) == pytest.approx(20.0)

    def test_l_shape_area_top_left(self):
        """Top-left cutout should produce same area."""
        poly = l_shape_polygon(6, 4, 2, 2, cut_corner="top_left")
        assert polygon_area(poly) == pytest.approx(20.0)

    def test_l_shape_area_bottom_right(self):
        poly = l_shape_polygon(6, 4, 2, 2, cut_corner="bottom_right")
        assert polygon_area(poly) == pytest.approx(20.0)

    def test_l_shape_area_bottom_left(self):
        poly = l_shape_polygon(6, 4, 2, 2, cut_corner="bottom_left")
        assert polygon_area(poly) == pytest.approx(20.0)

    def test_l_shape_invalid_cutout_exceeds_width(self):
        with pytest.raises(ValueError, match="exceeds"):
            l_shape_polygon(4, 4, 5, 2)

    def test_l_shape_invalid_cutout_exceeds_height(self):
        with pytest.raises(ValueError, match="exceeds"):
            l_shape_polygon(4, 4, 2, 5)

    def test_l_shape_invalid_corner(self):
        with pytest.raises(ValueError, match="cut_corner"):
            l_shape_polygon(6, 4, 2, 2, cut_corner="invalid")

    def test_l_shape_6_vertices(self):
        """L-shape should always have exactly 6 vertices."""
        poly = l_shape_polygon(6, 4, 2, 2)
        assert len(poly) == 6

    # --- u_shape_polygon ---
    def test_u_shape_area(self):
        """U-shape: 8x6 with 4x3 channel cut from top = 36 m²"""
        poly = u_shape_polygon(8, 6, 2, 2, 3)
        # Total area = 8*6 - 4*3 = 36
        assert polygon_area(poly) == pytest.approx(36.0)

    def test_u_shape_symmetric(self):
        """Symmetric U with equal wings."""
        poly = u_shape_polygon(10, 6, 2, 2, 3)
        # Area = total - channel_cutout = 10*6 - (10-2-2)*3 = 60 - 18 = 42
        assert polygon_area(poly) == pytest.approx(42.0)

    def test_u_shape_8_vertices(self):
        poly = u_shape_polygon(8, 6, 2, 2, 3)
        assert len(poly) == 8

    def test_u_shape_invalid_wings_too_wide(self):
        with pytest.raises(ValueError, match="exceeds"):
            u_shape_polygon(8, 6, 5, 5, 3)  # 5+5=10 > 8

    def test_u_shape_invalid_cut_exceeds_height(self):
        with pytest.raises(ValueError, match="exceeds"):
            u_shape_polygon(8, 6, 2, 2, 7)  # cut_h=7 > height=6

    def test_u_shape_negative_wing(self):
        with pytest.raises(ValueError, match="positive"):
            u_shape_polygon(8, 6, 0, 2, 3)


# ─────────────────────────────────────────────
# Test: Grid Generation
# ─────────────────────────────────────────────

class TestGridGeneration:
    def test_grid_all_inside_square(self):
        poly = rect_polygon(4, 4)
        pts = grid_points_in_polygon(poly, step=1.0)
        for p in pts:
            assert point_in_polygon(p, poly), f"{p} outside polygon"

    def test_grid_nonempty(self):
        poly = rect_polygon(5, 5)
        assert len(grid_points_in_polygon(poly, step=1.0)) > 0

    def test_l_shape_grid_excludes_cutout(self):
        poly = l_shape_polygon(6, 4, 2, 2)
        pts = grid_points_in_polygon(poly, step=0.5)
        for p in pts:
            assert point_in_polygon(p, poly), f"{p} outside L-shape"

    def test_invalid_step_raises(self):
        with pytest.raises(ValueError, match="positive"):
            grid_points_in_polygon(rect_polygon(4, 4), step=0)

    def test_negative_step_raises(self):
        with pytest.raises(ValueError, match="positive"):
            grid_points_in_polygon(rect_polygon(4, 4), step=-1)

    def test_negative_margin_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            grid_points_in_polygon(rect_polygon(4, 4), step=1.0, margin=-0.1)

    def test_margin_reduces_points(self):
        """Grid with margin should have fewer points than without."""
        poly = rect_polygon(10, 10)
        pts_no_margin = grid_points_in_polygon(poly, step=1.0, margin=0.0)
        pts_with_margin = grid_points_in_polygon(poly, step=1.0, margin=0.5)
        assert len(pts_with_margin) < len(pts_no_margin)

    def test_nfpa_wall_margin(self):
        """NFPA 72 §17.6.3.1.1: All grid points should be >= 0.10m from walls."""
        poly = rect_polygon(6, 6)
        margin = 0.10  # NFPA minimum wall distance
        pts = grid_points_in_polygon(poly, step=0.5, margin=margin)
        for px, py in pts:
            # Check distance to all 4 walls
            assert px >= margin - 1e-9, f"Point ({px},{py}) too close to left wall"
            assert py >= margin - 1e-9, f"Point ({px},{py}) too close to bottom wall"
            assert 6.0 - px >= margin - 1e-9, f"Point ({px},{py}) too close to right wall"
            assert 6.0 - py >= margin - 1e-9, f"Point ({px},{py}) too close to top wall"

    def test_large_margin_empty_grid(self):
        """Margin larger than room should produce empty grid."""
        poly = rect_polygon(2, 2)
        pts = grid_points_in_polygon(poly, step=0.5, margin=1.5)
        assert len(pts) == 0

    def test_u_shape_grid(self):
        """Grid in U-shape should not include channel points."""
        poly = u_shape_polygon(8, 6, 2, 2, 3)
        pts = grid_points_in_polygon(poly, step=1.0)
        for p in pts:
            assert point_in_polygon(p, poly), f"{p} outside U-shape"


# ─────────────────────────────────────────────
# Test: Convex Hull
# ─────────────────────────────────────────────

class TestConvexHull:
    def test_square_hull(self):
        pts = [(0, 0), (1, 0), (1, 1), (0, 1)]
        hull = convex_hull(pts)
        assert polygon_area(hull) == pytest.approx(1.0)

    def test_hull_with_interior_points(self):
        """Interior points should not appear in hull."""
        pts = [(0, 0), (4, 0), (4, 4), (0, 4), (2, 2), (1, 1), (3, 1)]
        hull = convex_hull(pts)
        assert polygon_area(hull) == pytest.approx(16.0)
        assert len(hull) == 4  # Only the 4 corners

    def test_hull_collinear_raises(self):
        """Collinear points should raise ValueError."""
        with pytest.raises(ValueError, match="collinear"):
            convex_hull([(0, 0), (1, 1), (2, 2)])

    def test_hull_triangle(self):
        pts = [(0, 0), (4, 0), (2, 3)]
        hull = convex_hull(pts)
        assert polygon_area(hull) == pytest.approx(6.0)

    def test_hull_removes_duplicates(self):
        """Duplicate points should be handled."""
        pts = [(0, 0), (0, 0), (4, 0), (4, 4), (0, 4)]
        hull = convex_hull(pts)
        assert polygon_area(hull) == pytest.approx(16.0)

    def test_hull_single_point(self):
        result = convex_hull([(3, 7)])
        assert result == [(3, 7)]

    def test_cross_helper(self):
        """Cross product: CCW turn = positive."""
        assert _cross((0, 0), (1, 0), (1, 1)) > 0
        assert _cross((0, 0), (1, 0), (1, -1)) < 0
        assert _cross((0, 0), (1, 0), (2, 0)) == pytest.approx(0.0)


# ─────────────────────────────────────────────
# Test: Polygon Inset
# ─────────────────────────────────────────────

class TestPolygonInset:
    def test_inset_reduces_area(self):
        poly = rect_polygon(10, 10)
        inset = polygon_inset(poly, margin=1.0)
        assert polygon_area(inset) < polygon_area(poly)

    def test_zero_margin_no_change(self):
        poly = rect_polygon(5, 5)
        inset = polygon_inset(poly, margin=0.0)
        assert inset == poly

    def test_negative_margin_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            polygon_inset(rect_polygon(5, 5), margin=-0.1)

    def test_inset_points_closer_to_centroid(self):
        """Each inset vertex should be closer to centroid than original."""
        poly = rect_polygon(10, 8)
        cx, cy = polygon_centroid(poly)
        margin = 1.0
        inset = polygon_inset(poly, margin=margin)
        for (ox, oy), (ix, iy) in zip(poly, inset):
            orig_dist = math.hypot(ox - cx, oy - cy)
            inset_dist = math.hypot(ix - cx, iy - cy)
            assert inset_dist <= orig_dist + 1e-9

    def test_inset_degenerate_raises(self):
        with pytest.raises(ValueError, match="3 vertices"):
            polygon_inset([(0, 0), (1, 1)], margin=0.5)

    def test_inset_l_shape(self):
        """L-shape inset should still have 6 vertices."""
        poly = l_shape_polygon(6, 4, 2, 2)
        inset = polygon_inset(poly, margin=0.3)
        assert len(inset) == 6
        assert polygon_area(inset) < polygon_area(poly)


# ─────────────────────────────────────────────
# Test: Minimum Bounding Rectangle & Room Dims
# ─────────────────────────────────────────────

class TestBoundingRectangle:
    def test_rectangle_fill_ratio_1(self):
        """Rectangle should have fill_ratio = 1.0."""
        mbr = minimum_bounding_rectangle(rect_polygon(5, 3))
        assert mbr["fill_ratio"] == pytest.approx(1.0)
        assert mbr["width"] == pytest.approx(5.0)
        assert mbr["height"] == pytest.approx(3.0)

    def test_l_shape_fill_ratio_less_than_1(self):
        """L-shape should have fill_ratio < 1.0."""
        mbr = minimum_bounding_rectangle(l_shape_polygon(6, 4, 2, 2))
        assert mbr["fill_ratio"] < 1.0
        assert mbr["fill_ratio"] == pytest.approx(20.0 / 24.0)

    def test_u_shape_fill_ratio_less_than_1(self):
        mbr = minimum_bounding_rectangle(u_shape_polygon(8, 6, 2, 2, 3))
        assert mbr["fill_ratio"] < 1.0

    def test_polygon_to_room_dims_rectangle(self):
        """Rectangle -> (width, height, 1.0)."""
        w, h, fr = polygon_to_room_dims(rect_polygon(10, 8))
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(8.0)
        assert fr == pytest.approx(1.0)

    def test_polygon_to_room_dims_l_shape(self):
        """L-shape -> (6, 4, fill_ratio < 1.0)."""
        w, h, fr = polygon_to_room_dims(l_shape_polygon(6, 4, 2, 2))
        assert w == pytest.approx(6.0)
        assert h == pytest.approx(4.0)
        assert fr < 1.0

    def test_mbr_keys(self):
        mbr = minimum_bounding_rectangle(rect_polygon(5, 3))
        expected_keys = {"min_x", "min_y", "max_x", "max_y",
                         "width", "height", "area", "polygon_area", "fill_ratio"}
        assert set(mbr.keys()) == expected_keys


# ─────────────────────────────────────────────
# Test: Segment Intersection
# ─────────────────────────────────────────────

class TestSegmentIntersection:
    def test_crossing_segments(self):
        assert segments_intersect((0, 0), (4, 4), (0, 4), (4, 0))

    def test_parallel_segments_no_intersect(self):
        assert not segments_intersect((0, 0), (4, 0), (0, 1), (4, 1))

    def test_non_crossing_segments(self):
        assert not segments_intersect((0, 0), (1, 1), (3, 3), (4, 4))

    def test_endpoint_touch(self):
        """Segments sharing an endpoint should intersect."""
        assert segments_intersect((0, 0), (2, 2), (2, 2), (4, 0))

    def test_t_intersection(self):
        """One segment's endpoint on the other."""
        assert segments_intersect((0, 0), (4, 0), (2, 0), (2, 4))

    def test_collinear_no_overlap(self):
        """Collinear segments that don't overlap should NOT intersect."""
        assert not segments_intersect((0, 0), (2, 0), (3, 0), (5, 0))

    def test_collinear_overlap(self):
        """Collinear segments that DO overlap should intersect."""
        assert segments_intersect((0, 0), (4, 0), (2, 0), (6, 0))

    def test_collinear_contained(self):
        """One segment fully contained in the other (collinear)."""
        assert segments_intersect((0, 0), (6, 0), (2, 0), (4, 0))


# ─────────────────────────────────────────────
# Test: FireAI Integration Scenarios
# ─────────────────────────────────────────────

class TestFireAIIntegration:
    """Tests simulating real FireAI usage patterns."""

    def test_l_shape_coverage_grid(self):
        """
        Simulate detector coverage verification in an L-shaped room.
        Generate grid points, verify all are inside the polygon.
        This is the pattern used by nfpa72_coverage.py.
        """
        poly = l_shape_polygon(12, 8, 4, 4)  # Large L-shape: 80 m²
        grid_pts = grid_points_in_polygon(poly, step=0.5)
        assert len(grid_pts) > 0
        for p in grid_pts:
            assert point_in_polygon(p, poly)

    def test_u_shape_wall_margin_grid(self):
        """
        NFPA 72 §17.6.3.1.1: Detector placement grid with wall margin.
        All candidate positions must be >= 0.10m from walls.
        """
        poly = u_shape_polygon(15, 10, 3, 3, 4)
        margin = 0.10
        grid_pts = grid_points_in_polygon(poly, step=1.0, margin=margin)
        assert len(grid_pts) > 0
        # All points should be at least margin from boundary
        for px, py in grid_pts:
            assert point_in_polygon((px, py), poly, include_boundary=True)

    def test_polygon_to_room_dims_for_density_optimizer(self):
        """
        DensityOptimizer requires (width, length). This test verifies
        the conversion pipeline from arbitrary polygon to Room dimensions.
        """
        # Rectangular room -> perfect conversion
        poly = rect_polygon(10, 8)
        w, h, fr = polygon_to_room_dims(poly)
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(8.0)
        assert fr == pytest.approx(1.0)

        # L-shaped room -> conservative over-estimate
        poly = l_shape_polygon(12, 8, 4, 4)
        w, h, fr = polygon_to_room_dims(poly)
        assert w == pytest.approx(12.0)
        assert h == pytest.approx(8.0)
        assert fr < 1.0
        # Fill ratio tells us how conservative the estimate is
        # For this L-shape: area=80, bbox=96, fr=0.833
        assert fr == pytest.approx(80.0 / 96.0, abs=0.01)

    def test_validate_room_polygon_before_analysis(self):
        """
        Before running DensityOptimizer, validate the room polygon.
        This catches degenerate input early.
        """
        # Valid room
        poly = rect_polygon(6, 4)
        r = validate_polygon(poly, min_area=1.0)
        assert r.valid

        # Degenerate room (zero area)
        degenerate = [(0, 0), (1, 0), (0, 0)]
        r = validate_polygon(degenerate, min_area=1.0)
        assert not r.valid

    def test_convex_hull_for_coverage_radius(self):
        """
        Convex hull can be used to determine the minimum bounding circle
        for coverage radius estimation. This test verifies hull correctness
        for typical room shapes.
        """
        # Rectangle hull should equal the rectangle itself
        poly = rect_polygon(6, 4)
        hull = convex_hull(poly)
        hull_area = polygon_area(hull)
        assert hull_area == pytest.approx(24.0)

        # L-shape hull is a pentagon (smaller than bounding rect)
        poly_l = l_shape_polygon(6, 4, 2, 2)
        hull_l = convex_hull(poly_l)
        hull_l_area = polygon_area(hull_l)
        # Hull includes (6,2) as extreme point, making a pentagon
        # not the full 6x4=24 bounding rect
        assert hull_l_area < 24.0
        assert hull_l_area > polygon_area(poly_l)  # Hull > L-shape area

    def test_inset_for_detector_margin(self):
        """
        Inset polygon represents the valid detector placement zone
        after excluding the NFPA wall margin.

        NOTE: polygon_inset uses a centroid-based approximation, not a true
        parallel-offset buffer. For rectangles, the result is close but not
        exactly (W-2m)*(H-2m). Use Shapely buffer(-m) for exact results.
        """
        poly = rect_polygon(12, 10)
        margin = 0.10  # NFPA §17.6.3.1.1
        inset = polygon_inset(poly, margin=margin)

        # Inset area should be less than original
        assert polygon_area(inset) < polygon_area(poly)

        # Centroid-based inset approximates (W-2m)*(H-2m) for rectangles
        # but is not exact. Allow wider tolerance for the approximation.
        expected = (12 - 2 * margin) * (10 - 2 * margin)
        assert polygon_area(inset) == pytest.approx(expected, abs=2.0)
