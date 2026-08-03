# UI Baseline — 2026-08-03

> Snapshot of the production deployment state BEFORE the UI cleanup plan
> starts. Used as the rollback reference if any PR breaks the build.

## Repository State

- **Repo:** https://github.com/ahmdelbaz28-ux/BAZspark
- **main HEAD:** 98e70c8c (98e70c8ca7a35016add34390dd133dd3d010c8ba)
- **main HEAD subject:** fix: update all URLs and references to new Vercel deployment
- **main HEAD date:** 2026-08-03 10:14:55 +0000
- **Backup branch:** `backup/pre-ui-cleanup-20260803-102710`
  - URL: https://github.com/ahmdelbaz28-ux/BAZspark/tree/backup/pre-ui-cleanup-20260803-102710
  - SHA: same as main HEAD above
  - Purpose: rollback target if any subsequent PR breaks production

## Production Deployments

### 1. Vercel (primary production)

- **URL:** https://ba-zspark-tau.vercel.app/
- **Project ID:** prj_4woP4FCyUNNi1Ak90ixCgwknB6lg
- **Framework:** Vite
- **Build command:** `cd frontend && npm run build`
- **Output dir:** `frontend/dist`
- **Last deployment SHA:** 53687569c277a3308aa70f2cc667c8cbae5efb96
- **Status:** ✅ READY (HTTP 200)
- **Title served:** "BAZSPARK Digital Twin"
- **Theme color:** #070b12 (correct, modern)

### 2. HuggingFace Space (secondary — also serves backend)

- **URL:** https://ahmdelbaz28-bazspark.hf.space/
- **Container:** Docker (FastAPI + built frontend served via StaticFiles)
- **Dockerfile:** Multi-stage (Node builder → Python runtime)
- **Backend env var:** BAZSPARK_FRONTEND_DIST=/app/frontend_dist
- **Last sync:** Auto-synced from GitHub on every CI Build Gate success
- **Status:** ✅ HTTP 200 on /
- **Known issue:** /critical.css returns 401 (blocked by ApiKeyMiddleware)
  — to be fixed in a future PR
- **Title served:** "BAZSPARK Digital Twin"

### 3. GitHub Pages (LEGACY — STALE)

- **URL:** https://ahmdelbaz28-ux.github.io/BAZspark/
- **Build type:** legacy (from gh-pages branch)
- **gh-pages branch last commit:** 26afe763 (2026-07-01 16:18:50 +0300)
- **Status:** ❌ Serving frozen build from July 1
- **Title served:** "FireAI Digital Twin" (OLD BRANDING)
- **Theme color:** #0f172a (OLD COLOR)
- **Bundle:** /assets/index-DeUH5xqE.js (493309 bytes — STALE)
- **Action plan:** Disable in Phase 3 (PR #1)

### 4. Legacy Vercel URL

- **URL:** https://ba-zspark.vercel.app/
- **Status:** ⚠️ Serves older deployment (different SHA than tau domain)
- **Bundle:** /assets/index-DdZXLCsz.js (241521 bytes)
- **Action plan:** Clean up in Phase 9

## Branches Currently on GitHub

- main (active production)
- backup/pre-ui-cleanup-20260803-102710 (THIS BACKUP)
- backup/main-pre-full-merge-20260729-223415 (older backup)
- backup/main-pre-merge (older backup)
- backup/v214-pre-merge (older backup)
- gh-pages (frozen July 1 build — to be deleted in Phase 3)
- v0/professional-user-interface-35de0476 (2117 files diff from main)
- Multiple dependabot/* and fix/* branches

## Security Posture

- **Branch protection on main:** ❌ NOT ENABLED (will be fixed in Phase 2)
- **Pre-commit hooks:** ✅ Configured (ruff, mypy, bandit, gitleaks, pytest)
- **CI Build Gate:** ✅ Active on every PR to main
  - frontend-build (typecheck + production build)
  - frontend-tests (Vitest)
  - backend-tests (pytest)
- **SonarCloud:** ✅ Active
- **HuggingFace sync:** ✅ Conditional on CI Build Gate success

## Definition of Done for Phase 0

- [x] Backup branch created and pushed to GitHub
- [x] This baseline document committed to the backup branch
- [x] main HEAD SHA recorded for rollback reference
