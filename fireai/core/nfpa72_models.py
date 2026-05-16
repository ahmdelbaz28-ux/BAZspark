"""NFPA 72-2022 data models with safe constructors and HVACDuct."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import ClassVar, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_NFPA_HEIGHT_MIN_M: float = 3.0
_NFPA_HEIGHT_MAX_M: float = 15.24

@unique
class DetectorType(str, Enum):
    SMOKE_PHOTOELECTRIC  = "SMOKE_PHOTOELECTRIC"
    SMOKE_IONIZATION     = "SMOKE_IONIZATION"
    SMOKE_MULTI_CRITERIA = "SMOKE_MULTI_CRITERIA"
    HEAT_FIXED           = "HEAT_FIXED"
    HEAT_RATE_OF_RISE    = "HEAT_RATE_OF_RISE"
    HEAT_COMBINATION     = "HEAT_COMBINATION"

@unique
class CeilingType(str, Enum):
    SMOOTH   = "SMOOTH"
    BEAMED   = "BEAMED"
    SLOPED   = "SLOPED"
    CORRIDOR = "CORRIDOR"

_SMOOTH_RATED_SPACING_M: Dict[DetectorType, float] = {
    DetectorType.SMOKE_PHOTOELECTRIC: 9.14, DetectorType.SMOKE_IONIZATION: 9.14,
    DetectorType.SMOKE_MULTI_CRITERIA: 9.14,
    DetectorType.HEAT_FIXED: 6.10, DetectorType.HEAT_RATE_OF_RISE: 6.10,
    DetectorType.HEAT_COMBINATION: 6.10,
}

MIN_WALL_DISTANCE_M: float = 0.10

def _height_correction_factor(height_m: float, detector_type: DetectorType) -> float:
    is_heat = detector_type in (DetectorType.HEAT_FIXED, DetectorType.HEAT_RATE_OF_RISE, DetectorType.HEAT_COMBINATION)
    if is_heat:
        table = ((3.05,1.0),(3.66,0.91),(4.57,0.84),(6.10,0.77),(7.62,0.71),(9.14,0.64),(10.67,0.55),(12.19,0.45),(15.24,0.33))
    else:
        table = ((3.05,1.0),(4.57,0.95),(6.10,0.90),(7.62,0.85),(9.14,0.80),(12.19,0.75),(15.24,0.70))
    if height_m <= table[0][0]: return table[0][1]
    if height_m >= table[-1][0]: return table[-1][1]
    for i in range(len(table)-1):
        h0,f0=table[i]; h1,f1=table[i+1]
        if h0 <= height_m <= h1:
            t=(height_m-h0)/(h1-h0)
            return f0+t*(f1-f0)
    return 1.0

@dataclass
class CeilingSpec:
    NFPA_HEIGHT_MIN_M: ClassVar[float] = _NFPA_HEIGHT_MIN_M
    NFPA_HEIGHT_MAX_M: ClassVar[float] = _NFPA_HEIGHT_MAX_M
    height_at_low_point_m: float
    height_at_high_point_m: float = field(default=0.0)
    ceiling_type: CeilingType = CeilingType.SMOOTH
    beam_depth_m: float = 0.0
    beam_spacing_m: float = 0.0
    _clamped: bool = field(default=False, init=False, repr=False)
    _original_height_m: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self):
        if self.height_at_high_point_m == 0.0:
            self.height_at_high_point_m = self.height_at_low_point_m
        if not (_NFPA_HEIGHT_MIN_M <= self.height_at_low_point_m <= _NFPA_HEIGHT_MAX_M):
            raise ValueError("Height out of NFPA range — use create_safe().")
        if self.height_at_low_point_m > self.height_at_high_point_m:
            raise ValueError("low point must be ≤ high point.")

    @classmethod
    def create_safe(cls, height_at_low_point_m: float, height_at_high_point_m: Optional[float] = None,
                    ceiling_type: CeilingType = CeilingType.SMOOTH, beam_depth_m: float = 0.0,
                    beam_spacing_m: float = 0.0) -> "CeilingSpec":
        original = height_at_low_point_m
        clamped = False
        if height_at_low_point_m < _NFPA_HEIGHT_MIN_M:
            height_at_low_point_m = _NFPA_HEIGHT_MIN_M; clamped = True
            logger.warning("Ceiling height clamped to min.")
        elif height_at_low_point_m > _NFPA_HEIGHT_MAX_M:
            height_at_low_point_m = _NFPA_HEIGHT_MAX_M; clamped = True
            logger.warning("Ceiling height clamped to max.")
        if height_at_high_point_m is None:
            height_at_high_point_m = height_at_low_point_m
        high = max(height_at_low_point_m, height_at_high_point_m)
        spec = cls(height_at_low_point_m=height_at_low_point_m, height_at_high_point_m=high,
                   ceiling_type=ceiling_type, beam_depth_m=beam_depth_m, beam_spacing_m=beam_spacing_m)
        spec._clamped = clamped
        spec._original_height_m = original
        return spec

    @property
    def was_clamped(self) -> bool: return self._clamped

    @property
    def original_height_m(self) -> float:
        return self._original_height_m if self._clamped else self.height_at_low_point_m

def get_smoke_detector_radius_safe(ceiling_height_m: float) -> float:
    spec = CeilingSpec.create_safe(height_at_low_point_m=ceiling_height_m)
    rated = _SMOOTH_RATED_SPACING_M[DetectorType.SMOKE_PHOTOELECTRIC]
    factor = _height_correction_factor(spec.height_at_low_point_m, DetectorType.SMOKE_PHOTOELECTRIC)
    return max(0.1, (rated * factor) / 2.0)

def get_heat_detector_radius_safe(ceiling_height_m: float, detector_type: DetectorType = DetectorType.HEAT_FIXED) -> float:
    spec = CeilingSpec.create_safe(height_at_low_point_m=ceiling_height_m)
    rated = _SMOOTH_RATED_SPACING_M.get(detector_type, 6.10)
    factor = _height_correction_factor(spec.height_at_low_point_m, detector_type)
    return max(0.1, (rated * factor) / 2.0)

def get_detector_radius_safe(ceiling_height_m: float, detector_type: DetectorType) -> float:
    if detector_type in (DetectorType.HEAT_FIXED, DetectorType.HEAT_RATE_OF_RISE, DetectorType.HEAT_COMBINATION):
        return get_heat_detector_radius_safe(ceiling_height_m, detector_type)
    return get_smoke_detector_radius_safe(ceiling_height_m)

@dataclass
class HVACDuct:
    duct_id:     str
    centerline:  list  # List[Tuple[float, float]]
    width_m:     float = 0.3
    height_m:    float = 0.3
    airflow_m3s: float = 0.0

@dataclass
class RoomSpec:
    room_id:        str
    name:           str
    polygon_coords: list
    ceiling:        CeilingSpec
    room_type:      str = "office"
    hvac_ducts:     List[HVACDuct] = field(default_factory=list)
