# NFPA 72 V9 Fire Alarm Coverage - FPE Review Protocol

## PR: #29 | Branch: fix/nfpa72-coverage-v8
## Tests: 103/103 PASS | 0 SKIPS | 0 TODOs
## Status: MERGEABLE

---

## ⚠️ CRITICAL: This is a REVIEW PROTOCOL, not a checklist

FPE must EXECUTE these commands to verify. Do NOT just check boxes.

---

## 1. Environment Setup (15 minutes)

```bash
# Clone and setup
git clone https://github.com/ahmdelbaz28-ux/revit.git
cd revit
git checkout fix/nfpa72-coverage-v8

# Install dependencies
pip install -r requirements.txt
pytest --version  # Must be ≥7.0

# Verify 103 tests
python -m pytest tests/unit/ --collect-only -q | tail -1
# Expected: 103 tests collected in 0.22s
```

---

## 2. Test Execution (30 minutes)

```bash
# Run ALL safety validation tests
pytest tests/unit/test_safety_validation.py -v --tb=short
# Expected: 103 passed, 0 failed, 0 skipped

# Run coverage tests
pytest tests/unit/test_coverage.py -v --tb=short
# Expected: 12 passed

# Run mortality tests
pytest tests/unit/test_coverage_mortality.py -v --tb=short
# Expected: 12 passed

# Run panel and voltage specific tests
pytest tests/unit/ -k "panel or voltage" -v
# Expected: 5 panel tests pass, 2 voltage tests pass
```

---

## 3. Code Review - Line by Line (2 hours)

### 3.1 REJECT Invalid Heights
**File: `nfpa72_models.py`** | Lines: 421-426

```python
# This MUST raise ValueError for ≤ 0
if ceiling_height_m <= 0:
    raise ValueError(
        f"CEILING_HEIGHT_MUST_BE_POSITIVE: {ceiling_height_m}m is not valid. "
        f"Must be > 0. REJECT - requires PE REVIEW"
    )
```

**Verify manually:**
```bash
python3 -c "from nfpa72_models import get_smoke_detector_radius_safe; get_smoke_detector_radius_safe(-3.0)"
# Must raise: ValueError: CEILING_HEIGHT_MUST_BE_POSITIVE

python3 -c "from nfpa72_models import get_smoke_detector_radius_safe; get_smoke_detector_radius_safe(0.0)"
# Must raise: ValueError: CEILING_HEIGHT_MUST_BE_POSITIVE
```

---

### 3.2 NFPA 72 Table Values
**File: `nfpa72_models.py`** | Lines: 442-456

```python
R = {
    (3.0, 4.3): 4.55,
    (4.3, 6.1): 5.35,
    (6.1, 7.6): 5.2,
    (7.1, 9.1): 5.8,
    (9.1, 15.3): 6.4
}
```

**Verify manually:**
```bash
python3 -c "from nfpa72_models import get_smoke_detector_radius_safe; print(get_smoke_detector_radius_safe(3.0))"
# Expected: 4.55

python3 -c "from nfpa72_models import get_smoke_detector_radius_safe; print(get_smoke_detector_radius_safe(6.0))"
# Expected: 5.35

python3 -c "from nfpa72_models import get_smoke_detector_radius_safe; print(get_smoke_detector_radius_safe(9.0))"
# Expected: 5.80

python3 -c "from nfpa72_models import get_smoke_detector_radius_safe; print(get_smoke_detector_radius_safe(15.3))"
# Expected: 6.40
```

---

### 3.3 Beam Reduction (NFPA 72 17.6.3.3)
**File: `nfpa72_coverage.py`** | Lines: ~100-120

**Verify logic:**
- Beam depth > 5% of ceiling height = 15% reduction
- Formula: `reduced_radius = nominal_radius * 0.85`

**Verify manually:**
```bash
python3 -c "from nfpa72_coverage import adjust_coverage_for_beams; print(adjust_coverage_for_beams(9.1, 0.15, 3.0))"
# Expected: 7.735 (9.1 * 0.85)

python3 -c "from nfpa72_coverage import adjust_coverage_for_beams; print(adjust_coverage_for_beams(9.1, 0.04, 3.0))"
# Expected: 9.1 (no reduction)
```

---

### 3.4 FireAlarmPanel (NFPA 72 Chapter 21)
**File: `nfpa72_models.py`** | Lines: 302-357

```python
@dataclass
class FireAlarmPanel:
    panel_id: str
    max_devices: int = 250
    voltage: float = 24.0
    min_voltage: float = 16.0
```

**Verify at 251:**
```bash
python3 -c "
from nfpa72_models import FireAlarmPanel
panel = FireAlarmPanel(panel_id='TEST')
for i in range(250):
    panel.add_device(f'DEV-{i}')
panel.add_device('DEV-251')
"
# Expected: PanelCapacityError: capacity exceeded
```

**Verify voltage drop formula:**
```python
# Formula: v_drop = distance_m × 0.0004  # V/m
# At 20000m: 24 - (20000 × 0.0004) = 16V → OK
# At 25000m: 24 - (25000 × 0.0004) = 14V → FAIL
```

---

### 3.5 Silent Death Scenarios
**File: `tests/unit/test_safety_validation.py`** | Lines: 174-260

Must verify these 7 tests:
1. `test_detectors_too_far_apart` - coverage < 100%
2. `test_dead_corner_no_coverage` - uncovered areas
3. `test_mixed_detectors_smoke_heat_not_equal`
4. `test_sloped_ceiling_no_adjustment`
5. `test_duct_blocks_line_of_sight`
6. `test_panel_overloaded` - PanelCapacityError
7. `test_voltage_drop_below_threshold`

---

## 4. Edge Case Validation (1 hour)

Run these MANUALLY:

| Test | Command | Expected |
|------|---------|----------|
| Negative height | `get_smoke_detector_radius_safe(-1)` | `ValueError` |
| Zero height | `get_smoke_detector_radius_safe(0)` | `ValueError` |
| 251 devices | `panel.add_device('DEV-251')` | `PanelCapacityError` |
| 25km wire | `panel.verify_voltage(25000)` | `False` (< 16V) |
| Exact 20km | `panel.verify_voltage(20000)` | `True` (16V exactly) |

---

## 5. Sign-off Requirements

FPE MUST verify ALL of these:

- [ ] All pytest tests pass (103/103)
- [ ] `(-3.0)` raises ValueError
- [ ] `(0.0)` raises ValueError
- [ ] `(3.0)` returns 4.55
- [ ] `(6.0)` returns 5.35
- [ ] `(9.0)` returns 5.80
- [ ] `(15.3)` returns 6.40
- [ ] Beam reduction = 15% at >5%
- [ ] Panel capacity = 250 (error at 251)
- [ ] Voltage drop at 25km < 16V = FAIL
- [ ] No hardcoded magic numbers without citation

---

## 🔴 SIGNATURE:

FPE Name: __________

License #: __________

Date: __________

Signature: __________

---

⚠️ **LEGAL DISCLAIMER**

This review is for compliance assistance only.
It does not constitute legal advice.
NFPA 72 (2022 Edition) is the authoritative standard.
Fire Protection Engineer stamp required for production.