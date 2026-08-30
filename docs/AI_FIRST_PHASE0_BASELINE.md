# AI_FIRST_PHASE0_BASELINE.md

**BAZspark — AI-FIRST / CHAT-FIRST ENGINEERING WORKSTATION**
**Phase 0 — Repository Forensic Baseline**

---

## 0. REPOSITORY STATE (VERIFIED EVIDENCE)

| Item | Value |
|---|---|
| Remote | `https://github.com/ahmdelbaz28-ux/BAZspark.git` |
| Branch | `main` |
| HEAD | `4b7a8a0d6dba170b6bf5272c370fe86eb08d7fe0` |
| Working tree | **DIRTY (1 file)**: `M docs/assets/banner/hero-banner.png` (binary asset, unrelated to code — documented baseline deviation) |
| Note | Workspace metadata claimed HEAD `a3c516c3`; actual repository HEAD is authoritative (`4b7a8a0d`). |

No source code was modified during Phase 0.

---

## 1. CURRENT ARCHITECTURE (AS-INSPECTED)

### 1.1 Backend (Python / FastAPI)

```
backend/
├── app.py                      # FastAPI application assembly
├── auth.py                     # has_permission(), authentication helpers
├── rbac.py                     # Role{ADMIN,ENGINEER,VIEWER} + ~35 granular Permissions
├── api_keys.py                 # validate_api_key()
├── database.py                 # DB layer; tables: project_revisions, command_executions, domain_events (~L880–931)
├── db_models.py / db_service.py / multi_db_service.py
├── security_middleware.py / security_csrf.py / session_store.py / session_secret.py
├── limiter.py                  # slowapi rate limiting
├── audit_integrity_helper.py   # audit trail integrity
├── admin_protection.py / request_context.py / response.py / env_validator.py
├── routers/                    # 42 routers (see §1.4)
├── services/
│   ├── llm_service.py          # ping_provider(), LLM provider abstraction
│   └── workflow_service.py     # LangGraph FireAI workflows (2305 lines)
└── core/                       # ★ AGENT EXECUTION SPINE
    ├── capability_registry.py  # CapabilityDefinition + default_capability_registry
    ├── command_bus.py          # DomainCommand, AuthenticatedPrincipal, default_command_bus, OCC revisions
    ├── context_resolver.py     # bounded context packets (≤1500 token budget)
    ├── workflow_engine.py      # EphemeralStateOverlay + WorkflowExecutor (DAG, dry-run, rollback)
    └── state_store.py          # CommandStateStore persistence adapter (SQLite/PostgreSQL)
```

### 1.2 Frontend (React + Vite + TypeScript + Tailwind)

```
frontend/src/
├── App.tsx                          # Router config — ALL routes defined here (~90 lazy-loaded pages)
├── main.tsx                         # BrowserRouter, QueryClient, ThemeProvider
├── contexts/
│   ├── AIControllerContext.tsx      # Agent run state (preview/approve/revision) — IN-MEMORY ONLY
│   ├── AgentSettingsContext.tsx     # LLM provider/model/key/skills/governance config
│   └── AuthContext.tsx / ThemeContext.tsx
├── hooks/
│   ├── useLlmChat.ts                # Chat hook (SSE streaming via /llm/chat/stream)
│   ├── useWebSocketStream.ts        # Generic WS hook (sequence lock, batching)
│   └── useVoiceControl.ts           # Voice/microphone input
├── components/
│   ├── ai/                          # AskAiButton.tsx, AskAiSheet.tsx, ExplainButton.tsx
│   ├── ui/WorkflowActionCard.tsx    # Approval card UI (currently test-only usage)
│   └── auth/RouteGuard.tsx          # Route protection
└── pages/                           # ~90 page components (engineering surfaces)
```

### 1.3 Agent Execution Spine (EXISTING — REUSE)

`backend/routers/agent_ws.py` (1229 lines) implements the deterministic orchestration loop:

```
User Intent (WS frame)
→ Context Resolution (bounded ≤1500 tokens)
→ Capability Discovery (scope-filtered)
→ Dry-Run DomainCommand (isDryRun=True, risk-classified)
→ Preview frame to client (ai_preview / ai_electrical_preview / ai_hydraulic_preview /
   ai_battery_preview / ai_composite_preview)
→ User Approval (ai_approve / ai_approve_composite)
→ OCC Check (expectedRevision vs current; CONCURRENCY_CONFLICT on mismatch)
→ Deterministic Commit (revision N → N+1, single DB transaction)
→ DomainEvent + Audit Reference emitted (ai_committed / ai_composite_committed)
```

