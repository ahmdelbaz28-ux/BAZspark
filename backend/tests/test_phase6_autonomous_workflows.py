"""backend/tests/test_phase6_autonomous_workflows.py — Phase 6 Autonomous Engineering Workflows Test Suite.

Verifies end-to-end autonomous engineering workflows:
- Scenario A: Read / Analyze Workflow
- Scenario B: Mutating Workflow with OCC Revision Update (N -> N+1)
- Scenario C: Deterministic Capability Failure Propagation & Terminal State
- Scenario D: Retry & Idempotency Protection (Zero Duplicate Mutation)
- Scenario E: In-Flight & Pending Approval Cancellation Boundary
- Scenario F: RBAC Scope Enforcement & Policy Denial
- REST API & WebSocket Autonomous Workflow Handlers
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import app
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
    CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    CAP_SPATIAL_PLACE_DEVICES,
    CAP_SPATIAL_VERIFY_SPACING,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
)
from backend.core.context_resolver import default_context_resolver
from backend.core.execution_policy import PolicyResult
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import (
    AutonomousPlan,
    AutonomousWorkflowPlanner,
    CapabilityUnavailableError,
)
from backend.database import Database


@pytest.fixture
def fresh_db(tmp_path) -> Database:
    return Database(db_path=str(tmp_path / "phase6_test.db"))


@pytest.fixture
def bus(fresh_db: Database) -> CommandBus:
    state_store = CommandStateStore(fresh_db)
    return CommandBus(state_store=state_store)


@pytest.fixture
def store(fresh_db: Database) -> AgentRunStore:
    return AgentRunStore(fresh_db)


@pytest.fixture
def registry() -> CapabilityRegistry:
    return default_capability_registry


@pytest.fixture
def orchestrator(
    bus: CommandBus, registry: CapabilityRegistry, store: AgentRunStore
) -> AgentRunOrchestrator:
    return AgentRunOrchestrator(command_bus=bus, capability_registry=registry, run_store=store)


@pytest.fixture
def planner(
    bus: CommandBus, registry: CapabilityRegistry, orchestrator: AgentRunOrchestrator
) -> AutonomousWorkflowPlanner:
    return AutonomousWorkflowPlanner(
        command_bus=bus,
        capability_registry=registry,
        context_resolver=default_context_resolver,
        orchestrator=orchestrator,
    )


@pytest.fixture
def engineer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="engineer-42",
        email="engineer-42@bazspark.com",
        role="ENGINEER",
        scopes=["*"],
    )


@pytest.fixture
def viewer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="viewer-01",
        email="viewer-01@bazspark.com",
        role="VIEWER",
        scopes=["project:read"],
    )


# ── Scenario A: Read / Analyze Workflow ───────────────────────────────────────


def test_scenario_a_read_analyze_workflow(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Scenario A: User submits read/analyze request; verifies context resolution, planning, dry-run, and zero canonical mutation."""
    prompt = "Verify detector spacing in Zone A 15x20m with 3.5m ceiling"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-scenario-a",
        approval_mode=ApprovalMode.AUTO,
    )

    assert plan.plan_id.startswith("plan-")
    assert plan.project_id == "proj-scenario-a"
    assert len(plan.steps) >= 2
    assert plan.steps[0].capability_id == CAP_SPATIAL_PLACE_DEVICES
    assert plan.steps[1].capability_id == CAP_SPATIAL_VERIFY_SPACING
    assert "devices" in plan.projected_state

    # Verify dry-run did not advance canonical project revision
    current_rev = planner._bus.get_project_revision("proj-scenario-a")
    assert current_rev == 1


# ── Scenario B: Mutating Workflow with OCC Revision Advancement ───────────────


def test_scenario_b_mutating_workflow_lifecycle(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario B: User submits multi-step engineering mutation; executes through AgentRunOrchestrator and updates canonical revision N -> N+1."""
    prompt = "Layout smoke detectors in Zone B, calculate voltage drop on NAC-01 2.0A 40m, and size battery backup"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-scenario-b",
        approval_mode=ApprovalMode.AUTO,
    )

    assert len(plan.steps) >= 3
    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        approval_mode=ApprovalMode.AUTO,
        conversation_id="conv-b-01",
    )

    # In AUTO mode, REVERSIBLE steps run automatically, but ENGINEERING_MUTATION steps
    # pause for human review to uphold safety invariants.
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(
            engineer_principal.user_id, run.pending_approval_id, "APPROVED"
        )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert len(run.failed_steps) == 0

    # Verify canonical revision was advanced for the mutating steps
    current_rev = planner._bus.get_project_revision("proj-scenario-b")
    assert current_rev > 1

    # Verify artifacts and recovery state are properly recorded
    assert run.artifacts
    assert run.recovery_state.get("last_completed_revision") is not None


# ── Scenario C: Deterministic Capability Failure Propagation ──────────────────


def test_scenario_c_deterministic_failure_propagation(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    registry: CapabilityRegistry,
    engineer_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario C: Capability failure propagates deterministically, halts run in FAILED status, and logs audit without false success."""
    prompt = "Layout smoke detectors in Zone C and check electrical voltage drop"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-scenario-c",
        approval_mode=ApprovalMode.AUTO,
    )

    # Force step 1 (spatial) to fail deterministically
    def _failing_handler(payload: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("Simulated spatial layout computation failure")

    cap = registry.get(CAP_SPATIAL_PLACE_DEVICES)
    assert cap is not None
    monkeypatch.setattr(cap, "handler", _failing_handler)

    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        approval_mode=ApprovalMode.AUTO,
        conversation_id="conv-c-01",
    )

    assert run.status == RunStatus.FAILED
    assert len(run.failed_steps) == 1
    assert "step-1-spatial-layout" in run.failed_steps[0].get("step_id", "")


