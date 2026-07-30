"""
fireai/core/results.py — Strongly typed computation result types.

Provides dataclass-based result types with dict-like backward compatibility
for all QOMN kernel computation functions. Each result type supports both
attribute access (result.field) and dict-style access (result["field"]),
enabling incremental migration from raw dicts to typed results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Optional


class _DictCompatMixin:
    """Mixin providing dict-like access for dataclass instances."""

    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def __getitem__(self, key: str) -> Any:
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return self._extra[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.__dataclass_fields__:
            if hasattr(self.__dataclass_fields__[key], "frozen") and self.__dataclass_fields__[key].frozen:
                raise TypeError(f"Cannot set frozen field '{key}'")
            object.__setattr__(self, key, value)
        else:
            self._extra[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.__dataclass_fields__ or key in self._extra

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, AttributeError):
            return default

    def keys(self) -> Iterator[str]:
        yield from self.__dataclass_fields__
        yield from self._extra

    def to_dict(self) -> dict[str, Any]:
        base = asdict(self)
        base.pop("_extra", None)
        base.update(self._extra)
        return base


@dataclass
class SmokeSpacingResult(_DictCompatMixin):
    listed_spacing_m: float = 0.0
    coverage_radius_m: float = 0.0
    wall_min_m: float = 0.0
    wall_max_m: float = 0.0
    corner_min_m: float = 0.0
    nfpa_section: str = ""
    table_row_used: str = ""
    formula: str = ""
    computation_hash: str = ""
    audit_notice: Optional[str] = None
    layer3_validated: bool = False
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class HeatSpacingResult(_DictCompatMixin):
    spacing_m: float = 0.0
    coverage_radius_m: float = 0.0
    max_spacing_m: float = 0.0
    is_within_max: bool = True
    nfpa_section: str = ""
    formula: str = ""
    computation_hash: str = ""
    layer3_validated: bool = False
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class BatteryCapacityResult(_DictCompatMixin):
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
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class VoltageDropResult(_DictCompatMixin):
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
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)