WS message types dispatched: `response`, `ping`, `ai_intent`/`intent_submit`,
`ai_electrical_intent`, `ai_battery_intent`, `ai_hydraulic_intent`,
`ai_composite_intent`, `ai_approve_composite`, `ai_approve`/`command_approve`,
`user_mutate`/`manual_edit`.

WS security controls already present:
- Header/subprotocol-based key extraction (S-06 fix — no keys in query strings)
- Origin allow-list validation (`ALLOWED_ORIGINS`)
- RBAC gate: `Permission.CALCULATION_EXECUTE` required
- Nonce replay protection (`_seen_agent_nonces`)
- Newest-wins agent registration (VERIFY-003 fix — rogue socket teardown)
- Heartbeat (25s ping / 30s timeout) + periodic API-key revalidation
- Pending-future cleanup on disconnect

### 1.4 Router Inventory (42 routers)

`admin_config, agent_ws, analyze, api_keys, aps, audio, auth, autocad, billing, cad,
conflicts, connections_v2, connections, devices, digital_twin, dwg, elements,
engineering_copilot, environment, etap, experimental_services, exports, facp,
fds_webhook, health, llm, marine, memory, mining, monitor, multi_db, projects, qomn,
rbac_admin, reports, revit_api, revit, self_healing, settings, sync, v2, workflow`

### 1.5 Registered Capabilities (capability_registry.py — EXACT LIST)

| Capability ID | Category | Risk Class | Required Scopes |
|---|---|---|---|
| `spatial.place_devices` | spatial | MEDIUM | spatial:write |
| `compliance.verify_detector_spacing` | compliance | LOW | compliance:read |
| `electrical.calculate_voltage_drop` | electrical | ENGINEERING_MUTATION | electrical:write |
| `hydraulics.solve_darcy_weisbach` | hydraulics | ENGINEERING_MUTATION | hydraulics:write |
| `electrical.calculate_battery` | electrical | ENGINEERING_MUTATION | electrical:write |

### 1.6 Workflow Engine Evidence (workflow_engine.py)

- `EphemeralStateOverlay`: in-memory dry-run projections, **0 DB leakage**.
- `WorkflowExecutor.execute(...)`: supports `is_dry_run`, `workflow_id`,
  `correlation_id`, `auto_rollback_on_warning`, `governance_policy`,
  `on_step_progress` callback, strict **all-or-nothing rollback**, OCC
  `CONCURRENCY_CONFLICT` detection, atomic composite commit
  (`state_store.commit_composite_transaction`).

### 1.7 Persistent Workflow State (workflow_service.py)

- LangGraph-based FireAI workflow service (2305 lines).
- **Persistent checkpoints**: `AsyncSqliteSaver` at
  `data/checkpoints/workflow_checkpoints.db` (in-memory `MemorySaver` was
  deliberately removed — life-safety rationale documented in source).
- `resume_from_checkpoint()` re-reads from SQLite → **survives process restart**.
- In-memory `self._workflows` dict does NOT survive restart (checkpoint path does).

---

## 2. TARGET ARCHITECTURE (TO-BE)

As specified by the master prompt:

```
USER → CHAT/AGENT CONTROL CENTER → INTENT INTERPRETATION → CONTEXT RESOLUTION
→ PLAN GENERATION → CAPABILITY DISCOVERY → EXECUTION POLICY
   ├─ AUTO APPROVAL MODE (with mandatory safety gates)
   └─ STEP-BY-STEP APPROVAL MODE
→ WORKFLOW/DAG EXECUTION → DETERMINISTIC CAPABILITIES → VALIDATION
→ CANONICAL PROJECT STATE → AUDIT TRAIL → CHAT RESPONSE + ARTIFACTS
```

The LLM is intent interpreter / planner / capability selector / coordinator /
summarizer — NEVER the calculator, truth source, or direct state mutator.
All engineering math remains in deterministic engines (fireai, facp_system,
qomn_fire, marine, mining, electrical/hydraulic calculators, CAD/BIM ops).

