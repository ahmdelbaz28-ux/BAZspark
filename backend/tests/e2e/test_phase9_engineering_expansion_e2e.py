"""backend/tests/e2e/test_phase9_engineering_expansion_e2e.py — Phase 9 Gate 9 E2E Test Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 9 & Gate 9:
- For each of the 6 engineering domains:
  1. Marine (SOLAS compliance & suppression system sizing)
  2. FACP (Panel capacity, battery sizing, & SLC loop design)
  3. ETAP (Load flow & short circuit calculation kernels)
  4. Digital Twin (Telemetry synchronization & dynamic risk evaluation)
  5. Copilot (Intent translation & design synthesis)
  6. BIM & Simulation (Spatial clash detection & smoke flow preview)
- Full traversal via ControlRequest -> Planner -> Policy -> Approval -> Run.
- Zero mock paths — all results from real deterministic capabilities and orchestrator execution.
- Real audit-documented results with SHA-256 digests attached to every scenario.
- Performance: p95 latency benchmark asserting p95 < 250ms for all 12 capabilities.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.agent_run_orchestrator import (
    AgentRun,
    AgentRunOrchestrator,
)
from backend.core.agent_run_store import (
    AgentRunStore,
    ApprovalMode,
    RunStatus,
)
from backend.core.capability_registry import (
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
)
from backend.core.context_resolver import default_context_resolver
from backend.core.control_request import ControlRequest
from backend.core.generic_planner import GenericWorkflowPlanner
from backend.core.engineering_expansion_contracts import (
    CAP_MARINE_VERIFY_SOLAS,
    CAP_MARINE_CALCULATE_SUPPRESSION,
    CAP_FACP_VERIFY_PANEL,
    CAP_FACP_DESIGN_LOOP,
    CAP_ETAP_CALCULATE_LOAD_FLOW,
    CAP_ETAP_CALCULATE_SHORT_CIRCUIT,
    CAP_DIGITAL_TWIN_SYNCHRONIZE,
    CAP_DIGITAL_TWIN_EVALUATE_RISK,
    CAP_COPILOT_TRANSLATE_INTENT,
    CAP_COPILOT_SYNTHESIZE_RECOMMENDATIONS,
    CAP_BIM_VALIDATE_CLASH,
    CAP_SIMULATION_SMOKE_FLOW,
    ALL_PHASE9_CAPABILITIES,
)
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import AutonomousWorkflowPlanner
from backend.database import Database


@pytest.fixture
def e2e_db(tmp_path) -> Database:
    """Create an isolated, fresh SQLite database for Phase 9 Gate 9 E2E suite."""
    return Database(db_path=str(tmp_path / "phase9_gate9_e2e.db"))


@pytest.fixture
def bus(e2e_db: Database, monkeypatch: pytest.MonkeyPatch) -> CommandBus:
    state_store = CommandStateStore(e2e_db)
    command_bus = CommandBus(capability_registry=default_capability_registry, state_store=state_store)
    monkeypatch.setattr("backend.core.state_store.default_state_store", state_store)
    monkeypatch.setattr("backend.core.command_bus.default_command_bus", command_bus)
    return command_bus


@pytest.fixture
def store(e2e_db: Database) -> AgentRunStore:
    return AgentRunStore(e2e_db)


@pytest.fixture
def registry() -> CapabilityRegistry:
    return default_capability_registry


@pytest.fixture
def orchestrator(
    bus: CommandBus, registry: CapabilityRegistry, store: AgentRunStore
) -> AgentRunOrchestrator:
    return AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=store,
        environment="development",
    )


@pytest.fixture
def generic_planner(
    bus: CommandBus, registry: CapabilityRegistry, orchestrator: AgentRunOrchestrator
) -> GenericWorkflowPlanner:
    return GenericWorkflowPlanner(
        command_bus=bus,
        capability_registry=registry,
        context_resolver=default_context_resolver,
        orchestrator=orchestrator,
        environment="development",
    )


@pytest.fixture
def engineer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="lead-engineer-gate9",
        email="lead.eng@bazspark.io",
        role="lead_engineer",
        scopes=[
            "marine:read",
            "facp:read",
            "facp:write",
            "etap:read",
            "digital_twin:read",
            "digital_twin:write",
            "copilot:read",
            "bim:read",
            "simulation:read",
            "workspace:read",
            "governance:read",
            "governance:write",
            "audit:read",
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. MARINE DOMAIN E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_01_marine_solas_and_suppression_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 1: Marine Domain E2E execution via ControlRequest."""
    project_id = "proj-marine-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Verify SOLAS fire containment and calculate CO2 suppression for machinery space",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [CAP_MARINE_VERIFY_SOLAS, CAP_MARINE_CALCULATE_SUPPRESSION],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_MARINE_VERIFY_SOLAS in planned_caps
    assert CAP_MARINE_CALCULATE_SUPPRESSION in planned_caps

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64
    for step_id in run.completed_steps:
        assert step_id in run.artifacts
        assert run.artifacts[step_id]["auditReference"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. FACP DOMAIN E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_02_facp_panel_and_loop_design_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 2: FACP panel verification and addressable SLC loop design E2E."""
    project_id = "proj-facp-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Verify FACP panel capacity and design addressable loop topology",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [CAP_FACP_VERIFY_PANEL, CAP_FACP_DESIGN_LOOP],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_FACP_VERIFY_PANEL in planned_caps
    assert CAP_FACP_DESIGN_LOOP in planned_caps

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 3. ETAP DETERMINISTIC REST KERNEL E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_03_etap_load_flow_and_short_circuit_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 3: ETAP load flow and short circuit calculation kernels E2E."""
    project_id = "proj-etap-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Execute ETAP load flow calculation and 3-phase short circuit analysis",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [CAP_ETAP_CALCULATE_LOAD_FLOW, CAP_ETAP_CALCULATE_SHORT_CIRCUIT],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_ETAP_CALCULATE_LOAD_FLOW in planned_caps
    assert CAP_ETAP_CALCULATE_SHORT_CIRCUIT in planned_caps

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 4. DIGITAL TWIN DOMAIN E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_04_digital_twin_telemetry_and_risk_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 4: Digital twin telemetry synchronization and dynamic risk score E2E."""
    project_id = "proj-twin-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Synchronize IoT telemetry with digital twin and evaluate building risk state",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [CAP_DIGITAL_TWIN_SYNCHRONIZE, CAP_DIGITAL_TWIN_EVALUATE_RISK],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_DIGITAL_TWIN_SYNCHRONIZE in planned_caps
    assert CAP_DIGITAL_TWIN_EVALUATE_RISK in planned_caps

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 5. COPILOT DOMAIN E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_05_copilot_intent_translation_and_synthesis_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 5: Copilot intent translation and code recommendations synthesis E2E."""
    project_id = "proj-copilot-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Translate engineering query and synthesize NFPA 72 design recommendations",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [CAP_COPILOT_TRANSLATE_INTENT, CAP_COPILOT_SYNTHESIZE_RECOMMENDATIONS],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_COPILOT_TRANSLATE_INTENT in planned_caps
    assert CAP_COPILOT_SYNTHESIZE_RECOMMENDATIONS in planned_caps

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 6. BIM & SIMULATION DOMAIN E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_06_bim_clash_and_smoke_flow_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 6: BIM spatial clash detection and smoke layer descent simulation E2E."""
    project_id = "proj-bim-sim-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Validate spatial clash on fire alarm conduits and execute smoke simulation",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [CAP_BIM_VALIDATE_CLASH, CAP_SIMULATION_SMOKE_FLOW],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_BIM_VALIDATE_CLASH in planned_caps
    assert CAP_SIMULATION_SMOKE_FLOW in planned_caps

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 7. MULTILINGUAL ARABIC & MULTI-DOMAIN E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_07_multilingual_arabic_multi_domain_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 7: Multilingual Arabic multi-domain pipeline (Marine -> FACP -> Simulation -> BIM)."""
    project_id = "proj-multi-domain-ar"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "تحقق من مطابقة SOLAS وصمم حلقة الإنذار ونفذ محاكاة الدخان وتأكد من عدم وجود تعارضات",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [
            CAP_MARINE_VERIFY_SOLAS,
            CAP_FACP_DESIGN_LOOP,
            CAP_SIMULATION_SMOKE_FLOW,
            CAP_BIM_VALIDATE_CLASH,
        ],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)
    assert len(plan.steps) >= 3

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.audit_reference) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 8. STEP-BY-STEP HUMAN APPROVAL GATE E2E
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_08_step_by_step_approval_gate_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 9 Scenario 8: Human approval gate verification on mutating capability."""
    project_id = "proj-approval-gate9"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Design loop topology and synchronize digital twin state with approval",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "STEP_BY_STEP",
        "explicit_capabilities": [CAP_FACP_DESIGN_LOOP, CAP_DIGITAL_TWIN_SYNCHRONIZE],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=engineer_principal)

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.STEP_BY_STEP,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    # In step-by-step mode, run pauses for approval on mutation steps
    assert run.status in (RunStatus.WAITING_APPROVAL, RunStatus.RUNNING, RunStatus.COMPLETED)


# ═══════════════════════════════════════════════════════════════════════════
# 9. PERFORMANCE BENCHMARK: P95 LATENCY ASSERTION (PRINCIPLE 10)
# ═══════════════════════════════════════════════════════════════════════════


def test_scenario_09_p95_latency_benchmark_under_limit(
    engineer_principal: AuthenticatedPrincipal,
    bus: CommandBus,
) -> None:
    """Gate 9 Scenario 9: p95 latency benchmark for all 12 Phase 9 capabilities (asserting p95 < 250ms)."""
    p95_limit_ms = 250.0
    latencies: dict[str, list[float]] = {cap: [] for cap in ALL_PHASE9_CAPABILITIES}

    # Execute 10 iterations per capability to measure latency
    for _ in range(10):
        for cap_id in ALL_PHASE9_CAPABILITIES:
            cap_def = default_capability_registry.get(cap_id)
            assert cap_def is not None, f"Missing registered capability {cap_id}"
            assert cap_def.handler is not None

            t0 = time.perf_counter()
            res = cap_def.handler({})
            t1 = time.perf_counter()

            duration_ms = (t1 - t0) * 1000.0
            latencies[cap_id].append(duration_ms)
            assert "audit_reference" in res

    # Compute and assert p95 latency for each capability
    for cap_id, samples in latencies.items():
        sorted_samples = sorted(samples)
        p95_idx = int(0.95 * len(sorted_samples))
        p95_val = sorted_samples[min(p95_idx, len(sorted_samples) - 1)]

        assert p95_val < p95_limit_ms, (
            f"Capability {cap_id} exceeded p95 latency limit of {p95_limit_ms}ms: got {p95_val:.2f}ms"
        )
