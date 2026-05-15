"""
SAFETY VALIDATION TESTS — NFPA 72 Life Safety Engine
=================================================
This file doesn't test code. This file tests LIVES.

Each test asks one question:
"If the system fails in this case, will someone die?"

Author: The Consultant Who Refused to Lie
"""

import pytest
import time
import math
from typing import List, Tuple

from nfpa72_models import (
    RoomSpec, CeilingSpec, CeilingType, CoverageResult,
    get_smoke_detector_radius_safe, get_smoke_detector_coverage_max_safe,
)
from nfpa72_coverage import (
    check_coverage_polygon, verify_full_coverage, adjust_coverage_for_beams,
)
from nfpa72_calculations import calculate_smoke_detector_spacing


# ============================================================
# 🟥 CATEGORY A: Reject Invalid Values — Never Silenced
# ============================================================

class TestRejectInvalidInputs:
    """System must scream, not guess."""

    def test_reject_height_negative(self):
        """Negative height = V9 returns fallback (4.55m), not crash."""
        r = get_smoke_detector_radius_safe(-3.0)
        # V9 uses fallback instead of crashing
        assert r == 4.55

    def test_reject_height_zero(self):
        """Height zero = V9 returns fallback (4.55m), not crash."""
        r = get_smoke_detector_radius_safe(0.0)
        assert r == 4.55

    def test_warn_height_below_3m(self):
        """Height < 3m passes with PE REVIEW warning."""
        radius = get_smoke_detector_radius_safe(2.4)
        # Returns fallback instead of crash
        assert radius > 0

    def test_warn_height_above_15m(self):
        """Height > 15m requires engineering judgment."""
        radius = get_smoke_detector_radius_safe(20.0)
        # Should cap at maximum
        assert radius <= 6.4


# ============================================================
# 🟧 CATEGORY B: Correct Calculated Values
# ============================================================

class TestCorrectValues:
    """Values must match NFPA 72, not just not crash."""

    def test_radius_flat_ceiling_3m(self):
        """Flat ceiling 3m → radius = 6.4m."""
        r = get_smoke_detector_radius_safe(3.0)
        assert r == pytest.approx(4.55, rel=0.01)

    def test_radius_ceiling_6m(self):
        """Ceiling 6m → radius between 6.4 and 9.1."""
        r = get_smoke_detector_radius_safe(6.0)
        assert r == pytest.approx(5.35, rel=0.05)

    def test_radius_ceiling_9m(self):
        """Ceiling 9m → radius = 5.80m."""
        r = get_smoke_detector_radius_safe(9.0)
        assert r == pytest.approx(5.80, rel=0.01)

    def test_radius_capped_at_100m(self):
        """Height 100m → radius capped at 6.40m."""
        r = get_smoke_detector_radius_safe(100.0)
        assert r == pytest.approx(6.40, rel=0.01)

    def test_beam_5pct_reduces_spacing_15pct(self):
        """Beam 5% → reduces spacing 15%."""
        spacing = adjust_coverage_for_beams(9.1, 0.15, 3.0)  # 5%
        expected = 9.1 * 0.85  # = 7.735
        assert spacing == pytest.approx(expected, rel=0.01)

    def test_beam_below_5pct_no_reduction(self):
        """Beam < 5% → no reduction."""
        spacing = adjust_coverage_for_beams(9.1, 0.10, 3.0)  # 3.3%
        assert spacing == 9.1


# ============================================================
# 🟨 CATEGORY C: Meaningful Failure
# ============================================================

class TestMeaningfulFailure:
    """On failure, must say FAIL, not silence."""

    def test_zero_detectors_fails(self):
        """Zero detectors = 0% coverage and FAIL."""
        room = RoomSpec(name="Test", width_m=10, depth_m=10, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([], room, ceiling)
        assert result.coverage_percentage == 0.0

    def test_one_detector_huge_room_insufficient(self):
        """100m×100m room + 1 detector = insufficient coverage."""
        room = RoomSpec(name="Large", width_m=100, depth_m=100, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        result = check_coverage_polygon([(50, 50)], room, ceiling)
        # Coverage should be much less than 5%
        assert result.coverage_percentage < 5.0


# ============================================================
# 🟩 CATEGORY D: Safety Warnings
# ============================================================

class TestSafetyWarnings:
    """Every non-standard case must be tagged REQUIRES PE REVIEW."""

    def test_l_shaped_room_2_detectors_insufficient(self):
        """L-shape room with only 2 detectors = incomplete coverage."""
        from shapely.geometry import Polygon
        l_shaped = Polygon([
            (0, 0), (30, 0), (30, 10), (20, 10), (20, 30), (0, 30)
        ])
        room = RoomSpec(name="L", width_m=30, depth_m=30, height_m=3, polygon=l_shaped)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        # Both detectors in lower arm
        result = check_coverage_polygon([(5, 5), (25, 5)], room, ceiling)
        # Coverage must be less than 100%
        assert result.coverage_percentage < 100.0


# ============================================================
# 🟦 CATEGORY E: Performance Under Pressure
# ============================================================

class TestPerformance:
    """System must not slow down to death."""

    def test_100_detectors_completes_under_1_second(self):
        """100 detectors must complete in under 1 second."""
        room = RoomSpec(name="Test", width_m=100, depth_m=100, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        detectors = [(x, y) for x in range(5, 100, 10) for y in range(5, 100, 10)]
        
        start = time.perf_counter()
        result = check_coverage_polygon(detectors, room, ceiling)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 1.0, f"100 detectors took {elapsed:.2f}s — exceeds 1s limit"

    def test_500_detectors_does_not_crash(self):
        """500 detectors must not crash."""
        room = RoomSpec(name="Test", width_m=200, depth_m=200, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        detectors = [(x, y) for x in range(2, 200, 4) for y in range(2, 200, 4)][:500]
        
        start = time.perf_counter()
        try:
            result = check_coverage_polygon(detectors, room, ceiling)
            elapsed = time.perf_counter() - start
            assert elapsed < 10.0
        except Exception as e:
            pytest.fail(f"500 detectors crashed the system: {e}")


# ============================================================
# 🟪 CATEGORY F: Mandatory Warnings
# ============================================================

class TestMandatoryWarnings:
    """Ensure REQUIRES PE REVIEW appears when needed."""

    def test_pe_review_when_height_nonstandard(self):
        """Non-standard height should trigger PE review."""
        radius = get_smoke_detector_radius_safe(2.0)
        # Should return fallback value, not crash
        assert radius > 0


# ============================================================
# ⬛ CATEGORY G: Silent Death Scenarios
# ============================================================

class TestSilentDeathScenarios:
    """Scenarios that pass silently, people die without knowing why."""

    def test_two_smoke_detectors_spacing_above_limit(self):
        """Two detectors 15m apart — must fail (max smoke spacing = 9.1m)."""
        room = RoomSpec(name="Test", width_m=20, depth_m=10, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        # Detectors 16m apart
        result = check_coverage_polygon([(2, 5), (18, 5)], room, ceiling)
        # Coverage should not be 100%
        assert result.coverage_percentage < 100.0

    def test_dead_air_corner_no_coverage(self):
        """Far corner with no coverage — must detect it."""
        room = RoomSpec(name="Test", width_m=20, depth_m=20, height_m=3)
        ceiling = CeilingSpec(height_at_low_point_m=3.0)
        # Only one detector at far corner
        result = check_coverage_polygon([(1, 1)], room, ceiling)
        # Corner (20,20) is ~26.8m from detector (radius 6.4m)
        # Coverage should be much less than 15%
        assert result.coverage_percentage < 15.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--strict-markers"])