---

## 3. REUSE MAP (DO NOT REWRITE — REUSE AS-IS)

| Asset | File(s) | Reuse Role |
|---|---|---|
| Capability Registry | `backend/core/capability_registry.py` | Extend with import/export capabilities using same pattern |
| Command Bus + OCC | `backend/core/command_bus.py` | All mutations flow through it unchanged |
| Context Resolver | `backend/core/context_resolver.py` | Bounded-context packets reused per-intent |
| Workflow Executor (DAG) | `backend/core/workflow_engine.py` | Dry-run/rollback/governance/progress reused verbatim |
| State Store | `backend/core/state_store.py` | Canonical state + revisions reused |
| WS Orchestration Service | `backend/routers/agent_ws.py` | Extended (not replaced) with run-state + policy hooks |
| LangGraph Workflows | `backend/services/workflow_service.py` | Checkpoint/resume foundation for AgentRun persistence |
| Workflow REST API | `backend/routers/workflow.py` | Run lifecycle endpoints extended |
| LLM Service | `backend/services/llm_service.py` | Provider abstraction reused |
| RBAC | `backend/rbac.py` | Roles/permissions reused; new permissions added additively |
| Rate Limiter | `backend/limiter.py` | Applied to new upload/export endpoints |
| Audit Integrity | `backend/audit_integrity_helper.py` | Approval decisions appended here |
| Secure Uploads | `dwg.py`, `autocad.py`, `revit.py`, `revit_api.py`, `digital_twin.py`, `experimental_services.py` | Parsers reused behind capability facade |
| Real Exporters | `reports.py` (PDF/DXF/JSON/MD), `exports.py` | Reused behind capability facade |
| Chat Hooks | `useLlmChat.ts`, `useWebSocketStream.ts`, `useVoiceControl.ts` | Chat Control Center foundation |
| Approval Card | `components/ui/WorkflowActionCard.tsx` | Promoted from test-only to production approval UI |
| Agent Settings | `contexts/AgentSettingsContext.tsx` | Provider/model/key/skills surface reused |

---

## 4. CHANGE MAP (FILES TO MODIFY IN PHASES 1–6)

### Phase 1 — Agent Run / Execution Policy Foundation (backend)
| Action | File |
|---|---|
| CREATE | `backend/core/agent_run_store.py` — persistent AgentRun model (run_id, conversation_id, user_id, project_id, status enum PLANNING/READY/RUNNING/WAITING_APPROVAL/PAUSED/FAILED/CANCELLED/COMPLETED, plan, steps, pending_approval, recovery_state, artifacts, timestamps, audit_reference) |
| CREATE | `backend/core/execution_policy.py` — centralized policy evaluating execution_mode, risk_class, capability, project, principal, required_scope, mutation_type, reversibility, mandatory_review, governance_policy, environment → AUTO_APPROVED / REQUIRES_APPROVAL / MANDATORY_HUMAN_REVIEW / DENIED |
| MODIFY | `backend/routers/agent_ws.py` — wire policy evaluation before every dry-run/commit; persist run state transitions; add cancel/resume message types |
| MODIFY | `backend/services/workflow_service.py` — expose checkpoint-backed resume for agent runs |
| MODIFY | `backend/rbac.py` — ADDITIVE new permissions (e.g., `approval:grant`) if required |
| MODIFY | `backend/database.py` — AgentRun table migration (alembic) |
| CREATE | Tests: `backend/tests/test_agent_run_store.py`, `test_execution_policy.py`, `test_run_lifecycle.py` |

### Phase 2 — Chat Control Center (frontend)
| Action | File |
|---|---|
| MODIFY | `frontend/src/App.tsx` — Chat route becomes primary/default |
| MODIFY/CREATE | Chat Control Center component (extends AskAiSheet pattern) — Auto Approval toggle, attachment button, step timeline, approval cards (promote `WorkflowActionCard.tsx`), cancel/retry/resume, artifact display |
| MODIFY | `frontend/src/contexts/AIControllerContext.tsx` — hydrate run state from backend (refresh-safe) |
| MODIFY | `frontend/src/hooks/useWebSocketStream.ts` — reconnect + run-state resync |

