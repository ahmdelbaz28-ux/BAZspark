# BAZspark Agent Architecture Audit Report

**Date:** 2026-08-06  
**Auditor:** Agent Architecture Audit (automated)  
**Scope:** All AI agents and LLM-adjacent subsystems in BAZspark  
**Framework:** 12-Layer Agent Stack  

---

## Executive Verdict

**OVERALL RISK: MEDIUM** — The BAZspark agent ecosystem demonstrates strong safety-first design in its LLM integration layer (whitelisted personas, source tagging, advisory-only memory, never-raises contracts). However, **3 HIGH** and **4 MEDIUM** findings require attention, concentrated in: (1) thread-safety gaps in SQLite-backed agents, (2) unvalidated auto-mutation in the self-improvement loop, and (3) simulated validation in the distributed agent system. No CRITICAL findings — the core NFPA 72 calculation pipeline is well-protected by deterministic guards and the self-healing engine's safety gates.

---

## Agents in Scope

| # | Agent | Type | LLM? | File |
|---|-------|------|------|------|
| 1 | CUAAgent | Computer Use | Vision API | `fireai/agents/cua_agent.py` |
| 2 | LearningAgent | Knowledge Accumulation | No | `fireai/agents/learning_agent.py` |
| 3 | PredictiveAgent | Anticipatory Recommendations | No | `fireai/agents/predictive_agent.py` |
| 4 | ToolSelector | Dynamic Tool Routing | No | `fireai/agents/tool_selector.py` |
| 5 | SelfImprovementEngine | Continuous Improvement | No | `fireai/agents/self_improvement_engine.py` |
| 6 | RevitAgent | BIM Model Inspection | No | `revit_integration/ai_agents/revit_agent.py` |
| 7 | GenerativeLayoutAgent | Layout Generation | No (explicitly documented) | `fireai/core/spatial_engine/generative_layout_agent.py` |
| 8 | PlannerAgent | Distributed Planning | No | `facp_distributed/l2_orchestrator/agent_manager.py` |
| 9 | ExecutorAgent | Distributed Execution | No | `facp_distributed/l2_orchestrator/agent_manager.py` |
| 10 | ValidatorAgent | Distributed Validation | No | `facp_distributed/l2_orchestrator/agent_manager.py` |
| 11 | OptimizerAgent | Distributed Optimization | No | `facp_distributed/l2_orchestrator/agent_manager.py` |
| 12 | LLMService | LLM Chat Service | Yes (Zenmux + Aliyun MaaS) | `backend/services/llm_service.py` |
| 13 | MemoryService | Long-term Memory (Mem0) | Yes (gpt-4o / gemini-2.0-flash) | `backend/services/memory_service.py` |
| 14 | mem0_workflow_bridge | Memory Enrichment | No (read-only) | `fireai/infrastructure/mem0_workflow_bridge.py` |
| 15 | qomn_self_healing_engine | Self-Healing Runtime | Optional (Ollama Tier 2) | `fireai/core/qomn_self_healing_engine.py` |

---

## Findings

### F-01: Thread-Safety Gap in ToolSelector and SelfImprovementEngine (SQLite without RLock)

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Layer** | 12 — Persistence |
| **Mechanism** | Race condition on concurrent SQLite writes |
| **Root Cause** | `ToolSelector` and `SelfImprovementEngine` access SQLite without a threading lock, while `LearningAgent` (same DB path `fireai_learning.sqlite3`) uses `threading.RLock()` on every method |
| **Evidence** | `tool_selector.py:86-92` — `__init__` creates `self.conn = sqlite3.connect(db_path)` with no lock. `self_improvement_engine.py:113-117` — same pattern. Compare `learning_agent.py:136-147` which creates `self._lock = threading.RLock()` and wraps every DB method with `with self._lock:` |
| **Confidence** | HIGH |
| **Impact** | Under concurrent requests (e.g., multi-user or async API calls), SQLite `OperationalError: database is locked` or silent data corruption. All three agents may share the same `fireai_learning.sqlite3` file. |
| **Recommended Fix** | Add `threading.RLock()` to both `ToolSelector` and `SelfImprovementEngine`, wrapping all SQLite operations with `with self._lock:`. Match the pattern already established in `LearningAgent`. |

