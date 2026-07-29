# 05 — Removed Code Report

**Project:** BAZspark v1.55.0
**Cleanup Date:** 2026-07-13

---

## Removed Code Summary

| Commit | File | Removed | Lines | Reason |
|---|---|---|:---:|---|
| `946bb6b2` | ContextPanel.tsx | `useMemo` import | 1 | Imported but never called |
| `946bb6b2` | ContextPanel.tsx | `getHelpContextId` function | 10 | Defined but never called or exported |
| `f1885a3f` | AICopilot.tsx | 7 lucide-react imports | 7 | Imported but never referenced in JSX |
| `23f4ec72` | MemoryPage.tsx | `Label` import | 1 | Imported but never used |
| `23f4ec72` | WorkflowPage.tsx | `Textarea` import | 1 | Imported but never used |
| `23f4ec72` | ReportGeneratorPage.tsx | `ActivityIcon` import | 1 | Imported but never used |
| `23f4ec72` | ReportGeneratorPage.tsx | `ShieldAlert` import | 1 | Imported but never used |
| `23f4ec72` | ReportsPage.tsx | `err` variable in catch | 1 | Declared but never used (V247 regression) |
| `23f4ec72` | fullApi.ts | `coreApi` import | 1 | Imported but never used |
| `23f4ec72` | fullApi.ts | `digitalTwinApiClient` import | 1 | Imported but never used |
| `fcd98a98` | CADSettingsPage.tsx | `t` from useTranslation | 1 | Destructured but never called |
| `fcd98a98` | DigitalTwinPage.tsx | `t` from useTranslation | 1 | Destructured but never called |
| `fcd98a98` | ReportGeneratorPage.tsx | `t` from useTranslation | 1 | Destructured but never called |

**Total: 28 lines removed across 8 files**

---

## Detailed Removal Justifications

### 1. `getHelpContextId` function (ContextPanel.tsx)

**Why it was safe to remove:**
- Defined on line 61 as a module-level function (not exported)
- Never called within ContextPanel.tsx (grep verified)
- Never imported by any other file (grep across `src/` = 0 results)
- No test files reference it

**What it did:** Mapped a `ContextPanelSelection` to a `HelpTopicId`. The function was likely written during development but the UI was changed to use a different approach, leaving this function orphaned.

### 2. `useMemo` import (ContextPanel.tsx)

**Why it was safe to remove:**
- Imported from "react" on line 8
- Never called anywhere in the file (grep count = 1, import line only)
- The file uses `useEffect` and `useState` but not `useMemo`

### 3. 7 lucide-react imports (AICopilot.tsx)

**Why they were safe to remove:**
- `AlertTriangle`, `ArrowRight`, `CheckCircle2`, `CheckSquare`, `Eye`, `FileText`, `User`
- Each was imported but never referenced in JSX
- Verified via grep: each icon name appears exactly once (the import line)
- All were marked `// NOSONAR: typescript:S1128` indicating the team knew they were unused

### 4. `err` variable (ReportsPage.tsx)

**Why it was safe to remove:**
- I introduced this in V247 when I changed `console.error("Download failed:", err)` to `toast.error("Download failed.")`
- The `err` variable was kept in the catch clause but no longer used in the body
- Changed `catch (err)` to `catch` (no binding)

### 5. `coreApi` and `digitalTwinApiClient` (fullApi.ts)

**Why they were safe to remove:**
- `coreApi` was imported as `api as coreApi` from "./api" — never referenced (grep count = 1)
- `digitalTwinApiClient` was imported as `api as digitalTwinApiClient` from "./digitalTwinApi" — never referenced (grep count = 1)
- `ApiError` from the same import WAS kept (used on lines 84, 107)
- `getApiKey` from the adjacent import WAS kept (used on lines 67, 168)

### 6. `t` from useTranslation (3 pages)

**Why it was safe to remove:**
- CADSettingsPage.tsx: 0 `t()` calls (grep verified)
- DigitalTwinPage.tsx: 0 `t()` calls (grep verified)
- ReportGeneratorPage.tsx: 0 `t()` calls (grep verified)
- Kept `useTranslation()` hook call (without destructuring) to maintain language context subscription

---

## What Was NOT Removed (and Why)

| Code | File | Reason for Keeping |
|---|---|---|
| `selectedDetector` state | FireAlarmDesigner.tsx | Setter is called in 3 places; value is for a partially-implemented feature |
| `apiLoading` state | EngineeringPage.tsx | Setter is called in 4 places; value is for a partially-implemented UI |
| `apiError` state | EngineeringPage.tsx | Setter is called in 4 places; value is for a partially-implemented UI |
| `_zoomLevel` state | FireAlarmDesigner.tsx | Underscore-prefixed (intentionally unused per ESLint convention) |
| `console.log` in services | digitalTwinApi.ts, dataService.ts | Already stripped by terser in production; useful for dev debugging |
| `any` types in mockups | Various mockup components | Not in production routes; fixing adds no production value |