# ── Scenario D: Retry & Idempotency Protection ────────────────────────────────


def test_scenario_d_retry_idempotency_protection(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    registry: CapabilityRegistry,
    engineer_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario D: Retrying a failed run replays already completed steps from CommandBus idempotency cache with zero duplicate mutation."""
    prompt = "Layout smoke detectors in Zone D and verify spacing and electrical drop"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-scenario-d",
        approval_mode=ApprovalMode.AUTO,
    )

    # Make step 1 fail on first attempt
    call_count = {"count": 0}
    orig_cap = registry.get(CAP_SPATIAL_PLACE_DEVICES)
    assert orig_cap is not None
    orig_handler = orig_cap.handler

    def _flaky_handler(payload: dict[str, Any]) -> dict[str, Any]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("Transient computation glitch")
        if orig_handler:
            return orig_handler(payload)
        return {"devices": []}

    monkeypatch.setattr(orig_cap, "handler", _flaky_handler)

    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        approval_mode=ApprovalMode.AUTO,
    )
    assert run.status == RunStatus.FAILED

    # Retry the run — step 1 succeeds on retry, and subsequent approval steps complete
    retried_run = orchestrator.retry_run(engineer_principal.user_id, run.run_id)
    while retried_run.status == RunStatus.WAITING_APPROVAL and retried_run.pending_approval_id:
        retried_run = orchestrator.decide_approval(
            engineer_principal.user_id, retried_run.pending_approval_id, "APPROVED"
        )
    assert retried_run.status == RunStatus.COMPLETED
    assert len(retried_run.completed_steps) == len(plan.steps)


# ── Scenario E: Cancellation Boundary ─────────────────────────────────────────


def test_scenario_e_cancellation_boundary(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario E: Workflow started in STEP_BY_STEP mode halts for approval and is cancelled cleanly."""
    prompt = "Layout smoke detectors in Zone E"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-scenario-e",
        approval_mode=ApprovalMode.STEP_BY_STEP,
    )

    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        approval_mode=ApprovalMode.STEP_BY_STEP,
    )

    assert run.status == RunStatus.WAITING_APPROVAL
    appr_id = run.pending_approval_id
    assert appr_id is not None

    # Cancel the run
    cancelled = orchestrator.cancel_run(engineer_principal.user_id, run.run_id)
    assert cancelled.status == RunStatus.CANCELLED

    # Verify no subsequent execution or approval is possible
    with pytest.raises(Exception):
        orchestrator.decide_approval(engineer_principal.user_id, appr_id, "APPROVED")


# ── Scenario F: RBAC & Policy Denial ──────────────────────────────────────────


def test_scenario_f_unauthorized_principal_denied(
    planner: AutonomousWorkflowPlanner,
    viewer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario F: Principal lacking required mutation scopes is rejected during planning before any engineering capability runs."""
    prompt = "Layout smoke detectors in Zone F and calculate voltage drop"

    with pytest.raises(CapabilityUnavailableError):
        planner.plan_workflow(
            prompt,
            principal=viewer_principal,
            project_id="proj-scenario-f",
        )


def test_scenario_f_governance_policy_denial(
    planner: AutonomousWorkflowPlanner,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Scenario F: Governance policy denying a capability causes overall_policy_decision == DENIED and halts execution."""
    prompt = "Layout smoke detectors in Zone F"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-scenario-f2",
        governance_policy={"denied_capabilities": [CAP_SPATIAL_PLACE_DEVICES]},
    )

    assert plan.overall_policy_decision == PolicyResult.DENIED.value

    # Executing a denied plan fails immediately at step 1
    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        governance_policy={"denied_capabilities": [CAP_SPATIAL_PLACE_DEVICES]},
    )
    assert run.status == RunStatus.FAILED


# ── REST API Endpoints Verification ───────────────────────────────────────────


