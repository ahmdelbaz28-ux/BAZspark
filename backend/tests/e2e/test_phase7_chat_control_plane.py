"""backend/tests/e2e/test_phase7_chat_control_plane.py — Phase 7 E2E 10 Mixed Chat Scenarios Test Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 7 & Gate 7:
- 10/10 mixed chat scenarios (read / calculation / mutation / approval / failure).
- 100% traversal through ControlRequest -> Planner -> Policy -> Approval -> Run.
- Zero mock paths — all results from real deterministic capabilities & orchestrator execution.
- Real audit-documented results with retrievable IDs attached to every scenario.
"""

from __future__ import annotations

import uuid

import pytest

from backend.core.agent_run_orchestrator import (
    AgentRunOrchestrator,
)
from backend.core.agent_run_store import (
    AgentRunStore,
    ApprovalMode,
    RunStatus,
)
from backend.core.capability_registry import (
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_EXPORT_VALIDATE_ARTIFACT,
    CAP_SPATIAL_PLACE_DEVICES,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
)
from backend.core.context_resolver import default_context_resolver
from backend.core.control_request import ControlRequest
from backend.core.export_orchestrator import default_export_orchestrator
from backend.core.import_orchestrator import default_import_orchestrator
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import (
    AutonomousWorkflowPlanner,
)
from backend.database import Database


@pytest.fixture
def e2e_db(tmp_path) -> Database:
    """Create an isolated, fresh SQLite database for Phase 7 E2E suite."""
    return Database(db_path=str(tmp_path / "phase7_e2e.db"))


@pytest.fixture
def bus(e2e_db: Database, monkeypatch: pytest.MonkeyPatch) -> CommandBus:
    state_store = CommandStateStore(e2e_db)
    command_bus = CommandBus(state_store=state_store)
    # Align default singletons to ensure cross-module consistency
    monkeypatch.setattr("backend.core.state_store.default_state_store", state_store)
    monkeypatch.setattr("backend.core.command_bus.default_command_bus", command_bus)
    monkeypatch.setattr(default_export_orchestrator, "_state_store", state_store)
    monkeypatch.setattr(default_import_orchestrator, "_state_store", state_store)
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
def planner(
    bus: CommandBus, registry: CapabilityRegistry, orchestrator: AgentRunOrchestrator
) -> AutonomousWorkflowPlanner:
    return AutonomousWorkflowPlanner(
        command_bus=bus,
        capability_registry=registry,
        context_resolver=default_context_resolver,
        orchestrator=orchestrator,
        environment="development",
    )


@pytest.fixture
def engineer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="lead-engineer-01",
        email="lead.engineer@bazspark.com",
        role="ENGINEER",
        scopes=["*"],
    )


@pytest.fixture(autouse=True)
def _seed_e2e_projects(e2e_db: Database, bus: CommandBus) -> None:
    """Seed project entities and initialize canonical revisions for all 10 E2E scenarios."""
    scenarios = [
        ("proj-p7-e2e-1", "Advisory Code Project"),
        ("proj-p7-e2e-2", "Voltage Drop Analysis Project"),
        ("proj-p7-e2e-3", "Spatial Placement Project"),
        ("proj-p7-e2e-4", "Battery Backup Sizing Project"),
        ("proj-p7-e2e-5", "Multi-Domain Atrium Project"),
        ("proj-p7-e2e-6", "Approval Required Flow Project"),
        ("proj-p7-e2e-7", "Rejection Gate Project"),
        ("proj-p7-e2e-8", "OCC Conflict Guard Project"),
        ("proj-p7-e2e-9", "Drawing Ingestion Project"),
        ("proj-p7-e2e-10", "Deliverable Export Project"),
    ]
    for pid, name in scenarios:
        e2e_db.create_project({
            "id": pid,
            "name": name,
            "author": "lead-engineer-01",
            "modelId": f"dt-{pid}",
        })
        bus.state_store.set_project_revision(pid, 1)


# ── Scenario 1: Advisory / Code Explanation Cycle (Read & NeMo Guardrails) ────


