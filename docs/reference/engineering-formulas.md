# Engineering Formulas Reference

Single consolidated reference for every engineering formula, constant, and assumption in BAZSpark's life-safety calculations. Each entry cites its NFPA 72 / NEC / IBC source.

**Source of truth:** `fireai/constants/nfpa72.py` and `fireai/constants/nec.py`

---

## NFPA 72-2022 Constants

### Smoke Detectors

| Constant | Value | Source | Notes |
|---|---|---|---|
| `SMOKE_MAX_SPACING_M` | 9.1 m (30 ft) | NFPA 72-2022 §17.7.3.2.3 | Flat spacing on smooth ceilings |
| `SMOKE_MAX_CEILING_HEIGHT_M` | 18.288 m (60 ft) | NFPA 72-2022 §17.7.3.2.4 | Maximum ceiling height |
| `SMOKE_PRACTICAL_CEILING_HEIGHT_M` | 6.096 m (20 ft) | ECMAG guidance | Practical recommendation, not code |
| `COVERAGE_RADIUS_FACTOR` | 0.7 | NFPA 72-2022 §17.7.4.2.3.1 | R = 0.7 × S |
| `WALL_MIN_DISTANCE_M` | 0.1016 m (4 in) | NFPA 72-2022 §17.7.3.2.3 | Dead-air space rule |
| `CEILING_HEIGHT_HARD_LIMIT_M` | 18.288 m (60 ft) | NFPA 72-2022 §17.7.3.2.4 | Matches smoke max |

### Heat Detectors

| Constant | Value | Source | Notes |
|---|---|---|---|
| `HEAT_MAX_SPACING_M` | 6.1 m (20 ft) | NFPA 72-2022 §17.6.3.1 | Standard spacing |
| `HEAT_MAX_CEILING_HEIGHT_M` | 15.24 m (50 ft) | NFPA 72-2022 §17.6.3.1 | Maximum ceiling height |
| `HEAT_ABSOLUTE_MAX_SPACING_M` | 15.24 m (50 ft) | NFPA 72-2022 §17.6.3.1 | Absolute max (not standard) |
| `CEILING_HEIGHT_SOFT_LIMIT_M` | 15.24 m (50 ft) | NFPA 72-2022 §17.6.3.1 | Matches heat max |

### Notification Appliances (NAC)

| Constant | Value | Source | Notes |
|---|---|---|---|
| `NAC_MIN_CD` | 75 cd | NFPA 72-2022 §18.5.5.1 | Minimum wall-mounted candela |
| `NAC_SLEEPING_MIN_CD` | 177 cd | NFPA 72-2022 §18.5.5.1 | Minimum for sleeping areas |
| `MAX_VOLTAGE_DROP_PCT` | 10.0% | NFPA 72-2022 §10.14.1.2 | Fire alarm circuit limit |
| `NOMINAL_VOLTAGE_FA` | 24.0 VDC | Industry standard | Standard FA panel voltage |

### Coverage Thresholds

| Constant | Value | Source | Notes |
|---|---|---|---|
| `PROOF_VERIFIED_THRESHOLD` | 99.99% | Internal quality gate | "Verified" tier |
| `STANDARD_COVERAGE_THRESHOLD` | 99.0% | Internal quality gate | "Valid" tier |
| `MINIMUM_COVERAGE_FOR_SUBMISSION` | 95.0% | Internal quality gate | Below = REJECTED |
| `ABSOLUTE_MINIMUM_COVERAGE` | 90.0% | Internal quality gate | Cannot be overridden |

---

## NEC 2023 Chapter 9 Table 8

### Copper Conductor Resistance (Stranded Class B)

| AWG | Ω/km @ 20°C | Ω/km @ 75°C |
|---|---|---|
| 18 | 10.870 (solid) | — |
| 16 | 6.820 (solid) | — |
| 14 | **8.470** | 10.30 |
| 12 | 5.322 | 6.50 |
| 10 | 3.340 | 4.10 |
| 8 | 2.099 | 2.62 |
| 6 | 1.322 | 1.65 |
| 4 | 0.833 | 1.04 |
| 3 | 0.661 | 0.83 |
| 2 | 0.524 | 0.66 |
| 1 | 0.416 | 0.52 |
| 1/0 | 0.330 | 0.41 |
| 2/0 | 0.262 | 0.33 |
| 3/0 | 0.208 | 0.26 |
| 4/0 | 0.164 | 0.21 |