### F-02: SelfImprovementEngine Auto-Adjusts Parameters Without Validation

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Layer** | 11 — Hidden Repair Loops |
| **Mechanism** | Unvalidated mutation of system parameters on high-severity feedback |
| **Root Cause** | `SelfImprovementEngine.ingest_feedback()` calls `_record_improvement()` when `severity in ("high", "critical")` and `gap > 0.05`, which auto-adjusts parameters via grid search without any validation gate or human approval |
| **Evidence** | `self_improvement_engine.py:157-191` — `ingest_feedback` method. Line ~185: when severity is high/critical and gap > 0.05, `_record_improvement` is called. `_record_improvement` (lines 193-222) writes to the `improvements` table and can trigger `optimize_parameters` which returns `ParameterSuggestion` objects that could be auto-applied |
| **Confidence** | HIGH |
| **Impact** | In a fire protection engineering system, auto-adjusting parameters (spacing_multiplier, min_area_threshold, coverage_target) based on unvalidated feedback could silently degrade calculation accuracy. A single piece of high-severity feedback from a misconfigured source could shift NFPA 72 parameters. |
| **Recommended Fix** | Add a validation gate: `_record_improvement` should mark suggestions as `pending_review` instead of auto-applying. Require explicit human approval (via API endpoint) before parameter changes take effect. Add a `max_auto_adjust_pct` config (e.g., 5%) beyond which approval is mandatory. |

### F-03: ValidatorAgent Always Returns is_valid=True (Simulated Validation)

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Layer** | 7 — Tool Execution |
| **Mechanism** | Validation bypass — all results pass regardless of correctness |
| **Root Cause** | `ValidatorAgent.execute_task()` hardcodes `is_valid = True` with a comment "In real implementation, this would perform actual validation" |
| **Evidence** | `agent_manager.py:170` — `is_valid = True  # In real implementation, this would perform actual validation`. Also `ExecutorAgent` returns hardcoded results like `"improvement": "15% improvement"` and `"execution_time": "0.123 seconds"` |
| **Confidence** | HIGH |
| **Impact** | The distributed agent pipeline (Planner → Executor → Validator → Optimizer) has a broken feedback loop. Invalid or suboptimal plans will always pass validation, meaning the Optimizer receives no signal to improve. In production, this means the system cannot self-correct. |
| **Recommended Fix** | Implement actual validation logic in `ValidatorAgent.execute_task()`: check output against NFPA 72 constraints, verify coverage percentages, validate spacing rules. At minimum, add a `strict_mode` flag that rejects results outside tolerance. If full implementation is deferred, add a `SIMULATED` status flag to the response so callers know validation was not performed. |

### F-04: No Memory Admission Control in LearningAgent

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Layer** | 3 — Long-term Memory |
| **Mechanism** | Memory contamination — any experience can be stored without validation |
| **Root Cause** | `LearningAgent.store_experience()` accepts any `DesignExperience` without checking data quality, source credibility, or contradiction with existing knowledge |
| **Evidence** | `learning_agent.py:196-225` — `store_experience` method. No validation of the experience data before INSERT. No check for contradictory existing entries. No source priority (user correction vs. agent assertion). |
| **Confidence** | MEDIUM |
| **Impact** | Over time, the knowledge base can accumulate low-quality, contradictory, or incorrect experiences. When `retrieve_similar()` or `suggest_patterns()` returns these, they influence engineering decisions. Without user-correction priority, an agent assertion can override a human engineer's correction. |
| **Recommended Fix** | Add admission control: (1) Validate experience data before storage (required fields, value ranges). (2) Implement user-correction priority: when a new experience contradicts an existing one, if the new one has `source="user_correction"`, it wins. (3) Add a confidence score threshold below which experiences are quarantined for review. |