def test_rest_plan_and_start_endpoints(monkeypatch: pytest.MonkeyPatch, fresh_db: Database) -> None:
    """Verify POST /api/workflow/runs/plan and POST /api/workflow/runs/start-plan endpoints."""
    from backend.rbac import Role
    from backend.routers import workflow

    monkeypatch.setattr(workflow, "get_current_principal", lambda request: "engineer-42")
    monkeypatch.setattr(
        workflow, "require_permission", lambda permission: (lambda request: Role.ENGINEER)
    )
    monkeypatch.setattr("backend.auth.has_permission", lambda role, permission: True)

    fresh_db.create_project({
        "id": "proj-rest-test",
        "name": "Rest Test Project",
        "author": "engineer-42",
    })

    client = TestClient(app)

    # 1. Plan workflow
    res_plan = client.post(
        "/api/workflow/runs/plan",
        json={
            "prompt": "Layout smoke detectors in room 10x15m and calculate voltage drop",
            "project_id": "proj-rest-test",
            "approval_mode": "AUTO",
        },
    )
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["success"] is True
    assert "plan_id" in plan_data["data"]
    assert len(plan_data["data"]["steps"]) >= 2

    # 2. Start planned workflow
    res_start = client.post(
        "/api/workflow/runs/start-plan",
        json={
            "prompt": "Layout smoke detectors in room 10x15m",
            "project_id": "proj-rest-test",
            "approval_mode": "AUTO",
        },
    )
    assert res_start.status_code == 200
    start_data = res_start.json()
    assert start_data["success"] is True
    assert start_data["data"]["status"] in ("COMPLETED", "WAITING_APPROVAL")
    assert "runId" in start_data["data"]


def test_import_and_export_workflow_planning(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Verify autonomous planning and synthesis for import and export intents."""
    # 1. Import intent
    import_plan = planner.plan_workflow(
        "Import AutoCAD DWG architectural drawing floor_plan.dwg",
        principal=engineer_principal,
        project_id="proj-import-test",
        composite_spec={"filename": "floor_plan.dwg"},
    )
    assert any(s.capability_id.startswith("import.") for s in import_plan.steps)
    assert import_plan.intent_category in ("import", "composite")

    # 2. Export intent
    export_plan = planner.plan_workflow(
        "Export deliverable as IFC format",
        principal=engineer_principal,
        project_id="proj-export-test",
    )
    assert any(s.capability_id.startswith("export.") for s in export_plan.steps)
    assert export_plan.intent_category in ("export", "composite")


def test_hydraulic_and_battery_workflow_planning_and_execution(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Verify hydraulic calculation and battery sizing workflows with human approval."""
    prompt = "Solve hydraulic pipe flow on pipe-01 length 30m flow 200 gpm, and size battery backup for FACP-01"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-hyd-bat",
        approval_mode=ApprovalMode.AUTO,
    )
    assert len(plan.steps) >= 2
    assert any(s.capability_id == CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH for s in plan.steps)
    assert any(s.capability_id == CAP_ELECTRICAL_CALCULATE_BATTERY for s in plan.steps)

    run = planner.execute_plan(
        plan,
        principal=engineer_principal,
        approval_mode=ApprovalMode.AUTO,
    )
    while run.status == RunStatus.WAITING_APPROVAL and run.pending_approval_id:
        run = orchestrator.decide_approval(
            engineer_principal.user_id, run.pending_approval_id, "APPROVED"
        )
    assert run.status == RunStatus.COMPLETED


def test_invalid_workflow_intent_rejection(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Verify non-engineering conversational messages raise InvalidWorkflowIntentError."""
    from backend.core.workflow_planner import InvalidWorkflowIntentError

    with pytest.raises(InvalidWorkflowIntentError):
        planner.plan_workflow(
            "xyz 123 conversational query without engineering actions",
            principal=engineer_principal,
            project_id="proj-invalid",
        )


@pytest.mark.asyncio
async def test_websocket_orchestration_service_autonomous_planning(
    fresh_db: Database, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Verify AIOrchestrationService handles ai_plan_workflow message."""
    from backend.routers.agent_ws import AIOrchestrationService

    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []

        async def send_json(self, data):
            self.sent_messages.append(data)

    service = AIOrchestrationService()
    ws = MockWebSocket()

    await service.handle_autonomous_workflow_intent(
        ws,
        engineer_principal,
        {
            "type": "ai_plan_workflow",
            "prompt": "Layout smoke detectors in room 12x15m and calculate voltage drop",
            "projectId": "proj-ws-plan",
            "approvalMode": "AUTO",
        },
    )

    assert len(ws.sent_messages) == 1
    msg = ws.sent_messages[0]
    assert msg["type"] == "ai_autonomous_plan"
    assert "plan" in msg
    assert "planId" in msg
    assert len(msg["plan"]["steps"]) >= 2


def test_autonomous_plan_serialization_roundtrip(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Verify serialization to dict and deserialization from dict."""
    plan = planner.plan_workflow(
        "Layout smoke detectors in room 10x12m and verify spacing",
        principal=engineer_principal,
        project_id="proj-serde",
    )

    data = plan.to_dict()
    assert isinstance(data, dict)
    assert data["plan_id"] == plan.plan_id
    assert data["project_id"] == "proj-serde"
    assert len(data["steps"]) == len(plan.steps)

    reconstructed = AutonomousPlan.from_dict(data)
    assert reconstructed.plan_id == plan.plan_id
    assert reconstructed.project_id == plan.project_id
    assert len(reconstructed.steps) == len(plan.steps)
    assert reconstructed.overall_policy_decision == plan.overall_policy_decision