### Phase 3 — Unified Import Orchestrator
| Action | File |
|---|---|
| CREATE | `backend/services/import_orchestrator.py` — format detection → importer selection → parse → validate → normalize → merge, reusing existing secure parsers |
| MODIFY | `backend/core/capability_registry.py` — register `project.import.dwg/dxf/rvt/pdf/json` capabilities |
| MODIFY | `backend/routers/agent_ws.py` — attachment upload path through orchestrator |

### Phase 4 — Unified Export Orchestrator
| Action | File |
|---|---|
| CREATE | `backend/services/export_orchestrator.py` — exporter selection, artifact validation & registration (artifact_id, filename, format, size, checksum, status) |
| MODIFY | `backend/core/capability_registry.py` — register `project.export.pdf/xlsx/dxf/json` capabilities |
| REPLACE (deprecate) | `backend/routers/projects.py` placeholder exporters (DXF/Revit-JSON/IFC marked "placeholder" — FAKE, must not be exposed as real) |

### Phase 5 — Legacy UI De-emphasis
| Action | File |
|---|---|
| MODIFY | `frontend/src/App.tsx` — classify routes: AGENT SURFACE / ADMIN / DIAGNOSTIC / LEGACY; Chat = default landing |

### Phase 6 — End-to-End Autonomous Workflows
| Action | File |
|---|---|
| MODIFY | Planner layer connecting NL instructions → multi-step DAGs (reusing `CompositeWorkflowDAG`) |
| CREATE | E2E tests (Playwright + backend integration) |

---

## 5. PROTECTED FILES (DO NOT MODIFY WITHOUT EXPLICIT STAGE AUTHORIZATION)

Deterministic engineering engines and safety-critical infrastructure:

```
fireai/                        # FireAI deterministic fire-protection engine
facp_system/                   # Fire Alarm Control Panel logic
facp_distributed/              # Distributed FACP
engineering_copilot/           # Engineering copilot domain logic
qomn_fire/ , qomn_conduit/     # QOMN fire/acoustics engines
marine/ , mining/              # Marine & mining verticals
revit_integration/ , revit_addin/ , revit_data/ , autocad_addin/
parsers/ , adapters/           # Import parsers (reuse-only)
core/models.py , core/database.py        # Universal Data Model (frozen dataclasses)
backend/core/command_bus.py              # OCC/revision authority
backend/core/state_store.py              # Canonical state authority
backend/core/workflow_engine.py          # Deterministic DAG executor (extend-only via params)
backend/auth.py , backend/rbac.py , backend/api_keys.py   # Security plane (additive changes only)
backend/security_middleware.py , backend/security_csrf.py , backend/session_store.py
backend/audit_integrity_helper.py        # Audit trail (append-only)
backend/limiter.py
.github/workflows/*            # CI/CD (R3 validation required before any edit)
```

Engineering formulas inside these modules are OUT OF SCOPE for all phases.

---

## 6. RISK REGISTER

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R-01 | No persistent AgentRun state — browser refresh/WS drop loses run context (frontend `AIControllerContext` is in-memory; backend has no run model) | **P0** | Phase 1 creates DB-backed AgentRun store; LangGraph checkpoint pattern proven in repo |
| R-02 | No centralized execution policy — approval decisions implicit in WS handler flow; no AUTO/MANUAL mode distinction; no MANDATORY_HUMAN_REVIEW class | **P0** | Phase 1 `execution_policy.py`; backend authoritative |
| R-03 | Placeholder exporters in `projects.py` (DXF/IFC/Revit-JSON labeled "placeholder") could be mistaken for real exports | **P1** | Phase 4 replaces/deprecates; never claim fake formats |
| R-04 | Approval binding: current `handle_approval` trusts client-supplied payload/expectedRevision without server-side pending-approval record | **P1** | Phase 1 binds approvals to persisted pending_approval records |
| R-05 | Cancel/pause do not exist for agent runs | **P1** | Phase 1 adds CANCELLED/PAUSED states + resume |
| R-06 | Imports not registered as capabilities — Agent cannot discover/select importers | **P2** | Phase 3 capability facade over existing parsers |
| R-07 | No artifact registration (checksum/integrity) for exports | **P2** | Phase 4 artifact registry |
| R-08 | Working tree dirty (hero-banner.png) — unrelated binary drift | **P3** | Documented; excluded from change control |
| R-09 | `_seen_agent_nonces` unbounded-growth guard clears entire set at 5000 (replay window reset) | **P3** | Pre-existing; note only — do not alter in Phase 1 unless authorized |
| R-10 | Frontend test files not found under expected globs (vitest configured; verify colocated tests exist before Phase 2 gate) | **P3** | Verify in Phase 2 pre-flight |

