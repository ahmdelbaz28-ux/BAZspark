# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
qomn_conduit.types — Type Definitions for Conduit Fitting System
================================================================

All types used throughout the conduit fitting engine.

ENGINEERING SOURCES:
  NEC 2022 Chapter 9           — Conduit fill and bend radius tables
  NEC 358 (EMT)                — Electrical Metallic Tubing
  NEC 352 (PVC/UPVC Sch 40/80) — Rigid Nonmetallic Conduit
  NEC 344 (RGD/RMC)            — Rigid Metal Conduit
  NFPA 72-2022 §12.2           — Fire alarm circuit class requirements

All float fields are float64 (Python float = C double). float32 is
prohibited per project zero-defect policy.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from fireai.core.base_types import (  # noqa: F401  # Result re-exported for qomn_conduit.catalog
    ConduitType,
    FittingType,
    Point3D,
    Result,
)

# ─────────────────────────────────────────────────────────────────────────────
# TradeSize — nominal pipe/conduit sizes
# ─────────────────────────────────────────────────────────────────────────────


class TradeSize(enum.Enum):
    """
    Nominal conduit trade sizes.

    These are nominal (marketing) sizes — not actual measurements.
    Actual OD values are defined per conduit type in the catalog.

    Reference: NEC Chapter 9, Table 4 — Dimensions and Percent Area
               of Conduit and Tubing.
    """

    HALF_INCH       = "1/2"
    THREE_QUARTER   = "3/4"
    ONE_INCH        = "1"
    ONE_QUARTER     = "1-1/4"
    ONE_HALF        = "1-1/2"
    TWO_INCH        = "2"

    def __repr__(self) -> str:
        return f"TradeSize.{self.name}({self.value!r})"


