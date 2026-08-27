# BAZspark Codebase Architecture Audit

**Date:** 2026-08-27
**Auditor:** `improve-codebase-architecture` skill (automated, static analysis)
**Scope:** Module/package architecture of the whole monorepo (Python engine + React SPA),
*not* the LLM/agent subsystem (covered separately in `AGENT_ARCHITECTURE_AUDIT_REPORT.md`).

---

## Executive Verdict

**OVERALL RISK: MEDIUM-HIGH** — The documented architecture (layered tiers, SSoT constants,
deep-module boundaries) is sound on paper, but the *implementation* has drifted from it:

- The single most safety-critical rule — **all NFPA 72 constants centralize in
  `fireai/constants/nfpa72.py`** (`ARCHITECTURE.md` §2) — is followed by only **7 of 130**
  `fireai/core` modules. The other **123 define or recompute constants locally**, creating
  real calculation-drift risk in a life-safety system.
- There are **19 modules ≥1500 LOC** (god modules), the largest being
  `backend/services/revit_service.py` at **2831 LOC**.
- **Two orphaned modules** (1,648 + 4 KB) have zero importers and are dead weight.
- A **redundant kernel/model lineage** (`fireai_kernel_v30`, `qomn_kernel`,
  `v131_kernel_extensions`, `models_v21`) indicates copy-paste evolution rather than stable seams.
- Frontend boundary enforcement exists (`lint:boundaries` via `dependency-cruiser`, wired into
  `npm run ci`), but the `src/packages` tree contains only the `example` package, so the rule
  is effectively unexercised by real code. **Python has no equivalent boundary/cycle guard.**

No CRITICAL findings — deterministic guards and the HMAC audit trail (see agent audit) still
protect the core pipeline. But the structural debt above raises change-risk and review cost.

---

## Methodology

- Static enumeration of Python modules by LOC (`Get-ChildItem` + line count).
- Import reachability: for each module, count files referencing its base name
  (`rg` across the repo, excluding self/tests) to detect orphans.
- SSoT adherence: count `fireai/core` modules importing `fireai.constants.nfpa72`.
- Boundary state: inspect `package.json` scripts and `src/packages` contents.
- Manual review of `ARCHITECTURE.md`, `AGENTS.md`, and `frontend/src/packages/README.md`.

---

## Metrics Snapshot

| Metric | Value |
|---|---|
| `fireai/core` modules (non-test) | 130 |
| …importing SSoT `nfpa72` constants | 7 |
| …defining/recomputing constants locally | 123 |
| Python modules ≥1500 LOC | 19 |
| Python modules ≥2000 LOC | 9 |
| Orphaned `fireai/core` modules (0 importers) | 2 |
| Frontend `src/packages` real packages | 0 (`example` only) |
| Python boundary/cycle enforcement in CI | none |

---

## Findings

### F-1 — SSoT constant fragmentation (HIGH · safety-critical)

| Field | Value |
|---|---|
| **Severity** | HIGH |
| **Area** | `fireai/core`, `fireai/conduit`, `fireai/bridges` |
| **Mechanism** | Local redefinition / recomputation of NFPA 72 constants |
| **Root cause** | `ARCHITECTURE.md` §2 mandates `fireai/constants/nfpa72.py` as the only source of
  engineering constants, but only **7/130** `fireai/core` modules import it; 123 compute or
  hardcode their own. |
| **Evidence** | `fireai/constants/nfpa72.py` is the documented SSoT. Reachability probe:
  `fireai/core/*.py` non-test = 130; importing `nfpa72` = 7. Overlapping NFPA-72 logic also
  lives in six sibling modules: `nfpa72_calculations.py`, `nfpa72_coverage.py`,
  `nfpa72_engine.py`, `nfpa72_models.py`, `nfpa72_schemas.py`, `nfpa72_technology_dispatcher.py`. |
| **Confidence** | HIGH |
| **Impact** | Two modules computing the same spacing/voltage threshold differently = silent
  calculation drift. In a life-safety engine this is the single most dangerous structural defect. |
