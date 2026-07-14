# 01-IVV-Architecture
## Independent Verification & Validation — Architectural Assessment

**Auditor:** Kilo (IV&V authority, independent of development team)
**Target:** BAZspark/FireAI monorepo @ `ivv-certification-20260714113042` (based on `d8d4a094`)
**Date:** 2026-07-14

---

## 1. Repository Topology

The monorepo contains **1,907 tracked files** across ~25 top-level directories. The architecture is a multi-paradigm engineering platform with the following structural decomposition:

| Subsystem | Files | Role |
|---|---|---|
| `fireai/` | 263 | Core engine — NFPA 72 calculations, routing, acoustics, duct detection, HAC classification, audit trail |
| `frontend/` | 293 | React 18 + TypeScript + Tailwind + Vite SPA, served by FastAPI |
| `skills/` | 501 | 24+ AI agent skill packages (ETAP, electrical, docx, etc.) |
| `tests/` | 169 | Root-level test suite (7,133 test cases) |
| `backend/` | 102 | FastAPI application — 30+ routers, auth, middleware, DB |
| `docs/` | 154 | Documentation (mostly .md) |
| `deploy/` | 46 | Docker, Helm, Kubernetes deployment artifacts |
| `parsers/` | 22 | DXF, IFC, PDF, image parsing |
| `facp_distributed/` | 39 | Distributed Fire Alarm Control Panel cluster |
| `qomn_fire/` | 31 | QOMN fire subsystem |
| `marine/` | 40 | Marine engineering module |
| `others` | ~150 | Core, adapters, services, scripts, samples |

**Deployment target:** Hugging Face Spaces (Docker, port 7860). Also supports Docker Compose, Kubernetes/Helm (staging + production), and Vercel (frontend preview).

---

## 2. Architecture Pattern

**Pattern:** Monorepo with modular package discovery via setuptools.

**`pyproject.toml` `[tool.setuptools.packages.find]`** includes all runtime packages:
```
backend* fireai* core* parsers* facp_system* facp_distributed*
qomn_fire* qomn_conduit* integration* marine* adapters* services* skills*
```

**Excluded:** `tests* docs* deploy* todo-app* revit_samples* test_data* build* dist*`

The package installs as `cad-bim-integration-platform` (name in pyproject), but the user-facing name is "BAZSPARK" and "FireAI" in different contexts — a naming inconsistency with operational risk.

---

## 3. Backend Architecture

**Entry point:** `backend.app:app` (FastAPI application at `backend/app.py:426`)

**Boot sequence (lifespan, `app.py:347–411`):**
1. Read `FIREAI_SESSION_SECRET` — hard-fail `RuntimeError` if missing or <43 chars
2. Call `set_core_modules_loaded()` (health tracking)
3. Call `Config.validate_config()` — warns about missing `DATABASE_URL`/`NEO4J_PASSWORD`, does NOT fail

**Middleware stack (outer to inner, `app.py`):**
1. `SecurityHeadersMiddleware` — CSP, HSTS, X-Frame-Options, etc.
2. `CSRFMiddleware` — double-submit cookie pattern (disabled by `FIREAI_CSRF_DISABLED`)
3. `TrustedHostMiddleware` — host header validation
4. `ApiKeyMiddleware` — X-API-Key header or session cookie auth
5. Rate limiter (`slowapi`, per-IP with optional Redis backend)
6. `DeprecationHeadersMiddleware` — `/api/v1/` sunset headers

**Router registration (`app.py:641–662`):**
Defensive `_safe_include_router` loop catches import errors and logs warnings. 30+ routers registered.

**Database:** Dual-mode SQLite (local dev) / PostgreSQL (production) via SQLAlchemy + Alembic. Single migration (`001_initial_schema`). Qdrant (vector) and Neo4j (graph) as optional secondary stores.

---

## 4. Frontend Architecture

**Stack:** React 18 + TypeScript + Tailwind CSS v4 + Vite 8. 
**Entry:** `frontend/index.html` → `frontend/src/main.tsx` → `App.tsx`.
**Build output:** Static files at `frontend/dist/`, served by FastAPI `StaticFiles` at `/` and `/assets`.