# ─────────────────────────────────────────────────────────────────────────────
# PlacedFitting — a fitting at a specific location
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlacedFitting:
    """
    A catalog fitting placed at a specific location in the conduit run.

    Attributes:
        fitting_type:       Type of fitting (ELBOW_90, COUPLING, etc.).
        conduit_type:       Material/standard of the conduit.
        trade_size:         Nominal trade size.
        position:           3D location of the fitting centre.
        catalog_number:     Manufacturer catalog reference (e.g. 'E90-050').
        angle_deg:          Bend angle in degrees (90 or 45 for elbows, 0 others).
        developed_length_m: Arc length of bend in metres (0 for straight fittings).
        weight_kg:          Fitting weight in kg (0.0 if not catalogued).

    """

    fitting_type:           FittingType
    conduit_type:           ConduitType
    trade_size:             TradeSize
    position:               Point3D
    catalog_number:         str
    angle_deg:              float = 0.0
    developed_length_m:     float = 0.0
    weight_kg:              float = 0.0

    def __repr__(self) -> str:
        return (
            f"PlacedFitting({self.catalog_number!r} "
            f"{self.fitting_type.name} @ {self.position!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ConduitSegment — a straight run between two fittings
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConduitSegment:
    """
    A straight conduit stick between two points.

    Attributes:
        start:       Start point (metres).
        end:         End point (metres).
        conduit_type: Material type.
        trade_size:  Nominal trade size.
        length_m:    Euclidean length in metres (computed from start/end).

    """

    start:        Point3D
    end:          Point3D
    conduit_type: ConduitType
    trade_size:   TradeSize

    @property
    def length_m(self) -> float:
        """One-way length in metres. Formula: sqrt(Dx^2 + Dy^2 + Dz^2)."""
        return self.start.distance_to(self.end)

    def __repr__(self) -> str:
        return (
            f"ConduitSegment({self.conduit_type.name} "
            f"{self.trade_size.value} "
            f"{self.length_m:.3f}m)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ConduitRun — complete routed conduit system
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ConduitRun:
    """
    A complete conduit run from one pull point to the next.

    Contains all segments and fittings. The run is bounded by pull points
    (pull boxes or panel knockouts). NEC 358.26/352.26/344.26 limit the
    total bend degrees between pull points to 360deg.

    Attributes:
        run_id:         Unique identifier for this run.
        conduit_type:   Material type (same throughout the run).
        trade_size:     Nominal trade size (same throughout the run).
        segments:       Ordered list of straight conduit sticks.
        fittings:       All fittings (elbows, couplings, pull boxes).
        total_length_m: Sum of all segment lengths in metres.
        total_bend_deg: Cumulative bend degrees (NEC limit: 360deg).
        is_compliant:   True if all NEC checks pass.
        violations:     List of NEC violation strings (empty if compliant).

    """

    run_id:         str
    conduit_type:   ConduitType
    trade_size:     TradeSize
    segments:       list[ConduitSegment] = field(default_factory=list)
    fittings:       list[PlacedFitting]  = field(default_factory=list)
    violations:     list[str]            = field(default_factory=list)

    @property
    def total_length_m(self) -> float:
        """Sum of all segment lengths in metres."""
        return sum(s.length_m for s in self.segments)

    @property
    def total_bend_deg(self) -> float:
        """Cumulative bend degrees across all fittings in this run."""
        return sum(
            f.angle_deg for f in self.fittings
            if f.fitting_type in (FittingType.ELBOW_90, FittingType.ELBOW_45)
        )

    @property
    def is_compliant(self) -> bool:
        """True if no NEC violations recorded."""
        return len(self.violations) == 0

    def __repr__(self) -> str:
        return (
            f"ConduitRun({self.run_id!r} "
            f"{self.conduit_type.name} {self.trade_size.value} "
            f"{self.total_length_m:.2f}m "
            f"{self.total_bend_deg:.0f}deg "
            f"{'OK' if self.is_compliant else 'VIOLATION'})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# FillResult — output of conduit fill calculator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FillResult:
    """
    Result of a NEC Chapter 9, Table 1 conduit fill calculation.

    Attributes:
        conduit_type:              Conduit material.
        trade_size:                Nominal conduit size.
        conductor_count:           Number of conductors in the conduit.
        total_conductor_area_in2:  Sum of pi*(d/2)^2 for all conductors (in^2).
        conduit_internal_area_in2: Tabulated internal area (NEC Table 4) (in^2).
        fill_percentage:           (total_conductor_area / internal_area) x 100.
        max_allowed_pct:           53%, 31%, or 40% per NEC Ch.9 Table 1.
        is_compliant:              fill_percentage <= max_allowed_pct.
        status:                    "COMPLIANT" or "VIOLATION" string.
        recommended_size:          Next larger trade size if non-compliant, else None.
        nec_reference:             Citation string for this calculation.

    """

    conduit_type:              ConduitType
    trade_size:                TradeSize
    conductor_count:           int
    total_conductor_area_in2:  float
    conduit_internal_area_in2: float
    fill_percentage:           float
    max_allowed_pct:           float
    is_compliant:              bool
    status:                    str
    recommended_size:          TradeSize | None
    nec_reference:             str

    def __repr__(self) -> str:
        return (
            f"FillResult({self.trade_size.value} {self.conduit_type.name} "
            f"{self.fill_percentage:.2f}%/{self.max_allowed_pct:.0f}% {self.status})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BendResult — output of bend radius verifier
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BendResult:
    """
    Result of NEC bend radius verification.

    Attributes:
        conduit_type:        Conduit material.
        trade_size:          Nominal trade size.
        actual_radius_in:    Radius of the bend as installed (inches).
        min_required_in:     NEC minimum bend radius (inches).
        angle_deg:           Bend angle (90deg or 45deg).
        developed_length_in: Arc length = pi x R x angle/180 (inches).
        developed_length_m:  Same in metres.
        is_compliant:        actual_radius_in >= min_required_in.
        nec_reference:       Article citation for this conduit type.

    """

    conduit_type:        ConduitType
    trade_size:          TradeSize
    actual_radius_in:    float
    min_required_in:     float
    angle_deg:           float
    developed_length_in: float
    developed_length_m:  float
    is_compliant:        bool
    nec_reference:       str

    def __repr__(self) -> str:
        status = "COMPLIANT" if self.is_compliant else "VIOLATION"
        return (
            f"BendResult({self.trade_size.value} {self.conduit_type.name} "
            f"R={self.actual_radius_in:.3f}in/{self.min_required_in:.3f}in_min "
            f"{self.angle_deg:.0f}deg {status})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# RoutePath — output of A* router
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoutePath:
    """
    Output of the orthogonal A* pathfinding algorithm.

    Attributes:
        waypoints:          Ordered list of Point3D nodes on the path.
        total_length_m:     Sum of segment lengths in metres.
        bend_count:         Number of direction changes (90deg turns).
        elevation_change_m: Absolute vertical displacement.

    """

    waypoints:          tuple[Point3D, ...]
    total_length_m:     float
    bend_count:         int
    elevation_change_m: float

    def __repr__(self) -> str:
        return (
            f"RoutePath({len(self.waypoints)} waypoints "
            f"{self.total_length_m:.2f}m "
            f"{self.bend_count} bends)"
        )