| **Recommended fix** | (1) Move all constant definitions into `fireai/constants/nfpa72.py` (+ `nec.py`).
  (2) Re-point the highest-risk modules (`voltage_drop.py`, `nfpa72_calculations.py`,
  `nfpa72_coverage.py`) to import from SSoT. (3) Add a **CI guard** (a `pytest` import check or
  `ruff` rule) that fails the build if a `fireai/core/**` module defines a constant already
  present in `nfpa72.py`. |

### F-2 — Orphaned / dead modules (MEDIUM · low effort, quick win)

| Field | Value |
|---|---|
| **Severity** | MEDIUM |
| **Area** | `fireai/core` |
| **Mechanism** | Modules with zero importers still shipped and listed in `pyproject.toml` |
| **Root cause** | Versioned copy-paste left behind after supersession. |
| **Evidence** | `fireai/core/qomn_fire_v4_fail_loud.py` — **1648 LOC**, **0 importers** (referenced only in
  `docs/archive/PROJECT_INDEX.md` and stale `pyproject.toml` package lists).
  `fireai/core/csd_generator.py` — **3.9 KB**, **0 importers**. |
| **Confidence** | HIGH |
| **Recommended fix** | Delete both files; remove their stale entries from `pyproject.toml` (lines ~293, ~459 for
  `qomn_fire_v4_fail_loud`). Confirm via `rg` that no dynamic `importlib` path references remain. |

### F-3 — Redundant kernel / model lineage (MEDIUM)

| Field | Value |
|---|---|
| **Severity** | MEDIUM |
| **Area** | `fireai/core` |
| **Mechanism** | Parallel, version-suffixed implementations of the same concern |
| **Evidence** | `fireai_kernel_v30.py` (1563 LOC, 5 refs), `qomn_kernel.py` (1317 LOC, 25 refs),
  `v131_kernel_extensions.py` (667 LOC, 2 refs); `models_v21.py` (2224 LOC, 20 refs) is the
  lone models module yet carries a versioned name — a signal of churn rather than a stable seam. |
| **Impact** | Readers cannot tell which kernel is canonical; refactors must touch three places;
  behavior may diverge between callers. |
| **Recommended fix** | Pick one kernel as canonical (e.g. `qomn_kernel`), reroute `fireai_kernel_v30` /
  `v131_kernel_extensions` callers to it, then deprecate the others with a thin shim. Rename
  `models_v21.py` → `models.py` once consolidated. |

### F-4 — God modules (HIGH · maintainability / review risk)

| Field | Value |
|---|---|
| **Severity** | HIGH (for change-safety, not runtime) |
| **Evidence (top 10 of 19 ≥1500 LOC)** | |
| | `backend/services/revit_service.py` — 2831 |
| | `backend/services/workflow_service.py` — 2308 |
| | `fireai/core/digital_twin.py` — 2266 |
| | `fireai/core/models_v21.py` — 2224 |
| | `fireai/integration/ar_vr_visualizer.py` — 2159 |
| | `qomn_fire_generator.py` — 2064 |
| | `fireai/core/qomn_self_healing_engine.py` — 2059 |
| | `fireai/core/bps_allocator.py` — 1947 |
| | `fireai/core/pipeline.py` — 1933 |
| | `fireai/core/multi_floor_orchestrator.py` — 1859 |
| **Impact** | Single-file changes ripple across huge diffs; unit-test isolation is hard; review
  quality drops; merge-conflict likelihood rises. |
| **Recommended fix** | Decompose along existing seams using the **deep-module pattern** already documented for the
  frontend (`frontend/src/packages/README.md`): one small entry point (`index.ts`/`client.ts`)
  over a private `lib/`. Start with `revit_service.py` as a template, then replicate. |

### F-5 — No Python module-boundary / cycle enforcement (MEDIUM)

| Field | Value |
|---|---|
| **Severity** | MEDIUM |
| **Area** | Whole Python backend |
| **Mechanism** | No automated guard against import cycles or cross-package private imports |
| **Evidence** | `package.json` wires `lint:boundaries` (`depcruise --ts-pre-compilation-deps src/packages`)
  into `npm run ci` — but this covers **frontend only**. No `import-linter`, `pydeps`, or
  cycle-check step exists for `fireai`, `core`, `qomn_fire`, `facp_system`, `backend`. |
