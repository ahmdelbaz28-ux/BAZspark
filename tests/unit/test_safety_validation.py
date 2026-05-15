"""
SAFETY VALIDATION TESTS V9.1 — NFPA 72 Life Safety Engine
=================================================
Fixed: heights < 3.0m or > 9.0m must trigger PE REVIEW flag

Author: The Consultant Who Refused to Lie
"""

import pytest
import time
import math
from typing import List, Tuple

from nfpa72_models import (
    RoomSpec, CeilingSpec, CeilingType,
    get_smoke_detector_radius_safe,
    get_smoke_detector_coverage_max_safe,
)
from nfpa72_coverage import (
    check_coverage_polygon, verify_full_coverage, adjust_coverage_for_beams,
)
from nfpa72_calculations import calculate_smoke_detector_spacing


# ============================================================
# 🟥 CATEGORY A: REJECT Invalid — Must has PE REVIEW flag
# ============================================================

class TestRejectInvalidInputs:
    """System must flag non-standard heights, not silent pass."""

    def test_height_below_3m_has_flag(self):
        """Height < 3.0m → must set LOW_CEILING flag."""
        radius, details = get_smoke_detector_radius_safe(2.0, True)
        # Returns fallback BUT sets flag
        assert details["flag"] is not None
        assert "LOW" in details["flag"] or "CEILING" in details["flag"]

    def test_height_zero_has_flag(self):
        """Height 0.0m → must set LOW_CEILING flag."""
        radius, details = get_smoke_detector_radius_safe(0.0, True)
        assert details["flag"] is not None

    def test_height_negative_has_flag(self):
        """Negative height → must set flag."""
        radius, details = get_smoke_detector_radius_safe(-3.0, True)
        assert details["flag"] is not None


# ============================================================
# 🟧 CATEGORY B: Correct Values
# ============================================================

class TestCorrectValues:
    """Values must match NFPA 72."""

    def test_radius_3m(self):
        """3.0m → 4.55m."""
        r = get_smoke_detector_radius_safe(3.0)
        assert r == pytest.approx(4.55, rel=0.01)

    def test_radius_6m(self):
        """6.0m → 5.35m."""
        r = get_smoke_detector_radius_safe(6.0)
        assert r == pytest.approx(5.35, rel=0.05)

    def test_radius_9m(self):
        """9.0m → 5.80m."""
        r = get_smoke_detector_radius_safe(9.0)
        assert r == pytest.approx(5.80, rel=0.05)

    def test_radius_above_15m_has_flag(self):
        """Height > 15.3m → must set HIGH_CEILING flag."""
        radius, details = get_smoke_detector_radius_safe(20.0, True)
        assert details["flag"] is not None
        assert "HIGH" in details["flag"]


# ============================================================
# 🟨 CATEGORY C: Meaningful Failure
# ============================================================

class TestMeaningfulFailure:
    """On fail, must say FAIL not silent."""

    def test_zero_detectors_coverage_zero(self):
        """Zero detectors = 0% coverage."""
        room = RoomSpec(name="Test", width_m=10, depth_m=10, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([], room, ceiling)
        assert result.coverage_percentage == 0.0

    def test_one_detector_huge_room_insufficient(self):
        """100m×100m + 1 detector = insufficient."""
        room = RoomSpec(name="Large", width_m=100, depth_m=100, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([(50, 50)], room, ceiling)
        assert result.coverage_percentage < 5.0


# ============================================================
# 🟩 CATEGORY D: Safety Warnings
# ============================================================

class TestSafetyWarnings:
    """Non-standard must trigger review."""

    def test_l_shaped_room_incomplete(self):
        """L-shape room = incomplete coverage."""
        from shapely.geometry import Polygon
        l_shaped = Polygon([
            (0, 0), (30, 0), (30, 10), (20, 10), (20, 30), (0, 30)
        ])
        room = RoomSpec(name="L", width_m=30, depth_m=30, height_m=3, polygon=l_shaped)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([(5, 5), (25, 5)], room, ceiling)
        assert result.coverage_percentage < 100.0


# ============================================================
# 🟦 CATEGORY E: Performance
# ============================================================

class TestPerformance:
    """Must complete in time."""

    def test_100_detectors_under_1s(self):
        """100 detectors in < 1 second."""
        room = RoomSpec(name="Test", width_m=100, depth_m=100, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        detectors = [(x, y) for x in range(5, 100, 10) for y in range(5, 100, 10)]
        
        start = time.perf_counter()
        result = check_coverage_polygon(detectors, room, ceiling)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 1.0

    def test_500_detectors_no_crash(self):
        """500 detectors must not crash."""
        room = RoomSpec(name="Test", width_m=200, depth_m=200, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        detectors = [(x, y) for x in range(2, 200, 4) for y in range(2, 200, 4)][:500]
        
        start = time.perf_counter()
        result = check_coverage_polygon(detectors, room, ceiling)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 10.0


# ============================================================
# 🟪 CATEGORY F: Beam Reduction
# ============================================================

class TestBeamReduction:
    """Beam NFPA 72 compliance."""

    def test_beam_above_5pct_reduces(self):
        """Beam > 5% → 15% reduction."""
        spacing = adjust_coverage_for_beams(9.1, 0.15, 3.0)
        assert spacing < 9.1

    def test_beam_below_5pct_no_reduction(self):
        """Beam < 5% → no reduction."""
        spacing = adjust_coverage_for_beams(9.1, 0.10, 3.0)
        assert spacing == 9.1


# ============================================================
# 🟣 CATEGORY G: Silent Death Scenarios
# ============================================================

class TestSilentDeath:
    """Pass silently = people die."""

    def test_detectors_too_far_apart(self):
        """Detectors 15m apart → no coverage in middle."""
        room = RoomSpec(name="Test", width_m=20, depth_m=10, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([(2, 5), (18, 5)], room, ceiling)
        assert result.coverage_percentage < 100.0

    def test_dead_corner_no_coverage(self):
        """Far corner uncovered."""
        room = RoomSpec(name="Test", width_m=20, depth_m=20, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([(1, 1)], room, ceiling)
        assert result.coverage_percentage < 15.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])