**Client structure (`frontend/src/`, 14 subdirectories):**
- `pages/` — Route components (monitor, reports, auth, settings, admin, etc.)
- `components/` — Reusable UI (Radix-based, shadcn-style)
- `services/` — API client layer
- `store/` — State management (React Context)
- `hooks/`, `utils/`, `lib/`, `types/` — Supporting code
- `i18n/` — Internationalization
- `contexts/` — React contexts (auth, theme, etc.)
- `styles/` — Global CSS + Tailwind
- `engine/` — Engineering calculation visualization (Three.js)
- `.generated/` — TypeScript types from OpenAPI spec

---

## 5. Build & Deploy Architecture

### Build Chain (Docker multi-stage, `Dockerfile`):
```
Stage 1 (frontend-builder):   Node 20 → npm ci → vite build
Stage 2 (python-builder):     Python 3.12 → pip install requirements.txt
Stage 3 (runtime):            Python 3.12-slim + LibreDWG + app code + frontend dist
```

### CI/CD Pipeline (`.github/workflows/ci.yml`):
| Gate | Step | Blocking? | Evidence |
|---|---|---|---|
| 1 | Ruff lint | YES | `--exit-non-zero-on-fix` |
| 1 | MyPy type check | **NO** (`\|\| true`) | 434+ pre-existing type errors accepted |
| 1 | Bandit security scan | PARTIAL (HIGH only) | MEDIUM/LOW ignored |
| 2 | pytest (full) | YES (with caveat: 137=SIGKILL=pass) | Coverage disabled in CI |
| 3 | Property-based tests | YES | Separate gate |
| 4 | Frontend build | YES | npm run build |
| 4b | Playwright visual | YES | Headless Chromium |
| 5 | Python dep audit | YES (HIGH blocked) | pip-audit |
| 5 | Frontend dep audit | YES (HIGH blocked) | npm audit |
| 6 | Docker build+test | YES | Build + health check |

### Deployment Targets:
- **Hugging Face Spaces** (auto-sync via `sync-to-hf.yml` on push to `main`)
- **GitHub Container Registry** (via `deploy.yml`)
- **Kubernetes** (staging + production via Helm, `deploy.yml`)
- **Vercel** (preview deployments, `vercel-preview.yml`)

---

## 6. Key Architectural Findings

### Finding ARC-01: Version divergence
The project has **three different version identifiers**:
- Package metadata: `1.55.0` (via `SETUPTOOLS_SCM_PRETEND_VERSION`)
- Frontend build env `VITE_APP_VERSION`: `8.1.0`
- Latest git tag: `v1.58.0-v214-final`
- **Risk:** Confusing for operators; release tooling may pick wrong version.

### Finding ARC-02: Editable install broken
`pip install -e .` fails without `SETUPTOOLS_SCM_PRETEND_VERSION=1.55.0` because `setuptools_scm` cannot parse tag `v1.58.0-v214-final`. The workaround is documented in pyproject comments but:
- Never mentioned in README, INSTALLATION.md, or QUICKSTART.md
- Dockerfile uses `requirements.txt` instead, which avoids the issue (but diverges from pyproject)

### Finding ARC-03: Dependency drift between install paths
**CONTRADICTION:** `pyproject.toml` is the authoritative manifest, but `Dockerfile` installs via `requirements.txt`. These two files disagree on lower bounds for 6+ packages:
| Package | pyproject.toml | requirements.txt |
|---|---|---|
| fastapi | >=0.138.0 | >=0.100.0 |
| pydantic-settings | >=2.14.2 | >=2.0.0 |
| python-multipart | >=0.0.27 | >=0.0.6 |
| pyjwt[crypto] | >=2.13.0 | >=2.6.0 |
| requests | >=2.34.0 | >=2.28.0 |
| websockets | >=12.0.0 | >=10.0.0 |

### Finding ARC-04: pyproject URLs point to wrong repo
`[project.urls]` points to `github.com/fireai/platform` (404) and `fireai.org` (unverified). The actual repo is `ahmdelbaz28-ux/BAZspark`. SBOM generators and supply-chain tooling will produce incorrect provenance.

### Finding ARC-05: Skills packaged into production wheel
`skills/` (501 files) is included in `[tool.setuptools.packages.find]` but not excluded from the production wheel. Skills data, scripts, and reference files ship to PyPI. No clear separation between development-only and production-required packages.

---

*This document was independently produced by Kilo IV&V. All evidence captured by execution — see `evidence/` directory for logs.*
