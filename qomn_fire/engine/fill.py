"""
QOMN-FIRE CONDUIT FILL SIZING ENGINE
Reference Standard: NEC 2023 Chapter 9, Table 1 & Table 4.

BUG-19 FIX: Added support for fire alarm cable types (FPLP, FPL, FPLR)
per NEC 760.179. Fire alarm systems require FPLP (Power-Limited Fire Alarm)
or FPL (Fire Alarm) cable types. The original code only supported generic
AWG gauges, rejecting FPLP/FPL/FPLR cables — making it impossible to
size conduit for fire alarm circuits, which is the PRIMARY use case.
"""

from qomn_fire.core.errors import Result, ConduitFillError
from qomn_fire.core.constants import (
    EMT_INTERNAL_AREA_1_2_MM2, EMT_INTERNAL_AREA_3_4_MM2, EMT_INTERNAL_AREA_1_MM2,
    WIRE_AREA_14_AWG_MM2, WIRE_AREA_12_AWG_MM2, WIRE_AREA_10_AWG_MM2,
    NEC_FILL_LIMIT_1_WIRE, NEC_FILL_LIMIT_2_WIRES, NEC_FILL_LIMIT_OVER_2_WIRES
)

# BUG-19 FIX: Fire alarm cable cross-sectional areas (NEC Chapter 9, Table 5A)
# FPLP = Power-Limited Fire Alarm Cable (NEC 760.179)
# FPL = Fire Alarm Cable (NEC 760.179)
# FPLR = Riser-Rated Fire Alarm Cable (NEC 760.179(B))
# These are the standard cable types for fire alarm systems.
# Values from NEC Chapter 9 Table 5A — approximate for typical 2-conductor cables.
FIRE_ALARM_CABLE_AREAS = {
    "FPLP 14": 6.26,    # FPLP 14 AWG 2-conductor ≈ same as 14 AWG THHN
    "FPLP 12": 8.58,    # FPLP 12 AWG 2-conductor
    "FPLP 10": 13.61,   # FPLP 10 AWG 2-conductor
    "FPL 14": 6.26,     # FPL 14 AWG 2-conductor
    "FPL 12": 8.58,     # FPL 12 AWG 2-conductor
    "FPL 10": 13.61,    # FPL 10 AWG 2-conductor
    "FPLR 14": 6.26,    # FPLR 14 AWG 2-conductor
    "FPLR 12": 8.58,    # FPLR 12 AWG 2-conductor
    "FPLR 10": 13.61,   # FPLR 10 AWG 2-conductor
    # Standard THHN/THWN building wire (NEC Table 5)
    "THHN 14": 6.26,
    "THHN 12": 8.58,
    "THHN 10": 13.61,
    "THWN 14": 6.26,
    "THWN 12": 8.58,
    "THWN 10": 13.61,
}

def calculate_conduit_fill(conduit_size: str, wire_gauge: str, wire_count: int) -> Result[float, ConduitFillError]:
    if wire_count <= 0:
        return Result(error=ConduitFillError(
            message="Wire count must be a positive integer.",
            code_ref="NEC Ch.9 Table 1",
            remedy="Increase wire count parameter above zero."
        ))

    conduit_area = 0.0
    if conduit_size == "1/2":
        conduit_area = EMT_INTERNAL_AREA_1_2_MM2
    elif conduit_size == "3/4":
        conduit_area = EMT_INTERNAL_AREA_3_4_MM2
    elif conduit_size == "1":
        conduit_area = EMT_INTERNAL_AREA_1_MM2
    else:
        return Result(error=ConduitFillError(
            message=f"Unsupported trade conduit size '{conduit_size}'",
            code_ref="NEC Table 4",
            remedy="Use standard sizes: '1/2', '3/4', or '1'."
        ))

    # BUG-19 FIX: Support fire alarm cable types (FPLP, FPL, FPLR) and
    # standard building wire (THHN, THWN) in addition to generic AWG.
    wire_area = 0.0
    if wire_gauge in FIRE_ALARM_CABLE_AREAS:
        wire_area = FIRE_ALARM_CABLE_AREAS[wire_gauge]
    elif wire_gauge == "14 AWG":
        wire_area = WIRE_AREA_14_AWG_MM2
    elif wire_gauge == "12 AWG":
        wire_area = WIRE_AREA_12_AWG_MM2
    elif wire_gauge == "10 AWG":
        wire_area = WIRE_AREA_10_AWG_MM2
    else:
        supported = ", ".join(sorted(set(
            list(FIRE_ALARM_CABLE_AREAS.keys()) + ["14 AWG", "12 AWG", "10 AWG"]
        )))
        return Result(error=ConduitFillError(
            message=f"Unsupported wire/cable type '{wire_gauge}'",
            code_ref="NEC Table 5/5A",
            remedy=f"Select a compliant wire/cable type. Supported: {supported}"
        ))

    total_wire_area = wire_area * wire_count
    fill_ratio = total_wire_area / conduit_area

    if wire_count == 1:
        limit = NEC_FILL_LIMIT_1_WIRE
    elif wire_count == 2:
        limit = NEC_FILL_LIMIT_2_WIRES
    else:
        limit = NEC_FILL_LIMIT_OVER_2_WIRES

    if fill_ratio > limit:
        return Result(error=ConduitFillError(
            message=f"Conduit fill exceeds permissible NEC threshold limit: {fill_ratio:.2%} > {limit:.2%}",
            code_ref="NEC Ch.9 Table 1",
            remedy="Upsize conduit selection or reduce wire run count."
        ))

    return Result(value=fill_ratio)
