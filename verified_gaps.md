# Verified UI Coverage Gaps

**Generated:** 2026-07-30
**Methodology:** Cross-checked every item in `BAZspark_UI_Coverage_Audit_Report.xlsx` against the actual codebase at `main` branch.

---

## Confirmed Missing (Verified against code)

- [ ] GAP-H1: FireAI Core Analysis UI — Priority: HIGH — Backend: `fireai/core/api_server.py` — API: POST `/analyse`, POST `/analyse/floor` — No `EngineeringFireAIPage.tsx` exists, no route `/engineering/fireai`
- [ ] GAP-H3: Self-Healing LLM Healing Toggle — Priority: HIGH — Backend: `fireai/core/qomn_self_healing_engine.py` — Config: `QOMN_ENABLE_LLM_HEALING` — No toggle in SettingsPage.tsx (security tab is placeholder)
- [ ] GAP-H4: Secret Key Rotation UI — Priority: HIGH — Backend: `fireai/core/secret_rotation.py` — Config: `FIREAI_SESSION_SECRET_NEW` — Only read-only badge, no rotation UI
- [ ] GAP-H5: Vision API Key Management UI — Priority: HIGH — Backend: `backend/routers/settings.py` — API: POST/GET/DELETE `/api/v1/settings/keys/openai` — No key management UI in SettingsPage
- [ ] GAP-H6: Admin Token Management UI — Priority: HIGH — Backend: `backend/admin_protection.py` — Config: `BAZSPARK_MASTER_ADMIN_TOKEN` — No admin token section in SettingsPage
- [ ] GAP-H10: Analyze Room Pipeline UI — Priority: HIGH — Backend: `backend/routers/analyze.py` — API: POST `/api/v1/analyze/projects/{id}/analyze/room` — No room analysis pipeline in EngineeringPage
- [ ] GAP-H11: CLI 5-Layer Pipeline UI — Priority: HIGH — Backend: `fireai/core/fireai_cli_engine.py` — No `PipelineLayersPage.tsx` exists, no route `/engineering/pipeline`
- [ ] GAP-H12: Integration Pipeline UI — Priority: HIGH — Backend: `fireai/core/api_server.py` — API: POST `/integration` — No integration pipeline UI in EngineeringPage

## Confirmed Partially Implemented (Page exists but unrouted)

- [ ] GAP-H2: Generative Design UI — Priority: HIGH — `GenerativeDesignPage.tsx` EXISTS (463 lines) but NOT routed in App.tsx — Needs route `/engineering/generative`
- [ ] GAP-H7: RBAC Management UI — Priority: HIGH — `RbacPage.tsx` EXISTS (460 lines) but NOT routed in App.tsx — Needs route `/settings/rbac`

## Unrouted Pages (Confirmed)

| Page Component | Route Needed | Status |
|---|---|---|
| `SystemHealthPage.tsx` (240 lines) | `/dashboard/system-health` | UNROUTED |
| `GenerativeDesignPage.tsx` (463 lines) | `/engineering/generative` | UNROUTED |
| `RbacPage.tsx` (460 lines) | `/settings/rbac` | UNROUTED |
| `WebhookManagementPage.tsx` (439 lines) | `/settings/webhooks` | UNROUTED |
| `AgentChatPage.tsx` (273 lines) | `/monitor/agent` | UNROUTED |
| `TopologyPage.tsx` (443 lines) | `/engineering/topology` | UNROUTED |

## Report Inaccuracies (Found in code but reported as missing)

- INACCURACY-001: Workflow Approve/Reject Actions — Found in: `frontend/src/pages/WorkflowPage.tsx` — Lines 332-360 — Has approve/reject buttons calling `workflowApi.approve()` and `workflowApi.reject()`
- INACCURACY-002: Report Download Button — Found in: `frontend/src/pages/ReportsPage.tsx` — Lines 500-528 — Has download button (client-side JSON blob). Note: Backend endpoint is `/export` not `/download` as report states.

## Mypy Regression Gate

- **Current errors:** 996
- **Baseline:** 979
- **Delta:** +17 (FAIL)
- **Top error categories:** `no-untyped-def` (1210), `assignment` (176), `attr-defined` (122)
- **New errors source:** `backend/app.py`, `backend/basebyright/__init__.py`, `backend/routers/workflow.py`

## Build Status

- Frontend build: ✅ PASSES (with warnings about ineffective dynamic imports)
- Backend mypy: ❌ FAILS (996 > 979 baseline)
- Frontend TypeScript: ✅ PASSES (build succeeds)