### F-05: MemoryService.add_memory Has No Scope Validation

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Layer** | 3 — Long-term Memory |
| **Mechanism** | Cross-scope memory injection |
| **Root Cause** | `MemoryService.add_memory()` accepts any `user_id`, `agent_id`, `run_id` from the request without verifying the caller has permission to write to that scope. The `/api/memory/add` endpoint does enforce `_enforce_principal_scope` on `user_id`, but `agent_id` and `run_id` are not validated. |
| **Evidence** | `memory_service.py:400-449` — `add_memory` method. `memory.py:158-159` — `_enforce_principal_scope` only applied to `user_id`. `agent_id` and `run_id` are passed through unchecked. |
| **Confidence** | MEDIUM |
| **Impact** | A compromised or misconfigured agent could write memories under another agent's scope, polluting the context for that agent's future queries. In a multi-tenant deployment, this could cross project boundaries. |
| **Recommended Fix** | Extend `_enforce_principal_scope` to validate `agent_id` (must match the authenticated agent's ID) and `run_id` (must belong to a project the user has access to). Add RBAC check for cross-scope writes. |

### F-06: qomn_self_healing_engine Tier 2 LLM Healing Can Produce Unvalidated Engineering Values

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Layer** | 11 — Hidden Repair Loops |
| **Mechanism** | LLM-generated engineering values bypass deterministic pipeline |
| **Root Cause** | When `QOMN_ENABLE_LLM_HEALING=true`, the Tier 2 path queries a local Ollama LLM and returns its response as a healed value. While physics validation and type checking are applied, the LLM has no access to the full NFPA 72 calculation context and can produce values that pass physics validators but are still incorrect for the specific scenario. |
| **Evidence** | `qomn_self_healing_engine.py:1571-1708` — Tier 2 healing. Line 1584: `QOMN_ENABLE_LLM_HEALING` gate. Line 1643: `query_local_ollama_engine()` call. Lines 1654-1669: verification checks (physics + type only). The LLM receives only the function signature and sanitized inputs — not the full calculation context. |
| **Confidence** | MEDIUM |
| **Impact** | **Currently mitigated** by the default-off safety gate (`QOMN_ENABLE_LLM_HEALING` defaults to empty). However, if enabled, a value like 7.5 psi could pass `validate_sprinkler_pressure` but be wrong for the specific hazard category. The audit trail captures this (HMAC-signed), but the value is already in the pipeline. |
| **Recommended Fix** | Add a `TIER_2_REQUIRES_HUMAN_ACK` config (default: true). When true, Tier 2 healed values are returned with `status=DEGRADED` and `metadata.requires_ack=True`, and the calling pipeline must log human acknowledgment before using the value downstream. Consider adding scenario context (room type, hazard class) to the LLM prompt. |

### F-07: Distributed Agent Manager Uses Simulated Execution Results

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Layer** | 7 — Tool Execution |
| **Mechanism** | Hardcoded results masquerading as computed values |
| **Root Cause** | `PlannerAgent`, `ExecutorAgent`, and `OptimizerAgent` all return hardcoded mock data with no actual computation. Results include fabricated metrics like "15% improvement" and "0.123 seconds". |
| **Evidence** | `agent_manager.py:64-115` (PlannerAgent), `agent_manager.py:125-160` (ExecutorAgent), `agent_manager.py:215-251` (OptimizerAgent). All `execute_task` methods return static dicts. |
| **Confidence** | HIGH |
| **Impact** | Any system relying on the distributed agent pipeline for actual FACP orchestration will receive fabricated results. The `AgentManager.execute_task_with_agent()` method dispatches to these agents transparently — callers cannot distinguish simulated from real results. |
| **Recommended Fix** | Add a `SIMULATED` flag to all agent responses when using mock implementations. Implement real computation logic or remove the agents from production routing. At minimum, `execute_task_with_agent` should check `agent.get_status()["simulated"]` and log a warning. |

---

## Positive Findings (No Action Required)

| # | Pattern | Agent | Evidence |
|---|---------|-------|----------|
| P-01 | System prompt whitelist | LLMService | `llm.py` restricts personas to a whitelist — prevents persona injection |
| P-02 | Source tagging | LLMService, MemoryService | `LLMResponse.source` and `MemoryResult.source="memory"` distinguish AI from deterministic results |
| P-03 | Advisory-only memory | mem0_workflow_bridge | Read-only (search only, no writes), advisory hints tagged `source="memory"`, conservative caps (`_MAX_QUERIES=8`, `_TOP_K_PER_QUERY=3`, `_MAX_HINTS=10`) |
| P-04 | Never-raises contract | CUAAgent, LLMService, mem0_workflow_bridge | All catch exceptions and return safe defaults — never propagate crashes to callers |
| P-05 | Safety-critical failure re-raise | qomn_self_healing_engine | `SafetyCriticalFailure` is explicitly re-raised, not swallowed (line 1399-1420) |
| P-06 | HMAC audit trail | qomn_self_healing_engine | Tamper-evident chain with SHA-256 linking and `verify_chain()` for forensic analysis |
| P-07 | Tier 2 LLM healing default-off | qomn_self_healing_engine | `QOMN_ENABLE_LLM_HEALING` defaults to empty — LLM healing must be explicitly enabled |
| P-08 | Input sanitization | qomn_self_healing_engine | Tier 2 sends only function signatures (not source code) and sanitizes inputs (scrubs paths, secrets) |
| P-09 | WebSocket nonce replay protection | agent_ws | `_validate_agent_nonce` prevents replay attacks, `_seen_agent_nonces` cleared at 5000 |
| P-10 | Newest-wins agent registration | agent_ws | VERIFY-003 FIX prevents rogue socket from intercepting commands |
| P-11 | Thread-safe singleton | LLMService | Double-checked locking pattern for thread-safe initialization |
| P-12 | Deterministic agents properly documented | GenerativeLayoutAgent | Explicitly documented as "NOT an LLM agent" — no confusion risk |

---

## Ordered Fix Plan

| Priority | Finding | Effort | Risk Reduction |
|----------|---------|--------|----------------|
| 1 | F-01: Add RLock to ToolSelector and SelfImprovementEngine | Small (1-2h) | Eliminates race condition on shared SQLite DB |
| 2 | F-02: Add validation gate to SelfImprovementEngine | Medium (4-8h) | Prevents unvalidated parameter mutation in safety-critical system |
| 3 | F-03: Implement or flag ValidatorAgent simulation | Medium (4-8h) | Restores feedback loop integrity in distributed pipeline |
| 4 | F-04: Add admission control to LearningAgent | Medium (4-8h) | Prevents memory contamination over time |
| 5 | F-05: Validate agent_id/run_id scope in MemoryService | Small (2-4h) | Prevents cross-scope memory injection |
| 6 | F-06: Add human-ack requirement for Tier 2 LLM healing | Small (2-4h) | Defense-in-depth for LLM-generated engineering values |
| 7 | F-07: Add SIMULATED flag to distributed agent responses | Small (1-2h) | Prevents callers from trusting fabricated results |

---

## 12-Layer Stack Summary

| Layer | Name | Status | Notes |
|-------|------|--------|-------|
| 1 | System Prompt | ✅ PASS | Whitelisted personas, custom instructions for engineering |
| 2 | Session History | ✅ PASS | No issues found |
| 3 | Long-term Memory | ⚠️ MEDIUM | No admission control (F-04), scope validation gap (F-05) |
| 4 | Distillation | ✅ N/A | No distillation layer in current architecture |
| 5 | Active Recall | ✅ PASS | mem0_workflow_bridge is read-only and advisory |
| 6 | Tool Selection | ⚠️ LOW | ToolSelector works but lacks thread safety (F-01) |
| 7 | Tool Execution | ⚠️ HIGH | ValidatorAgent always returns True (F-03), simulated agents (F-07) |
| 8 | Tool Interpretation | ✅ PASS | Source tagging distinguishes AI from deterministic |
| 9 | Answer Shaping | ✅ PASS | AI_DISCLAIMER present, advisory-only memory |
| 10 | Platform Rendering | ✅ N/A | Frontend out of scope |
| 11 | Hidden Repair Loops | ⚠️ HIGH | Auto-adjust without validation (F-02), Tier 2 LLM healing (F-06) |
| 12 | Persistence | ⚠️ HIGH | Thread-safety gap on SQLite (F-01) |

---

*Report generated by Agent Architecture Audit — BAZspark project*
