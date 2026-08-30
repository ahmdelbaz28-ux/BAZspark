# Capability Conformance Report — Phase 1 & Phase 2 Canonical Registry & Discovery

**Document ID:** CCR-2026-08-30-PHASE2  
**Authoritative Plan Reference:** `BAZSPARK_PLAN_V2_2.md` §5 Phase 1 (Canonical Capability Contract) & Phase 2 (Capability Discovery)  
**Execution Baseline:** `1d9d9ed5`  
**Evaluation Date:** 2026-08-30  
**Phase Coverage:** 100% (11/11 Conforming Capabilities)  

---

## 1. Executive Summary

As mandated by **BAZSPARK_PLAN_V2_2 §5 Phase 1 & Phase 2**, every capability exposed to the orchestration and LLM planner runtime must be strictly bounded by a typed `CapabilityContract` and queryable via an authorized, fail-closed discovery interface.

All 11 canonical engineering capabilities conform to the Phase 2 contract standard:
1. **Schema Versioning:** Every contract explicitly declares `schema_version="1.0"`, enforced via `major.minor` regex validation.
2. **Authorized Discovery:** `discover_authorized()` enforces strict AND authorization (`principal.scopes ⊇ capability.required_scopes`), returns lean payloads (strictly excluding `handler` and raw CAD/project state), and fails closed on invalid filter parameters.
3. **Read-Only HTTP Surface:** Dedicated router mounted at `/api/v1/capabilities` exposing discovery query over existing authentication middleware.
4. **O-C1 Resolution:** `export.execute_export` scopes hardened to `["export:write", "project:read"]` aligning contract scopes with its state-mutating execution profile.

---

## 2. Canonical Capability Conformance Matrix (11/11)

| # | Capability ID | Category | Version | `revision_binding` | `execution_mode` | `execution_channel` | Risk | Scopes | `mutation_type` | `approval_policy` |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `spatial.place_devices` | spatial | `1.0` | `none` | `inline` | `sync` | `MEDIUM` | `["spatial:write"]` | `read_only` | `auto` |
| 2 | `compliance.verify_detector_spacing` | compliance | `1.0` | `none` | `inline` | `sync` | `LOW` | `["compliance:read"]` | `read_only` | `auto` |
| 3 | `electrical.calculate_voltage_drop` | electrical | `1.0` | `none` | `inline` | `sync` | `ENGINEERING_MUTATION` | `["electrical:write"]` | `read_only` | `auto` |
| 4 | `electrical.calculate_battery` | electrical | `1.0` | `none` | `inline` | `sync` | `ENGINEERING_MUTATION` | `["electrical:write"]` | `read_only` | `auto` |
| 5 | `hydraulics.solve_darcy_weisbach` | hydraulics | `1.0` | `none` | `inline` | `sync` | `ENGINEERING_MUTATION` | `["hydraulics:write"]` | `read_only` | `auto` |
| 6 | `import.inspect_file` | import | `1.0` | `none` | `inline` | `sync` | `LOW` | `["import:read", "project:read"]` | `read_only` | `auto` |
| 7 | `import.plan_import` | import | `1.0` | `none` | `inline` | `sync` | `LOW` | `["import:read", "project:read"]` | `read_only` | `auto` |
| 8 | `import.execute_import` | import | `1.0` | `canonical_project_state` | `inline` | `sync` | `MEDIUM` | `["import:write", "project:write"]` | `state_mutation` | `auto` |
| 9 | `export.plan_export` | export | `1.0` | `none` | `inline` | `sync` | `LOW` | `["export:read", "project:read"]` | `read_only` | `auto` |
| 10 | `export.execute_export` | export | `1.0` | `canonical_project_state` | `inline` | `sync` | `MEDIUM` | `["export:write", "project:read"]` | `state_mutation` | `auto` |
| 11 | `export.validate_artifact` | export | `1.0` | `none` | `inline` | `sync` | `LOW` | `["export:read"]` | `read_only` | `auto` |

---

## 3. Detailed Architectural Justifications & O-C1 Resolution

### 3.1 Canonical Project State Mutations (`revision_binding="canonical_project_state"`)

1. **`import.execute_import`**:
   - **Rationale:** Mutates canonical project state by persisting newly imported devices, rooms, and circuits into the database. To prevent race conditions, dirty writes, and lost updates, it strictly requires `expected_revision`.
   - **Enforcement:** Invocation via WebSocket `run_start` without `expected_revision` fails closed with `MISSING_EXPECTED_REVISION`.

2. **`export.execute_export`**:
   - **Rationale:** Generates deterministic engineering artifacts (DXF, Revit, IFC, JSON, PDF) representing an exact snapshot of project state. Binding to `canonical_project_state` guarantees that artifacts are tied to a specific project revision and fail if concurrent modifications occurred during export generation.

### 3.2 O-C1 Resolution (`export.execute_export` Scope Hardening)

- **Prior State (FG-1C Observation O-C1):** `export.execute_export` was registered with `mutation_type="state_mutation"` and `revision_binding="canonical_project_state"`, but its declared scopes were `["export:read", "project:read"]`.
- **Resolution (Option A):** Hardened declared scopes to `["export:write", "project:read"]`.
- **Architectural Impact:** 
  1. Principal authorization matrix now enforces write privilege for artifact generation. Principals with read-only scopes (`VIEWER`) cannot discover or trigger `export.execute_export`.
  2. Aligns with other stateful execution capabilities (`import.execute_import` requiring `import:write`).
  3. Verified by automated test: `test_export_execute_export_requires_write_scope_oc1()`.

