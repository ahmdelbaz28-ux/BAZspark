# Phase 1 — Local Environment Baseline Results

> Verified that the current main HEAD builds and tests cleanly
> BEFORE starting any UI cleanup work.
>
> Date: 2026-08-03 10:31:46 UTC
> main HEAD: 98e70c8c — fix: update all URLs and references to new Vercel deployment

## Tooling Versions

- **Node.js:** v24.18.0 (CI uses 22, .nvmrc says 20 — all compatible)
- **npm:** 11.16.0
- **Python:** 3.12.13 (for backend tests later)
- **Vite:** 8.2.0
- **Vitest:** 4.x

## Test Results Summary

| Step | Command | Result | Duration |
|---|---|---|---|
| 1 | `npm ci --no-audit --no-fund --ignore-scripts` | ✅ Pass (782 packages) | 13s |
| 2 | `npm run typecheck` | ✅ Pass (0 errors) | ~5s |
| 3 | `npm run lint` | ✅ Pass (0 errors, 82 warnings) | ~10s |
| 4 | `npm run test` (Vitest) | ✅ Pass (353/353 tests) | 35.86s |
| 5 | `npm run build` | ✅ Pass (234 files in dist/) | 7.82s |
| 6 | `npm run dev` server | ✅ Responds HTTP 200 | 324ms startup |

## Lint Warnings Breakdown (82 total — all non-blocking)

- ~50 warnings: `@typescript-eslint/no-unused-vars` in test files
  (test props named `props` that aren't used — typical test boilerplate)
- ~10 warnings: `@typescript-eslint/no-explicit-any` in `src/services/fullApi.ts`
  (OpenAPI-generated code, expected)
- ~22 warnings: similar minor issues in prototype/test files

**None of these warnings are blockers.** CI Build Gate treats warnings as
non-fatal (only errors fail the gate).

## Build Output Verification

- `frontend/dist/index.html` serves:
  - `<title>BAZSPARK Digital Twin</title>` ✅ (modern branding)
  - `<meta name="theme-color" content="#070b12">` ✅ (modern color)
- `frontend/dist/assets/` contains 234 files totaling 9.5 MB
- Main bundle: `index-CiYuemdX.js` (241.52 kB / 72.94 kB gzip)
- Source maps: emitted as hidden (production-correct)

## Build Warnings (non-blocking)

- 3 `INEFFECTIVE_DYNAMIC_IMPORT` warnings for gsap plugins (CustomEase,
  DrawSVGPlugin, SplitText) — known issue, documented in vite.config.ts
  comments. Does not affect runtime.
- 1 `PLUGIN_TIMINGS` warning for vite:terser — informational only.

## Conclusion

✅ **The codebase is in a healthy state and ready for the UI cleanup plan.**

All CI Build Gate checks would pass on the current main HEAD. We can
proceed with Phase 2 (branch protection) and then start opening PRs
for the actual cleanup work (Phases 3-10).

## How to Reproduce

```bash
cd /home/z/my-project/analysis/BAZspark
git checkout main
git pull origin main --ff-only
cd frontend
npm ci --no-audit --no-fund --ignore-scripts
npm run typecheck
npm run lint
npm run test
npm run build
```

Expected total runtime: ~75 seconds (excluding npm ci).
