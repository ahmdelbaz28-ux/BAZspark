"""
QOMN-FIRE PHYSICAL AND REGULATORY CONSTANTS
"""

# NFPA 72 Spacing Limits (2022 §17)
NFPA_SMOKE_DETECTOR_SPACING_M = 9.144  # 30 feet smooth ceiling spacing
NFPA_MAX_WALL_DISTANCE_M = 6.400       # 0.7 times spacing constraint (21 feet)

# NEC Conduit Area Specifications (mm2) - Chapter 9 Table 4
EMT_INTERNAL_AREA_1_2_MM2 = 196.1
EMT_INTERNAL_AREA_3_4_MM2 = 343.9
EMT_INTERNAL_AREA_1_MM2 = 557.4

# NEC Wire Cross Sectional Areas (mm2) - Chapter 9 Table 5
WIRE_AREA_14_AWG_MM2 = 6.26
WIRE_AREA_12_AWG_MM2 = 8.58
WIRE_AREA_10_AWG_MM2 = 13.61

# NEC Chapter 9 Table 1 Fill Limits
NEC_FILL_LIMIT_1_WIRE = 0.53
NEC_FILL_LIMIT_2_WIRES = 0.31
NEC_FILL_LIMIT_OVER_2_WIRES = 0.40