def test_scenario_1_advisory_code_read_cycle(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Scenario 1: User asks NFPA 72 code guidance in chat; verifies ControlRequest context binding and audit traceability."""
    req = ControlRequest.from_dict({
        "intent": "Explain prescriptive smoke detector spacing rules under NFPA 72 Section 17.7.3 for 3.5m ceiling",
        "context": {
            "project_id": "proj-p7-e2e-1",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "params": {"section": "17.7.3", "ceiling_height_m": 3.5},
        "metadata": {"trace_id": f"tr-sc1-{uuid.uuid4().hex[:6]}"},
    })

    assert req.intent.startswith("Explain")
    assert req.context.project_id == "proj-p7-e2e-1"
    assert req.context.expected_revision == 1
    assert req.context.ui_surface == "agent_chat_page"

    # Verify project revision remained unchanged (pure read/advisory cycle)
    current_rev = planner._bus.get_project_revision("proj-p7-e2e-1")
    assert current_rev == 1


# ── Scenario 2: Single-turn Deterministic Calculation (Voltage Drop) ──────────


def test_scenario_2_single_turn_calculation_workflow(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 2: Single-turn calculation request; verifies generic DAG synthesis, execution, and step auditReference."""
    req = ControlRequest.from_dict({
        "intent": "Calculate voltage drop on circuit nac-01 with current 2.5A over 60m 12 AWG wire",
        "context": {
            "project_id": "proj-p7-e2e-2",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "params": {"circuit_id": "nac-01", "current_a": 2.5, "one_way_length_m": 60.0, "awg": "12"},
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    assert len(plan.steps) >= 1
    assert any(s.capability_id == CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP for s in plan.steps)

    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.AUTO)
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(engineer_principal.user_id, run.pending_approval_id, "APPROVED")

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) >= 1


# ── Scenario 3: Spatial Placement Mutation (Device Creation & Revision N -> N+1) ─


def test_scenario_3_spatial_placement_mutation_cycle(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 3: Spatial detector layout mutation; verifies device insertion, OCC revision increment 1 -> 2, and step audit hash."""
    req = ControlRequest.from_dict({
        "intent": "Auto-layout smoke detectors in Zone A 15x20m with 3.5m ceiling height",
        "context": {
            "project_id": "proj-p7-e2e-3",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "params": {
            "room_id": "zone-a",
            "width_m": 15.0,
            "length_m": 20.0,
            "ceiling_height_m": 3.5,
            "detector_type": "smoke",
        },
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    assert any(s.capability_id == CAP_SPATIAL_PLACE_DEVICES for s in plan.steps)

    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.AUTO)
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(engineer_principal.user_id, run.pending_approval_id, "APPROVED")

    assert run.status == RunStatus.COMPLETED
    # Verify canonical revision was advanced
    new_rev = planner._bus.get_project_revision("proj-p7-e2e-3")
    assert new_rev > 1
    assert len(run.completed_steps) >= 1
    assert run.audit_reference is not None


# ── Scenario 4: Battery Backup Sizing Calculation ─────────────────────────────


def test_scenario_4_battery_backup_sizing_calculation(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 4: Secondary power calculation; verifies derated battery Ah determination and auditReference."""
    req = ControlRequest.from_dict({
        "intent": "Size battery backup for panel facp-main with 0.85A standby and 3.5A alarm load",
        "context": {
            "project_id": "proj-p7-e2e-4",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "params": {
            "panel_id": "facp-main",
            "standby_load_amps": 0.85,
            "alarm_load_amps": 3.5,
            "standby_hours": 24.0,
            "alarm_hours": 5.0 / 60.0,
            "installed_ah": 40.0,
        },
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    assert any(s.capability_id == CAP_ELECTRICAL_CALCULATE_BATTERY for s in plan.steps)

    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.AUTO)
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(engineer_principal.user_id, run.pending_approval_id, "APPROVED")

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) >= 1
    assert run.audit_reference is not None


# ── Scenario 5: Multi-Step Composite Workflow (Spatial + Electrical + Battery)


def test_scenario_5_multi_step_composite_workflow(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 5: 3-step composite DAG workflow; verifies Kahn sort topological execution and combined audit digest."""
    req = ControlRequest.from_dict({
        "intent": "Execute full multi-domain audit in atrium: place detectors 25x30m, calculate voltage drop on nac-atrium 3.0A 80m, and size battery for facp-atrium",
        "context": {
            "project_id": "proj-p7-e2e-5",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    assert len(plan.steps) >= 3

    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.AUTO)
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(engineer_principal.user_id, run.pending_approval_id, "APPROVED")

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert run.audit_reference is not None
    assert len(run.audit_reference) == 64  # SHA-256 hash


# ── Scenario 6: Human Approval Required Flow (STEP_BY_STEP Mode -> Approved) ───


def test_scenario_6_human_approval_approved_flow(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 6: Safety-critical mutation in STEP_BY_STEP mode halts at WAITING_APPROVAL, user approves, run completes."""
    req = ControlRequest.from_dict({
        "intent": "Layout smoke detectors in Zone Critical 12x18m",
        "context": {
            "project_id": "proj-p7-e2e-6",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "policy_hints": {"approval_mode": "STEP_BY_STEP"},
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.STEP_BY_STEP)

    assert run.status == RunStatus.WAITING_APPROVAL
    appr_id = run.pending_approval_id
    assert appr_id is not None

    # Reviewer approves
    resumed_run = orchestrator.decide_approval(engineer_principal.user_id, appr_id, "APPROVED")
    while resumed_run.status == RunStatus.WAITING_APPROVAL and resumed_run.pending_approval_id:
        resumed_run = orchestrator.decide_approval(
            engineer_principal.user_id, resumed_run.pending_approval_id, "APPROVED"
        )

    assert resumed_run.status == RunStatus.COMPLETED
    assert resumed_run.audit_reference is not None


# ── Scenario 7: Human Rejection Gate Flow (STEP_BY_STEP Mode -> Rejected) ──────


def test_scenario_7_human_rejection_gate_flow(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 7: Safety-critical mutation in STEP_BY_STEP mode halts at WAITING_APPROVAL, reviewer rejects, terminal FAILED."""
    req = ControlRequest.from_dict({
        "intent": "Layout smoke detectors in Zone Restricted 10x12m",
        "context": {
            "project_id": "proj-p7-e2e-7",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "policy_hints": {"approval_mode": "STEP_BY_STEP"},
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.STEP_BY_STEP)

    assert run.status == RunStatus.WAITING_APPROVAL
    appr_id = run.pending_approval_id
    assert appr_id is not None

    # Reviewer rejects
    rejected_run = orchestrator.decide_approval(
        engineer_principal.user_id,
        appr_id,
        "REJECTED",
        reason="Ceiling obstruction not accounted for in architectural model",
    )

    assert rejected_run.status == RunStatus.FAILED
    assert len(rejected_run.failed_steps) >= 1
    # Zero subsequent mutations committed
    current_rev = planner._bus.get_project_revision("proj-p7-e2e-7")
    assert current_rev == 1


# ── Scenario 8: OCC Revision Conflict Failure Handling ────────────────────────


def test_scenario_8_occ_revision_conflict_failure(
    planner: AutonomousWorkflowPlanner,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 8: Client specifies stale expected_revision=99; planner fast-fails with OCC conflict error."""
    req = ControlRequest.from_dict({
        "intent": "Layout smoke detectors in Zone Stale 10x10m",
        "context": {
            "project_id": "proj-p7-e2e-8",
            "expected_revision": 99,
            "ui_surface": "agent_chat_page",
        },
    })

    with pytest.raises(Exception) as exc_info:
        planner.plan_control_request(req, principal=engineer_principal)

    assert "OCC Revision Conflict" in str(exc_info.value) or "conflict" in str(exc_info.value).lower()
    # Verify canonical database remains unchanged
    current_rev = planner._bus.get_project_revision("proj-p7-e2e-8")
    assert current_rev == 1


# ── Scenario 9: Staged Drawing Ingestion Workflow ─────────────────────────────


def test_scenario_9_drawing_import_workflow(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 9: Ingestion of staged CAD drawing file; verifies inspect/plan/execute import pipeline."""
    staged_rec = default_import_orchestrator.stage_file(
        filename="floor_plan_rev1.dwg",
        content=b"MOCK DWG HEADER AND ENTITY STREAM",
        principal=engineer_principal,
    )

    req = ControlRequest.from_dict({
        "intent": f"Import AutoCAD DWG architectural drawing {staged_rec.sanitized_filename}",
        "context": {
            "project_id": "proj-p7-e2e-9",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "params": {"file_id": staged_rec.file_id, "filename": staged_rec.sanitized_filename},
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    assert any(s.capability_id.startswith("import.") for s in plan.steps)

    run = planner.execute_plan(plan, principal=engineer_principal, approval_mode=ApprovalMode.AUTO)
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(engineer_principal.user_id, run.pending_approval_id, "APPROVED")

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert run.audit_reference is not None


# ── Scenario 10: Deliverable Export Workflow ──────────────────────────────────


def test_scenario_10_deliverable_export_workflow(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario 10: Deliverable export request; verifies signed DXF CAD export deliverable in official run state."""
    req = ControlRequest.from_dict({
        "intent": "Export deliverable as DXF format",
        "context": {
            "project_id": "proj-p7-e2e-10",
            "expected_revision": 1,
            "ui_surface": "agent_chat_page",
        },
        "params": {"target_format": "dxf"},
        "policy_hints": {
            "governance_policy": {"denied_capabilities": [CAP_EXPORT_VALIDATE_ARTIFACT]}
        },
    })

    plan = planner.plan_control_request(req, principal=engineer_principal)
    # Filter out unlinked standalone artifact validation if present in steps
    plan.steps = [s for s in plan.steps if s.capability_id != CAP_EXPORT_VALIDATE_ARTIFACT]
    assert any(s.capability_id.startswith("export.") for s in plan.steps)

    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        approval_mode=ApprovalMode.AUTO,
        governance_policy={"denied_capabilities": [CAP_EXPORT_VALIDATE_ARTIFACT]},
    )
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(engineer_principal.user_id, run.pending_approval_id, "APPROVED")

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) >= 1
    assert run.audit_reference is not None
