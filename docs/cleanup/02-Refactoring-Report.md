# 02 — Refactoring Report

**Project:** BAZspark v1.55.0
**Refactoring Date:** 2026-07-13

---

## Refactoring Principle

**Stability over optimization.** Every refactoring decision was evaluated against:
1. Does this change behavior? → If yes, DON'T do it
2. Is the code proven unused? → If no, DON'T remove it
3. Can I verify no regression? → If no, DON'T change it

---

## Refactoring Actions

### 1. Dead Function Removal — ContextPanel.tsx

**Before:**
```typescript
import { useEffect, useMemo, useState } from "react";

function getHelpContextId(
    selection: ContextPanelSelection | null,
    contextId?: HelpTopicId | string,
): HelpTopicId | string {
    if (selection?.helpTopicId) return selection.helpTopicId;
    if (contextId) return contextId;
    if (selection?.type === "project") return "projects.manage";
    return "fire-alarm.detector-placement";
}
```

**After:**
```typescript
import { useEffect, useState } from "react";
// getHelpContextId removed — was never called
```

**Why safe:** `getHelpContextId` was defined on line 61 but:
- Never called within the file (grep verified)
- Never exported (no `export` keyword)
- Never imported by any other file (grep across `src/` = 0 results)

`useMemo` was imported but never called in the file.

### 2. Unused Import Removal — AICopilot.tsx

**Before:** 19 lucide-react imports (7 unused)
**After:** 12 lucide-react imports (0 unused)

**Why safe:** Each removed import was verified via grep — count = 1 (only on the import line). The icons were imported but never referenced in JSX.

### 3. Catch Block Cleanup — ReportsPage.tsx

**Before:**
```typescript
} catch (err) {
    toast.error("Download failed. Please try again.");
}
```

**After:**
```typescript
} catch {
    toast.error("Download failed. Please try again.");
}
```

**Why safe:** `err` was declared but never used in the catch body. The toast shows a generic message, not the error details.

### 4. Translation Hook Cleanup — 3 Pages

**Before:**
```typescript
const { t } = useTranslation();
```

**After:**
```typescript
useTranslation();
```

**Why safe:** `t` was destructured but never called (0 `t()` calls verified via grep). Kept the `useTranslation()` hook call to maintain language context subscription. Removing the hook entirely could affect re-render behavior on language change.

### 5. Unused API Client Imports — fullApi.ts

**Before:**
```typescript
import { ApiError, api as coreApi } from "./api";
import { getApiKey } from "./apiKey";
import { api as digitalTwinApiClient } from "./digitalTwinApi";
```

**After:**
```typescript
import { ApiError } from "./api";
import { getApiKey } from "./apiKey";
```

**Why safe:** `coreApi` and `digitalTwinApiClient` were imported but never referenced (grep count = 1, import line only). `ApiError` (used on lines 84, 107) and `getApiKey` (used on lines 67, 168) were kept.

---

## What Was NOT Refactored (and Why)

1. **EngineeringPage `apiLoading`/`apiError`** — setters are called (lines 115, 116, 127, 132). Removing the state would break the setter calls. This is a partially-implemented feature.

2. **FireAlarmDesigner `selectedDetector`** — setter is called in 3 places (lines 167, 176, 295). Same pattern as above.

3. **`any` types in mockup components** — not in production routes. Fixing adds no production value.

4. **`console.log` in services** — already stripped by terser in production build. Useful for dev debugging.

5. **Files >500 LOC** — refactoring these risks regressions for no behavioral benefit. Documented for future work.

---

## Refactoring Safety Protocol

Every change followed this protocol:

1. **Analyze** — grep for all references across `src/`
2. **Verify** — confirm the code is truly unused (count = 1, import line only)
3. **Edit** — make the smallest possible change
4. **Typecheck** — `npm run typecheck` must pass
5. **Lint** — `npm run lint` must show 0 errors
6. **Build** — `npm run build` must succeed
7. **Test** — `npm run test` must show 140/140
8. **Commit** — one logical change = one commit
9. **If ANY failure** — rollback and analyze

**No rollbacks were needed.** All changes passed validation on the first try.
