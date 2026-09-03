# docs/PHASE5_PLANNER.md — Phase 5 Generic Planner Reference & Verification Report

> **Version:** 1.0  
> **Status:** Implemented & Verified (Forensic Gate 5 Contract)  
> **Precondition Baseline:** FG-4 Commit `3819193c84644835225fd19a10d9d626f63e7f2c`  
> **Branch:** `feature/phase-5-generic-planner`  
> **Governance:** BAZSPARK_PLAN_V2_2 §5 Phase 5, Principle 11, CI/CD Rules 1–12

---

## 1. Executive Summary

Phase 5 transitions the BAZspark engine from hardcoded regex-based workflow planning to a pure, capability-agnostic **Generic Workflow Planner** (`backend.core.generic_planner.GenericWorkflowPlanner`). The legacy regex planner is formally isolated and frozen as a compatibility fallback (`RegexFallbackPlanner`), governed by mandatory invocation telemetry and explicit removal gate criteria.

All six contract deliverables (**S1–S6**) have been authored and verified against the 7-stage intent pipeline:
1. **S1: Baseline Inventory & Regex Retirement Contract** (`backend/core/planner_telemetry.py`)
2. **S2: Generic Planner & JSON Schema Validation** (`backend/core/planner_schema.py`, `backend/core/generic_planner.py`)
3. **S3: Disambiguation Loop** (`backend/core/disambiguation.py`)
4. **S4: Prompt Injection Shield** (`backend/core/prompt_shield.py`)
5. **S5: Default dry_run=true Guarantee** (`backend/core/generic_planner.py`)
6. **S6: 7-Stage Intent Suite & Architecture Guardrails** (`backend/tests/intent_suite/`, `backend/tests/architecture/`)

---

## 2. Architecture & Components

```
                User Request (Natural Language / Structured Spec)
                                      │
                                      ▼
                        [ Prompt Injection Shield ]
                         (zero raw file leakages,
                          tag neutralization)
                                      │
                                      ▼
                           [ Disambiguation Engine ]
                         (checks missing/ambiguous params)
                         ──(Clarification Needed?)──► [ DisambiguationRequiredError ]
                                      │ No (Complete Intent)
                                      ▼
                         [ Dynamic Capability Discovery ]
                         (CapabilityRegistry.discover_authorized,
                          zero hardcoded branches/literals)
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
                         (Server-authoritative dry_run=True,
                          expected_revision OCC verification)
                                      │
                                      ▼
                         [ Telemetry & Degradation Ladder ]
                         (Primary LLM -> Fallback LLM -> Regex Fallback)
```

### 2.1 Component Manifest

| Component | Path | Responsibility |
|---|---|---|
| **Planner Telemetry** | `backend/core/planner_telemetry.py` | In-memory telemetry recorder tracking invocations, latencies, fallback reasons, pass rates, and retirement evaluation. |
| **Planner Schema Validator** | `backend/core/planner_schema.py` | Strict JSON Schema and Pydantic validation enforcing DAG acyclicity, referential integrity, and non-empty IDs. |
| **Disambiguation Engine** | `backend/core/disambiguation.py` | Detects missing parameters, ambiguous export formats, and non-silent fallthrough diagnostics. |
| **Prompt Injection Shield** | `backend/core/prompt_shield.py` | Input sanitizer and file content isolation layer guaranteeing zero raw file text/bytes enter LLM prompts. |
| **Generic Workflow Planner** | `backend/core/generic_planner.py` | Capability-agnostic dynamic planner using dynamic capability discovery, DAG synthesis, policy evaluation, dry-run overlay, and canonical system prompt ([`_build_system_prompt`](file:///c:/Users/EWS-01/Desktop/BAZ/backend/core/generic_planner.py#L310)). |
| **Unified Routing & Fallback** | `backend/core/workflow_planner.py` | Routes to generic planner as preferred path, captures fallback telemetry, and isolates frozen regex planner. |

---

## 3. Legacy Regex Fallback Retirement Contract

The legacy regex planner (`RegexFallbackPlanner`) is strictly **FROZEN** per Principle 11.
- **Frozen Capabilities (10):** `import.inspect_file`, `import.plan_import`, `import.execute_import`, `export.plan_export`, `export.execute_export`, `spatial.place_devices`, `compliance.verify_detector_spacing`, `electrical.calculate_voltage_drop`, `electrical.calculate_battery`, `hydraulics.solve_darcy_weisbach`.
- **Retirement Criteria:**
  1. Intent Suite pass rate $\ge 95\%$ over $\ge 50$ consecutive runs.
  2. LLM service availability SLO $\ge 99.9\%$.
- **Automated Removal Gate:** `backend/tests/architecture/test_removal_gate.py` asserts that removal of the fallback is prohibited until both conditions are met.

---

## 4. Test Verification Summary

| Test Suite | Total Tests | Status | Scope |
|---|---|---|---|
| `tests/intent_suite/test_full_pipeline_intent_suite.py` | 10 | **PASSED** | 10 Scenarios covering the full 7-stage pipeline (varied phrasings, Arabic multilingual, missing/ambiguous parameters, RBAC scope denial, degradation ladder, OCC revision mismatch, conflicting capabilities, multi-step DAG, pass rate export). |
| `tests/intent_suite/test_prompt_injection_shield.py` | 6 | **PASSED** | 5 Adversarial prompt injection attack fixtures + 1 file content isolation zero-leakage test. |
| `tests/intent_suite/test_disambiguation_and_degradation.py` | 7 | **PASSED** | Parameter clarification detection, non-silent fallthrough, and schema corruption rejection. |
| `tests/architecture/test_planner_purity.py` | 2 | **PASSED** | AST validation asserting 0 hardcoded capability string literals and 0 capability-specific branch variables in `generic_planner.py`. |
| `tests/architecture/test_regex_freeze.py` | 2 | **PASSED** | AST validation asserting exact 10 frozen capabilities match and zero additions in `workflow_planner.py`. |
| `tests/architecture/test_removal_gate.py` | 3 | **PASSED** | Unit verification of the removal gate evaluation logic. |
| `tests/architecture/test_mutation_authority_gate.py` | 3 | **PASSED** | Existing architectural authority gate validation. |
| **Intent & Architecture Subtotal** | **33** | **PASSED** | Full Phase 5 contract verification. |
