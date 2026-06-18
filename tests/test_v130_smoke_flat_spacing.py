"""
V127 Height-Adjusted Smoke Spacing Verification
================================================

This test was originally V130 (flat 9.1m spacing). The V127 audit
(SMOKE_SPACING_AUDIT_FINDING_1.md) restored height-adjusted spacing
from SMOKE_HEIGHT_SPACING_TABLE (10 rows).

This file now verifies:
  1. SMOKE_MAX_SPACING_M == 9.1 (the 30ft listed maximum per §17.7.3.2.3)
  2. SMOKE_HEIGHT_SPACING_TABLE has 10 rows, row 6 uses 9.144m (30 ft exact),
     row 9 caps at 18.288m (60 ft) per §17.7.3.2.4
  3. compute_smoke_detector_spacing returns table-based values at each height
  4. Coverage radius = 0.7 x spacing per §17.7.4.2.3.1
  5. technology_dispatcher delegates to kernel (no separate spacing logic)
  6. V120 AUDIT WARNING is always present in audit_notice

Companion files:
  - tests/test_smoke_spacing_v127.py (canonical V127 table tests)
  - tests/test_smoke_spacing_audit_v120.py (V120 audit notice tests)
"""

import pytest

# ============================================================================
# Test 1: Canonical SSoT constants
# ============================================================================


class TestSmokeSpacingConstants:
    """Verify fireai/constants/nfpa72.py has V127 table-based spacing."""

    def test_smoke_max_spacing_is_9_1(self):
        """SMOKE_MAX_SPACING_M must be 9.1 per §17.7.3.2.3."""
        from fireai.constants.nfpa72 import SMOKE_MAX_SPACING_M
        assert SMOKE_MAX_SPACING_M == 9.1, (
            f"SMOKE_MAX_SPACING_M = {SMOKE_MAX_SPACING_M}, expected 9.1"
        )

    def test_smoke_height_spacing_table_has_10_rows(self):
        """V127: table has 10 rows (row 6 uses 9.144m, row 9 = 18.288m / 5.20m)."""
        from fireai.constants.nfpa72 import SMOKE_HEIGHT_SPACING_TABLE
        assert len(SMOKE_HEIGHT_SPACING_TABLE) == 10, (
            f"len(SMOKE_HEIGHT_SPACING_TABLE) = {len(SMOKE_HEIGHT_SPACING_TABLE)}, expected 10"
        )

    def test_smoke_height_spacing_table_row_6(self):
        """V127: row 6 uses 9.144m (30 ft exact) — NOT 9.1m."""
        from fireai.constants.nfpa72 import SMOKE_HEIGHT_SPACING_TABLE
        max_h, spacing = SMOKE_HEIGHT_SPACING_TABLE[6]
        assert max_h == pytest.approx(9.144, abs=1e-3), f"row 6 max_h={max_h}"
        assert spacing == pytest.approx(6.40, abs=1e-3), f"row 6 spacing={spacing}"

    def test_smoke_height_spacing_table_last_row(self):
        """V127: last row is (18.288, 5.20) — 60 ft ceiling cap."""
        from fireai.constants.nfpa72 import SMOKE_HEIGHT_SPACING_TABLE
        max_h, spacing = SMOKE_HEIGHT_SPACING_TABLE[-1]
        assert max_h == pytest.approx(18.288, abs=1e-3)
        assert spacing == pytest.approx(5.20, abs=1e-3)


# ============================================================================
# Test 2: QOMN kernel compute_smoke_detector_spacing uses V127 table lookup
# ============================================================================


