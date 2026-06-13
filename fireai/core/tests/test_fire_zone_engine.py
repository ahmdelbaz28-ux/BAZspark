"""
fireai/core/tests/test_fire_zone_engine.py — Tests for the Fire Zone Clustering Engine.

NFPA 72 §21.3.3: Zone requirements
NFPA 72 §21.2.2: Maximum 250 devices per panel
NFPA 72 Section 17.7.3.2: Irregular zone calculations
"""

import pytest

from fireai.core.fire_zone_engine import (
    FireZoneEngine,
    FireZone,
    ZoneConstraints,
    ZoneReport,
)


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> FireZoneEngine:
    """Create a FireZoneEngine with default constraints."""
    return FireZoneEngine()


@pytest.fixture
def engine_no_separation() -> FireZoneEngine:
    """Create a FireZoneEngine that does not separate occupancy types."""
    constraints = ZoneConstraints(separate_occupancy_types=False)
    return FireZoneEngine(constraints=constraints)


# ── Clustering Tests ─────────────────────────────────────────────────────


class TestClusterFloor:
    """NFPA 72 §21.3.3: Zone clustering tests."""

    def test_empty_rooms(self, engine: FireZoneEngine):
        """Empty room list should produce empty report."""
        report = engine.cluster_floor("GF", [])
        assert report.total_zones == 0
        assert report.total_area_sqm == 0.0

    def test_single_room(self, engine: FireZoneEngine):
        """Single room should create one zone."""
        rooms = [{"id": "R1", "area": 50.0, "detectors": 2, "occupancy": "office"}]
        report = engine.cluster_floor("GF", rooms)
        assert report.total_zones == 1
        assert report.total_area_sqm == 50.0
        assert report.total_detectors == 2

    def test_adjacent_rooms_grouped(self, engine: FireZoneEngine):
        """Adjacent rooms should be grouped into same zone."""
        rooms = [
            {"id": "R1", "area": 50.0, "detectors": 2, "occupancy": "office"},
            {"id": "R2", "area": 60.0, "detectors": 3, "occupancy": "office"},
        ]
        adjacency = {"R1": {"R2"}, "R2": {"R1"}}
        report = engine.cluster_floor("GF", rooms, adjacency=adjacency)
        assert report.total_zones == 1
        assert report.total_area_sqm == 110.0
        assert report.total_detectors == 5

    def test_different_occupancy_separated(self, engine: FireZoneEngine):
        """Rooms with different occupancy types should be in separate zones."""
        rooms = [
            {"id": "R1", "area": 50.0, "detectors": 2, "occupancy": "office"},
            {"id": "R2", "area": 80.0, "detectors": 3, "occupancy": "boiler"},
        ]
        report = engine.cluster_floor("GF", rooms)
        assert report.total_zones == 2

    def test_no_separation_flag(self, engine_no_separation: FireZoneEngine):
        """With separate_occupancy_types=False, rooms can share zones."""
        rooms = [
            {"id": "R1", "area": 50.0, "detectors": 2, "occupancy": "office"},
            {"id": "R2", "area": 80.0, "detectors": 3, "occupancy": "boiler"},
        ]
        report = engine_no_separation.cluster_floor("GF", rooms)
        assert report.total_zones == 1

    def test_area_constraint_split(self):
        """Zones exceeding max area should be split."""
        constraints = ZoneConstraints(max_area_sqm=100.0)
        engine = FireZoneEngine(constraints=constraints)
        rooms = [
            {"id": "R1", "area": 60.0, "detectors": 2, "occupancy": "office"},
            {"id": "R2", "area": 50.0, "detectors": 2, "occupancy": "office"},
        ]
        report = engine.cluster_floor("GF", rooms)
        assert report.total_zones == 2

    def test_detector_constraint_split(self):
        """Zones exceeding max detectors should be split."""
        constraints = ZoneConstraints(max_detectors_per_zone=3)
        engine = FireZoneEngine(constraints=constraints)
        rooms = [
            {"id": "R1", "area": 30.0, "detectors": 2, "occupancy": "office"},
            {"id": "R2", "area": 30.0, "detectors": 2, "occupancy": "office"},
        ]
        report = engine.cluster_floor("GF", rooms)
        assert report.total_zones == 2


# ── Build Zone Map Tests ─────────────────────────────────────────────────