| **Impact** | Dependency cycles between Python packages are possible and would only surface as runtime
  `ImportError` during startup — exactly the kind of failure R11 ("no assumptions, always verify")
  is meant to prevent. |
| **Recommended fix** | Add `import-linter` (with a `contracts` file) or a small `pytest` cycle detector over the
  Python top-level packages, gated in CI. Mirror the frontend `lint:boundaries` discipline. |

### F-6 — Deep-module discipline not adopted by real frontend code (LOW)

| Field | Value |
|---|---|
| **Severity** | LOW |
| **Area** | `frontend/src` |
| **Mechanism** | Boundary rule enforced but unexercised |
| **Evidence** | `src/packages` contains only `example/` (correct deep-module demo). All real UI lives in
  `components/`, `contexts/`, `pages/`, `engine/`, `domain/`, etc. with no entry-point boundaries,
  so `lint:boundaries` passes trivially (nothing to check). |
| **Impact** | The documented boundary rule provides no real protection until real code is structured as
  packages; accidental private-subfolder imports are currently free. |
| **Recommended fix** | Migrate one high-churn domain (e.g. `engine/` or `domain/`) into `src/packages/<name>/` with
  an `index.ts` entry point, or explicitly document the pattern as aspirational until then. |

---

## Positive Findings (no action required)

| # | Pattern | Evidence |
|---|---------|----------|
| P-1 | Frontend boundary tooling exists & is in CI | `package.json`: `lint:boundaries` → `depcruise ... src/packages`, in `ci` script |
| P-2 | Correct deep-module example shipped | `src/packages/example/{index.ts, lib/impl.ts, tests/}` matches `README.md` exactly |
| P-3 | Clear architectural intent documented | `ARCHITECTURE.md` (tiers, SSoT, QOMN-FIRE 5-layer, port map) and `AGENTS.md` |
| P-4 | Safety guards in core engine | HMAC audit trail + fail-loud design (see `AGENT_ARCHITECTURE_AUDIT_REPORT.md` P-05..P-08) |
| P-5 | Repo has mature CI/CD policy | `CI-CD-POLICY.md` (12 rules) enforced via AGENTS.md |

---

## Prioritized Roadmap

| Priority | Item | Effort | Risk reduced |
|---|---|---|---|
| **P1** (quick win) | F-2 remove dead modules + prune `pyproject.toml` | S (1–2h) | Cuts dead 1.65 MB; removes confusion |
| **P2** (safety-critical) | F-1 SSoT constant consolidation + CI import guard | M (1–2d) | Eliminates calculation-drift risk |
| **P3** | F-5 add Python boundary/cycle guard in CI | M (0.5–1d) | Prevents startup `ImportError` / cycles |
| **P4** | F-3 consolidate kernel/model lineage | M (1–2d) | Single source per concern, less churn |
| **P5** | F-7 (folded into F-1) de-duplicate `nfpa72_*` modules | M | Removes overlapping logic |
| **P6** | F-4 decompose one god module as template (`revit_service.py`) | L (2–4d) | Reusable decomposition pattern |
| **P7** | F-6 adopt deep-module pattern in real frontend code | M | Real boundary protection |

---

## Appendix — reproduction commands

```powershell
# SSoT adherence
$core = (Get-ChildItem fireai/core/*.py -Exclude *test*).Count
$imp  = (rg -l "constants.nfpa72|constants\.nfpa72" fireai/core --glob '!*test*' --glob '*.py').Count
"core modules: $core | import SSoT: $imp | local: $($core-$imp)"

# Orphan detection (module with 0 external references)
# for each base name X:  rg -l "\bX\b" --glob '*.py' .  | ? { $_ -notmatch "X.py" }

# God modules
Get-ChildItem -Recurse -Filter *.py | ? { -not $_.FullName.Contains('node_modules') } |
  % { [pscustomobject]@{LOC=(Get-Content $_.FullName).Count; Path=$_.FullName} } |
  ? { $_.LOC -ge 1500 -and $_.Path -notmatch 'test' } | Sort LOC -Desc | Select -First 25

# Frontend boundary wiring
Select-String -Path frontend/package.json -Pattern "boundaries|cruiser"
```

*Report generated by the `improve-codebase-architecture` skill — static analysis only; no code was modified.*