---

## 7. TEST BASELINE

| Suite | Runner | Count / Config |
|---|---|---|
| Backend | pytest | **46 test files** in `backend/tests/` (incl. `test_agent_ws_spine.py` — existing agent spine coverage) |
| Frontend unit | vitest (`npm run test` → `vitest run --no-file-parallelism`) | Configured; colocated test files to be verified in Phase 2 pre-flight |
| Frontend visual/a11y | Playwright (`test:visual`, `test:a11y` w/ @axe-core) | Configured |
| Frontend CI chain | `npm run ci` = ci → typecheck → audit → lint:boundaries → test → build → perf:check → docs:check | Enforced |
| Root scripts | `setup_and_run_tests.bat/.sh`, `run_comprehensive_tests.bat` | Present |

Existing agent-related backend test: `backend/tests/test_agent_ws_spine.py`.
No existing tests for: execution policy, AgentRun store, approval lifecycle, import/export orchestrators (to be created in respective phases).

---

## 8. IMPORT MAP (CAPABILITY MATRIX)

| Format | Real Parser? | Location | Endpoint | Notes |
|---|---|---|---|---|
| DWG | ✅ YES | `backend/routers/dwg.py` (`_parse_dwg_impl`), `autocad.py` (`read_dwg_file`, `upload_and_read_dwg`) | POST parse/upload | Rate-limited (10/min parse, 30/min read); permission-gated (ELEMENT_READ/CREATE) |
| DXF | ✅ YES | `autocad.py` (ezdxf-based read) | POST | Permission-gated |
| RVT | ✅ YES | `revit.py` (`upload_and_read_rvt`), `revit_api.py` (`upload_revit_model`) | POST | Revit sync pipeline |
| PDF/Image (OCR) | ✅ YES | `experimental_services.py` (Tesseract eng+ara; temp-file write→process→delete) | POST | SystemConfigRole-gated |
| Audio (voice) | ✅ YES | `audio.py` | POST | Voice input path |
| Format conversion | ✅ YES | `digital_twin.py` (upload + `target_format`, e.g., "ifc"; safe path resolution `_safe_resolve_upload_path`; FileResponse download) | POST/GET | Path-traversal protected |
| IFC direct import | ⚠️ PARTIAL | Only via digital_twin conversion | — | Do NOT claim native IFC parser |
| XLSX / CSV | ❓ UNVERIFIED | Not confirmed in recon | — | Verify before claiming support (Phase 3 rule) |
| JSON | ✅ (project payloads) | projects/projects bridge | — | Native format |

Secure-upload mechanisms observed: slowapi rate limits, extension/content checks,
safe filename handling (`_safe_filename`), safe path resolution, temp-file cleanup,
permission dependencies on every upload route.

## 9. EXPORT MAP (CAPABILITY MATRIX)

| Format | Real Exporter? | Location | Notes |
|---|---|---|---|
| PDF | ✅ YES | `reports.py` `_build_pdf_report` (reportlab) → StreamingResponse `application/pdf` | Real generation |
| DXF | ✅ YES | `reports.py` `_build_dxf_report` (ezdxf) → `application/dxf` | Real generation |
| JSON | ✅ YES | `reports.py` → `application/json` | Real |
| Markdown | ✅ YES | `reports.py` → `text/markdown` (safe filenames) | Real |
| Generic file | ✅ YES | `exports.py` StreamingResponse w/ media_type + Content-Disposition | Real |
| Metrics text | ✅ YES | `projects.py` metrics export | Real |
| **DXF (project)** | ❌ **PLACEHOLDER** | `projects.py` `export_project_dxf` — explicitly "placeholder implementation" | **FAKE — deprecate/replace in Phase 4** |
| **Revit JSON (project)** | ❌ **PLACEHOLDER** | `projects.py` `export_project_revit` — "placeholder" | **FAKE** |
| **IFC (project)** | ❌ **PLACEHOLDER** | `projects.py` `export_project_ifc` — "placeholder" | **FAKE — do NOT claim IFC 4.3 export until real writer exists** |
| XLSX | ❓ UNVERIFIED | Not confirmed | Verify before claiming |

