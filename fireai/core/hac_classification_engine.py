"""
hac_classification_engine.py – Hazardous Area Classification Engine
=====================================================================
Classifies hazardous areas from physical parameters (physics-first,
no manual human input for zone assignment).

Standards:
  IEC 60079-10-1:2015  – Explosive gas atmospheres (Zone 0/1/2)
  IEC 60079-10-2:2015  – Explosive dust atmospheres (Zone 20/21/22)
  NFPA 497-2021        – Classification of flammable liquids/gases (NEC)
  NFPA 499-2021        – Classification of combustible dusts (NEC)
  API RP 505-2014      – Petroleum facilities classification
  EN 60079-10-1        – EU/ATEX equivalent of IEC 60079-10-1

Key principle: Zones are derived from:
  1. Substance properties (flash point, LFL, LEL, MIE, Kst, Pmax)
  2. Release grade (continuous, primary, secondary)
  3. Ventilation adequacy (degree + availability)
  4. Source of release geometry

NOT from subjective human judgment.

V20.2 Fix #6 (CRITICAL): _apply_ventilation_degree() only handled gas zones
  (0/1/2) in its upgrade/downgrade maps. Dust zones (20/21/22) were silently
  ignored — ventilation had NO effect on dust classification. IEC 60079-10-2
  §6 explicitly allows zone reduction with adequate ventilation for dust.

V20.2 Fix #7 (CRITICAL): _compute_extent() used arbitrary max_rate×10 multiplier
  in log1p formula, had overly small base radii, and used full sphere volume
  for indoor calculations. Fixed to use IEC 60079-10-1 Annex A conservative
  defaults, hemisphere for indoor, and indoor/outdoor distinction.

V20.2 Fix #8 (CRITICAL): DUST_HYBRID material type was defined but treated
  identically to DUST_COMB. Hybrid mixtures (gas + dust) can ignite at
  concentrations BELOW the LFL of gas AND below the MEC of dust per
  IEC 60079-10-1 §5.7. Must classify for BOTH gas and dust and take
  the more stringent result.

V20.2 Fix #9 (HIGH): flash_point_c was collected but never used in
  classification logic. NFPA 497 §4.2: liquid with flash point > ambient+20°C
  does not produce flammable atmosphere unless heated.

V20.2 Fix #10 (HIGH): MIE and Kst were collected but never used. MIE < 3 mJ
  means dust ignitable by static discharge (IEC 60079-10-2 §5.2). Kst > 200
  means St-2/3 explosion severity requiring larger zone extent.

V20.2 Fix #11 (HIGH): Zone 0/20 with POOR ventilation availability was silently
  accepted without warning. This is the most dangerous possible combination —
  continuously present hazard with unreliable ventilation. Added explicit warning.

V20.2 Fix #12 (MEDIUM): temperature_class not validated against autoignition_c.
  IEC 60079-0 §7.3: equipment max surface temp must be < autoignition temp.
  T3 (200°C max) with autoignition 180°C = equipment could ignite substance.

V20.2 Fix #13 (MEDIUM): _compute_extent() used full sphere volume (4/3πr³)
  for indoor zones. Hazardous zones from a source on floor/wall are hemispheres
  (2/3πr³). Full sphere overestimates volume by 2x.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from fireai.core.international_reg_selector import ATEXZone, HazardClass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReleaseGrade(str, Enum):
    """
    Grade of release per IEC 60079-10-1 §5.3.
    Determines base zone classification.
    """
    CONTINUOUS  = "CONTINUOUS"   # Present > 1000 h/year -> Zone 0/20
    PRIMARY     = "PRIMARY"      # 10-1000 h/year -> Zone 1/21
    SECONDARY   = "SECONDARY"    # < 10 h/year -> Zone 2/22


class VentilationDegree(str, Enum):
    """
    Ventilation degree per IEC 60079-10-1 §6.
    """
    HIGH    = "HIGH"     # Dilutes to < LFL rapidly, negligible extent
    MEDIUM  = "MEDIUM"   # Controls zone extent, not eliminates
    LOW     = "LOW"      # Cannot prevent zone formation


class VentilationAvailability(str, Enum):
    """
    Ventilation availability (continuity) per IEC 60079-10-1 §6.3.
    """
    GOOD    = "GOOD"     # Present virtually all the time
    FAIR    = "FAIR"     # Expected to be present during normal ops
    POOR    = "POOR"     # Not present reliably


class HazardousMaterial(str, Enum):
    GAS         = "GAS"         # Flammable gas
    VAPOR       = "VAPOR"       # Flammable liquid vapor
    DUST_COMB   = "DUST_COMB"   # Combustible dust (organic, metal)
    DUST_HYBRID = "DUST_HYBRID" # Hybrid mixture (gas + dust)
    MIST        = "MIST"        # Flammable mist


class SoRGeometry(str, Enum):
    """Source of Release geometry."""
    POINT    = "POINT"     # Single point (flange, fitting)
    LINE     = "LINE"      # Pipe, duct
    AREA     = "AREA"      # Tank surface, pool
    VOLUME   = "VOLUME"    # Room, enclosure


# ---------------------------------------------------------------------------
# V20.2 Fix #12: IEC 60079-0 §7.3 Temperature Class limits
# ---------------------------------------------------------------------------

T_CLASS_MAX_TEMP: Dict[str, float] = {
    "T1": 450.0,
    "T2": 300.0,
    "T2A": 280.0,
    "T2B": 260.0,
    "T2C": 230.0,
    "T2D": 215.0,
    "T3": 200.0,
    "T3A": 180.0,
    "T3B": 165.0,
    "T3C": 160.0,
    "T4": 135.0,
    "T4A": 120.0,
    "T5": 100.0,
    "T6": 85.0,
}

# V20.2 Fix #8: Hazard ordering for hybrid mixture — lower zone number = more hazardous
_ZONE_HAZARD_ORDER: Dict[ATEXZone, int] = {
    ATEXZone.ZONE_0:  0,   # Most hazardous (continuous gas)
    ATEXZone.ZONE_20: 1,   # Continuous dust
    ATEXZone.ZONE_1:  2,   # Primary gas
    ATEXZone.ZONE_21: 3,   # Primary dust
    ATEXZone.ZONE_2:  4,   # Secondary gas
    ATEXZone.ZONE_22: 5,   # Secondary dust
    ATEXZone.SAFE:    99,  # Non-hazardous
}

# V20.2 Fix #7: Base radii per IEC 60079-10-1 Annex A (conservative defaults)
# These are MINIMUM expected extents for typical industrial sources.
_BASE_RADII_M: Dict[ATEXZone, float] = {
    ATEXZone.ZONE_0:  3.0,   # Continuous release — significant extent
    ATEXZone.ZONE_1:  6.0,   # Primary release
    ATEXZone.ZONE_2:  10.0,  # Secondary release — largest extent
    ATEXZone.ZONE_20: 1.5,   # Continuous dust
    ATEXZone.ZONE_21: 3.0,   # Primary dust
    ATEXZone.ZONE_22: 6.0,   # Secondary dust
    ATEXZone.SAFE:    0.0,   # Non-hazardous
}


# ---------------------------------------------------------------------------
# Substance data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubstanceProperties:
    """
    Physical/chemical properties of the hazardous substance.
    Required for physics-based zone classification.
    IEC 60079-10-1 Annex B.
    """
    substance_name:   str
    cas_number:       str = ""
    # Gas / Vapor properties
    lfl_vol_pct:      float = 0.0    # Lower Flammable Limit (vol%)
    ufl_vol_pct:      float = 100.0  # Upper Flammable Limit (vol%)
    flash_point_c:    Optional[float] = None  # °C
    autoignition_c:   Optional[float] = None  # °C
    vapor_density:    float = 1.0    # relative to air
    # Dust properties (IEC 60079-10-2)
    mec_g_m3:         Optional[float] = None  # Min Explosible Conc. (g/m³)
    mie_mj:           Optional[float] = None  # Min Ignition Energy (mJ)
    kst_bar_m_s:      Optional[float] = None  # Kst value (bar*m/s)
    pmax_bar:         Optional[float] = None  # Max explosion pressure
    dust_group:       str = ""               # "IIIA", "IIIB", "IIIC"
    # NEC / ATEX group
    nec_group:        str = ""       # "A", "B", "C", "D", "E", "F", "G"
    temperature_class: str = "T3"   # T1-T6 (IEC 60079-0 §7.3)
    material_type:    HazardousMaterial = HazardousMaterial.GAS


@dataclass(frozen=True)
class ReleaseSource:
    """
    Describes a single source of hazardous material release.
    IEC 60079-10-1 §5.
    """
    source_id:    str
    grade:        ReleaseGrade
    geometry:     SoRGeometry
    release_rate_kg_s: float = 0.0   # kg/s at worst case
    # Geometry dimensions
    diameter_m:   float = 0.0
    length_m:     float = 0.0
    area_m2:      float = 0.0


# ---------------------------------------------------------------------------
# Output data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ZoneExtent:
    """
    Computed extent of a hazardous zone around a source.
    IEC 60079-10-1 §7.
    """
    zone:              ATEXZone
    radius_m:          float     # Radial extent from source
    area_m2:           float     # Projected 2-D area
    volume_m3:         float     # 3-D extent
    is_negligible:     bool      # Can zone be reduced to negligible?


@dataclass(frozen=True)
class HACResult:
    """
    Complete Hazardous Area Classification result for a space/source.
    Physics-derived — no manual zone assignment.
    """
    space_id:          str
    substance:         SubstanceProperties
    release_sources:   Tuple[ReleaseSource, ...]
    ventilation_degree: VentilationDegree
    ventilation_avail:  VentilationAvailability
    classified_zone:   ATEXZone
    zone_extent:       ZoneExtent
    hazard_class:      HazardClass
    nec_division:      Optional[str]    = None  # "DIVISION_1" or "DIVISION_2"
    temperature_class: str              = "T3"
    confidence_pct:    float            = 100.0
    assumptions:       Tuple[str, ...]  = ()
    warnings:          Tuple[str, ...]  = ()
    nfpa_reference:    str              = ""
    iec_reference:     str              = ""


# ---------------------------------------------------------------------------
# Classification Engine
# ---------------------------------------------------------------------------

class HACClassificationEngine:
    """
    Classifies hazardous areas from physical parameters.

    Physics-first: zone is derived from substance properties,
    release grade, and ventilation — not from user opinion.

    IEC 60079-10-1:2015 (Gas)  / IEC 60079-10-2:2015 (Dust)
    NFPA 497-2021 / NFPA 499-2021
    """

    def classify(
        self,
        space_id:            str,
        substance:           SubstanceProperties,
        release_sources:     List[ReleaseSource],
        ventilation_degree:  VentilationDegree,
        ventilation_avail:   VentilationAvailability,
        room_volume_m3:      float = 100.0,
        is_indoor:           bool = True,           # V20.2 Fix #7
        ambient_temp_c:      float = 25.0,          # V20.2 Fix #9
    ) -> HACResult:
        """
        Classify the hazardous zone for a space based on physics.

        Algorithm (IEC 60079-10-1 §7):
          1. Determine base zone from release grade
          2. Modify based on ventilation degree
          3. Modify based on ventilation availability
          4. Compute zone extent
          5. Check for zone reduction to negligible
          6. Validate substance properties (V20.2 Fix #9, #10, #12)

        Args:
            space_id:           Unique identifier for the space.
            substance:          Physical/chemical substance properties.
            release_sources:    List of release sources in the space.
            ventilation_degree: Ventilation degree (HIGH/MEDIUM/LOW).
            ventilation_avail:  Ventilation availability (GOOD/FAIR/POOR).
            room_volume_m3:     Room volume in cubic meters.
            is_indoor:          True = indoor (hemisphere), False = outdoor.
            ambient_temp_c:     Ambient temperature in °C for flash point check.

        Returns:
            HACResult with physics-derived zone classification.
        """
        if not release_sources:
            return self._safe_result(space_id, substance)

        warnings: List[str] = []
        assumptions: List[str] = []

        # Use worst-case (highest grade) release source
        worst_grade = self._worst_grade(release_sources)

        # Step 1: Base zone from release grade
        base_zone = self._grade_to_base_zone(worst_grade, substance)

        # V20.2 Fix #8: Hybrid mixture — classify for BOTH gas and dust,
        # take the more stringent result per IEC 60079-10-1 §5.7
        if substance.material_type == HazardousMaterial.DUST_HYBRID:
            base_zone = self._classify_hybrid(
                worst_grade, ventilation_degree, ventilation_avail)
            warnings.append(
                "Hybrid mixture (gas + dust): classified for both gas and "
                "dust, using more stringent result per IEC 60079-10-1 §5.7. "
                "Hybrid mixtures may ignite at concentrations BELOW the LFL "
                "of the gas AND below the MEC of the dust."
            )
        else:
            # Step 2: Modify by ventilation degree
            base_zone, zone_note = self._apply_ventilation_degree(
                base_zone, ventilation_degree, substance)
            if zone_note:
                assumptions.append(zone_note)

            # Step 3: Modify by ventilation availability
            base_zone = self._apply_ventilation_availability(
                base_zone, ventilation_avail, warnings)

        zone = base_zone

        # Step 4: Compute zone extent
        extent = self._compute_extent(
            zone, release_sources, ventilation_degree,
            room_volume_m3, is_indoor, substance)   # V20.2 Fix #7, #10

        # Step 5: Check for negligible zone
        if self._can_be_negligible(zone, ventilation_degree, ventilation_avail):
            extent = ZoneExtent(
                zone=zone,
                radius_m=0.0,
                area_m2=0.0,
                volume_m3=0.0,
                is_negligible=True,
            )
            assumptions.append(
                "Zone reduced to negligible extent due to HIGH ventilation "
                "with GOOD availability. IEC 60079-10-1 §6.4.2."
            )

        # Step 6: Validate substance properties
        # V20.2 Fix #9: Flash point check
        self._check_flash_point(substance, worst_grade, ambient_temp_c, warnings)

        # V20.2 Fix #10: MIE and Kst checks
        self._check_dust_properties(substance, warnings)

        # V20.2 Fix #12: Temperature class validation
        self._check_temperature_class(substance, warnings)

        # LFL sanity check
        if substance.lfl_vol_pct <= 0 and substance.material_type in (
            HazardousMaterial.GAS, HazardousMaterial.VAPOR
        ):
            warnings.append(
                f"Substance {substance.substance_name!r} has LFL <= 0%. "
                "Verify substance data before using classification result."
            )

        # Determine hazard class
        hazard_class = self._substance_to_hazard_class(substance)

        # NEC Division equivalent
        nec_div = self._zone_to_nec_division(zone)

        # NFPA / IEC reference
        nfpa_ref = (
            "NFPA 497-2021" if substance.material_type not in (
                HazardousMaterial.DUST_COMB, HazardousMaterial.DUST_HYBRID)
            else "NFPA 499-2021"
        )
        iec_ref = (
            "IEC 60079-10-1:2015"
            if substance.material_type not in (
                HazardousMaterial.DUST_COMB, HazardousMaterial.DUST_HYBRID)
            else "IEC 60079-10-2:2015"
        )

        logger.info(
            "HAC: space=%s substance=%s grade=%s vent=%s/%s -> %s (extent=%.1fm radius)",
            space_id, substance.substance_name,
            worst_grade.value, ventilation_degree.value,
            ventilation_avail.value, zone.value, extent.radius_m,
        )

        return HACResult(
            space_id=space_id,
            substance=substance,
            release_sources=tuple(release_sources),
            ventilation_degree=ventilation_degree,
            ventilation_avail=ventilation_avail,
            classified_zone=zone,
            zone_extent=extent,
            hazard_class=hazard_class,
            nec_division=nec_div,
            temperature_class=substance.temperature_class,
            confidence_pct=self._confidence(warnings, assumptions),
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
            nfpa_reference=nfpa_ref,
            iec_reference=iec_ref,
        )

    # -----------------------------------------------------------------------
    # Private classification logic
    # -----------------------------------------------------------------------

    @staticmethod
    def _worst_grade(sources: List[ReleaseSource]) -> ReleaseGrade:
        order = {
            ReleaseGrade.CONTINUOUS: 0,
            ReleaseGrade.PRIMARY:    1,
            ReleaseGrade.SECONDARY:  2,
        }
        return min(sources, key=lambda s: order[s.grade]).grade

    @staticmethod
    def _grade_to_base_zone(
        grade: ReleaseGrade,
        substance: SubstanceProperties,
    ) -> ATEXZone:
        """
        IEC 60079-10-1 Table 1 / IEC 60079-10-2 Table 1.
        Gas/Vapor: Continuous->Zone0, Primary->Zone1, Secondary->Zone2
        Dust:      Continuous->Zone20, Primary->Zone21, Secondary->Zone22
        """
        is_dust = substance.material_type in (
            HazardousMaterial.DUST_COMB, HazardousMaterial.DUST_HYBRID)
        if is_dust:
            mapping = {
                ReleaseGrade.CONTINUOUS: ATEXZone.ZONE_20,
                ReleaseGrade.PRIMARY:    ATEXZone.ZONE_21,
                ReleaseGrade.SECONDARY:  ATEXZone.ZONE_22,
            }
        else:
            mapping = {
                ReleaseGrade.CONTINUOUS: ATEXZone.ZONE_0,
                ReleaseGrade.PRIMARY:    ATEXZone.ZONE_1,
                ReleaseGrade.SECONDARY:  ATEXZone.ZONE_2,
            }
        return mapping[grade]

    # V20.2 Fix #6: Now handles dust zones (20/21/22) in addition to gas (0/1/2)
    @staticmethod
    def _apply_ventilation_degree(
        base_zone: ATEXZone,
        degree: VentilationDegree,
        substance: SubstanceProperties,
    ) -> Tuple[ATEXZone, str]:
        """
        IEC 60079-10-1 §6.2 / IEC 60079-10-2 §6 – Ventilation degree effect.
        HIGH vent can reduce zone; LOW vent can increase zone.

        V20.2 Fix #6: Now handles dust zones (20/21/22) separately from
        gas zones (0/1/2). Previously, dust zones were silently ignored
        because the gas-only lookup maps didn't contain Zone 20/21/22 keys.
        """
        note = ""

        # Gas zone upgrade (reduced hazard) with HIGH ventilation
        gas_upgrade = {
            ATEXZone.ZONE_0: ATEXZone.ZONE_1,
            ATEXZone.ZONE_1: ATEXZone.ZONE_2,
            ATEXZone.ZONE_2: ATEXZone.ZONE_2,  # cannot reduce below Zone 2
        }
        # Dust zone upgrade with HIGH ventilation
        dust_upgrade = {
            ATEXZone.ZONE_20: ATEXZone.ZONE_21,
            ATEXZone.ZONE_21: ATEXZone.ZONE_22,
            ATEXZone.ZONE_22: ATEXZone.ZONE_22,  # cannot reduce below Zone 22
        }
        # Gas zone downgrade (increased hazard) with LOW ventilation
        gas_downgrade = {
            ATEXZone.ZONE_2: ATEXZone.ZONE_1,
            ATEXZone.ZONE_1: ATEXZone.ZONE_0,
            ATEXZone.ZONE_0: ATEXZone.ZONE_0,
        }
        # Dust zone downgrade with LOW ventilation
        dust_downgrade = {
            ATEXZone.ZONE_22: ATEXZone.ZONE_21,
            ATEXZone.ZONE_21: ATEXZone.ZONE_20,
            ATEXZone.ZONE_20: ATEXZone.ZONE_20,
        }

        is_dust = base_zone in (ATEXZone.ZONE_20, ATEXZone.ZONE_21, ATEXZone.ZONE_22)

        if degree == VentilationDegree.HIGH:
            lookup = dust_upgrade if is_dust else gas_upgrade
            new_zone = lookup.get(base_zone, base_zone)
            if new_zone != base_zone:
                note = (
                    f"Zone upgraded {base_zone.value}->{new_zone.value} "
                    "due to HIGH ventilation degree. "
                    f"{'IEC 60079-10-2' if is_dust else 'IEC 60079-10-1'} §6.2."
                )
            return new_zone, note
        elif degree == VentilationDegree.LOW:
            lookup = dust_downgrade if is_dust else gas_downgrade
            new_zone = lookup.get(base_zone, base_zone)
            if new_zone != base_zone:
                note = (
                    f"Zone downgraded {base_zone.value}->{new_zone.value} "
                    "due to LOW ventilation degree. "
                    f"{'IEC 60079-10-2' if is_dust else 'IEC 60079-10-1'} §6.2."
                )
            return new_zone, note
        # MEDIUM ventilation — no change
        return base_zone, note

    # V20.2 Fix #11: Added warning for Zone 0/20 with POOR ventilation
    @staticmethod
    def _apply_ventilation_availability(
        zone: ATEXZone,
        avail: VentilationAvailability,
        warnings: List[str],
    ) -> ATEXZone:
        """
        IEC 60079-10-1 §6.3 – Ventilation availability effect.
        POOR availability may upgrade the zone (higher hazard).

        V20.2 Fix #11: Zone 0/20 with POOR ventilation is the most
        dangerous possible combination — continuously present hazard
        with unreliable ventilation. Now emits explicit warning.
        """
        if avail == VentilationAvailability.POOR:
            downgrade = {
                ATEXZone.ZONE_2:  ATEXZone.ZONE_1,
                ATEXZone.ZONE_1:  ATEXZone.ZONE_0,
                ATEXZone.ZONE_22: ATEXZone.ZONE_21,
                ATEXZone.ZONE_21: ATEXZone.ZONE_20,
            }
            new_zone = downgrade.get(zone, zone)

            # V20.2 Fix #11: Warn on Zone 0/20 + POOR ventilation
            if zone in (ATEXZone.ZONE_0, ATEXZone.ZONE_20):
                warnings.append(
                    f"SAFETY: Zone {zone.value} with POOR ventilation "
                    "availability — this is the most hazardous combination. "
                    "Continuously present hazardous substance with unreliable "
                    "ventilation. Consider installing mechanical ventilation "
                    "with monitoring per IEC 60079-10-1 §6.3."
                )
            return new_zone
        return zone

    # V20.2 Fix #7: Rewrote extent computation with IEC Annex A defaults,
    # hemisphere for indoor, no arbitrary ×10, indoor/outdoor distinction
    @staticmethod
    def _compute_extent(
        zone: ATEXZone,
        sources: List[ReleaseSource],
        ventilation: VentilationDegree,
        room_volume_m3: float,
        is_indoor: bool = True,
        substance: Optional[SubstanceProperties] = None,
    ) -> ZoneExtent:
        """
        Estimate zone extent per IEC 60079-10-1 Annex A (simplified).
        Full CFD is outside scope; this provides conservative estimate.

        V20.2 Fix #7: Rewrote with:
          - Larger base radii per IEC 60079-10-1 Annex A defaults
          - Hemisphere for indoor, full sphere for outdoor
          - Removed arbitrary ×10 multiplier on release rate
          - Added indoor/outdoor distinction (1.5x for outdoor)
          - Kst-based extent scaling for high-severity dust (Fix #10)
        """
        base_r = _BASE_RADII_M.get(zone, 3.0)

        # Scale by max release rate — V20.2: removed arbitrary ×10
        max_rate = max((s.release_rate_kg_s for s in sources), default=0.0)
        rate_factor = 1.0 + math.log1p(max_rate)  # Natural scaling, no multiplier

        # V20.2 Fix #10: Kst-based scaling for high-severity dust
        kst_factor = 1.0
        if substance is not None and substance.kst_bar_m_s is not None:
            if substance.kst_bar_m_s > 200:
                # St-2 or St-3 dust — explosion severity requires larger extent
                kst_factor = 1.0 + (substance.kst_bar_m_s - 200) / 400.0
                # Cap at 2.0 to prevent unreasonable extents
                kst_factor = min(kst_factor, 2.0)

        # Ventilation reduces extent
        vent_factor = {
            VentilationDegree.HIGH:   0.5,
            VentilationDegree.MEDIUM: 1.0,
            VentilationDegree.LOW:    1.5,   # V20.2: was 2.0, too aggressive
        }.get(ventilation, 1.0)

        # Indoor/outdoor distinction — outdoor zones are larger
        # per IEC 60079-10-1 Annex B (less confinement = wider spread)
        location_factor = 1.0 if is_indoor else 1.5

        radius = base_r * rate_factor * vent_factor * location_factor * kst_factor
        area   = math.pi * radius ** 2

        # V20.2 Fix #13: Hemisphere for indoor, full sphere for outdoor
        # Indoor: source on floor/wall -> zone is hemispherical
        if is_indoor:
            volume = (2.0 / 3.0) * math.pi * radius ** 3
        else:
            volume = (4.0 / 3.0) * math.pi * radius ** 3
        volume = min(volume, room_volume_m3)

        return ZoneExtent(
            zone=zone,
            radius_m=round(radius, 2),
            area_m2=round(area, 2),
            volume_m3=round(volume, 2),
            is_negligible=False,
        )

    @staticmethod
    def _can_be_negligible(
        zone: ATEXZone,
        degree: VentilationDegree,
        avail: VentilationAvailability,
    ) -> bool:
        """
        IEC 60079-10-1 §6.4.2 – Zone can be declared negligible if:
        HIGH ventilation degree + GOOD availability + Zone 2/22 only.
        """
        return (
            degree == VentilationDegree.HIGH
            and avail == VentilationAvailability.GOOD
            and zone in (ATEXZone.ZONE_2, ATEXZone.ZONE_22)
        )

    @staticmethod
    def _substance_to_hazard_class(sub: SubstanceProperties) -> HazardClass:
        if sub.material_type in (HazardousMaterial.DUST_COMB,
                                  HazardousMaterial.DUST_HYBRID):
            return HazardClass.DUST
        return HazardClass.GAS_VAPOR

    @staticmethod
    def _zone_to_nec_division(zone: ATEXZone) -> Optional[str]:
        mapping = {
            ATEXZone.ZONE_0:  "DIVISION_1",
            ATEXZone.ZONE_1:  "DIVISION_1",
            ATEXZone.ZONE_2:  "DIVISION_2",
            ATEXZone.ZONE_20: "DIVISION_1",
            ATEXZone.ZONE_21: "DIVISION_1",
            ATEXZone.ZONE_22: "DIVISION_2",
            ATEXZone.SAFE:    None,
        }
        return mapping.get(zone)

    @staticmethod
    def _confidence(warnings: List[str], assumptions: List[str]) -> float:
        base = 100.0
        base -= len(warnings) * 10.0
        base -= len(assumptions) * 5.0
        return max(50.0, base)

    @staticmethod
    def _safe_result(space_id: str, substance: SubstanceProperties) -> HACResult:
        return HACResult(
            space_id=space_id,
            substance=substance,
            release_sources=(),
            ventilation_degree=VentilationDegree.HIGH,
            ventilation_avail=VentilationAvailability.GOOD,
            classified_zone=ATEXZone.SAFE,
            zone_extent=ZoneExtent(
                zone=ATEXZone.SAFE,
                radius_m=0.0, area_m2=0.0, volume_m3=0.0,
                is_negligible=True,
            ),
            hazard_class=HazardClass.GAS_VAPOR,
            nec_division=None,
            confidence_pct=100.0,
            assumptions=("No release sources defined — space classified SAFE.",),
            warnings=(),
            nfpa_reference="NFPA 497-2021",
            iec_reference="IEC 60079-10-1:2015",
        )

    # -----------------------------------------------------------------------
    # V20.2 Fix #8: Hybrid mixture classification
    # -----------------------------------------------------------------------

    def _classify_hybrid(
        self,
        grade: ReleaseGrade,
        ventilation_degree: VentilationDegree,
        ventilation_avail: VentilationAvailability,
    ) -> ATEXZone:
        """
        V20.2 Fix #8: Classify hybrid mixture (gas + dust).

        Per IEC 60079-10-1 §5.7: hybrid mixtures may ignite at
        concentrations BELOW the LFL of the gas AND below the MEC
        of the dust. Must classify for BOTH gas and dust independently,
        then take the more stringent (lower zone number) result.
        """
        # Classify as gas
        gas_zone = self._grade_to_base_zone(
            grade,
            SubstanceProperties(
                substance_name="_hybrid_gas",
                material_type=HazardousMaterial.GAS,
            ),
        )
        gas_zone, _ = self._apply_ventilation_degree(
            gas_zone, ventilation_degree,
            SubstanceProperties(
                substance_name="_hybrid_gas",
                material_type=HazardousMaterial.GAS,
            ),
        )

        # Classify as dust
        dust_zone = self._grade_to_base_zone(
            grade,
            SubstanceProperties(
                substance_name="_hybrid_dust",
                material_type=HazardousMaterial.DUST_COMB,
            ),
        )
        dust_zone, _ = self._apply_ventilation_degree(
            dust_zone, ventilation_degree,
            SubstanceProperties(
                substance_name="_hybrid_dust",
                material_type=HazardousMaterial.DUST_COMB,
            ),
        )

        # Apply ventilation availability to each
        dummy_warnings: List[str] = []
        gas_zone = self._apply_ventilation_availability(
            gas_zone, ventilation_avail, dummy_warnings)
        dust_zone = self._apply_ventilation_availability(
            dust_zone, ventilation_avail, dummy_warnings)

        # Take more stringent (lower hazard order = more hazardous)
        if _ZONE_HAZARD_ORDER.get(gas_zone, 99) <= _ZONE_HAZARD_ORDER.get(dust_zone, 99):
            return gas_zone
        return dust_zone

    # -----------------------------------------------------------------------
    # V20.2 Fix #9: Flash point validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _check_flash_point(
        substance: SubstanceProperties,
        worst_grade: ReleaseGrade,
        ambient_temp_c: float,
        warnings: List[str],
    ) -> None:
        """
        V20.2 Fix #9: Validate flash point against ambient temperature.

        NFPA 497 §4.2: a liquid with flash point well above ambient
        temperature does not produce a flammable atmosphere unless
        it is heated above its flash point (e.g. process heating).
        """
        if (substance.flash_point_c is not None
                and substance.material_type in (HazardousMaterial.VAPOR, HazardousMaterial.GAS)):
            margin = substance.flash_point_c - ambient_temp_c
            if margin > 20 and worst_grade != ReleaseGrade.CONTINUOUS:
                warnings.append(
                    f"Flash point ({substance.flash_point_c:.0f}°C) exceeds "
                    f"ambient ({ambient_temp_c:.0f}°C) by {margin:.0f}°C. "
                    "Zone may not apply unless liquid is heated above flash "
                    "point. NFPA 497 §4.2."
                )

    # -----------------------------------------------------------------------
    # V20.2 Fix #10: MIE and Kst validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _check_dust_properties(
        substance: SubstanceProperties,
        warnings: List[str],
    ) -> None:
        """
        V20.2 Fix #10: Validate MIE and Kst values.

        IEC 60079-10-2 §5.2: MIE < 3 mJ means dust is ignitable by
        static discharge — special precautions required.
        Kst > 200 bar·m/s means St-2 or St-3 explosion severity.
        """
        if substance.material_type not in (
            HazardousMaterial.DUST_COMB, HazardousMaterial.DUST_HYBRID
        ):
            return

        # MIE check
        if substance.mie_mj is not None and substance.mie_mj < 3.0:
            warnings.append(
                f"MIE = {substance.mie_mj:.1f} mJ < 3 mJ. Dust ignitable "
                "by static discharge. Special precautions required per "
                "IEC 60079-10-2 §5.2 (grounding, bonding, conductive "
                "equipment)."
            )

        # Kst check
        if substance.kst_bar_m_s is not None:
            if substance.kst_bar_m_s > 200:
                st_class = "St-2" if substance.kst_bar_m_s <= 300 else "St-3"
                warnings.append(
                    f"Kst = {substance.kst_bar_m_s:.0f} bar·m/s ({st_class}). "
                    "Explosion severity requires enhanced protection. "
                    "Zone extent has been increased by Kst factor. "
                    "Verify venting and suppression per NFPA 654."
                )

    # -----------------------------------------------------------------------
    # V20.2 Fix #12: Temperature class validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _check_temperature_class(
        substance: SubstanceProperties,
        warnings: List[str],
    ) -> None:
        """
        V20.2 Fix #12: Validate temperature class against autoignition.

        IEC 60079-0 §7.3: equipment maximum surface temperature must
        be below the autoignition temperature of the hazardous substance.
        E.g. T3 (200°C max) with autoignition 180°C = DANGER.
        """
        if substance.autoignition_c is None:
            return

        max_surface_temp = T_CLASS_MAX_TEMP.get(substance.temperature_class)
        if max_surface_temp is None:
            warnings.append(
                f"Unknown temperature class {substance.temperature_class!r}. "
                "Cannot validate against autoignition temperature. "
                "Valid classes: " + ", ".join(T_CLASS_MAX_TEMP.keys())
            )
            return

        if max_surface_temp >= substance.autoignition_c:
            # Find appropriate T class
            safe_classes = [
                tc for tc, temp in sorted(T_CLASS_MAX_TEMP.items(), key=lambda x: x[1])
                if temp < substance.autoignition_c  # type: ignore[operator]
            ]
            recommended = safe_classes[-1] if safe_classes else "T6 or lower"

            warnings.append(
                f"SAFETY: Equipment T-class {substance.temperature_class} "
                f"(max surface {max_surface_temp:.0f}°C) >= autoignition "
                f"({substance.autoignition_c:.0f}°C). Equipment COULD "
                f"IGNITE the substance! Must use T-class {recommended} "
                f"(max surface < {substance.autoignition_c:.0f}°C) per "
                "IEC 60079-0 §7.3."
            )
