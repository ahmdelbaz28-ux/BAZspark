# Universal Session Context and Wire Contract Specification

**BAZspark Engineering Platform — Architecture & Protocol Documentation**
*Authoritative Reference for Phase 3 Execution per BAZSPARK_PLAN_V2_2 §5*

---

## 1. Universal Context Matrix Overview

The **Universal Session Context** is the canonical server-side model defining execution boundaries, target assets, and concurrency controls across all client surfaces (2D Canvas, 3D BIM Viewer, Calculation Worksheets, Single-Line Diagrams, Chat Control Center, CLI, and Background Daemons).

### Canonical 5-Field Matrix

| Field | Type | Authority | Description |
| :--- | :--- | :--- | :--- |
| `project_id` | `string` (Required) | Canonical Aggregate Root | Target project identifier. All validation and RBAC checks anchor on `project_id`. |
| `model_id` | `string \| null` | Server/Project Bound | Authoritative Digital Twin / BIM model identity (derived from `project.modelId` or `dt-{project_id}`). Mismatches are rejected with HTTP 400. |
| `entity_ids` | `list[str]` | Server/Project Bound | Target entity/device/circuit identifiers. Must exist in the project database (no prefixes bypass like `elem-*` or `mock-*`). Single `entity_id` is automatically wrapped for backward compatibility. |
| `expected_revision` | `int \| null` | OCC State Token | Persistent OCC revision token from `project_revisions`. Mandatory for state-mutating capabilities (`revision_binding == "canonical_project_state"`). |
| `ui_surface` | `string \| null` | Client Metadata | Originating client view (`canvas_2d`, `bim_3d`, `chat_control_center`, `panel_config`, `schematic_sld`). Metadata only: strictly **zero** functional execution side effects. |

---

## 2. Dynamic Revision Binding Derivation

In accordance with architectural invariants, **no capability IDs are hardcoded** in conditional statements or validation logic.

### Derivation Invariant
For any target capability $C \in \text{CapabilityRegistry}$:
$$\text{RevisionRequired}(C) = \begin{cases} \text{True} & \text{if } C.\text{contract}.\text{revision\_binding} = \text{"canonical\_project\_state"} \\ \text{False} & \text{if } C.\text{contract}.\text{revision\_binding} = \text{"none"} \end{cases}$$

When an execution request (REST or WebSocket) targets a capability with $\text{RevisionRequired}(C) = \text{True}$:
- If `expected_revision` is `None` or omitted $\rightarrow$ Rejected immediately with error code **`MISSING_EXPECTED_REVISION`** (HTTP 400 / WS `ai_error` or `run_error`).
- If `expected_revision` $\neq \text{canonical\_revision}$ $\rightarrow$ Rejected with **`REVISION_CONFLICT`** / `CONCURRENCY_CONFLICT` (HTTP 409 / WS `ai_conflict`).

---

## 3. Concurrency Conflict & Error Mapping Table

The table below maps concurrency and validation error representations across the internal spine, REST API, and WebSocket channels:

| Layer / Source | Error Code | HTTP Status / WS Type | Meaning & Action |
| :--- | :--- | :--- | :--- |
| **Command Bus / State Store** | `CONCURRENCY_CONFLICT` | Internal result | OCC version mismatch during command execution. |
| **REST Router** (`/workflow/*`) | `MISSING_EXPECTED_REVISION` | HTTP 400 Bad Request | Mutation attempted without `expected_revision`. Client must pass active revision. |
| **REST Router** (`/workflow/*`) | `OCC revision conflict` | HTTP 409 Conflict | `expected_revision != canonical_revision`. Client must refresh and re-plan. |
| **WebSocket** (`/agent/ws`) | `MISSING_EXPECTED_REVISION` | `ai_error` / `run_error` | Missing revision token on state mutation frame. |
| **WebSocket** (`/agent/ws`) | `INVALID_EXPECTED_REVISION` | `ai_error` / `run_error` | Non-integer revision value provided on wire. |
| **WebSocket** (`/agent/ws`) | `MISSING_CAPABILITY_ID` | `ai_error` | Approval frame missing valid capability identifier. |
| **WebSocket** (`/agent/ws`) | `REVISION_CONFLICT` | `ai_conflict` / `run_error` | OCC conflict. Frontend transitions to `isConflict: true`, pauses run, offers O6 recovery. |
| **WebSocket Handshake** | Close `4401` | Close Frame | Browser client with `Origin` connected without valid single-use ticket. |

---

## 4. Semantic Context Token Budget Invariant

To guarantee deterministic, cost-bounded, and low-latency LLM orchestration:
1. **Token Budget Ceiling:** Bounded context packets have a hard ceiling of **$\le 1,500$ tokens**.
2. **Zero Raw CAD State:** The LLM receives synthesized summaries and topological bounds, never raw geometry meshes or unindexed element databases.
3. **Enforcement:** `enforce_context_budget()` validates packet size before LLM invocation, raising `ContextBudgetExceededError` on breach.

---

## 5. Settlement of Open Decisions (O4, O5, O6, O-B6)

### O4 Settlement: Sync WebSocket Authorization
- In `backend/routers/sync.py`, `is_admin` strictly evaluates whether `rbac_info.role == Role.ADMIN`.
- The legacy `or bool(env_match)` fallback was removed to prevent environment API keys from automatically inheriting unrestricted administrative capabilities across all projects without explicit RBAC roles.

### O5 Settlement: Browser WebSocket Ticket Enforcement
- Browser clients sending an `Origin` header cannot supply custom authorization headers on WebSocket handshakes.
- Browsers **must** obtain a single-use ticket via `POST /api/v1/agent/ws-ticket` prior to connecting.
- Connections presenting an `Origin` header without a valid ticket are closed immediately with WebSocket code `4401`.
- Frontend `useAgentRun` captures ticket acquisition failure, prevents runaway reconnect loops, and displays a dedicated error.

### O6 Settlement: UI Conflict Recovery Path
- `useAgentRun.ts` maintains reactive state properties: `isConflict: boolean` and `conflictRevision: number | null`.
- Upon receiving `REVISION_CONFLICT` / `ai_conflict`, the run status transitions to `PAUSED` and exposes `recoverFromConflict(canonicalRevision)`.
- Triggering `recoverFromConflict` resets conflict flags, records the recovery event in `recoveryState`, transitions to `READY`, and allows safe re-evaluation.

### O-B6 Settlement: Live Execution Anchor
- Condition deferred with explicit documentation anchor; execution environment remains client-assisted with dry-run/preview steps verified.