Artifact registration: **NOT PRESENT** — exports stream directly with no
artifact_id/checksum registry (Phase 4 requirement).

## 10. APPROVAL MAP (CURRENT STATUS)

| Requirement | Status |
|---|---|
| Dry-run preview before mutation | ✅ Implemented (all intent handlers) |
| Explicit approve → commit | ✅ Implemented (`ai_approve`, `ai_approve_composite`) |
| OCC concurrency check at commit | ✅ Implemented (CONCURRENCY_CONFLICT frames) |
| Audit event + reference on commit | ✅ Implemented (DomainEvent, auditReference) |
| Auto Approval mode toggle | ❌ NOT IMPLEMENTED |
| Step-by-step pause between steps | ⚠️ Partial (per-command preview→approve exists; no multi-step pause/resume of a running DAG) |
| Centralized policy service (AUTO_APPROVED/REQUIRES_APPROVAL/MANDATORY_HUMAN_REVIEW/DENIED) | ❌ NOT IMPLEMENTED (verified: zero matches repo-wide) |
| Server-side pending-approval record bound to run+step+revision | ❌ NOT IMPLEMENTED |
| Immutable approval decision record | ⚠️ Partial (commit events audited; decision itself not separately recorded) |
| Risk classification | ✅ Present per-capability (LOW/MEDIUM/ENGINEERING_MUTATION) |

## 11. AGENT MAP (CURRENT STATUS)

| Component | Status | Location |
|---|---|---|
| WS orchestration (intent→plan→dry-run→approve→commit) | ✅ | `agent_ws.py` |
| Composite DAG planning + preview + atomic commit | ✅ | `agent_ws.py` + `workflow_engine.py` |
| Progress streaming (per-step frames) | ✅ | `_create_progress_callback` |
| LLM provider abstraction + SSE chat | ✅ | `llm_service.py`, `routers/llm.py` (30/min limit) |
| Agent settings (provider/model/key/skills) | ✅ | `AgentSettingsContext.tsx` |
| Voice input | ✅ | `useVoiceControl.ts`, `audio.py` |
| Persistent AgentRun state model | ❌ | To create (Phase 1) |
| Resume after disconnect/restart | ⚠️ LangGraph workflows yes; agent runs no | Phase 1 |
| Cancel | ❌ | Phase 1 |
| Chat-first import/export via Agent | ❌ | Phases 3–4 |
| Artifact display in chat | ❌ | Phase 2/4 |

## 12. SECURITY BASELINE

- **AuthN**: API keys (`validate_api_key`) + session store + CSRF middleware.
- **AuthZ**: RBAC — roles {ADMIN, ENGINEER, VIEWER}; ~35 permissions spanning
  project/device/connection/calculation/report/export/element/conflict/system/
  qomn/facp/workflow/integration/billing domains; `get_role_permissions(role)`;
  `require_permission(...)` dependency on sensitive routes; WS requires
  CALCULATION_EXECUTE.
- **Rate limiting**: slowapi throughout (parse 10/min, reads 30/min, LLM 30/min).
- **Audit**: append-only domain events + `audit_integrity_helper.py`.
- **Secrets hygiene**: gitleaks config, secrets baseline, trivyignore, secret-scan
  CI workflow; S-06 fix removed keys from query strings.
- **Frontend controls are NOT security controls** — backend remains authoritative
  (principle preserved in target design).

## 13. CI/CD BASELINE (19 workflows)

`ci.yml`, `ci-build-gate.yml`, `deploy.yml`, `full-deploy.yml`, `rollback.yml`,
`secret-scan.yml`, `container-scan.yml`, `sonarcloud.yml`, `governance-audit.yml`,
`ai-code-review.yml`, `bundle-size.yml`, `dependabot-auto-merge.yml`,
`integration-diagnostic.yml`, `modernization-showcase.yml`, `rag-eval.yml`,
`regulatory-data-guard.yml`, `sync-to-hf.yml`, `trigger-vercel.yml`,
`vercel-preview.yml`.

Deployment targets: Vercel (frontend), Render/render.yaml + Docker (backend).
Per CI-CD-POLICY: feature branches only; local validation before push; green
pipeline before merge; no force pushes.