### 3.3 Pure Calculations and Read-Only Verifications (`revision_binding="none"`)

1. **Calculations (`electrical.calculate_voltage_drop`, `electrical.calculate_battery`, `hydraulics.solve_darcy_weisbach`)**:
   - **Rationale:** Pure deterministic engineering math kernels operating on their input payload without mutating canonical project elements directly.
   - **Risk Classification:** `ENGINEERING_MUTATION` to reflect high domain significance while having `mutation_type="read_only"` and `revision_binding="none"`.

2. **Spatial Grid Placement (`spatial.place_devices`) & Compliance (`compliance.verify_detector_spacing`)**:
   - **Rationale:** Computes geometric layouts or validates NFPA spacing rules against payload geometries without directly mutating canonical entities.

3. **Inspection & Planning (`import.inspect_file`, `import.plan_import`, `export.plan_export`, `export.validate_artifact`)**:
   - **Rationale:** Read-only inspection and dry-run planning stages.

---

## 4. Contract Registration & Schema Versioning Invariants

`CapabilityRegistry.register()` enforces the following automatic entry requirements (fail-closed):

1. **Explicit Contract Requirement:** Every `CapabilityDefinition` MUST have an explicitly declared, valid `CapabilityContract` (`contract_explicit=True`). Natural instantiation without a contract or synthetic/implicit default contracts are strictly rejected.
   > **Bounded exception (test-harness compatibility):** `CapabilityDefinition` instances with `category="test"` or a `capability_id` prefixed with `"test."` / `"failing."` receive a synthesized, maximally restrictive read-only contract (`revision_binding="none"`, `execution_mode="inline"`) so that legacy test mocks can register unchanged. This path is unreachable for production registrations: every production capability is declared with an explicit contract inside `capability_registry.py`, and no production code constructs `CapabilityDefinition` outside that module. All other non-explicit instantiations are strictly rejected.
2. **Schema Versioning Policy (D-2b):**
   - Every `CapabilityContract` defines `schema_version: str = "1.0"`.
   - `register()` strictly validates `schema_version` against `^\d+\.\d+$` (numeric `major.minor` pattern).
   - Formats such as `"1"`, `"v1.0"`, `"1.0.0"`, `"-1.0"`, `""`, or non-string types are rejected with `ValueError`.
   - **Upgrade Policy:** Breaking changes to input/output schema require a major version bump (`2.0`); non-breaking additive improvements require a minor bump (`1.1`). Consumers pin the schema version.
3. **Explicit Revision Binding:** `contract.revision_binding` must be explicitly declared as `"canonical_project_state"` or `"none"`.
4. **Execution Mode Validation:** `contract.execution_mode` must be `"inline"` or `"background_run"`.
5. **Expanded Literal Field Validation:**
   - `mutation_type`: Validated against `{"read_only", "idempotent_write", "state_mutation", "none"}`.
   - `risk`: Validated against `{"LOW", "MEDIUM", "HIGH", "CRITICAL", "ENGINEERING_MUTATION"}`.
   - `approval_policy`: Validated against `{"auto", "user_confirm", "pe_signoff", "admin_only"}`.
   - `execution_channel`: Validated against `{"sync", "async", "websocket", "worker", "inline"}`.
6. **Schema, Scope, and Timeout Typing:** `input_schema` and `output_schema` must be dictionaries, `scopes` must be a list of strings, and `timeout_seconds` must be a positive number.

---

## 5. Authorized Capability Discovery (D-2a & D-2c)

### 5.1 Registry Query Interface (`discover_authorized`)
- **Inputs:** Principal identity (`scopes: list[str] | set[str] | None`, `is_admin: bool`) and optional query filters (`category: str | None`, `execution_channel: str | None`).
- **Authorization Rule (AND):** A capability is returned if and only if the principal possesses all required scopes (`principal.scopes ⊇ capability.required_scopes`) or `is_admin=True` / wildcard scope (`"*"`).
- **Fail-Closed Filtering:** Non-existent category or execution channel filter values immediately raise `ValueError` (HTTP 400 at router boundary).
- **Lean Output Payload:** Returns dictionary containing exactly 15 schema metadata fields:
  `capability_id, name, description, category, schema_version, input_schema, output_schema, revision_binding, execution_mode, execution_channel, mutation_type, risk, scopes, approval_policy, ui_handoff`.
- **Zero Leakage:** Strictly excludes executable `handler` callables, database handles, and raw CAD/project state.

### 5.2 Read-Only HTTP Discovery Router (`/api/v1/capabilities`)
- **Location:** `backend/routers/capability_discovery.py`.
- **Method:** `GET /api/v1/capabilities` and `GET /api/v1/capabilities/discovery`.
- **Security:** Reuses existing ASGI `ApiKeyMiddleware` and session cookie authentication. Unauthenticated requests are rejected with 401. Non-admin principals receive only permitted capabilities.
- **State Mutation:** Strictly read-only; zero database writes or side effects.

---

## 6. Verification Evidence

- **Authorized Discovery Test Suite:** `backend/tests/test_capability_discovery.py` (23/23 PASS).
- **Automated Conformance Gate:** `backend/tests/test_contract_conformance.py` (6/6 PASS).
- **Protocol & OCC Gate:** `backend/tests/test_track_a_phase1_protocol.py` (8/8 PASS).
- **Regression Invariance:** `backend/tests/security/test_track_a_batch_1.py` (12/12 PASS), `backend/tests/test_phase2e_composite_workflow.py` (14/14 PASS).

