# BAZSPARK Phase 4.0 Surgical Refactoring & Production Hardening Design Specification

**Document ID:** SPEC-2026-08-20-PHASE4-HARDENING  
**Date:** 2026-08-20  
**Branch:** `feat/phase4-surgical-refactoring`  
**Status:** APPROVED  
**Author:** Pair Programming Agent & Engineering Team (Eng. Ahmed Elbaz)  

---

## 1. Executive Summary & Goals

This specification defines the exact architectural refactoring and hardening actions for Phase 4.0 of BAZSPARK.
The core goals are:
1. **Decouple Blocking Physics Computations from ASGI Event Loop:** Ensure that heavy physics and mathematical calculations (Darcy-Weisbach, Monte Carlo reliability, Raytracing, full room analysis) never block FastAPI's asynchronous event loop or starve WebSocket heartbeats. Emit streaming `ai_progress_frame` envelopes over WebSocket during multi-step executions.
2. **Harden Native IPC Bridges with Circuit Breakers & Auto-Recovery:** Implement an explicit 3-state Circuit Breaker (`CLOSED`, `OPEN`, `HALF-OPEN`) on Named Pipe channels (`RevitNamedPipeClient`, `LocalAgentServer.cs`), capping connection timeouts at 2.0s per heartbeat and failing fast with `BRIDGE_PROCESS_UNRESPONSIVE` when native CAD/BIM bridges are disconnected or unresponsive.
3. **Unify Spatial Density & Optimization Engine:** Establish `fireai/core/density_optimizer_v2.py` as the authoritative Single Source of Truth (SSOT) for spatial optimization, redirecting all consumers (`floor_orchestrator.py`, `auto_drafting_engine.py`, etc.) and maintaining backward-compatible shims in `fireai/core/spatial_engine/density_optimizer.py`.
4. **Repository Hygiene & Synthetic Documentation Purge:** Remove obsolete, duplicate, and static mockup artifacts (`docs/chaos/`, `docs/killer/`, `docs/ivv/`, `archived/mockups-v1/`) while preserving active ADRs and official documentation.
5. **Zero-Diff Core Invariants:** Ensure strict zero-diff immutability on `fireai/core/darcy_weisbach_solver.py`, `fireai/core/battery_aging_derating.py`, and `backend/db_models.py`.

---

## 2. Detailed Technical Architecture

### 2.1 Action 1: Event Loop Decoupling & WebSocket Progress Framing
- **Target Files:** `backend/routers/agent_ws.py`, `backend/routers/analyze.py`
- **Mechanism:**
  - Wrap synchronous CPU-heavy functions (`self.command_bus.execute`, `analyze_room`, `QOMNKernel.battery_capacity`, `QOMNKernel.voltage_drop`) in `asyncio.to_thread(...)`.
  - In `AIOrchestrationService` (`handle_intent`, `handle_electrical_intent`, `handle_hydraulic_intent`, `handle_battery_intent`, `handle_approval`, `handle_composite_intent`, `handle_composite_approval`), offload command execution and DAG execution to worker threads.
  - In `handle_composite_intent` and `handle_composite_approval`, emit `ai_progress_frame` messages:
    ```json
    {
      "type": "ai_progress_frame",
      "workflowId": "wf-...",
      "correlationId": "corr-...",
      "stepIndex": 1,
      "totalSteps": 3,
      "stepId": "step-1-spatial",
      "progressPct": 33.3,
      "elapsedMs": 42.5,
      "status": "in_progress"
    }
    ```
  - In `backend/routers/analyze.py`, wrap `kernel.battery_capacity`, `kernel.voltage_drop`, and `analyze_room` in `asyncio.to_thread`.

### 2.2 Action 2: Native Bridge Circuit Breaker & Auto-Recovery
- **Target Files:** `fireai/mcp_server/named_pipe_client.py`, `fireai/mcp_server/revit_mcp_server.py`
- **Circuit Breaker State Machine:**
  - **States:**
    - `CLOSED`: Normal operation. Requests pass through to named pipe.
    - `OPEN`: Tripped after 3 consecutive connection failures or timeouts (> 2.0s per heartbeat/probe). Fast-fails immediately returning `{"status": "error", "error_code": "BRIDGE_PROCESS_UNRESPONSIVE", "message": "Native bridge process is unresponsive"}` without hanging threads or mutating state.
    - `HALF-OPEN`: After a recovery cooldown (e.g. 5.0s), a single probe request is permitted. If successful, transitions to `CLOSED`; if failed, resets to `OPEN`.
  - **Thread Safety:** Protect state transitions with a re-entrant lock.
  - **Timeout:** Per-attempt connection timeout capped at 2.0s.

### 2.3 Action 3: Spatial Density & Optimization Engine Canonical Unification
- **Target Files:** `fireai/core/density_optimizer_v2.py`, `fireai/core/spatial_engine/density_optimizer.py`, `fireai/core/floor_orchestrator.py`, `fireai/core/auto_drafting_engine.py`
- **Mechanism:**
  - Consolidate the core single-room `DensityOptimizer` class, constants (`DETECTOR_RADIUS`, `MAX_SPACING_M`, `WALL_MIN_M`, `VERIFY_STEP`, etc.), and data structures (`Room`, `DetectorLayout`, `ProofCertificate`) into `fireai/core/density_optimizer_v2.py`.
  - `DensityOptimizerV2` provides both single-room (`optimize`, `optimize_single`) and batch (`optimize_batch`) execution.
  - `fireai/core/spatial_engine/density_optimizer.py` becomes a thin, backward-compatible deprecation shim that imports and re-exports all symbols from `fireai.core.density_optimizer_v2`.
  - Update `fireai/core/floor_orchestrator.py` to import directly from `fireai.core.density_optimizer_v2`.
  - Validate deterministic output on regular and irregular convex/concave polygons.

### 2.4 Action 4: Repository Hygiene & Synthetic Documentation Purge
- **Target Directories:**
  - `docs/chaos/` — Remove 7 redundant chaos test reports.
  - `docs/killer/` — Remove 7 redundant killer bug reports.
  - `docs/ivv/` — Remove 8 redundant IV&V reports.
  - `archived/mockups-v1/` — Remove legacy static UI mockups.
- **Authoritative Docs Kept:**
  - `docs/adr/`, `docs/how-to/`, `docs/reference/`, `docs/system/`.

---

## 3. Verification & Compliance Matrix

| Gate | Requirement | Verification Command |
|---|---|---|
| G1 | Non-blocking Concurrency & Routing | `py -3.12 -m pytest backend/tests/test_dynamic_provider_routing.py backend/tests/test_phase4_stress_audit.py -v --tb=short` |
| G2 | Circuit Breaker Fault Injection | Unit tests asserting fast-fail `BRIDGE_PROCESS_UNRESPONSIVE` when pipe broken |
| G3 | Full Backend Regression | `py -3.12 -m pytest backend/tests/ -q` |
| G4 | Frontend Vitest & Compilers | `npx vitest run`, `npx tsc -p tsconfig.json --noEmit`, `npm run lint` |
| G5 | Core Physics Zero-Diff Invariant | `git diff main..HEAD -- fireai/core/darcy_weisbach_solver.py fireai/core/battery_aging_derating.py backend/db_models.py` (Must output 0 diff lines) |

---
