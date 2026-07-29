# 02 — Hidden Bugs

**Project:** BAZspark v1.55.0
**Audit Date:** 2026-07-13

---

## Hidden Bugs Found & Fixed

### Bug 1: PageErrorBoundary Dead Code (V250)
- **Location:** `src/components/core/PageErrorBoundary.tsx`
- **Bug:** Component was defined (124 lines) but never imported outside test files
- **Impact:** Any page-level error crashed the entire application via the top-level ErrorRecovery boundary, instead of being isolated to the page
- **Root Cause:** The component was created during V193 but never wired into App.tsx routing
- **Fix:** Imported and wrapped all protected routes in `<PageErrorBoundary>`

### Bug 2: SelfHealingPage Null Crash (V250)
- **Location:** `src/pages/SelfHealingPage.tsx:203`
- **Bug:** `cb.utilization_pct.toFixed(0)` — no null guard
- **Impact:** If the backend omits or nulls `utilization_pct`, the page crashes with "Cannot read properties of null (reading 'toFixed')"
- **Root Cause:** Assumed backend always returns the field
- **Fix:** `typeof cb.utilization_pct === "number" ? ... : "—"`

### Bug 3: simpleStore Boot Crash (V250)
- **Location:** `src/store/simpleStore.ts:173`
- **Bug:** `localStorage.getItem("nexus_project_state")` at module-load time, not in try/catch
- **Impact:** In sandboxed iframes (e.g., embedded previews) or when cookies are blocked, `localStorage.getItem()` throws `SecurityError`. This crashes the ENTIRE app at boot — before React even mounts.
- **Root Cause:** Browser API access without SSR/sandbox guard
- **Fix:** Wrapped in `try { ... } catch { console.warn(...); }` with fallback to `initialState`

### Bug 4: MiningPage Memory Leak (V250)
- **Location:** `src/pages/MiningPage.tsx:421`
- **Bug:** `URL.createObjectURL(blob)` called but `URL.revokeObjectURL(url)` never called
- **Impact:** Each download click creates a Blob URL that's never freed. Repeated downloads leak memory.
- **Root Cause:** Missing cleanup
- **Fix:** `setTimeout(() => URL.revokeObjectURL(url), 100)` after click

### Bug 5: ReportsPage Memory Leak (V250)
- **Location:** `src/pages/ReportsPage.tsx:134`
- **Bug:** Blob URL stored in `ahjDownloadUrl` state, never revoked on unmount or regeneration
- **Impact:** Each AHJ submittal generation creates a new Blob URL; old ones are never freed
- **Root Cause:** Missing useEffect cleanup
- **Fix:** Added `useEffect(() => () => { if (ahjDownloadUrl) URL.revokeObjectURL(ahjDownloadUrl); }, [ahjDownloadUrl])`

### Bug 6: ProjectsPage Silent Failures (V250)
- **Location:** `src/pages/ProjectsPage.tsx:105-136`
- **Bug:** `handleCreate`, `handleDelete`, `handleSync` — when API returns null (failure), no toast/error shown
- **Impact:** User clicks "Create Project", nothing happens, no feedback. User doesn't know if it worked or failed.
- **Root Cause:** Missing error feedback
- **Fix:** Added `toast.error()` for failures, `toast.success()` for success

### Bug 7: No ChunkLoadError Recovery (V250)
- **Location:** `src/main.tsx`
- **Bug:** When a stale deployment causes a chunk 404 (user has old index.html, new chunks have different hashes), the app shows a full-screen error view
- **Impact:** User must manually reload the page
- **Root Cause:** No global error handler for chunk load failures
- **Fix:** Added `window.addEventListener("error", ...)` that detects `ChunkLoadError` and auto-reloads once

---

## Hidden Bugs NOT Found (Verified Safe)

- ✅ No hydration mismatches (SPA, no SSR)
- ✅ No state corruption (React state is component-scoped)
- ✅ No database inconsistency (backend uses parameterized queries)
- ✅ No broken API contracts (Pydantic models validate inputs)
- ✅ No session expiration bugs (AuthContext re-checks on focus)
- ✅ No token refresh bugs (HttpOnly cookie, no JS token handling)
