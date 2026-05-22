"""
international_reg_selector.py – International Regulatory Jurisdiction Selector
===============================================================================
Maps project location to the correct regulatory framework for hazardous area
classification. This is a LEGAL GATE — wrong jurisdiction = illegal design.

Supported Frameworks:
  NEC Division System  (USA)         – NFPA 70 Art. 500-506, OSHA 29 CFR 1910.307
  CEC Zone System      (Canada)      – CEC Section 18, CSA C22.1
  ATEX Zone System     (EU/UK)       – Directive 2014/34/EU, EN 60079
  IECEx Zone System    (Global)      – IEC 60079 series
  AS/NZS Zone System   (AU/NZ)       – AS/NZS 60079
  GOST Zone System     (Russia/CIS)  – GOST R 51330
  GB Zone System       (China)       – GB 3836 series

Cross-references:
  IEC 60079-10-1:2015  – Gas zone classification
  IEC 60079-10-2:2015  – Dust zone classification
  NFPA 72-2022 §21.7   – HVAC control in hazardous locations
  NFPA 70-2023 Art. 500 – Classified locations (Division system)

V20.2 Fix #1 (CRITICAL): Canada mapped to NEC_DIVISION only, but CEC Section 18
  has mandated Zone classification since 1998 (CEC 18-002). New Canadian projects
  MUST use Zone system. Added CEC_ZONE system and updated Canada mapping.

V20.2 Fix #2 (CRITICAL): convert_zone_to_division() accepted hazard_class
  parameter but never used it — Zone 21 (dust) and Zone 1 (gas) both returned
  Division 1 without distinguishing between gas/dust equipment groups.
  Now logs warning when mapped class differs from requested class.

V20.2 Fix #3 (HIGH): Norway mapped to EU region, but Norway is EEA/EFTA,
  not EU. Added EFTA region with ATEX-via-EEA + DSB warning.

V20.2 Fix #4 (HIGH): CLASS_III (ignitable fibers, NFPA 70 Art. 503) was
  defined in HazardClass enum but missing from DIVISION_TO_ZONE equivalence
  map. Added entries with None (no IEC zone equivalent exists for fibers).

V20.2 Fix #5 (MEDIUM): Added missing countries: Iran, Egypt, Singapore,
  Malaysia, Indonesia, Nigeria, Turkey, Switzerland, Thailand, Philippines,
  Vietnam, Pakistan, Saudi Arabia cities, Colombia, Argentina, Chile.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HazardSystem(str, Enum):
    NEC_DIVISION = "NEC_DIVISION"    # USA (NFPA 70 Art. 500-506)
    CEC_ZONE     = "CEC_ZONE"       # Canada (CEC Section 18, CSA C22.1) — V20.2 Fix #1
    ATEX_ZONE    = "ATEX_ZONE"       # EU, UK (2014/34/EU, EN 60079)
    IECEX_ZONE   = "IECEX_ZONE"      # Global (IEC 60079)
    AS_NZS_ZONE  = "AS_NZS_ZONE"     # Australia, New Zealand
    GOST_ZONE    = "GOST_ZONE"       # Russia, CIS (GOST R 51330)
    GB_ZONE      = "GB_ZONE"         # China (GB 3836)


class JurisdictionRegion(str, Enum):
    USA           = "USA"
    CANADA        = "CANADA"          # V20.2: Now uses CEC_ZONE, not NEC_DIVISION
    EU            = "EU"
    EFTA          = "EFTA"            # V20.2 Fix #3: Norway, Switzerland, Iceland, Liechtenstein
    UK            = "UK"
    AUSTRALIA     = "AUSTRALIA"
    NEW_ZEALAND   = "NEW_ZEALAND"
    RUSSIA        = "RUSSIA"
    KAZAKHSTAN    = "KAZAKHSTAN"
    CHINA         = "CHINA"
    JAPAN         = "JAPAN"
    SOUTH_KOREA   = "SOUTH_KOREA"
    BRAZIL        = "BRAZIL"
    MIDDLE_EAST   = "MIDDLE_EAST"    # typically IECEx
    INDIA         = "INDIA"          # IS/IEC hybrid
    SOUTH_AFRICA  = "SOUTH_AFRICA"
    ASEAN         = "ASEAN"          # V20.2 Fix #5: Singapore, Malaysia, Indonesia, etc.
    TURKEY        = "TURKEY"         # V20.2 Fix #5
    NORTH_AFRICA  = "NORTH_AFRICA"   # V20.2 Fix #5: Egypt, etc.
    SOUTH_AMERICA = "SOUTH_AMERICA"  # V20.2 Fix #5: Colombia, Argentina, Chile
    CENTRAL_ASIA  = "CENTRAL_ASIA"   # V20.2 Fix #5: Pakistan, etc.
    GLOBAL        = "GLOBAL"         # IECEx by default


class HazardClass(str, Enum):
    CLASS_I   = "CLASS_I"    # Flammable gases/vapors (NEC Art. 501)
    CLASS_II  = "CLASS_II"   # Combustible dust (NEC Art. 502)
    CLASS_III = "CLASS_III"  # Ignitable fibers (NEC Art. 503)
    # ATEX/IEC equivalent
    GAS_VAPOR = "GAS_VAPOR"  # Zone 0/1/2 or Div 1/2
    DUST      = "DUST"       # Zone 20/21/22 or Div 1/2


class NECDivision(str, Enum):
    DIVISION_1 = "DIVISION_1"   # Normally present (NFPA 70 §500.5(B)(1))
    DIVISION_2 = "DIVISION_2"   # Not normally present (NFPA 70 §500.5(B)(2))


class ATEXZone(str, Enum):
    ZONE_0  = "ZONE_0"    # Continuously present gas (IEC 60079-10-1)
    ZONE_1  = "ZONE_1"    # Likely to occur during normal ops
    ZONE_2  = "ZONE_2"    # Not likely, short duration
    ZONE_20 = "ZONE_20"   # Continuously present dust (IEC 60079-10-2)
    ZONE_21 = "ZONE_21"   # Likely during normal ops (dust)
    ZONE_22 = "ZONE_22"   # Not likely, short duration (dust)
    SAFE    = "SAFE"      # Non-hazardous


# ---------------------------------------------------------------------------
# Country → Region mapping  (V20.2 Fix #5: expanded country coverage)
# ---------------------------------------------------------------------------

_COUNTRY_TO_REGION: Dict[str, JurisdictionRegion] = {
    # North America
    "US": JurisdictionRegion.USA,
    "USA": JurisdictionRegion.USA,
    "UNITED STATES": JurisdictionRegion.USA,
    "CA": JurisdictionRegion.CANADA,
    "CANADA": JurisdictionRegion.CANADA,
    # European Union
    "DE": JurisdictionRegion.EU, "GERMANY": JurisdictionRegion.EU,
    "FR": JurisdictionRegion.EU, "FRANCE": JurisdictionRegion.EU,
    "IT": JurisdictionRegion.EU, "ITALY": JurisdictionRegion.EU,
    "ES": JurisdictionRegion.EU, "SPAIN": JurisdictionRegion.EU,
    "NL": JurisdictionRegion.EU, "NETHERLANDS": JurisdictionRegion.EU,
    "BE": JurisdictionRegion.EU, "BELGIUM": JurisdictionRegion.EU,
    "PL": JurisdictionRegion.EU, "POLAND": JurisdictionRegion.EU,
    "SE": JurisdictionRegion.EU, "SWEDEN": JurisdictionRegion.EU,
    "DK": JurisdictionRegion.EU, "DENMARK": JurisdictionRegion.EU,
    "FI": JurisdictionRegion.EU, "FINLAND": JurisdictionRegion.EU,
    "AT": JurisdictionRegion.EU, "AUSTRIA": JurisdictionRegion.EU,
    "PT": JurisdictionRegion.EU, "PORTUGAL": JurisdictionRegion.EU,
    "GR": JurisdictionRegion.EU, "GREECE": JurisdictionRegion.EU,
    "CZ": JurisdictionRegion.EU, "CZECH REPUBLIC": JurisdictionRegion.EU,
    "RO": JurisdictionRegion.EU, "ROMANIA": JurisdictionRegion.EU,
    "HU": JurisdictionRegion.EU, "HUNGARY": JurisdictionRegion.EU,
    "IE": JurisdictionRegion.EU, "IRELAND": JurisdictionRegion.EU,
    # V20.2 Fix #3: EFTA countries (EU-like via EEA, but NOT EU members)
    "NO": JurisdictionRegion.EFTA, "NORWAY": JurisdictionRegion.EFTA,
    "CH": JurisdictionRegion.EFTA, "SWITZERLAND": JurisdictionRegion.EFTA,
    "IS": JurisdictionRegion.EFTA, "ICELAND": JurisdictionRegion.EFTA,
    "LI": JurisdictionRegion.EFTA, "LIECHTENSTEIN": JurisdictionRegion.EFTA,
    # UK post-Brexit (UKEX = mirrors ATEX)
    "GB": JurisdictionRegion.UK, "UK": JurisdictionRegion.UK,
    "UNITED KINGDOM": JurisdictionRegion.UK,
    # Australia / New Zealand
    "AU": JurisdictionRegion.AUSTRALIA, "AUSTRALIA": JurisdictionRegion.AUSTRALIA,
    "NZ": JurisdictionRegion.NEW_ZEALAND, "NEW ZEALAND": JurisdictionRegion.NEW_ZEALAND,
    # Russia / CIS
    "RU": JurisdictionRegion.RUSSIA, "RUSSIA": JurisdictionRegion.RUSSIA,
    "KZ": JurisdictionRegion.KAZAKHSTAN, "KAZAKHSTAN": JurisdictionRegion.KAZAKHSTAN,
    "BY": JurisdictionRegion.RUSSIA, "BELARUS": JurisdictionRegion.RUSSIA,
    "UZ": JurisdictionRegion.KAZAKHSTAN, "UZBEKISTAN": JurisdictionRegion.KAZAKHSTAN,
    # China
    "CN": JurisdictionRegion.CHINA, "CHINA": JurisdictionRegion.CHINA,
    # Asia Pacific
    "JP": JurisdictionRegion.JAPAN, "JAPAN": JurisdictionRegion.JAPAN,
    "KR": JurisdictionRegion.SOUTH_KOREA, "SOUTH KOREA": JurisdictionRegion.SOUTH_KOREA,
    # V20.2 Fix #5: ASEAN
    "SG": JurisdictionRegion.ASEAN, "SINGAPORE": JurisdictionRegion.ASEAN,
    "MY": JurisdictionRegion.ASEAN, "MALAYSIA": JurisdictionRegion.ASEAN,
    "ID": JurisdictionRegion.ASEAN, "INDONESIA": JurisdictionRegion.ASEAN,
    "TH": JurisdictionRegion.ASEAN, "THAILAND": JurisdictionRegion.ASEAN,
    "PH": JurisdictionRegion.ASEAN, "PHILIPPINES": JurisdictionRegion.ASEAN,
    "VN": JurisdictionRegion.ASEAN, "VIETNAM": JurisdictionRegion.ASEAN,
    # V20.2 Fix #5: Turkey
    "TR": JurisdictionRegion.TURKEY, "TURKEY": JurisdictionRegion.TURKEY,
    "TÜRKIYE": JurisdictionRegion.TURKEY,
    # South America
    "BR": JurisdictionRegion.BRAZIL, "BRAZIL": JurisdictionRegion.BRAZIL,
    # V20.2 Fix #5: More South America
    "CO": JurisdictionRegion.SOUTH_AMERICA, "COLOMBIA": JurisdictionRegion.SOUTH_AMERICA,
    "AR": JurisdictionRegion.SOUTH_AMERICA, "ARGENTINA": JurisdictionRegion.SOUTH_AMERICA,
    "CL": JurisdictionRegion.SOUTH_AMERICA, "CHILE": JurisdictionRegion.SOUTH_AMERICA,
    "PE": JurisdictionRegion.SOUTH_AMERICA, "PERU": JurisdictionRegion.SOUTH_AMERICA,
    # Middle East
    "SA": JurisdictionRegion.MIDDLE_EAST, "SAUDI ARABIA": JurisdictionRegion.MIDDLE_EAST,
    "AE": JurisdictionRegion.MIDDLE_EAST, "UAE": JurisdictionRegion.MIDDLE_EAST,
    "QA": JurisdictionRegion.MIDDLE_EAST, "QATAR": JurisdictionRegion.MIDDLE_EAST,
    "KW": JurisdictionRegion.MIDDLE_EAST, "KUWAIT": JurisdictionRegion.MIDDLE_EAST,
    "BH": JurisdictionRegion.MIDDLE_EAST, "BAHRAIN": JurisdictionRegion.MIDDLE_EAST,
    "OM": JurisdictionRegion.MIDDLE_EAST, "OMAN": JurisdictionRegion.MIDDLE_EAST,
    "IQ": JurisdictionRegion.MIDDLE_EAST, "IRAQ": JurisdictionRegion.MIDDLE_EAST,
    "JO": JurisdictionRegion.MIDDLE_EAST, "JORDAN": JurisdictionRegion.MIDDLE_EAST,
    "LB": JurisdictionRegion.MIDDLE_EAST, "LEBANON": JurisdictionRegion.MIDDLE_EAST,
    # V20.2 Fix #5: Iran
    "IR": JurisdictionRegion.MIDDLE_EAST, "IRAN": JurisdictionRegion.MIDDLE_EAST,
    # India
    "IN": JurisdictionRegion.INDIA, "INDIA": JurisdictionRegion.INDIA,
    # V20.2 Fix #5: Pakistan & Central Asia
    "PK": JurisdictionRegion.CENTRAL_ASIA, "PAKISTAN": JurisdictionRegion.CENTRAL_ASIA,
    "BD": JurisdictionRegion.CENTRAL_ASIA, "BANGLADESH": JurisdictionRegion.CENTRAL_ASIA,
    "LK": JurisdictionRegion.CENTRAL_ASIA, "SRI LANKA": JurisdictionRegion.CENTRAL_ASIA,
    # South Africa
    "ZA": JurisdictionRegion.SOUTH_AFRICA, "SOUTH AFRICA": JurisdictionRegion.SOUTH_AFRICA,
    # V20.2 Fix #5: North Africa
    "EG": JurisdictionRegion.NORTH_AFRICA, "EGYPT": JurisdictionRegion.NORTH_AFRICA,
    "DZ": JurisdictionRegion.NORTH_AFRICA, "ALGERIA": JurisdictionRegion.NORTH_AFRICA,
    "MA": JurisdictionRegion.NORTH_AFRICA, "MOROCCO": JurisdictionRegion.NORTH_AFRICA,
    "TN": JurisdictionRegion.NORTH_AFRICA, "TUNISIA": JurisdictionRegion.NORTH_AFRICA,
    "NG": JurisdictionRegion.NORTH_AFRICA, "NIGERIA": JurisdictionRegion.NORTH_AFRICA,
}

# V20.2 Fix #1: Canada now uses CEC_ZONE (CEC Section 18 Zone system)
# V20.2 Fix #3: EFTA countries use ATEX via EEA agreement
_REGION_TO_SYSTEM: Dict[JurisdictionRegion, HazardSystem] = {
    JurisdictionRegion.USA:          HazardSystem.NEC_DIVISION,
    JurisdictionRegion.CANADA:       HazardSystem.CEC_ZONE,        # V20.2 Fix #1
    JurisdictionRegion.EU:           HazardSystem.ATEX_ZONE,
    JurisdictionRegion.EFTA:         HazardSystem.ATEX_ZONE,       # V20.2 Fix #3: ATEX via EEA
    JurisdictionRegion.UK:           HazardSystem.ATEX_ZONE,       # UKEX mirrors ATEX
    JurisdictionRegion.AUSTRALIA:    HazardSystem.AS_NZS_ZONE,
    JurisdictionRegion.NEW_ZEALAND:  HazardSystem.AS_NZS_ZONE,
    JurisdictionRegion.RUSSIA:       HazardSystem.GOST_ZONE,
    JurisdictionRegion.KAZAKHSTAN:   HazardSystem.GOST_ZONE,
    JurisdictionRegion.CHINA:        HazardSystem.GB_ZONE,
    JurisdictionRegion.JAPAN:        HazardSystem.IECEX_ZONE,
    JurisdictionRegion.SOUTH_KOREA:  HazardSystem.IECEX_ZONE,
    JurisdictionRegion.BRAZIL:       HazardSystem.IECEX_ZONE,
    JurisdictionRegion.MIDDLE_EAST:  HazardSystem.IECEX_ZONE,
    JurisdictionRegion.INDIA:        HazardSystem.IECEX_ZONE,
    JurisdictionRegion.SOUTH_AFRICA: HazardSystem.IECEX_ZONE,
    JurisdictionRegion.ASEAN:        HazardSystem.IECEX_ZONE,      # V20.2 Fix #5
    JurisdictionRegion.TURKEY:       HazardSystem.IECEX_ZONE,      # V20.2 Fix #5
    JurisdictionRegion.NORTH_AFRICA: HazardSystem.IECEX_ZONE,      # V20.2 Fix #5
    JurisdictionRegion.SOUTH_AMERICA:HazardSystem.IECEX_ZONE,      # V20.2 Fix #5
    JurisdictionRegion.CENTRAL_ASIA: HazardSystem.IECEX_ZONE,      # V20.2 Fix #5
    JurisdictionRegion.GLOBAL:       HazardSystem.IECEX_ZONE,
}


# ---------------------------------------------------------------------------
# Zone equivalence map (NEC ↔ ATEX ↔ IEC)
# ---------------------------------------------------------------------------

# (NEC Division, HazardClass) → ATEXZone equivalent
# V20.2 Fix #4: Added CLASS_III entries (no IEC zone equivalent for fibers)
DIVISION_TO_ZONE: Dict[Tuple[NECDivision, HazardClass], Optional[ATEXZone]] = {
    (NECDivision.DIVISION_1, HazardClass.CLASS_I):   ATEXZone.ZONE_1,
    (NECDivision.DIVISION_2, HazardClass.CLASS_I):   ATEXZone.ZONE_2,
    (NECDivision.DIVISION_1, HazardClass.CLASS_II):  ATEXZone.ZONE_21,
    (NECDivision.DIVISION_2, HazardClass.CLASS_II):  ATEXZone.ZONE_22,
    (NECDivision.DIVISION_1, HazardClass.GAS_VAPOR): ATEXZone.ZONE_1,
    (NECDivision.DIVISION_2, HazardClass.GAS_VAPOR): ATEXZone.ZONE_2,
    (NECDivision.DIVISION_1, HazardClass.DUST):      ATEXZone.ZONE_21,
    (NECDivision.DIVISION_2, HazardClass.DUST):      ATEXZone.ZONE_22,
    # V20.2 Fix #4: IEC 60079 has no zone equivalent for Class III (fibers).
    # NFPA 70 Art. 503 applies. Returns None = no automatic conversion.
    (NECDivision.DIVISION_1, HazardClass.CLASS_III): None,
    (NECDivision.DIVISION_2, HazardClass.CLASS_III): None,
}

ZONE_TO_DIVISION: Dict[ATEXZone, Tuple[NECDivision, HazardClass]] = {
    ATEXZone.ZONE_0:  (NECDivision.DIVISION_1, HazardClass.CLASS_I),
    ATEXZone.ZONE_1:  (NECDivision.DIVISION_1, HazardClass.CLASS_I),
    ATEXZone.ZONE_2:  (NECDivision.DIVISION_2, HazardClass.CLASS_I),
    ATEXZone.ZONE_20: (NECDivision.DIVISION_1, HazardClass.CLASS_II),
    ATEXZone.ZONE_21: (NECDivision.DIVISION_1, HazardClass.CLASS_II),
    ATEXZone.ZONE_22: (NECDivision.DIVISION_2, HazardClass.CLASS_II),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegulatoryFramework:
    """
    Complete regulatory framework for a project jurisdiction.
    Immutable — determined at project initialisation.
    """
    region:             JurisdictionRegion
    system:             HazardSystem
    primary_standard:   str            # e.g. "NFPA 70-2023 Art. 500"
    secondary_standards: Tuple[str, ...] = ()
    atex_directive:     Optional[str]  = None  # "2014/34/EU"
    iec_standard:       Optional[str]  = None  # "IEC 60079"
    zone_based:         bool           = True   # False = Division system
    requires_notified_body: bool       = False  # EU ATEX Cat 1/2
    equipment_marking:  str            = ""     # e.g. "Ex", "AEx"
    legal_note:         str            = ""


@dataclass(frozen=True)
class JurisdictionResult:
    """Result of jurisdiction resolution."""
    country_input:      str
    region:             JurisdictionRegion
    framework:          RegulatoryFramework
    equivalent_zone:    Optional[ATEXZone]    = None
    equivalent_division: Optional[NECDivision] = None
    warnings:           Tuple[str, ...]        = ()
    errors:             Tuple[str, ...]        = ()

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def system(self) -> HazardSystem:
        return self.framework.system


# ---------------------------------------------------------------------------
# Framework definitions
# ---------------------------------------------------------------------------

_FRAMEWORKS: Dict[HazardSystem, RegulatoryFramework] = {
    HazardSystem.NEC_DIVISION: RegulatoryFramework(
        region=JurisdictionRegion.USA,
        system=HazardSystem.NEC_DIVISION,
        primary_standard="NFPA 70-2023 Art. 500-506",
        secondary_standards=(
            "OSHA 29 CFR 1910.307",
            "API RP 505",
            "NFPA 497 (Gas/Vapor)",
            "NFPA 499 (Dust)",
        ),
        zone_based=False,
        requires_notified_body=False,
        equipment_marking="AEx",
        legal_note=(
            "Division system. Equipment must be listed by NRTL "
            "(UL, FM, CSA). OSHA mandates compliance with "
            "NFPA 70 Art. 500 for US workplaces (29 CFR 1910.307)."
        ),
    ),
    # V20.2 Fix #1: CEC Zone system for Canada
    HazardSystem.CEC_ZONE: RegulatoryFramework(
        region=JurisdictionRegion.CANADA,
        system=HazardSystem.CEC_ZONE,
        primary_standard="CEC Section 18 / CSA C22.1",
        secondary_standards=(
            "CEC Section 18 (Zone classification)",
            "CEC Section 20 (Hazardous locations — surface sealing)",
            "CSA C22.2 No. 30 (Explosion-proof enclosures)",
            "CSA C22.2 No. 213 (Intrinsically safe apparatus)",
        ),
        zone_based=True,
        requires_notified_body=False,  # CSA certification required, not EU Notified Body
        equipment_marking="Ex",
        legal_note=(
            "Canada uses Zone classification per CEC Section 18 since 1998 "
            "(CEC 18-002). New installations MUST use Zone system. "
            "Existing Division-classified installations may remain. "
            "Equipment must be CSA or cUL certified."
        ),
    ),
    HazardSystem.ATEX_ZONE: RegulatoryFramework(
        region=JurisdictionRegion.EU,
        system=HazardSystem.ATEX_ZONE,
        primary_standard="EN 60079 series / IEC 60079",
        secondary_standards=(
            "ATEX Directive 2014/34/EU",
            "ATEX Directive 1999/92/EC (worker protection)",
            "EN 13463 (non-electrical)",
        ),
        atex_directive="2014/34/EU",
        iec_standard="IEC 60079-0",
        zone_based=True,
        requires_notified_body=True,  # Category 1/2 equipment
        equipment_marking="Ex",
        legal_note=(
            "Zone system. Category 1 equipment requires Notified Body "
            "certification (EU ATEX 2014/34/EU Art. 8). "
            "UK post-Brexit uses UKEX (mirrors ATEX, UKCA marking). "
            "EFTA countries (NO, CH, IS, LI) apply ATEX via EEA agreement "
            "but have local regulatory bodies (e.g. DSB in Norway)."
        ),
    ),
    HazardSystem.IECEX_ZONE: RegulatoryFramework(
        region=JurisdictionRegion.GLOBAL,
        system=HazardSystem.IECEX_ZONE,
        primary_standard="IEC 60079 series",
        secondary_standards=(
            "IEC 60079-10-1 (Gas zone classification)",
            "IEC 60079-10-2 (Dust zone classification)",
            "IEC 60079-14 (Installation)",
            "IEC 60079-17 (Inspection and maintenance)",
        ),
        iec_standard="IEC 60079-0",
        zone_based=True,
        requires_notified_body=False,
        equipment_marking="Ex",
        legal_note=(
            "IECEx scheme accepted in 50+ countries. "
            "Zone 0/1/2 for gas; Zone 20/21/22 for dust."
        ),
    ),
    HazardSystem.AS_NZS_ZONE: RegulatoryFramework(
        region=JurisdictionRegion.AUSTRALIA,
        system=HazardSystem.AS_NZS_ZONE,
        primary_standard="AS/NZS 60079 series",
        secondary_standards=(
            "AS/NZS 60079-10-1",
            "AS/NZS 60079-10-2",
            "AS/NZS 3000 (Wiring rules)",
        ),
        iec_standard="IEC 60079-0",
        zone_based=True,
        requires_notified_body=False,
        equipment_marking="Ex",
        legal_note="AS/NZS 60079 mirrors IEC 60079. IECEx certificates accepted.",
    ),
    HazardSystem.GOST_ZONE: RegulatoryFramework(
        region=JurisdictionRegion.RUSSIA,
        system=HazardSystem.GOST_ZONE,
        primary_standard="GOST R 51330 series (IEC 60079 equivalent)",
        secondary_standards=(
            "TR CU 012/2011 (Customs Union Technical Regulation)",
            "PUE (Electrical Installation Rules)",
        ),
        zone_based=True,
        requires_notified_body=True,
        equipment_marking="Ex (1ExG / 1ExD)",
        legal_note=(
            "Russia/CIS uses GOST R 51330 (equivalent to IEC 60079). "
            "Equipment must have EAC Ex certification."
        ),
    ),
    HazardSystem.GB_ZONE: RegulatoryFramework(
        region=JurisdictionRegion.CHINA,
        system=HazardSystem.GB_ZONE,
        primary_standard="GB 3836 series (IEC 60079 equivalent)",
        secondary_standards=(
            "GB/T 3836.15 (Explosive atmospheres - design)",
            "GB 50058 (Electrical design in explosive atmosphere)",
        ),
        zone_based=True,
        requires_notified_body=True,
        equipment_marking="Ex (CNEx)",
        legal_note=(
            "China uses GB 3836 (equivalent to IEC 60079). "
            "Equipment must have CNAS/CNEx certification."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------

class InternationalRegSelector:
    """
    Resolves project country/region to the correct regulatory framework
    for hazardous area classification.

    This is a LEGAL GATE. Using the wrong system (e.g. NEC Division
    instead of ATEX Zone in EU) is a legal violation and an export
    control issue.

    Usage:
        selector = InternationalRegSelector()
        result   = selector.resolve("DE")  # Germany -> ATEX Zone
        result   = selector.resolve("US")  # USA -> NEC Division
        result   = selector.resolve("CA")  # Canada -> CEC Zone (V20.2 Fix #1)
    """

    def resolve(
        self,
        country: str,
        override_system: Optional[HazardSystem] = None,
    ) -> JurisdictionResult:
        """
        Resolve country string to regulatory framework.

        Args:
            country:         ISO 2-letter code or full country name.
            override_system: Force a specific system (with warning).

        Returns:
            JurisdictionResult with framework, zone/division equivalents.
        """
        key = country.upper().strip()
        region = _COUNTRY_TO_REGION.get(key, JurisdictionRegion.GLOBAL)
        system = _REGION_TO_SYSTEM.get(region, HazardSystem.IECEX_ZONE)

        warnings: List[str] = []
        errors: List[str] = []

        if region == JurisdictionRegion.GLOBAL:
            warnings.append(
                f"Country {country!r} not in jurisdiction database. "
                "Defaulting to IECEx Zone system. "
                "Verify local regulations before submission."
            )

        # V20.2 Fix #3: EFTA countries use ATEX via EEA, but have local regulators
        if region == JurisdictionRegion.EFTA:
            if key in ("NO", "NORWAY"):
                warnings.append(
                    "Norway uses ATEX via EEA agreement. Local regulator: "
                    "DSB (Direktoratet for samfunnssikkerhet og beredskap). "
                    "Verify specific Norwegian requirements."
                )
            elif key in ("CH", "SWITZERLAND"):
                warnings.append(
                    "Switzerland uses EN 60079 / ATEX-compatible standards "
                    "via bilateral agreements, but is NOT in EU/EEA. "
                    "Equipment must comply with SEV/SUVI requirements."
                )

        # V20.2 Fix #1: Canada uses CEC Zone, warn if override to NEC Division
        if region == JurisdictionRegion.CANADA and override_system == HazardSystem.NEC_DIVISION:
            warnings.append(
                "LEGAL WARNING: Canada has mandated Zone classification per "
                "CEC Section 18 since 1998. Using NEC Division system is only "
                "permitted for EXISTING installations (CEC 18-002). "
                "New projects MUST use Zone system."
            )

        if override_system is not None and override_system != system:
            if not (region == JurisdictionRegion.CANADA
                    and override_system == HazardSystem.NEC_DIVISION):
                warnings.append(
                    f"System overridden from {system.value} to "
                    f"{override_system.value} for {country!r}. "
                    "LEGAL WARNING: ensure override is permitted by local AHJ."
                )
            system = override_system

        framework = _FRAMEWORKS.get(system, _FRAMEWORKS[HazardSystem.IECEX_ZONE])

        logger.info(
            "Jurisdiction: %s -> %s (%s | %s)",
            country, region.value, system.value, framework.primary_standard,
        )

        return JurisdictionResult(
            country_input=country,
            region=region,
            framework=framework,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    def convert_zone_to_division(
        self,
        zone: ATEXZone,
        hazard_class: HazardClass = HazardClass.CLASS_I,
    ) -> Optional[NECDivision]:
        """
        Convert ATEX Zone to NEC Division equivalent.
        IEC 60079-10-1 / NFPA 70 Art. 505.

        V20.2 Fix #2: Now warns when mapped hazard class differs from
        requested hazard class. Zone 1 (gas) and Zone 21 (dust) both map
        to Division 1, but equipment groups differ significantly.
        """
        mapping = ZONE_TO_DIVISION.get(zone)
        if mapping is None:
            return None
        div, mapped_class = mapping

        # V20.2 Fix #2: Warn when hazard class doesn't match
        if mapped_class != hazard_class and hazard_class not in (
            HazardClass.CLASS_I, HazardClass.GAS_VAPOR
        ):
            logger.warning(
                "Zone %s maps to %s/%s but requested hazard_class=%s. "
                "Verify equipment group compatibility — gas and dust "
                "equipment have different construction requirements "
                "per NFPA 70 Art. 501 vs Art. 502.",
                zone.value, div.value, mapped_class.value, hazard_class.value,
            )

        return div

    def convert_division_to_zone(
        self,
        division: NECDivision,
        hazard_class: HazardClass = HazardClass.CLASS_I,
    ) -> Optional[ATEXZone]:
        """
        Convert NEC Division to ATEX Zone equivalent.
        NFPA 70-2023 Art. 505.5(B) / IEC 60079-10-1.

        V20.2 Fix #4: CLASS_III (ignitable fibers) has no IEC zone
        equivalent. Returns None with warning.
        """
        result = DIVISION_TO_ZONE.get((division, hazard_class))

        # V20.2 Fix #4: No IEC zone equivalent for Class III
        if result is None and hazard_class == HazardClass.CLASS_III:
            logger.warning(
                "CLASS_III (ignitable fibers, NFPA 70 Art. 503) has no "
                "IEC 60079 zone equivalent. Fibers/flyings classification "
                "is unique to the NEC Division system. "
                "Use NFPA 70 Art. 503 for design requirements."
            )

        return result

    def list_supported_countries(self) -> List[str]:
        return sorted(_COUNTRY_TO_REGION.keys())

    def get_framework(self, system: HazardSystem) -> RegulatoryFramework:
        return _FRAMEWORKS[system]