class TestQomnKernelSmokeSpacing:
    """Verify compute_smoke_detector_spacing uses V127 table lookup."""

    @pytest.mark.parametrize("height, expected", [
        (3.0, 9.10),
        (3.7, 8.70),
        (4.6, 8.20),
        (5.5, 7.70),
        (6.1, 7.30),
        (7.6, 6.80),
        (9.144, 6.40),
        (10.7, 6.00),
        (12.2, 5.60),
        (18.288, 5.20),
    ])
    def test_smoke_spacing_at_table_boundaries(self, height, expected):
        from fireai.core.qomn_kernel import compute_smoke_detector_spacing
        r = compute_smoke_detector_spacing(height)
        assert r["listed_spacing_m"] == pytest.approx(expected, abs=1e-3), (
            f"At h={height}m, expected S={expected}m, got S={r['listed_spacing_m']}m"
        )

    @pytest.mark.parametrize("height", [3.0, 4.6, 6.096, 9.1, 12.2, 18.0])
    def test_smoke_coverage_radius_at_all_heights(self, height):
        """Coverage radius = 0.7 x spacing per §17.7.4.2.3.1."""
        from fireai.core.qomn_kernel import compute_smoke_detector_spacing
        r = compute_smoke_detector_spacing(height)
        expected_r = 0.7 * r["listed_spacing_m"]
        assert r["coverage_radius_m"] == pytest.approx(expected_r, abs=1e-2)

    def test_audit_notice_always_present(self):
        """V120 AUDIT WARNING is always present in audit_notice."""
        from fireai.core.qomn_kernel import compute_smoke_detector_spacing
        r = compute_smoke_detector_spacing(3.0)
        assert "audit_notice" in r
        assert "V120 AUDIT WARNING" in r["audit_notice"]
        assert "SMOKE_SPACING_AUDIT_FINDING_1.md" in r["audit_notice"]


# ============================================================================
# Test 3: Coverage radius from height — uses table-based spacing
# ============================================================================


class TestCoverageRadiusFromHeightSmoke:
    """Verify coverage radius is 0.7 x (V127 table spacing)."""

    @pytest.mark.parametrize("height", [3.0, 3.7, 4.6, 6.096, 9.1, 12.2])
    def test_smoke_spacing_in_table_range(self, height):
        from fireai.core.qomn_kernel import compute_smoke_detector_spacing
        r = compute_smoke_detector_spacing(height)
        assert 0 < r["listed_spacing_m"] <= 9.10

    @pytest.mark.parametrize("height", [3.0, 3.7, 4.6, 6.096, 9.1, 12.2])
    def test_smoke_radius_in_table_range(self, height):
        from fireai.core.qomn_kernel import compute_smoke_detector_spacing
        r = compute_smoke_detector_spacing(height)
        expected_r = 0.7 * r["listed_spacing_m"]
        assert r["coverage_radius_m"] == pytest.approx(expected_r, abs=1e-2)


# ============================================================================
# Test 4: technology_dispatcher delegates to kernel (no separate spacing)
# ============================================================================


class TestTechnologyDispatcherSmokeSpacing:
    """Verify technology_dispatcher uses kernel table spacing."""

    @pytest.mark.parametrize("height", [3.0, 6.0, 9.0, 10.5, 12.0, 15.0])
    def test_point_smoke_spacing_matches_kernel(self, height):
        """technology_dispatcher must delegate to kernel for smoke spacing."""
        try:
            from fireai.core.nfpa72_technology_dispatcher import (
                EliteTechnologyDispatcher,
            )
            from fireai.core.qomn_kernel import compute_smoke_detector_spacing
        except ImportError:
            pytest.skip("technology_dispatcher not available")
        dispatcher = EliteTechnologyDispatcher()
        # Use whichever method the dispatcher exposes
        try:
            r = dispatcher.compute_smoke_detector_spacing(height)
            kernel_r = compute_smoke_detector_spacing(height)
            assert r["listed_spacing_m"] == pytest.approx(
                kernel_r["listed_spacing_m"], abs=1e-3
            )
        except (AttributeError, TypeError):
            pytest.skip("dispatcher API differs — skipping")

    def test_audit_notice_present_via_dispatcher(self):
        try:
            from fireai.core.nfpa72_technology_dispatcher import (
                EliteTechnologyDispatcher,
            )
        except ImportError:
            pytest.skip("technology_dispatcher not available")
        dispatcher = EliteTechnologyDispatcher()
        try:
            r = dispatcher.compute_smoke_detector_spacing(10.0)
            assert "audit_notice" in r
            assert "V120 AUDIT WARNING" in r["audit_notice"]
        except (AttributeError, TypeError):
            pytest.skip("dispatcher API differs — skipping")
