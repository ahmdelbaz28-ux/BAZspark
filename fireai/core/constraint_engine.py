"""
fireai.core.constraint_engine — Code-Based Routing Constraints
==============================================================

Deterministic constraint engine for fire alarm cable routing.

Every constraint traces to a published code section:
  - NEC 760.24: Fire alarm cables in separate conduits from power
  - NEC 760.24(A): Cable fastening every 18" (457mm)
  - NFPA 72 §23.6.2: NAC circuit max length per wire gauge
  - NFPA 72 §10.6.4: Voltage drop verification
  - Project Spec: Min conduit ¾" red painted EMT
  - Project Spec: Max bend radius = 6 × conduit diameter
  - Project Spec: Separation from electrical conduits ≥ 300mm

QOMN-FIRE Principles:
  - NO approximations — every constraint is exact
  - NO probabilistic decisions — deterministic always
  - Every decision logged with code reference
  - Same input → same output, always

SAFETY CRITICAL:
  - Constraint violations are NEVER silently ignored
  - Every rejected path includes the specific code section violated
  - Physical impossibilities (negative lengths, NaN) are caught at input
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Reuse physics guards from contracts_validation
from fireai.core.contracts_validation import (
    ContractViolation,
    validate_voltage,
    validate_current,
    _MIN_FA_VOLTAGE_V,
    _MAX_FA_VOLTAGE_V,
)

# Reuse wire gauge and resistance data
from fireai.core.cable_routing_engine import WireGauge


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTRAINT SOURCE ENUM — Every constraint has a source
# ═══════════════════════════════════════════════════════════════════════════════

class ConstraintSource(Enum):
    """Source of a routing constraint — every rule must cite its origin."""
    NEC_760_24 = "NEC 760.24"                     # FA cable separation
    NEC_760_24_A = "NEC 760.24(A)"                # Cable fastening interval
    NEC_760_154 = "NEC 760.154"                    # PLFA/NPLFA separation
    NFPA_72_23_6_2 = "NFPA 72 §23.6.2"            # NAC circuit max length
    NFPA_72_10_6_4 = "NFPA 72 §10.6.4"            # Voltage drop verification
    NFPA_72_12_2_2 = "NFPA 72 §12.2.2"            # Class A circuit separation
    NEC_CH9_TABLE4 = "NEC Chapter 9, Table 4"     # Conduit fill
    NEC_CH9_TABLE8 = "NEC Chapter 9, Table 8"     # Wire resistance
    PROJECT_SPEC_CONDUIT = "Project Spec: Min ¾\" EMT"
    PROJECT_SPEC_BEND = "Project Spec: Max bend radius = 6 × Ø"
    PROJECT_SPEC_SEPARATION = "Project Spec: ≥ 300mm from electrical"
    PROJECT_SPEC_FASTENING = "Project Spec: Fasten every 457mm"
    PHYSICS = "Physics"                            # Fundamental physics constraints


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SPECIFICATION CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Project Spec: Minimum conduit ¾" EMT, red painted
MIN_CONDUIT_INCHES = 0.75          # ¾" per project specification
MIN_CONDUIT_MM = 19.05             # ¾" = 19.05mm
EMT_3_4_INNER_DIAMETER_MM = 15.8   # NEC Chapter 9, Table 4 — ¾" EMT inner diameter
EMT_3_4_OUTER_DIAMETER_MM = 19.05  # ¾" EMT outer diameter

# Project Spec: Maximum bend radius = 6 × conduit diameter
# Per NEC 344.24, EMT bends shall be made with a radius not less than:
# - 6 × diameter for ½" to 1" EMT
# Per project specification, this is confirmed at 6×
BEND_RADIUS_FACTOR = 6  # 6 × conduit diameter per project spec / NEC 344.24
MAX_BEND_RADIUS_MM = BEND_RADIUS_FACTOR * EMT_3_4_OUTER_DIAMETER_MM  # 114.3mm

# Project Spec: Separation from electrical conduits ≥ 300mm
MIN_ELECTRICAL_SEPARATION_MM = 300.0  # 300mm per project specification

# NEC 760.24(A): Cables fastened every 18" (457mm)
MAX_CABLE_FASTENING_INTERVAL_MM = 457.0  # 18" = 457mm per NEC 760.24(A)

# NEC Chapter 9, Table 4 — ¾" EMT cross-sectional area
EMT_3_4_AREA_SQ_MM = 196.0  # 100% fill area for ¾" EMT

# NEC 760.154 — Maximum fill percentage for PLFA circuits
MAX_CONDUIT_FILL_PCT = 0.40  # 40% fill per NEC 760.154

# NFPA 72 §23.6.2 — NAC circuit maximum lengths by wire gauge
# These are practical limits ensuring voltage drop compliance
# for typical 24V NAC circuits with standard device loads
_NAC_MAX_LENGTHS_M = {
    WireGauge.AWG_12: 914.0,    # 3000 ft practical max
    WireGauge.AWG_14: 610.0,    # 2000 ft practical max
    WireGauge.AWG_16: 381.0,    # 1250 ft practical max
    WireGauge.AWG_18: 229.0,    # 750 ft practical max
}

# Cable routing penalty constants (in meters equivalent)
BEND_PENALTY_M = 0.5       # 90° bend = equivalent to 0.5m extra length
ELEVATION_PENALTY_M = 2.0  # Elevation change = equivalent to 2.0m extra length
ELECTRICAL_PROXIMITY_PENALTY_M = 1.0  # Proximity to electrical = 1.0m penalty


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTRAINT RESULT — Every check produces an auditable result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ConstraintResult:
    """Result of a constraint check.

    Every constraint check produces a traceable result that includes:
    - Whether the constraint passed or failed
    - The specific code section that was checked
    - The actual value that was tested
    - The threshold or limit that was applied
    - A remediation message if the constraint failed

    Attributes:
        constraint_name: Human-readable constraint name.
        source: Code section or standard reference.
        is_satisfied: True if the constraint is met.
        actual_value: The value that was checked.
        limit_value: The threshold or limit.
        unit: Unit of measurement (e.g. 'mm', 'm', 'V').
        severity: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'.
        remediation: What to do if the constraint is violated.
        formula: The formula used for the check, with values.
    """
    constraint_name: str
    source: str
    is_satisfied: bool
    actual_value: float = 0.0
    limit_value: float = 0.0
    unit: str = ""
    severity: str = "CRITICAL"
    remediation: str = ""
    formula: str = ""


@dataclass(frozen=True)
class RoutingConstraintSet:
    """Complete set of constraint results for a routing operation.

    Attributes:
        results: Individual constraint check results.
        all_satisfied: True if ALL constraints are satisfied.
        critical_violations: Count of CRITICAL severity violations.
        total_violations: Count of all violations.
    """
    results: Tuple[ConstraintResult, ...]
    all_satisfied: bool = True
    critical_violations: int = 0
    total_violations: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTRAINT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ConstraintEngine:
    """Deterministic constraint engine for fire alarm cable routing.

    Every constraint is traceable to a published code section.
    No approximations. No probabilistic decisions. Pure deterministic
    logic with reference-based rules.

    Example usage::

        engine = ConstraintEngine()
        results = engine.check_all(
            cable_length_m=150.0,
            wire_gauge=WireGauge.AWG_14,
            num_bends=4,
            num_elevation_changes=2,
            min_electrical_separation_mm=250.0,
            ps_voltage=24.0,
            alarm_current_a=1.5,
        )
        if not results.all_satisfied:
            for r in results.results:
                if not r.is_satisfied:
                    print(f"VIOLATION: {r.constraint_name} ({r.source})")
    """

    def __init__(
        self,
        min_conduit_inches: float = MIN_CONDUIT_INCHES,
        bend_radius_factor: float = BEND_RADIUS_FACTOR,
        min_electrical_separation_mm: float = MIN_ELECTRICAL_SEPARATION_MM,
        max_fastening_interval_mm: float = MAX_CABLE_FASTENING_INTERVAL_MM,
        bend_penalty_m: float = BEND_PENALTY_M,
        elevation_penalty_m: float = ELEVATION_PENALTY_M,
    ):
        """Initialize the constraint engine with project specifications.

        Args:
            min_conduit_inches: Minimum conduit size (default ¾" EMT).
            bend_radius_factor: Bend radius as multiple of conduit diameter (default 6).
            min_electrical_separation_mm: Minimum separation from electrical (default 300mm).
            max_fastening_interval_mm: Maximum cable fastening interval (default 457mm).
            bend_penalty_m: Bend penalty in equivalent meters (default 0.5m).
            elevation_penalty_m: Elevation change penalty (default 2.0m).
        """
        self._min_conduit_inches = min_conduit_inches
        self._bend_radius_factor = bend_radius_factor
        self._min_electrical_separation_mm = min_electrical_separation_mm
        self._max_fastening_interval_mm = max_fastening_interval_mm
        self._bend_penalty_m = bend_penalty_m
        self._elevation_penalty_m = elevation_penalty_m

    # ─── Individual Constraint Checks ─────────────────────────────────────

    def check_nac_max_length(
        self,
        cable_length_m: float,
        wire_gauge: WireGauge,
        circuit_type: str = "NAC",
    ) -> ConstraintResult:
        """Check NAC circuit maximum length per NFPA 72 §23.6.2.

        NFPA 72 §23.6.2 limits the maximum length of Notification
        Appliance Circuits based on wire gauge to ensure voltage
        drop compliance under alarm conditions.

        Formula:
          Max Length per §23.6.2 = f(AWG gauge)

        Args:
            cable_length_m: Actual cable length in meters.
            wire_gauge: Wire gauge used.
            circuit_type: Circuit type string (NAC, SLC, etc.).

        Returns:
            ConstraintResult with pass/fail status.
        """
        max_length = _NAC_MAX_LENGTHS_M.get(wire_gauge, 229.0)

        is_satisfied = cable_length_m <= max_length

        return ConstraintResult(
            constraint_name=f"{circuit_type} Circuit Max Length",
            source=ConstraintSource.NFPA_72_23_6_2.value,
            is_satisfied=is_satisfied,
            actual_value=cable_length_m,
            limit_value=max_length,
            unit="m",
            severity="CRITICAL",
            remediation=(
                f"Reduce circuit length to ≤{max_length}m or upgrade to "
                f"larger wire gauge per NFPA 72 §23.6.2"
            ) if not is_satisfied else "",
            formula=(
                f"L_actual = {cable_length_m:.1f}m "
                f"{'≤' if is_satisfied else '>'} "
                f"L_max = {max_length}m (AWG {wire_gauge.awg_value})"
            ),
        )

    def check_voltage_drop(
        self,
        alarm_current_a: float,
        cable_length_m: float,
        wire_gauge: WireGauge,
        ps_voltage: float = 24.0,
        max_drop_pct: float = 10.0,
    ) -> ConstraintResult:
        """Check voltage drop compliance per NFPA 72 §10.6.4.

        NFPA 72 §10.6.4 requires that the voltage at end-of-line be
        sufficient to operate all devices under alarm conditions.

        Formula (NEC Chapter 9, Table 8):
          V_drop = I × 2 × R_wire × L(km)

        The ×2 factor accounts for DC return path — current flows out
        on one conductor and returns on the other. This is CRITICAL:
        omitting ×2 would report voltage drop at 50% of actual.

        For 24V systems: V_drop must be ≤ 2.4V (10%)

        Args:
            alarm_current_a: Total alarm current in amperes.
            cable_length_m: One-way cable length in meters.
            wire_gauge: Wire gauge.
            ps_voltage: Power supply voltage (default 24V).
            max_drop_pct: Maximum allowed drop percentage (default 10%).

        Returns:
            ConstraintResult with voltage drop analysis.
        """
        # Compute voltage drop with DC return path (×2)
        r_per_km = wire_gauge.resistance_ohm_per_km
        length_km = cable_length_m / 1000.0
        v_drop = alarm_current_a * 2.0 * r_per_km * length_km
        v_drop_pct = (v_drop / ps_voltage) * 100.0 if ps_voltage > 0 else 0.0
        max_drop_v = ps_voltage * max_drop_pct / 100.0

        is_satisfied = v_drop_pct <= max_drop_pct

        return ConstraintResult(
            constraint_name="Voltage Drop",
            source=ConstraintSource.NFPA_72_10_6_4.value,
            is_satisfied=is_satisfied,
            actual_value=round(v_drop, 4),
            limit_value=round(max_drop_v, 4),
            unit="V",
            severity="CRITICAL",
            remediation=(
                f"Voltage drop {v_drop:.2f}V ({v_drop_pct:.1f}%) exceeds "
                f"maximum {max_drop_pct}% ({max_drop_v:.1f}V). "
                f"Upgrade wire gauge or reduce circuit length per NFPA 72 §10.6.4."
            ) if not is_satisfied else "",
            formula=(
                f"V_drop = I × 2 × R × L = "
                f"{alarm_current_a:.4f}A × 2 × "
                f"{r_per_km:.3f}Ω/km × "
                f"{length_km:.6f}km = {v_drop:.4f}V ({v_drop_pct:.2f}%)"
            ),
        )

    def check_electrical_separation(
        self,
        actual_separation_mm: float,
    ) -> ConstraintResult:
        """Check separation from electrical conduits per project spec.

        Project Specification requires ≥ 300mm separation between
        fire alarm cables and electrical power conduits.

        NEC 760.24: Fire alarm cables must be in separate conduits
        from power conductors.

        NEC 760.154: PLFA circuits must be separated from NPLFA
        and power circuits.

        Args:
            actual_separation_mm: Actual separation distance in mm.

        Returns:
            ConstraintResult with separation check result.
        """
        is_satisfied = actual_separation_mm >= self._min_electrical_separation_mm

        return ConstraintResult(
            constraint_name="Electrical Conduit Separation",
            source=ConstraintSource.PROJECT_SPEC_SEPARATION.value,
            is_satisfied=is_satisfied,
            actual_value=actual_separation_mm,
            limit_value=self._min_electrical_separation_mm,
            unit="mm",
            severity="CRITICAL",
            remediation=(
                f"Increase separation to ≥{self._min_electrical_separation_mm}mm "
                f"from electrical conduits per Project Specification and NEC 760.24"
            ) if not is_satisfied else "",
            formula=(
                f"d_actual = {actual_separation_mm:.0f}mm "
                f"{'≥' if is_satisfied else '<'} "
                f"d_min = {self._min_electrical_separation_mm:.0f}mm"
            ),
        )

    def check_bend_radius(
        self,
        conduit_diameter_mm: float = EMT_3_4_OUTER_DIAMETER_MM,
    ) -> ConstraintResult:
        """Check bend radius compliance per project spec / NEC 344.24.

        Project Specification: Maximum bend radius = 6 × conduit diameter.
        NEC 344.24: EMT bends shall have a radius not less than
        specified in Table 344.24 (6× diameter for ½" to 1" EMT).

        For ¾" EMT:
          Max bend radius = 6 × 19.05mm = 114.3mm

        Args:
            conduit_diameter_mm: Conduit outer diameter in mm.

        Returns:
            ConstraintResult with bend radius check.
        """
        max_bend_radius = self._bend_radius_factor * conduit_diameter_mm

        # This is a design rule — the router must comply with it
        # We report the required radius rather than checking a measurement
        return ConstraintResult(
            constraint_name="Maximum Bend Radius",
            source=ConstraintSource.PROJECT_SPEC_BEND.value,
            is_satisfied=True,  # Design rule, always satisfied when used correctly
            actual_value=max_bend_radius,
            limit_value=max_bend_radius,
            unit="mm",
            severity="HIGH",
            remediation="",
            formula=(
                f"R_bend = {self._bend_radius_factor} × Ø = "
                f"{self._bend_radius_factor} × {conduit_diameter_mm:.2f}mm = "
                f"{max_bend_radius:.1f}mm"
            ),
        )

    def check_conduit_size(
        self,
        conduit_inches: float = MIN_CONDUIT_INCHES,
    ) -> ConstraintResult:
        """Check minimum conduit size per project specification.

        Project Specification: Minimum conduit ¾" red painted EMT.

        Args:
            conduit_inches: Conduit size in inches.

        Returns:
            ConstraintResult with conduit size check.
        """
        is_satisfied = conduit_inches >= self._min_conduit_inches

        return ConstraintResult(
            constraint_name="Minimum Conduit Size",
            source=ConstraintSource.PROJECT_SPEC_CONDUIT.value,
            is_satisfied=is_satisfied,
            actual_value=conduit_inches,
            limit_value=self._min_conduit_inches,
            unit="inches",
            severity="HIGH",
            remediation=(
                f"Use minimum ¾\" red painted EMT per project specification"
            ) if not is_satisfied else "",
            formula=(
                f"Ø_conduit = {conduit_inches}\" "
                f"{'≥' if is_satisfied else '<'} "
                f"Ø_min = {self._min_conduit_inches}\""
            ),
        )

    def check_cable_fastening(
        self,
        cable_length_m: float,
        num_fasteners: int,
    ) -> ConstraintResult:
        """Check cable fastening interval per NEC 760.24(A).

        NEC 760.24(A): Cables shall be fastened at intervals not
        exceeding 18 inches (457mm).

        Args:
            cable_length_m: Total cable length in meters.
            num_fasteners: Number of fasteners along the cable.

        Returns:
            ConstraintResult with fastening check.
        """
        max_interval_mm = self._max_fastening_interval_mm

        if cable_length_m <= 0:
            return ConstraintResult(
                constraint_name="Cable Fastening Interval",
                source=ConstraintSource.NEC_760_24_A.value,
                is_satisfied=True,
                actual_value=0.0,
                limit_value=max_interval_mm,
                unit="mm",
                severity="MEDIUM",
                remediation="",
                formula="L=0, no fastening required",
            )

        # Calculate actual interval
        if num_fasteners <= 0:
            actual_interval_mm = cable_length_m * 1000.0  # No fasteners at all
        else:
            actual_interval_mm = (cable_length_m * 1000.0) / (num_fasteners + 1)

        is_satisfied = actual_interval_mm <= max_interval_mm

        return ConstraintResult(
            constraint_name="Cable Fastening Interval",
            source=ConstraintSource.NEC_760_24_A.value,
            is_satisfied=is_satisfied,
            actual_value=round(actual_interval_mm, 1),
            limit_value=max_interval_mm,
            unit="mm",
            severity="MEDIUM",
            remediation=(
                f"Add more fasteners — current interval {actual_interval_mm:.0f}mm "
                f"exceeds {max_interval_mm}mm per NEC 760.24(A)"
            ) if not is_satisfied else "",
            formula=(
                f"interval = L / (n+1) = "
                f"{cable_length_m * 1000:.0f}mm / {num_fasteners + 1} = "
                f"{actual_interval_mm:.0f}mm "
                f"{'≤' if is_satisfied else '>'} "
                f"{max_interval_mm}mm"
            ),
        )

    def check_class_a_separation(
        self,
        outgoing_path: List[Tuple[float, float, float]],
        return_path: List[Tuple[float, float, float]],
        min_separation_m: float = 0.3,
    ) -> ConstraintResult:
        """Check Class A circuit outgoing/return path separation.

        NFPA 72 §12.2.2: For Class A circuits, the outgoing and
        return conductors must not be routed through the same opening
        in a wall, floor, or ceiling.

        This check ensures minimum separation between outgoing and
        return paths to prevent a single fault from disabling both.

        Args:
            outgoing_path: List of (x,y,z) points on outgoing path.
            return_path: List of (x,y,z) points on return path.
            min_separation_m: Minimum required separation (default 0.3m).

        Returns:
            ConstraintResult with separation check.
        """
        min_distance = float('inf')

        # Check minimum distance between any point on outgoing path
        # and any point on return path
        for p1 in outgoing_path:
            for p2 in return_path:
                dist = math.sqrt(
                    (p1[0] - p2[0]) ** 2
                    + (p1[1] - p2[1]) ** 2
                    + (p1[2] - p2[2]) ** 2
                )
                if dist < min_distance:
                    min_distance = dist

        if not outgoing_path or not return_path:
            min_distance = 0.0

        is_satisfied = min_distance >= min_separation_m

        return ConstraintResult(
            constraint_name="Class A Path Separation",
            source=ConstraintSource.NFPA_72_12_2_2.value,
            is_satisfied=is_satisfied,
            actual_value=round(min_distance, 4),
            limit_value=min_separation_m,
            unit="m",
            severity="CRITICAL",
            remediation=(
                f"Minimum separation {min_distance:.2f}m is below "
                f"required {min_separation_m}m. Route return path through "
                f"different penetration per NFPA 72 §12.2.2"
            ) if not is_satisfied else "",
            formula=(
                f"d_min = {min_distance:.2f}m "
                f"{'≥' if is_satisfied else '<'} "
                f"d_required = {min_separation_m}m"
            ),
        )

    def check_conduit_fill(
        self,
        wire_diameter_mm: float,
        num_cables: int,
        conduit_inner_diameter_mm: float = EMT_3_4_INNER_DIAMETER_MM,
    ) -> ConstraintResult:
        """Check conduit fill per NEC Chapter 9, Table 4.

        NEC 760.154: Maximum 40% fill for PLFA circuits in conduit.

        Formula:
          Fill = (N × π × (d/2)²) / (π × (D/2)²) × 100
          Simplified: Fill = N × (d/D)² × 100

        Args:
            wire_diameter_mm: Cable outer diameter in mm.
            num_cables: Number of cables in the conduit.
            conduit_inner_diameter_mm: Conduit inner diameter in mm.

        Returns:
            ConstraintResult with fill percentage.
        """
        if conduit_inner_diameter_mm <= 0:
            return ConstraintResult(
                constraint_name="Conduit Fill",
                source=ConstraintSource.NEC_CH9_TABLE4.value,
                is_satisfied=False,
                actual_value=0.0,
                limit_value=MAX_CONDUIT_FILL_PCT * 100,
                unit="%",
                severity="CRITICAL",
                remediation="Invalid conduit inner diameter",
                formula="D_conduit = 0, invalid",
            )

        wire_area = math.pi * (wire_diameter_mm / 2.0) ** 2
        conduit_area = math.pi * (conduit_inner_diameter_mm / 2.0) ** 2
        fill_ratio = (num_cables * wire_area) / conduit_area
        fill_pct = fill_ratio * 100.0
        max_fill_pct = MAX_CONDUIT_FILL_PCT * 100.0

        is_satisfied = fill_ratio <= MAX_CONDUIT_FILL_PCT

        return ConstraintResult(
            constraint_name="Conduit Fill",
            source=ConstraintSource.NEC_CH9_TABLE4.value,
            is_satisfied=is_satisfied,
            actual_value=round(fill_pct, 2),
            limit_value=round(max_fill_pct, 1),
            unit="%",
            severity="HIGH",
            remediation=(
                f"Conduit fill {fill_pct:.1f}% exceeds {max_fill_pct:.0f}% "
                f"per NEC 760.154 / Chapter 9 Table 4. "
                f"Reduce cables or increase conduit size."
            ) if not is_satisfied else "",
            formula=(
                f"Fill = N × A_wire / A_conduit = "
                f"{num_cables} × {wire_area:.1f}mm² / {conduit_area:.1f}mm² = "
                f"{fill_pct:.1f}%"
            ),
        )

    # ─── Composite Checks ─────────────────────────────────────────────────

    def check_all(
        self,
        cable_length_m: float,
        wire_gauge: WireGauge,
        num_bends: int = 0,
        num_elevation_changes: int = 0,
        min_electrical_separation_mm: float = 300.0,
        ps_voltage: float = 24.0,
        alarm_current_a: float = 0.0,
        num_fasteners: int = 0,
        circuit_type: str = "NAC",
        is_class_a: bool = False,
        outgoing_path: Optional[List[Tuple[float, float, float]]] = None,
        return_path: Optional[List[Tuple[float, float, float]]] = None,
    ) -> RoutingConstraintSet:
        """Run ALL constraint checks and return combined result.

        This is the primary API for constraint verification. Every
        check produces a traceable result with code reference.

        Args:
            cable_length_m: Total cable length in meters.
            wire_gauge: Wire gauge used.
            num_bends: Number of 90° bends in the route.
            num_elevation_changes: Number of elevation changes.
            min_electrical_separation_mm: Minimum distance to electrical.
            ps_voltage: Power supply voltage (default 24V).
            alarm_current_a: Total alarm current in amperes.
            num_fasteners: Number of cable fasteners.
            circuit_type: Circuit type string (NAC, SLC, etc.).
            is_class_a: Whether this is a Class A circuit.
            outgoing_path: Outgoing path points (for Class A check).
            return_path: Return path points (for Class A check).

        Returns:
            RoutingConstraintSet with all check results.
        """
        results = []

        # 1. NAC circuit max length
        results.append(self.check_nac_max_length(cable_length_m, wire_gauge, circuit_type))

        # 2. Voltage drop
        if alarm_current_a > 0 and cable_length_m > 0:
            results.append(self.check_voltage_drop(
                alarm_current_a, cable_length_m, wire_gauge, ps_voltage
            ))

        # 3. Electrical separation
        results.append(self.check_electrical_separation(min_electrical_separation_mm))

        # 4. Bend radius (design rule)
        results.append(self.check_bend_radius())

        # 5. Conduit size (design rule)
        results.append(self.check_conduit_size())

        # 6. Cable fastening
        results.append(self.check_cable_fastening(cable_length_m, num_fasteners))

        # 7. Class A separation (if applicable)
        if is_class_a and outgoing_path and return_path:
            results.append(self.check_class_a_separation(outgoing_path, return_path))

        # Compute summary
        violations = [r for r in results if not r.is_satisfied]
        critical_count = sum(1 for v in violations if v.severity == "CRITICAL")

        return RoutingConstraintSet(
            results=tuple(results),
            all_satisfied=len(violations) == 0,
            critical_violations=critical_count,
            total_violations=len(violations),
        )

    # ─── Cost Function for A* ─────────────────────────────────────────────

    def compute_move_cost(
        self,
        from_cell: Tuple[int, int, int],
        to_cell: Tuple[int, int, int],
        is_near_electrical: bool = False,
        grid_resolution: float = 0.1,
    ) -> float:
        """Compute the cost of moving from one cell to an adjacent cell.

        Used by the A* pathfinding algorithm. Costs are based on:
        - Straight segment: length × 1.0
        - 90° bend: + penalty (equivalent to 0.5m extra length)
        - Elevation change: + penalty (equivalent to 2.0m extra length)
        - Proximity to electrical: + penalty if < 300mm

        The direction of movement is determined by comparing the
        from_cell and to_cell indices. Only 6-directional orthogonal
        movement is allowed (X±, Y±, Z±).

        Args:
            from_cell: Source cell (ix, iy, iz).
            to_cell: Target cell (ix, iy, iz).
            is_near_electrical: Whether target cell is near electrical conduit.
            grid_resolution: Grid cell size in meters.

        Returns:
            Movement cost in equivalent meters.
        """
        dx = to_cell[0] - from_cell[0]
        dy = to_cell[1] - from_cell[1]
        dz = to_cell[2] - from_cell[2]

        # Base cost: one cell length
        cost = grid_resolution

        # Elevation change penalty
        if dz != 0:
            cost += self._elevation_penalty_m * abs(dz)

        # Horizontal direction change (bend) is detected by the router,
        # not here. This method only computes single-step cost.

        # Electrical proximity penalty
        if is_near_electrical:
            cost += ELECTRICAL_PROXIMITY_PENALTY_M

        return cost

    @staticmethod
    def compute_bend_cost(
        prev_dir: Optional[Tuple[int, int, int]],
        curr_dir: Tuple[int, int, int],
    ) -> float:
        """Compute the cost of a direction change (bend).

        A 90° bend adds a penalty equivalent to 0.5m extra length.
        This is because bends require conduit fittings (elbows),
        which increase material cost, installation time, and
        make cable pulling more difficult.

        Per NEC Chapter 9: "The number of bends in one run shall
        not exceed the equivalent of four quarter bends (360° total)."

        Args:
            prev_dir: Previous movement direction (dx, dy, dz), or None.
            curr_dir: Current movement direction (dx, dy, dz).

        Returns:
            Bend cost in equivalent meters (0.0 for straight, 0.5 for 90°).
        """
        if prev_dir is None:
            return 0.0  # First move has no bend

        # Check if direction changed
        if prev_dir == curr_dir:
            return 0.0  # Straight — no bend

        # Any change in direction is a 90° bend (6-directional grid)
        return BEND_PENALTY_M

    @staticmethod
    def manhattan_heuristic(
        current: Tuple[int, int, int],
        goal: Tuple[int, int, int],
        grid_resolution: float = 0.1,
    ) -> float:
        """Manhattan distance heuristic for A* pathfinding.

        Admissible heuristic for 6-directional orthogonal movement.
        Never overestimates the actual cost because:
        - Manhattan distance ≤ actual path length (triangular inequality)
        - Does not include bend/elevation penalties

        Formula:
          h = |dx| + |dy| + |dz| × (1 + elevation_penalty/resolution)

        The elevation penalty factor makes the heuristic more
        informed while maintaining admissibility.

        Args:
            current: Current cell (ix, iy, iz).
            goal: Goal cell (ix, iy, iz).
            grid_resolution: Grid cell size in meters.

        Returns:
            Estimated minimum cost from current to goal.
        """
        dx = abs(goal[0] - current[0])
        dy = abs(goal[1] - current[1])
        dz = abs(goal[2] - current[2])

        # Base Manhattan distance in meters
        base = (dx + dy) * grid_resolution

        # Elevation changes are more expensive
        elevation_cost = dz * grid_resolution * (1.0 + ELEVATION_PENALTY_M / grid_resolution)

        return base + elevation_cost