## 14. PHASE 1 IMPLEMENTATION BOUNDARY

Phase 1 will touch ONLY:
1. NEW: `backend/core/agent_run_store.py` (+ alembic migration)
2. NEW: `backend/core/execution_policy.py`
3. NEW: `backend/tests/test_agent_run_store.py`, `test_execution_policy.py`, `test_run_lifecycle.py`
4. MODIFY (minimal): `backend/routers/agent_ws.py` — policy hook + run-state persistence + cancel/resume message types
5. MODIFY (minimal): `backend/routers/workflow.py` — run status/resume/cancel REST endpoints
6. ADDITIVE: `backend/rbac.py` only if a new permission is provably required

Phase 1 will NOT touch: frontend, engineering engines, parsers, exporters,
auth mechanics, CI workflows.

## 15. PHASE 0 GATE RESULTS (EXECUTED & VERIFIED)

All gate validations were executed against baseline HEAD `4b7a8a0d` (zero source modifications):

| Gate Criterion | Command | Result |
|---|---|---|
| Repository clean or explicitly documented baseline | `git status` | ✅ PASS — single binary asset deviation documented (§0) |
| Architecture map completed | forensic recon | ✅ PASS — §1–§11 |
| Frontend typecheck passes | `npm run typecheck` (tsc -p tsconfig.json --noEmit) | ✅ **PASS** (exit 0, zero errors) |
| Frontend tests pass or documented existing failures | `npm run test` (vitest) | ⚠️ **DOCUMENTED EXISTING FAILURES**: 326 passed / 27 failed of 353 (9 files failed / 27 passed). Failures are pre-existing at HEAD: DevicesPage.test.tsx (24 — i18next NO_I18NEXT_INSTANCE in test setup), SimReadyPage.test.tsx (mock-spy type errors), plus isolated failures in DWGPage/SimReady suites. Not caused by Phase 0 (no code changed). |
| Backend tests pass or documented existing failures | `py -3.12 -m pytest backend/tests -q` | ⚠️ **DOCUMENTED EXISTING FAILURES**: 1064 passed / 3 failed / 1 skipped of 1068. Pre-existing security-test failures: `test_m2_websocket_transport.py::test_websocket_transport_class_not_referenced_outside_facp_distributed`, `test_marshal_loads_not_http_reachable.py::test_dangerous_methods_are_only_called_within_isolation_py`, `test_marshal_loads_not_http_reachable.py::test_runtime_sentinel_actually_catches_violations`. |
| Build passes | `npm run build` (vite build) | ✅ **PASS** (exit 0; 2608 modules; built in 13.08s) |
| No unexpected modifications | `git status` after all runs | ✅ PASS — zero source modifications made |
| Protected modules identified | forensic recon | ✅ PASS — §5 |
| Import/Export matrices completed | forensic recon | ✅ PASS — §8–§9 |
| Approval/Agent maps completed | forensic recon | ✅ PASS — §10–§11 |

### Environment Notes (documented, not defects)

- Project requires **Python >= 3.12** (`pyproject.toml: requires-python = ">=3.12"`).
  The machine's default `python` is 3.8.4 → backend test collection fails with
  `ImportError: cannot import name 'StrEnum' from 'enum'` under 3.8.
  Correct invocation on this machine: **`py -3.12 -m pytest backend/tests`**
  (Python 3.12.10 available via py launcher). This is an environment constraint,
  NOT a repository defect.
- Vitest reports "close timed out after 60000ms … something prevents Vite server
  from exiting" after suite completion — pre-existing teardown hang; results are
  still reported correctly before the hang.

**GATE 0 DECISION: PASS**

- Typecheck: PASS. Build: PASS. Backend: 99.6% green (3 pre-existing security-test
  failures documented). Frontend: 92.4% green (27 pre-existing failures documented).
- All failures are PRE-EXISTING at HEAD `4b7a8a0d`; none were introduced by Phase 0
  (no source file was modified).
- Per master prompt §19 (evidence-first) these exact counts are recorded as the
  regression baseline for every subsequent phase gate.

---

## HARD STOP

Per master prompt §21: **Phase 1 MUST NOT begin automatically.**
This report is delivered; execution waits for explicit authorization.