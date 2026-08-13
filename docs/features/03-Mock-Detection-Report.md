# 03 — Mock Detection Report

**Project:** BAZspark v1.55.0
**Audit Date:** 2026-07-13

---

## Mock Detection Results

### Search 1: Hardcoded Sample Data
- **Found:** `ReportsPage.tsx` sampleDevices/sampleRooms/sampleDetectors
- **Status:** ✅ FIXED (V253) — now fetches real elements from API; sample data only used as fallback when no project elements exist, with visible warning banner

### Search 2: Fake Loading (setTimeout → setLoading)
- **Found:** 0 matches
- **Status:** ✅ CLEAN — all loading states are driven by real API calls

### Search 3: Hardcoded Return Values
- **Found:** 0 matches (no `return 42`, `return Math.random`, etc.)
- **Status:** ✅ CLEAN

### Search 4: Disabled Features / TODOs
- **Found:** 1 — SettingsPage 2FA toggle
- **Status:** ✅ FIXED (V253) — now disabled with "Coming Soon" label (honest)

### Search 5: alert()/confirm() in Production
- **Found:** 0 alert(), 0 confirm() (V253 replaced last confirm() in ApiKeysPage)
- **Status:** ✅ CLEAN

### Search 6: Math.random / mockData / fakeData
- **Found:** 0 matches
- **Status:** ✅ CLEAN

### Search 7: Empty onClick handlers
- **Found:** 0 matches
- **Status:** ✅ CLEAN — all buttons have real handlers

### Search 8: Fake charts/statistics
- **Found:** 0 matches
- **Status:** ✅ CLEAN — all charts use real data

---

## Mock Detection Summary

| Check | Results | Status |
|---|:---:|:---:|
| Hardcoded sample data | 1 found → FIXED | ✅ |
| Fake loading | 0 | ✅ |
| Hardcoded returns | 0 | ✅ |
| Disabled features | 1 → FIXED (marked Coming Soon) | ✅ |
| alert()/confirm() | 0 | ✅ |
| Math.random/mockData | 0 | ✅ |
| Empty onClick | 0 | ✅ |
| Fake charts | 0 | ✅ |

**ZERO mocks remain in production code paths.** ✅

---

## What Was Fixed in V253

1. **ReportsPage battery calculation** — was using hardcoded `sampleDevices` array (4 fake devices with fake current values). Now fetches real elements from `GET /api/v1/projects/{id}/elements` and maps `properties.standby_current` and `properties.alarm_current` to the battery calculator.

2. **ApiKeysPage confirm()** — was using blocking `confirm()` dialog. Now uses non-blocking toast with action/cancel buttons.

3. **SettingsPage 2FA toggle** — was appearing functional but only persisted to localStorage with no backend enforcement. Now disabled with "Coming Soon" label.
