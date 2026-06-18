"""
tests/test_smoke_spacing_v127.py - V127 Height-Adjusted Smoke Spacing Tests
==========================================================================
V127 FIX: Smoke detector spacing is height-adjusted per
SMOKE_HEIGHT_SPACING_TABLE (10 rows). Row 6 uses 9.144m (30 ft exact),
NOT 9.1m. Row 9 caps at 18.288m (60 ft) per NFPA 72 §17.7.3.2.4.

Per NFPA 72-2022 §17.7.3.2.3 (verbatim):
  "Spot-type smoke detectors shall be spaced not more than
   30 ft (9.1 m) apart on smooth ceilings."

The V127 table retains height-adjusted values as a CONSERVATIVE
fail-safe fallback pending licensed FPE sign-off. A V120 AUDIT WARNING
is always emitted and references SMOKE_SPACING_AUDIT_FINDING_1.md.

These tests verify:
  1. Table-based height-adjusted spacing (V127) at all valid heights
  2. The V120 audit_notice is always present and references the finding doc
  3. The runtime WARNING log fires with "V120 AUDIT WARNING"
  4. Pre-existing physics guards are preserved
  5. Consistency with fireai/constants/nfpa72.py (single source of truth)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from fireai.constants.nfpa72 import (
    SMOKE_HEIGHT_SPACING_TABLE,
    SMOKE_MAX_SPACING_M,
)
from fireai.core.qomn_kernel import (
    NFPA72_SMOKE_MAX_SPACING_M,
    compute_smoke_detector_spacing,
)


# ═══════════════════════════════════════════════════════════════════════════════
# V127 - Height-Adjusted Table Spacing
# ═══════════════════════════════════════════════════════════════════════════════


class TestV127TableSpacing:
    """V127: Spacing is height-adjusted per SMOKE_HEIGHT_SPACING_TABLE."""

    @pytest.mark.parametrize("height, expected", [
        (3.0,    9.10),   # h<=3.0m -> 9.10
        (3.7,    8.70),   # h<=3.7m -> 8.70
        (4.6,    8.20),   # h<=4.6m -> 8.20
        (5.5,    7.70),   # h<=5.5m -> 7.70
        (6.1,    7.30),   # h<=6.1m -> 7.30
        (7.6,    6.80),   # h<=7.6m -> 6.80
        (9.144,  6.40),   # h<=9.144m (30 ft exact) -> 6.40
        (10.7,   6.00),   # h<=10.7m -> 6.00
        (12.2,   5.60),   # h<=12.2m -> 5.60
        (18.288, 5.20),   # h<=18.288m (60 ft) -> 5.20
    ])
    def test_table_lookup_at_each_boundary(self, height, expected):
        """Spacing at each table row boundary must match the table value."""
        r = compute_smoke_detector_spacing(height)
        assert r["listed_spacing_m"] == pytest.approx(expected, abs=1e-3), (
            f"At h={height}m, expected S={expected}m, "
            f"got S={r['listed_spacing_m']}m"
        )

    def test_h_above_table_uses_fallback(self):
        """h=15.0m is above the table max (12.2m) but below 18.288m cap.
        The table includes row 9 (18.288m, 5.20m) so h=15.0 falls in row 9
        and returns 5.20m."""
        r = compute_smoke_detector_spacing(15.0)
        assert r["listed_spacing_m"] == pytest.approx(5.20, abs=1e-3)

    def test_h_max_boundary_18_288m(self):
        """h=18.288m (60 ft): Maximum allowed by guard, returns 5.20m."""
        r = compute_smoke_detector_spacing(18.288)
        assert r["listed_spacing_m"] == pytest.approx(5.20, abs=1e-3)

    def test_spacing_never_exceeds_max(self):
        """Spacing at any height must never exceed SMOKE_MAX_SPACING_M."""
        for h in (3.0, 4.0, 6.0, 9.0, 12.0, 15.0, 18.0):
            r = compute_smoke_detector_spacing(h)
            assert r["listed_spacing_m"] <= NFPA72_SMOKE_MAX_SPACING_M + 1e-9

    def test_coverage_radius_is_0p7_times_spacing(self):
        """Coverage radius = 0.7 x S at all heights per NFPA 72 §17.7.4.2.3.1."""
        for h in (3.0, 4.0, 5.0, 6.0, 9.0, 12.0, 15.0):
            r = compute_smoke_detector_spacing(h)
            expected_r = 0.7 * r["listed_spacing_m"]
            assert r["coverage_radius_m"] == pytest.approx(expected_r, abs=1e-2)


# ═══════════════════════════════════════════════════════════════════════════════
# V120 - Audit Notice (always emitted in V127)
# ═══════════════════════════════════════════════════════════════════════════════


class TestV120AuditNotice:
    """V120: The audit_notice is ALWAYS emitted (V127) and references the
    finding document."""

    def test_audit_notice_always_present(self):
        """audit_notice must always be present in V127."""
        r = compute_smoke_detector_spacing(3.0)
        assert "audit_notice" in r
        assert r["audit_notice"] is not None

    def test_audit_notice_at_high_ceiling(self):
        """audit_notice present at h=10.0m."""
        r = compute_smoke_detector_spacing(10.0)
        assert "audit_notice" in r
        assert r["audit_notice"] is not None

    def test_audit_notice_cites_v120(self):
        """Audit notice must contain 'V120 AUDIT WARNING'."""
        r = compute_smoke_detector_spacing(10.0)
        notice = r.get("audit_notice", "")
        assert "V120 AUDIT WARNING" in notice, f"Missing V120 ref: {notice}"

    def test_audit_notice_references_finding_doc(self):
        """Audit notice must reference SMOKE_SPACING_AUDIT_FINDING_1.md."""
        r = compute_smoke_detector_spacing(10.0)
        notice = r.get("audit_notice", "")
        assert "SMOKE_SPACING_AUDIT_FINDING_1.md" in notice, (
            f"Missing finding doc reference: {notice}"
        )

    def test_audit_notice_cites_nfpa_sections(self):
        """Audit notice must cite NFPA sections (§17.7.3.2.3, §17.7.1.11)."""
        r = compute_smoke_detector_spacing(10.0)
        notice = r.get("audit_notice", "")
        assert "17.7.3.2.3" in notice
        assert "17.7.1.11" in notice

    def test_runtime_warning_fires(self, caplog):
        """Runtime WARNING log must fire with V120 AUDIT WARNING."""
        with caplog.at_level(logging.WARNING, logger="fireai.core.qomn_kernel"):
            compute_smoke_detector_spacing(3.0)
        assert any("V120 AUDIT WARNING" in rec.message for rec in caplog.records), (
            f"Expected V120 WARNING log, got: {[r.message for r in caplog.records]}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Physics Guards - Preserved
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhysicsGuards:
    """Pre-existing physics guards must still function."""

    def test_zero_height_rejected(self):
        with pytest.raises(Exception):
            compute_smoke_detector_spacing(0.0)

    def test_negative_height_rejected(self):
        with pytest.raises(Exception):
            compute_smoke_detector_spacing(-1.0)

    def test_height_above_hard_limit_rejected(self):
        """h > 18.288m must be rejected by guard."""
        with pytest.raises(Exception):
            compute_smoke_detector_spacing(19.0)

    def test_nan_rejected(self):
        with pytest.raises(Exception):
            compute_smoke_detector_spacing(float("nan"))

    def test_inf_rejected(self):
        with pytest.raises(Exception):
            compute_smoke_detector_spacing(float("inf"))


# ═══════════════════════════════════════════════════════════════════════════════
# SSoT Consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestSSoTConsistency:
    """Verify consistency with fireai.constants (single source of truth)."""

    def test_max_spacing_matches_constants(self):
        """Kernel SMOKE_MAX_SPACING_M must match constants."""
        assert NFPA72_SMOKE_MAX_SPACING_M == SMOKE_MAX_SPACING_M == 9.10

    def test_table_has_10_rows(self):
        """SMOKE_HEIGHT_SPACING_TABLE must have exactly 10 rows."""
        assert len(SMOKE_HEIGHT_SPACING_TABLE) == 10

    def test_table_row_6_is_9p144m(self):
        """Row 6 must use 9.144m (30 ft exact) — NOT 9.1m."""
        assert SMOKE_HEIGHT_SPACING_TABLE[6][0] == pytest.approx(9.144, abs=1e-3)

    def test_table_row_9_is_18p288m(self):
        """Row 9 must be 18.288m / 5.20m (60 ft ceiling cap)."""
        assert SMOKE_HEIGHT_SPACING_TABLE[9][0] == pytest.approx(18.288, abs=1e-3)
        assert SMOKE_HEIGHT_SPACING_TABLE[9][1] == pytest.approx(5.20, abs=1e-3)

    def test_table_values_are_monotonically_decreasing(self):
        """Spacing values must monotonically decrease with height."""
        spacings = [s for _, s in SMOKE_HEIGHT_SPACING_TABLE]
        for i in range(1, len(spacings)):
            assert spacings[i] <= spacings[i - 1], (
                f"Row {i} spacing {spacings[i]} > row {i-1} {spacings[i-1]}"
            )
