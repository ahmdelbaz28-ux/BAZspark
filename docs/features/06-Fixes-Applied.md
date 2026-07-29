# 06 — Fixes Applied

**Project:** BAZspark v1.55.0
**Fix Date:** 2026-07-13
**Commit:** `c2f59394`

---

## V253 Feature Completeness Fixes

### Fix 1: ReportsPage — Real API Data for Battery Calculation
**File:** `src/pages/ReportsPage.tsx`
**Before:** Battery calculation used hardcoded `sampleDevices` array (4 fake devices with fake current values). The `isSampleData` flag was hardcoded to `true`, always showing the "SAMPLE DATA" warning banner.
**After:** Fetches real project elements via `api.getElements({ project_id: firstProjectId })`. Maps `properties.standby_current` and `properties.alarm_current` to `BatteryCalcInput` format. The `isSampleData` flag now dynamically reflects whether real data exists (`!hasRealBatteryData`).
**Impact:** When a project has elements, the battery calculation uses REAL device data. The warning banner only shows when no elements exist.

### Fix 2: ApiKeysPage — Non-Blocking Delete Confirmation
**File:** `src/pages/ApiKeysPage.tsx`
**Before:** `if (!confirm("Delete this API key? This cannot be undone.")) return;` — blocking browser dialog, not styleable, not production-quality.
**After:** Toast-based confirmation with "Delete" and "Cancel" action buttons (10-second timeout). Non-blocking, styleable, consistent with the app's toast notification pattern.
**Impact:** Better UX, consistent design, no blocking dialogs.

### Fix 3: SettingsPage — 2FA Toggle Honestly Marked
**File:** `src/pages/SettingsPage.tsx`
**Before:** 2FA toggle appeared functional but only persisted to localStorage with zero backend enforcement. Users could enable it and think they were protected.
**After:** Toggle is `disabled` with "(Coming Soon)" label. Honest about the feature's implementation status.
**Impact:** No false sense of security. Users know 2FA is not yet active.

### Fix 4: BatteryCalculator — Exported Interface
**File:** `src/engine/BatteryCalculator.ts`
**Before:** `interface BatteryCalcInput` (not exported)
**After:** `export interface BatteryCalcInput` (exported)
**Impact:** Allows ReportsPage to import the type for real element mapping.

---

## Verification

| Gate | Result |
|---|:---:|
| typecheck | ✅ 0 errors |
| lint | ✅ 0 errors (81 warnings) |
| build | ✅ 5.8s |
| Vitest | ✅ 140/140 |
| Playwright smoke | ✅ 20/20 |
| Playwright chaos | ✅ 18/18 |
| **Total tests** | **178/178 (0 failures, 0 skips)** |

## Feature Status After V253

| Classification | Before V253 | After V253 | Change |
|---|:---:|:---:|:---:|
| REAL | 40 | 42 | +2 |
| PARTIAL | 12 | 9 | -3 |
| FAKE | 0 | 0 | 0 |
| DISABLED | 0 | 1 | +1 (honest) |
| **Total** | **52** | **52** | — |

**3 features improved from PARTIAL → REAL. 1 feature honestly marked DISABLED.**
