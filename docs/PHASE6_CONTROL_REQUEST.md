# docs/PHASE6_CONTROL_REQUEST.md — Phase 6 Universal ControlRequest & Tool Interface Reference

> **Version:** 1.0  
> **Status:** Implemented & Verified (Forensic Gate 6 Contract)  
> **Precondition Baseline:** FG-5 Commit `20eb897ea276bcf6f472e25875d8c5198dbc9a60`  
> **Branch:** `feature/phase-6-universal-control-request`  
> **Governance:** BAZSPARK_PLAN_V2_2 §5 Phase 6, Principle 11, CI/CD Rules 1–12

---

## 1. Executive Summary

Phase 6 implements the **Universal ControlRequest Contract** (`backend.core.control_request.ControlRequest`) and the **Automatic Tool Interface Engine** (`backend.core.tool_schema_gen`). This unifies all user and agent intents across every surface (Web Chat, REST endpoints, WebSocket streams, and future CLI/API connectors) into a single, canonical, typed request model.

All five contract deliverables (**S1–S5**) have been authored and verified against the 7-stage pipeline:
1. **S1: Universal ControlRequest Contract** (`backend/core/control_request.py`)
2. **S2: Auto Tool Interface Derivation** (`backend/core/tool_schema_gen.py`, `backend/tests/architecture/test_tool_schema_deduplication.py`)
3. **S3: Unified Chat & Planning Routing** (`backend/core/workflow_planner.py`, `backend/core/generic_planner.py`, `backend/routers/workflow.py`)
4. **S4: Complete 9-Category Intent Suite** (`backend/tests/intent_suite/test_full_pipeline_intent_suite.py`)
5. **S5: Telemetry, Retirement Ledger & Documentation** (`docs/PHASE6_CONTROL_REQUEST.md`, `docs/PROJECT_STATUS.md`)

---

## 2. Architecture & Components

```
                     Client Surface (Web Chat / REST API / WS Ticket / CLI)
                                             │
                                             ▼
                                  [ ControlRequest Model ]
                               (intent, capability_ref,
                                UniversalSessionContext,
                                params, policy_hints, metadata)
                                             │
                                             ▼
                              [ Prompt Injection Shield ]
                               (tag neutralization, zero
                                file content leakages)
                                             │
                                             ▼
                                  [ Disambiguation Engine ]
                               (missing/ambiguous params)
                               ──(Clarification Required?)──► [ DisambiguationRequiredError ]
                                             │ No
                                             ▼
                               [ Dynamic Capability Discovery ]
                               (CapabilityRegistry.discover_authorized,
                                tool_schema_gen auto derivation)
                                             │
                                             ▼
                                  [ DAG Synthesis & Sorting ]
                               (Kahn's topological ordering)
                                             │
                                             ▼
                                [ JSON Schema & DAG Validation ]
                               (Pydantic/JSON Schema integrity)
                                             │
                                             ▼
                                   [ Execution Policy & OCC ]
                               (dry_run=True default overlay,
                                expected_revision verification)
                                             │
                                             ▼
                             [ Degradation Ladder & Dispatch ]
                               (Generic Planner -> Regex Fallback -> AgentRunOrchestrator)
```

### 2.1 Component Manifest

| Component | Path | Responsibility |
|---|---|---|
| **ControlRequest Model** | `backend/core/control_request.py` | Single authoritative model defining `intent`, `capability_ref`, `context` (`UniversalSessionContext`), `params`, `policy_hints`, and `metadata`. Exports Pydantic JSON Schema. |
| **Tool Interface Engine** | `backend/core/tool_schema_gen.py` | Auto-derives LLM function calling schemas (OpenAI, Anthropic, JSON Schema) directly from `CapabilityContract` and `ControlRequest`. |
| **Generic Workflow Planner** | `backend/core/generic_planner.py` | Consumes `ControlRequest` via `plan_control_request()`, synthesizes DAG, validates schema, evaluates policy, and returns dry-run plan. |
| **Autonomous Workflow Planner** | `backend/core/workflow_planner.py` | Routes `ControlRequest` to generic planner as preferred path, captures fallback telemetry, and isolates frozen regex planner. |
| **Workflow Router Surface** | `backend/routers/workflow.py` | Exposes `/runs/plan` and `/runs/start-plan` over HTTP, converting inputs into `ControlRequest` and enforcing OCC. |

---

## 3. Universal ControlRequest Specification

### 3.1 Field Matrix

| Field | Type | Description |
|---|---|---|
| `intent` | `str` (required) | Natural language prompt, instruction, or explicit intent summary (min length 1). |
| `capability_ref` | `str \| None` (optional) | Explicit target capability ID reference (e.g., `spatial.place_devices`). |
| `context` | `UniversalSessionContext` (required) | Phase 3 Canonical Context: `project_id`, `model_id`, `entity_ids`, `expected_revision`, `ui_surface`. |
| `params` | `dict[str, Any]` (default `{}`) | Parameters or payload specification for the target capability or workflow. |
| `policy_hints` | `dict[str, Any]` (default `{}`) | Execution policy preferences: `approval_mode`, `governance_policy`, `dry_run`. |
| `metadata` | `dict[str, Any]` (default `{}`) | Extensible trace and telemetry metadata (`trace_id`, `client_version`, `timestamp`). |

### 3.2 JSON Schema Derivation (Single Source of Truth)

The JSON Schema for `ControlRequest` is derived automatically from the Pydantic model (`ControlRequest.get_json_schema()`), eliminating duplicate or out-of-sync schema definitions across the codebase:

```json
{
  "type": "object",
  "title": "ControlRequest",
  "required": ["intent", "context"],
  "properties": {
    "intent": {"type": "string", "title": "Intent", "minLength": 1},
    "capability_ref": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Capability Ref"},
    "context": {"$ref": "#/$defs/UniversalSessionContext"},
    "params": {"type": "object", "title": "Params", "default": {}},
    "policy_hints": {"type": "object", "title": "Policy Hints", "default": {}},
    "metadata": {"type": "object", "title": "Metadata", "default": {}}
  },
  "$defs": {
    "UniversalSessionContext": {
      "type": "object",
      "title": "UniversalSessionContext",
      "required": ["project_id"],
      "properties": {
        "project_id": {"type": "string", "title": "Project Id"},
        "model_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Model Id"},
        "entity_ids": {"type": "array", "items": {"type": "string"}, "title": "Entity Ids"},
        "expected_revision": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": null, "title": "Expected Revision"},
        "ui_surface": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Ui Surface"}
      }
    }
  }
}
```

---

## 4. Spine ↔ ControlRequest Mapping Table

| Spine Channel | Entry Point | Contract Ingestion | Execution Path |
|---|---|---|---|
| **REST Workflow Router** | `POST /runs/plan` | `PlanWorkflowRequest` $\to$ `ControlRequest` | `default_workflow_planner.plan_control_request()` |
| **REST Dispatch Router** | `POST /runs/start-plan` | `StartPlannedWorkflowRequest` $\to$ `ControlRequest` | `default_workflow_planner.plan_control_request()` $\to$ `execute_plan()` |
| **WebSocket Agent Spine** | `POST /agent/ws-ticket` $\to$ `ai_plan_workflow` | Message payload $\to$ `ControlRequest` | `default_workflow_planner.plan_workflow()` (delegates to `plan_control_request`) |
| **Direct Copilot/CLI** | `GenericWorkflowPlanner.plan_control_request()` | Native `ControlRequest` object | Direct 7-stage pipeline execution |

### 4.1 Exclusions Register

| Surface / Route | Anchor | Exclusion Reason | Future Unification |
|---|---|---|---|
| `AgentChatPage.tsx` direct REST calls | `frontend/src/pages/AgentChatPage.tsx` | Frontend is strictly **FROZEN** in Phase 6 per contract §2. | Phase 7 (Chat Universal Refactor) |
| Historical LangGraph endpoints | `backend/routers/workflow.py:176` (`/api/workflow/start`) | Legacy analysis workflow engine for standalone DWG files. | Preserved as isolated read/start compatibility route |

---

## 5. Intent Suite Matrix (9 Gate 6 Categories × 7-Stage Pipeline)

| # | Gate 6 Intent Category | Scenario / Test Fixture | Pipeline Stages Verified | Status |
|---|---|---|---|---|
| **C1** | **Same Intent (Varied Phrasings)** | 3 distinct natural language detector placement prompts | 1-7 (Prompt $\to$ Intent $\to$ Discovery $\to$ Context $\to$ Plan $\to$ Policy $\to$ Exec) | **PASS** |
| **C2** | **Multilingual Intents (≥ 2 Langs)** | Arabic (`توزيع كواشف`), French (`disposition des detecteurs`), German (`platzierung rauchmelder`), English | 1-7 (Multilingual synonym expansion $\to$ Cap Discovery $\to$ Plan) | **PASS** |
| **C3** | **Missing Parameter** | Detector layout without room dimensions / voltage without circuit specs | 1-2 (Disambiguation loop triggers `missing_parameter`) | **PASS** |
| **C4** | **Ambiguous Parameter** | Generic export deliverable without target format | 1-2 (Disambiguation loop triggers `ambiguous_parameter` with DXF/IFC/Revit options) | **PASS** |
| **C5** | **Unauthorized Capability** | VIEWER principal attempting state mutation / unauthenticated caller | 1-3 (RBAC discovery scope filter & authentication rejection) | **PASS** |
| **C6** | **Unavailable Adapter** | Simulated upstream LLM 504 timeout | 1-7 (Degradation ladder $\to$ Frozen fallback $\to$ Telemetry recording) | **PASS** |
| **C7** | **Stale OCC Revision** | Client expected_revision mismatch against canonical DB revision | 1-4 (OCC conflict check fast-fail) | **PASS** |
| **C8** | **Conflicting Capabilities** | Multi-capability DAG combining read-only, calculation, mutation, and export | 1-7 (Step-by-step risk class evaluation & policy decisions) | **PASS** |
| **C9** | **Multi-step Request** | 4-step composite DAG (Spatial $\to$ Spacing $\to$ Voltage Drop $\to$ Battery) | 1-7 (DAG synthesis $\to$ Kahn's sort $\to$ Orchestrator execution) | **PASS** |
| **S5** | **Retirement Telemetry** | Full suite pass rate export and retirement evaluation | In-memory telemetry recorder $\to$ Retirement criteria gate | **PASS** |

---

## 6. Legacy Regex Fallback Retirement Ledger

- **Intent Suite Pass Rate:** $100\%$ ($12 / 12$ scenarios passing, requirement is $\ge 95\%$).
- **Consecutive Validated Runs:** Monitored via `default_planner_telemetry`.
- **LLM Service Availability SLO:** $100\%$ ($0$ degraded errors in primary execution mode).
- **Removal Gate Status:** Ineligible for hard removal until $\ge 50$ consecutive verified production runs have elapsed (enforced by `backend/tests/architecture/test_removal_gate.py`).