class TestBuildZoneMap:
    """NFPA 72 §12.3.2: Zone map for fault isolator injection."""

    def test_zone_map_creation(self, engine: FireZoneEngine):
        """Zone map should map room_id to zone_id."""
        rooms = [
            {"id": "R1", "area": 50.0, "detectors": 2, "occupancy": "office"},
            {"id": "R2", "area": 60.0, "detectors": 3, "occupancy": "office"},
        ]
        report = engine.cluster_floor("GF", rooms)
        zone_map = engine.build_zone_map(report)
        assert "R1" in zone_map
        assert "R2" in zone_map

    def test_empty_report_zone_map(self, engine: FireZoneEngine):
        """Empty report should produce empty zone map."""
        report = engine.cluster_floor("GF", [])
        zone_map = engine.build_zone_map(report)
        assert zone_map == {}


# ── Irregular Zone Calculation Tests ─────────────────────────────────────


class TestIrregularZoneCalculations:
    """NFPA 72 Section 17.7.3.2: Irregular zone calculations.

    These tests verify the calculate_zone_for_irregular_shape method
    which computes area, perimeter, and detector count for non-rectangular
    fire zones using the shoelace formula.
    """

    def test_triangle_zone(self, engine: FireZoneEngine):
        """Test triangular fire zone — area = 0.5 * base * height."""
        vertices = [(0, 0), (10, 0), (0, 10)]
        result = engine.calculate_zone_for_irregular_shape(vertices)
        # Area = 0.5 * 10 * 10 = 50 sqm
        assert result["area"] == 50.0
        assert result["detector_count"] >= 1

    def test_square_zone(self, engine: FireZoneEngine):
        """Test square fire zone — area = side^2."""
        vertices = [(0, 0), (10, 0), (10, 10), (0, 10)]
        result = engine.calculate_zone_for_irregular_shape(vertices)
        assert result["area"] == 100.0
        assert result["perimeter"] == 40.0
        assert result["detector_count"] >= 2  # 100 / 83.61 + 1 = 2

    def test_complex_polygon(self, engine: FireZoneEngine):
        """Test complex polygonal fire zone (L-shape)."""
        vertices = [(0, 0), (20, 0), (20, 10), (10, 10), (10, 15), (0, 15)]
        result = engine.calculate_zone_for_irregular_shape(vertices)
        assert result["area"] > 0
        assert result["compliant"] is True

    def test_too_few_vertices(self, engine: FireZoneEngine):
        """Test error with insufficient vertices."""
        with pytest.raises(ValueError, match="at least 3 vertices"):
            engine.calculate_zone_for_irregular_shape([(0, 0), (10, 0)])

    def test_two_vertices_raises(self, engine: FireZoneEngine):
        """Two vertices should raise ValueError."""
        with pytest.raises(ValueError, match="at least 3 vertices"):
            engine.calculate_zone_for_irregular_shape([(0, 0), (5, 5)])

    def test_large_zone_non_compliant(self, engine: FireZoneEngine):
        """Test zone exceeding NFPA 72 area limits (area > 2500 sqm)."""
        # Create a very large polygon (100m x 100m = 10,000 sqm)
        vertices = [(0, 0), (100, 0), (100, 100), (0, 100)]
        result = engine.calculate_zone_for_irregular_shape(vertices)
        assert result["compliant"] is False
        assert result["area"] == 10000.0
        assert result["detector_count"] >= 120  # 10000 / 83.61 + 1 ≈ 120

    def test_small_zone_compliant(self, engine: FireZoneEngine):
        """Test small zone within NFPA 72 limits."""
        vertices = [(0, 0), (5, 0), (5, 5), (0, 5)]
        result = engine.calculate_zone_for_irregular_shape(vertices)
        assert result["compliant"] is True
        assert result["area"] == 25.0
        assert result["detector_count"] >= 1

    def test_perimeter_calculation(self, engine: FireZoneEngine):
        """Test perimeter is correctly calculated for a right triangle."""
        # Right triangle: 3-4-5
        vertices = [(0, 0), (3, 0), (0, 4)]
        result = engine.calculate_zone_for_irregular_shape(vertices)
        # Perimeter = 3 + 4 + 5 = 12
        assert abs(result["perimeter"] - 12.0) < 0.01
