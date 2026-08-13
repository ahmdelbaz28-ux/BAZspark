"""
fireai/core/results.py — Strongly typed computation result types.

Provides dataclass-based result types for all QOMN kernel computation
functions. Results are accessed via ATTRIBUTES only (``result.field``);
the historical dict-style access (``result["field"]``) is gone — callers
must migrate to attribute access (deep-modules doctrine: one typed
interface, no compatibility mixins).

Healing metadata is part of every result type: when the kernel's
self-healing path activates, the same result type is returned with
``is_healed=True``, ``safety_tier="FALLBACK_USED"`` and
``requires_fpe_review=True`` so downstream safety classification can
never silently accept a healed computation as PROOF_VERIFIED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SmokeSpacingResult:
    listed_spacing_m: float = 0.0
    coverage_radius_m: float = 0.0
    wall_min_m: float = 0.0
    wall_max_m: float = 0.0
    corner_min_m: float = 0.0
    nfpa_section: str = ""
    table_row_used: str = ""
    formula: str = ""
    computation_hash: str = ""
    audit_notice: str | None = None
    layer3_validated: bool = False
    # Healing metadata — set only on the self-healing fallback path.
    is_healed: bool = False
    healing_tier: int = 0
    healing_error: str | None = None
    safety_tier: str = ""
    requires_fpe_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HeatSpacingResult:
    spacing_m: float = 0.0
    coverage_radius_m: float = 0.0
    max_spacing_m: float = 0.0
    is_within_max: bool = True
    nfpa_section: str = ""
    formula: str = ""
    computation_hash: str = ""
    layer3_validated: bool = False
    # Healing metadata — set only on the self-healing fallback path.
    is_healed: bool = False
    healing_tier: int = 0
    healing_error: str | None = None
    safety_tier: str = ""
    requires_fpe_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatteryCapacityResult:
    standby_load_a: float = 0.0
    alarm_load_a: float = 0.0
    standby_hours: float = 24.0
    alarm_minutes: float = 5.0
    ah_standby: float = 0.0
    ah_alarm: float = 0.0
    ah_raw: float = 0.0
    discharge_efficiency: float = 0.80
    safety_factor: float = 1.25
    required_ah: float = 0.0
    nfpa_section: str = ""
    formula: str = ""
    computation_hash: str = ""
    layer3_validated: bool = False
    # Healing metadata — set only on the self-healing fallback path.
    is_healed: bool = False
    healing_tier: int = 0
    healing_error: str | None = None
    safety_tier: str = ""
    requires_fpe_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VoltageDropResult:
    current_a: float = 0.0
    length_m: float = 0.0
    awg_gauge: str = ""
    supply_voltage_v: float = 24.0
    r_ohm_per_m: float = 0.0
    voltage_drop_v: float = 0.0
    drop_pct: float = 0.0
    max_drop_pct: float = 10.0
    max_length_m: float = 0.0
    is_compliant: bool = True
    nec_section: str = ""
    formula: str = ""
    computation_hash: str = ""
    layer3_validated: bool = False
    # Healing metadata — set only on the self-healing fallback path.
    is_healed: bool = False
    healing_tier: int = 0
    healing_error: str | None = None
    safety_tier: str = ""
    requires_fpe_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
