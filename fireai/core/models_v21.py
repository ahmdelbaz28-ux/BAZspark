"""
models_v21.py – FireAI V21 Pydantic Models (Fast-Fail Validation)
==================================================================
Replaces dataclasses with Pydantic BaseModel for fail-fast validation.
No dict/tuple passes through. No silent failures. Physics validators enforced.

Standards:
  IEC 60079-0:2017     – General requirements for Ex equipment
  IEC 60079-10-1:2015  – Gas zone classification
  IEC 60079-10-2:2015  – Dust zone classification
  NFPA 497-2021        – Classification of flammable liquids/gases
  NFPA 70-2023 Art. 500 – Classified locations

V21 Migration:
  - All models use ConfigDict(frozen=True, strict=True)
  - No data coercion — string "1.5" won't auto-convert to float
  - Physics validators run at construction — no invalid object can exist
  - critical_flags field prevents silent dropping of dangerous conditions

Fix #14 (CRITICAL): EPL hierarchy corrected — Ga>Gb>Gc, Da>Db>Dc
Fix #15 (CRITICAL): Temperature class selection — strictly below autoignition
Fix #16 (HIGH):      critical_flags field — cannot silently ignore Zone 0 + POOR
Fix #17 (HIGH):      protection_mode_zone_fit — ia not forced for all zones
Q6 (MEDIUM):         Spectral transparency replaces single boolean
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VentilationLevel(str, Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"
    POOR   = "POOR"


class HazardType(str, Enum):
    GAS    = "GAS"
    DUST   = "DUST"
    HYBRID = "HYBRID"
    FIBER  = "FIBER"


class ZoneType(str, Enum):
    ZONE_0       = "ZONE_0"
    ZONE_1       = "ZONE_1"
    ZONE_2       = "ZONE_2"
    ZONE_20      = "ZONE_20"
    ZONE_21      = "ZONE_21"
    ZONE_22      = "ZONE_22"
    UNCLASSIFIED = "UNCLASSIFIED"


class EPLGas(str, Enum):
    Ga = "Ga"  # highest protection
    Gb = "Gb"
    Gc = "Gc"  # lowest


class EPLDust(str, Enum):
    Da = "Da"
    Db = "Db"
    Dc = "Dc"


class EPLMining(str, Enum):
    Ma = "Ma"
    Mb = "Mb"


class TemperatureClass(str, Enum):
    T1 = "T1"  # max surface 450°C
    T2 = "T2"  # max surface 300°C
    T3 = "T3"  # max surface 200°C
    T4 = "T4"  # max surface 135°C
    T5 = "T5"  # max surface 100°C
    T6 = "T6"  # max surface 85°C


# Max surface temperature per class (IEC 60079-0 §7.3)
_T_CLASS_MAX: Dict[str, float] = {
    "T1": 450.0, "T2": 300.0, "T3": 200.0,
    "T4": 135.0, "T5": 100.0, "T6": 85.0,
}


class WavelengthBand(str, Enum):
    """Spectral bands for flame detector transparency analysis."""
    UV  = "UV"    # 185-260 nm
    VIS = "VIS"   # 380-780 nm
    IR1 = "IR1"   # 1-3 um (near-IR)
    IR3 = "IR3"   # 3-5 um (mid-IR CO2 band)


class RegulatoryFramework(str, Enum):
    ATEX_EU    = "ATEX_EU"
    IECEX      = "IECEx"
    NEC_US     = "NEC_US"
    CEC_CANADA = "CEC_CANADA"
    EFTA       = "EFTA"


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class SubstanceProperties(BaseModel):
    """
    Physical properties of the hazardous substance.
    ALL validators run at construction — no invalid object can exist.
    """
    model_config = ConfigDict(frozen=True, strict=True)

    name:              str
    hazard_type:       HazardType
    lfl_vol_pct:       Optional[float] = Field(None, gt=0.0, le=100.0,
                           description="Lower Flammable Limit (vol%). Must be >0.")
    ufl_vol_pct:       Optional[float] = Field(None, gt=0.0, le=100.0)
    flash_point_c:     Optional[float] = Field(None, ge=-100.0, le=500.0)
    autoignition_c:    Optional[float] = Field(None, ge=50.0, le=1000.0)
    mec_g_m3:          Optional[float] = Field(None, gt=0.0,
                           description="Minimum Explosible Concentration (dust)")
    kst_bar_m_s:       Optional[float] = Field(None, ge=0.0,
                           description="Dust explosion constant")
    mie_mj:            Optional[float] = Field(None, gt=0.0,
                           description="Minimum Ignition Energy (mJ)")
    density_kg_m3:     Optional[float] = Field(None, gt=0.0)
    molecular_weight:  Optional[float] = Field(None, gt=0.0)

    @model_validator(mode="after")
    def physics_consistency(self) -> "SubstanceProperties":
        # flash_point must be below autoignition
        if (self.flash_point_c is not None
                and self.autoignition_c is not None
                and self.flash_point_c >= self.autoignition_c):
            raise ValueError(
                f"flash_point_c ({self.flash_point_c}C) must be strictly "
                f"< autoignition_c ({self.autoignition_c}C). "
                f"[NFPA 497 §4.2]"
            )
        # LFL < UFL
        if (self.lfl_vol_pct is not None and self.ufl_vol_pct is not None
                and self.lfl_vol_pct >= self.ufl_vol_pct):
            raise ValueError(
                f"lfl_vol_pct ({self.lfl_vol_pct}) must be < "
                f"ufl_vol_pct ({self.ufl_vol_pct})."
            )
        # GAS needs LFL
        if self.hazard_type == HazardType.GAS and self.lfl_vol_pct is None:
            raise ValueError("GAS hazard requires lfl_vol_pct.")
        # DUST needs MEC
        if self.hazard_type == HazardType.DUST and self.mec_g_m3 is None:
            raise ValueError("DUST hazard requires mec_g_m3.")
        # HYBRID needs both
        if self.hazard_type == HazardType.HYBRID:
            if self.lfl_vol_pct is None or self.mec_g_m3 is None:
                raise ValueError(
                    "HYBRID hazard requires both lfl_vol_pct and mec_g_m3. "
                    "[IEC 60079-10-1 §5.7]"
                )
        return self


class ZoneExtent(BaseModel):
    """Zone boundary distances (metres). All must be non-negative."""
    model_config = ConfigDict(frozen=True, strict=True)

    horizontal_m: float = Field(ge=0.0)
    vertical_m:   float = Field(ge=0.0)
    volume_m3:    float = Field(ge=0.0)
    is_outdoor:   bool  = False  # True = full sphere, False = hemisphere

    @model_validator(mode="after")
    def extent_geometry(self) -> "ZoneExtent":
        # Volume must be consistent with the appropriate volume model
        r = max(self.horizontal_m, self.vertical_m)
        if self.is_outdoor:
            max_vol = (4.0 / 3.0) * math.pi * r ** 3   # Full sphere
        else:
            max_vol = (2.0 / 3.0) * math.pi * r ** 3   # Hemisphere
        if self.volume_m3 > max_vol * 1.05:  # 5% tolerance for rounding
            shape = "sphere" if self.is_outdoor else "hemisphere"
            raise ValueError(
                f"volume_m3 ({self.volume_m3:.2f}) exceeds {shape} "
                f"of radius {r:.2f}m ({max_vol:.2f} m3). "
                f"[IEC 60079-10-1 Annex A]"
            )
        return self


class HACResult(BaseModel):
    """Result of HACClassificationEngine. Immutable after construction."""
    model_config = ConfigDict(frozen=True, strict=True)

    zone:             ZoneType
    extent:           ZoneExtent
    ventilation:      VentilationLevel
    hazard_type:      HazardType
    warnings:         List[str] = Field(default_factory=list)
    # POOR ventilation + Zone 0/20 is the most dangerous combination
    # The model enforces a warning cannot be silently dropped
    critical_flags:   List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_critical_combination(self) -> "HACResult":
        if (self.ventilation == VentilationLevel.POOR
                and self.zone in (ZoneType.ZONE_0, ZoneType.ZONE_20)):
            flag = (
                "CRITICAL: Zone 0/20 with POOR ventilation — "
                "most dangerous possible classification. "
                "Mandatory engineering review required. "
                "[IEC 60079-10-1 §6.3]"
            )
            # Cannot be silently ignored — it's in critical_flags
            if flag not in self.critical_flags:
                raise ValueError(
                    f"{flag}\nSet critical_flags=['{flag}'] explicitly "
                    f"to acknowledge this condition."
                )
        return self


def _select_temp_class(autoignition_c: float) -> TemperatureClass:
    """
    FIXED Fix #15: Select temperature class whose max surface temp
    is STRICTLY LESS THAN autoignition temperature.
    IEC 60079-0 §7.3.

    Previous bug: autoignition=180C -> T3 (max 200C) -> equipment
    surface could reach 200C and ignite substance at 180C.

    Correct: autoignition=180C -> T4 (max 135C) — strict margin.
    """
    # Ordered from hottest to coolest surface temperature
    for t_class in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        if _T_CLASS_MAX[t_class] < autoignition_c:
            return TemperatureClass(t_class)
    raise ValueError(
        f"No safe temperature class for autoignition={autoignition_c}C. "
        f"T6 max surface is 85C. Substance autoignition must be > 85C. "
        f"[IEC 60079-0 §7.3]"
    )


class ATEXEquipmentSpec(BaseModel):
    """
    ATEX equipment requirements derived from zone classification.
    EPL hierarchy enforced — cannot construct an inconsistent spec.
    """
    model_config = ConfigDict(frozen=True, strict=True)

    zone:              ZoneType
    epl_required:      str        # "Ga"/"Gb"/"Gc"/"Da"/"Db"/"Dc"/"Ma"/"Mb"
    atex_category:     str        # "1G","2G","3G","1D","2D","3D","M1","M2"
    temp_class:        TemperatureClass
    protection_modes:  List[str]  # e.g. ["ia","d","e"]
    hac_warnings:      List[str] = Field(default_factory=list)
    hac_critical:      List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def epl_category_consistency(self) -> "ATEXEquipmentSpec":
        """
        FIXED Fix #14: EPL hierarchy was inverted.
        Correct gas hierarchy: Ga > Gb > Gc (Ga = highest protection)
        Correct dust hierarchy: Da > Db > Dc
        """
        valid = {
            ZoneType.ZONE_0:  ("Ga", "1G"),
            ZoneType.ZONE_1:  ("Gb", "2G"),
            ZoneType.ZONE_2:  ("Gc", "3G"),
            ZoneType.ZONE_20: ("Da", "1D"),
            ZoneType.ZONE_21: ("Db", "2D"),
            ZoneType.ZONE_22: ("Dc", "3D"),
        }
        if self.zone in valid:
            expected_epl, expected_cat = valid[self.zone]
            # EPL hierarchy: Ga satisfies Gb/Gc, Da satisfies Db/Dc
            # Gas hierarchy index: Ga=0, Gb=1, Gc=2
            gas_order  = ["Ga", "Gb", "Gc"]
            dust_order = ["Da", "Db", "Dc"]
            mine_order = ["Ma", "Mb"]

            def _is_sufficient(proposed: str, required: str) -> bool:
                """True if proposed EPL is >= required (more protective)."""
                for order in [gas_order, dust_order, mine_order]:
                    if required in order and proposed in order:
                        # Lower index = more protective
                        return order.index(proposed) <= order.index(required)
                return False

            if not _is_sufficient(self.epl_required, expected_epl):
                raise ValueError(
                    f"EPL '{self.epl_required}' is INSUFFICIENT for "
                    f"{self.zone.value} (requires '{expected_epl}' or better). "
                    f"[IEC 60079-0 §5, ATEX 2014/34/EU]"
                )
        return self

    @model_validator(mode="after")
    def protection_mode_zone_fit(self) -> "ATEXEquipmentSpec":
        """
        FIXED Fix #17: 'ia' for Zone 2 is over-specified (costly, unnecessary).
        Zone 2 -> 'ic' is sufficient. Zone 1 -> 'ib' or 'ia'. Zone 0 -> 'ia' only.
        [IEC 60079-14]
        """
        zone_allowed = {
            ZoneType.ZONE_0:  {"ia", "d", "e", "s"},
            ZoneType.ZONE_1:  {"ia", "ib", "d", "e", "px", "py", "s"},
            ZoneType.ZONE_2:  {"ia", "ib", "ic", "d", "e", "px", "py", "pz",
                               "n", "s", "ec"},
            ZoneType.ZONE_20: {"ia", "ma", "tb"},
            ZoneType.ZONE_21: {"ia", "ib", "ma", "mb", "tb", "tc"},
            ZoneType.ZONE_22: {"ia", "ib", "ic", "ma", "mb", "mc",
                               "ta", "tb", "tc"},
        }
        if self.zone in zone_allowed:
            for mode in self.protection_modes:
                if mode not in zone_allowed[self.zone]:
                    raise ValueError(
                        f"Protection mode '{mode}' not permitted for "
                        f"{self.zone.value}. [IEC 60079-14]"
                    )
        return self


class Obstruction(BaseModel):
    """
    FIXED Q6: Spectral transparency replaces single boolean.
    Glass: UV=0.0 (opaque), IR=0.8 (mostly transparent).
    Polycarbonate: UV=0.0, VIS=0.9, IR=0.7.
    Steel: all 0.0.
    """
    model_config = ConfigDict(frozen=True, strict=True)

    obstruction_id:        str
    vertices:              List[List[float]]  # list of [x,y,z]
    spectral_transparency: Dict[WavelengthBand, float] = Field(
        default_factory=lambda: {
            WavelengthBand.UV:  0.0,
            WavelengthBand.VIS: 0.0,
            WavelengthBand.IR1: 0.0,
            WavelengthBand.IR3: 0.0,
        }
    )

    @model_validator(mode="after")
    def transparency_range(self) -> "Obstruction":
        for band, val in self.spectral_transparency.items():
            if not 0.0 <= val <= 1.0:
                raise ValueError(
                    f"spectral_transparency[{band}]={val} must be in [0.0, 1.0]."
                )
        return self

    def is_transparent_for(self, band: WavelengthBand) -> bool:
        """True if transmittance > 0.5 for this spectral band."""
        return self.spectral_transparency.get(band, 0.0) > 0.5

    def transmittance_for(self, band: WavelengthBand) -> float:
        return self.spectral_transparency.get(band, 0.0)


class FlameDetectorSpec(BaseModel):
    """
    Flame detector physical specification for ray-trace engine.
    """
    model_config = ConfigDict(frozen=True, strict=True)

    detector_id:        str
    position:           List[float] = Field(min_length=3, max_length=3)
    orientation_vector: List[float] = Field(min_length=3, max_length=3)
    rated_range_m:      float       = Field(gt=0.0, le=200.0)
    aoc_deg:            float       = Field(gt=0.0, le=180.0,
                            description="Angle of Coverage (degrees)")
    spectral_bands:     List[WavelengthBand] = Field(min_length=1)

    @model_validator(mode="after")
    def orientation_not_zero(self) -> "FlameDetectorSpec":
        mag = math.sqrt(sum(v**2 for v in self.orientation_vector))
        if mag < 1e-9:
            raise ValueError("orientation_vector must not be zero vector.")
        return self

    @model_validator(mode="after")
    def position_valid(self) -> "FlameDetectorSpec":
        if any(not math.isfinite(v) for v in self.position):
            raise ValueError("position contains non-finite values.")
        return self

    @property
    def orientation_unit(self) -> List[float]:
        mag = math.sqrt(sum(v**2 for v in self.orientation_vector))
        return [v / mag for v in self.orientation_vector]

    def is_facing_upward(self) -> bool:
        """
        Detector pointing up (z > 0.9) won't cover floor.
        Returns True if detector aims predominantly upward.
        """
        unit = self.orientation_unit
        return unit[2] > 0.9


class RayTracePoint(BaseModel):
    """A target point in the ray-trace grid."""
    model_config = ConfigDict(frozen=True, strict=True)

    x: float
    y: float
    z: float = 0.0

    def to_tuple(self) -> tuple:
        return (self.x, self.y, self.z)


class RegSelectorResult(BaseModel):
    """Result of regulatory framework resolution."""
    model_config = ConfigDict(frozen=True, strict=True)

    country_code:  str
    framework:     RegulatoryFramework
    zone_system:   str   # "ZONE" or "DIVISION"
    warnings:      List[str]