### Temperature Correction

```
R_T = R_20 × [1 + α × (T - 20)]
```

Where:
- `α = 0.00393` (copper temperature coefficient)
- `T` = operating temperature (°C)
- `R_20` = resistance at 20°C

---

## Voltage Drop Calculation

### Formula

```
V_drop = 2 × I × L × R_per_m
```

Where:
- `2` = DC return path factor (NFPA 72 §10.14, NEC Art. 310)
- `I` = circuit current (Amperes)
- `L` = one-way cable length (metres)
- `R_per_m` = conductor resistance at operating temperature (Ω/m)

### Compliance Thresholds

| Circuit Type | Limit | Source |
|---|---|---|
| Fire alarm | ≤ 10% | NFPA 72-2022 §10.14.1.2 |
| Branch (info only) | ≤ 3% | NEC §210.19(A)(1) note |
| Total (info only) | ≤ 5% | NEC §215.2(A)(2) note |

**Note:** NEC voltage drop limits are informational, not enforceable for fire alarm circuits. NFPA 72 §10.14.1.2 is the governing standard.

---

## Coverage Calculation

### Smoke Detector Coverage

The coverage radius is **flat** for all ceiling heights:

```
R = COVERAGE_RADIUS_FACTOR × S
R = 0.7 × 9.1m = 6.37m (for standard spacing)
```

**Critical correction (C-09):** Smoke detectors use flat 9.1m spacing regardless of ceiling height. The old code incorrectly reduced spacing for higher ceilings.

### Coverage Percentage

```
coverage = (covered_area / total_area) × 100
```

Where:
- `covered_area` = union of all detector coverage circles
- `total_area` = room floor area

---

## Battery Sizing

### Formula

```
C_required = (I_standby × T_standby) + (I_alarm × T_alarm)
```

Where:
- `C_required` = required battery capacity (Ah)
- `I_standby` = standby current (A)
- `T_standby` = standby time (hours) — typically 24h for fire alarm
- `I_alarm` = alarm current (A)
- `T_alarm` = alarm time (minutes) — typically 5–15 min

**Note (BUG-13 fix):** All values must be in consistent units (Amps × hours = Ah). The old code mixed Amps and mA, causing incorrect sizing.

---

## Acoustic Calculations

### Sound Pressure Level

```
L_p = L_w + 10 × log10(Q / (4πr²)) - α × r
```

Where:
- `L_p` = sound pressure level at distance r (dB)
- `L_w` = source sound power level (dB)
- `Q` = directivity factor
- `r` = distance from source (m)
- `α` = absorption coefficient

---

## Coverage Radius Correction Factors

When deviation from standard spacing is needed, apply these factors (engineering judgement):

| Condition | Factor | Source |
|---|---|---|
| Beamed ceiling (depth > 0.3m) | 0.7 | ECMAG guidance |
| Irregular ceiling | 0.8 | Engineering judgement |
| High airflow areas | 0.9 | Engineering judgement |

**Note:** These are engineering judgement values, not code-cited. Use with caution and document rationale.

---

## Self-Healing Kernel

The QOMN-FIRE kernel implements a self-healing philosophy:

1. **Try deterministic calculation first**
2. **If it fails, apply engineering judgement with documented rationale**
3. **If that fails, return a conservative default with a warning**
4. **Always log the fallback path taken**

This ensures the system never crashes silently and always produces a result, even if conservative.

---

## CI/CD Regulatory Guard

All constants in `fireai/constants/nfpa72.py` and `fireai/constants/nec.py` are protected by the `regulatory-data-guard` CI check. Any change to these files:

1. Triggers an automatic review
2. Requires explicit approval from project lead
3. Must update this document (`ENGINEERING_BASIS.md`)
4. Must include updated test assertions

---

## References

- NFPA 72-2022: National Fire Alarm and Signaling Code
- NEC 2023: National Electrical Code (NFPA 70)
- IBC 2021: International Building Code
- ECMAG: Electrical Contractor Magazine guidance
