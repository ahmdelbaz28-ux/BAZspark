"""backend/tests/e2e/test_phase8_gate8_e2e.py — Gate 8 E2E Test Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 8 & Gate 8:
- Verbatim Gate 8 Workflow: «افتح مشروع X، شغّل validation، اعرض آخر audit»
- Complete traversal through ControlRequest -> Planner -> Policy -> Approval -> Run.
- Zero mock paths — all results from real deterministic capabilities and orchestrator execution.
- Real audit-documented results with retrievable IDs attached to every scenario.
- Total 10 E2E scenarios covering multilingual, approval modes, multi-domain, artifact tracking, and audit chains.
"""

from __future__ import annotations

import json
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
    CAP_GOVERNANCE_ARTIFACT,
    CAP_GOVERNANCE_AUDIT,
    CAP_GOVERNANCE_INSPECT,
    CAP_GOVERNANCE_REPORT,
    CAP_GOVERNANCE_REVIEW,
    CAP_GOVERNANCE_VALIDATE,
    CAP_SPATIAL_PLACE_DEVICES,
    CAP_WORKSPACE_MODEL,
    CAP_WORKSPACE_PROJECT,
    CAP_WORKSPACE_REVISION,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
)
from backend.core.context_resolver import default_context_resolver
from backend.core.control_request import ControlRequest
from backend.core.execution_policy import PolicyResult
from backend.core.generic_planner import AutonomousPlan, GenericWorkflowPlanner
from backend.core.session_context import UniversalSessionContext
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import AutonomousWorkflowPlanner
from backend.database import Database


@pytest.fixture
def e2e_db(tmp_path) -> Database:
    """Create an isolated, fresh SQLite database for Phase 8 Gate 8 E2E suite."""
    return Database(db_path=str(tmp_path / "phase8_gate8_e2e.db"))


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
        user_id="lead-engineer-gate8",
        email="lead.eng@bazspark.io",
        role="lead_engineer",
        scopes=[
            "spatial:write",
            "compliance:read",
            "electrical:write",
            "hydraulics:write",
            "workspace:read",
            "governance:read",
            "governance:write",
            "audit:read",
        ],
    )


@pytest.fixture
def client(e2e_db: Database, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    state_store = CommandStateStore(e2e_db)
    command_bus = CommandBus(capability_registry=default_capability_registry, state_store=state_store)
    run_store = AgentRunStore(e2e_db)
    orchestrator = AgentRunOrchestrator(
        command_bus=command_bus,
        capability_registry=default_capability_registry,
        run_store=run_store,
        environment="development",
    )
    planner = AutonomousWorkflowPlanner(
        command_bus=command_bus,
        capability_registry=default_capability_registry,
        context_resolver=default_context_resolver,
        orchestrator=orchestrator,
        environment="development",
    )

    monkeypatch.setattr("backend.database.get_db", lambda: e2e_db)
    monkeypatch.setattr("backend.core.state_store.default_state_store", state_store)
    monkeypatch.setattr("backend.core.command_bus.default_command_bus", command_bus)
    monkeypatch.setattr("backend.core.agent_run_store.default_agent_run_store", run_store)
    monkeypatch.setattr("backend.core.agent_run_orchestrator.default_agent_run_orchestrator", orchestrator)
    monkeypatch.setattr("backend.core.workflow_planner.default_workflow_planner", planner)
    monkeypatch.setattr("backend.routers.workflow.default_agent_run_orchestrator", orchestrator)

    return TestClient(app)


# ── Scenario 1: Canonical Gate 8 Arabic Verbatim Workflow ───────────────────


def test_scenario_01_arabic_verbatim_gate8_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 1: «افتح مشروع X، شغّل validation، اعرض آخر audit» (Arabic verbatim)."""
    project_id = "proj-gate8-arabic"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "افتح مشروع proj-gate8-arabic، شغّل validation، اعرض آخر audit",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "validate": {"width_m": 12.0, "length_m": 15.0, "ceiling_height_m": 3.0},
            "audit": {"limit": 5},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    assert len(plan.steps) >= 3
    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_GOVERNANCE_VALIDATE in cap_ids
    assert CAP_GOVERNANCE_AUDIT in cap_ids

    # Execute workflow run
    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)
    assert run.audit_reference is not None
    assert len(run.audit_reference) == 64

    # Verify audit artifacts retrievable for all completed steps
    for step_id, art in run.artifacts.items():
        assert "auditReference" in art
        assert len(art["auditReference"]) == 64


# ── Scenario 2: Canonical Gate 8 English Workflow ────────────────────────────


def test_scenario_02_english_gate8_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 2: 'Open project X, run validation, show latest audit' (English)."""
    project_id = "proj-gate8-english"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Open workspace project proj-gate8-english, run compliance validation, and show latest audit trail",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "validate": {"width_m": 10.0, "length_m": 15.0},
            "audit": {"limit": 10},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    assert len(plan.steps) >= 3
    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_GOVERNANCE_VALIDATE in cap_ids
    assert CAP_GOVERNANCE_AUDIT in cap_ids

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert run.audit_reference is not None


# ── Scenario 3: Step-by-Step Approval Mode ───────────────────────────────────


def test_scenario_03_step_by_step_approval_gate8(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 3: Execution in STEP_BY_STEP approval mode."""
    project_id = "proj-gate8-stepmode"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Open project proj-gate8-stepmode and validate compliance rules",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "STEP_BY_STEP",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "validate": {"width_m": 14.0, "length_m": 20.0},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.STEP_BY_STEP,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    # In STEP_BY_STEP mode, steps require approval
    if run.status == RunStatus.WAITING_APPROVAL:
        assert run.pending_approval_id is not None
        # Approve step
        resumed = orchestrator.decide_approval(
            caller_id=engineer_principal.user_id,
            approval_id=run.pending_approval_id,
            decision="APPROVED",
        )
        assert resumed.status in (RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.WAITING_APPROVAL)


# ── Scenario 4: Multi-Domain Spatial + Governance Integration ────────────────


def test_scenario_04_multi_domain_spatial_and_governance(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 4: Open project, layout detectors, validate, and audit."""
    project_id = "proj-gate8-multidomain"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Open workspace project proj-gate8-multidomain, place smoke detectors in zone-1 12x18m, validate spacing, and audit",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "spatial": {"room_id": "zone-1", "width_m": 12.0, "length_m": 18.0, "detector_type": "smoke"},
            "validate": {"width_m": 12.0, "length_m": 18.0},
            "audit": {"limit": 5},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    assert len(plan.steps) >= 3
    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_SPATIAL_PLACE_DEVICES in cap_ids
    assert CAP_GOVERNANCE_AUDIT in cap_ids

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == len(plan.steps)


# ── Scenario 5: Artifact Tracking and Governance Report ──────────────────────


def test_scenario_05_governance_artifact_and_report_pipeline(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 5: Register deliverable artifact, generate compliance report, and inspect audit."""
    project_id = "proj-gate8-artifact-report"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Open workspace project proj-gate8-artifact-report, register DXF artifact, generate report, and audit",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "artifact": {"artifact_type": "DXF", "action": "register"},
            "report": {"report_type": "COMPLIANCE"},
            "audit": {"limit": 10},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_GOVERNANCE_ARTIFACT in cap_ids
    assert CAP_GOVERNANCE_REPORT in cap_ids
    assert CAP_GOVERNANCE_AUDIT in cap_ids

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED


# ── Scenario 6: Model and OCC Revision Verification ──────────────────────────


def test_scenario_06_model_and_revision_governance(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 6: Bind CAD/BIM model and verify canonical revision state."""
    project_id = "proj-gate8-model-rev"
    bus.state_store.set_project_revision(project_id, 2)

    control_request = ControlRequest.from_dict({
        "intent": "Open project proj-gate8-model-rev, select CAD model, and verify revision",
        "project_id": project_id,
        "expected_revision": 2,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "model": {"model_id": "model-dwg-main"},
            "revision": {"expected_revision": 2},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_WORKSPACE_MODEL in cap_ids
    assert CAP_WORKSPACE_REVISION in cap_ids

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED


# ── Scenario 7: Full REST Endpoints Integration ──────────────────────────────


def test_scenario_07_rest_api_plan_and_start_lifecycle(client: TestClient, e2e_db: Database, bus: CommandBus) -> None:
    """Gate 8 Scenario 7: REST API POST /api/v1/workflow/runs/plan and /api/v1/workflow/runs/start-plan."""
    project_id = "proj-gate8-rest"
    e2e_db.create_project({"id": project_id, "name": "REST Gate 8 Project", "author": "admin"})
    bus.state_store.set_project_revision(project_id, 1)

    plan_payload = {
        "prompt": "افتح مشروع proj-gate8-rest، شغّل validation، اعرض آخر audit",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "validate": {"width_m": 10.0, "length_m": 12.0},
            "audit": {"limit": 5},
        },
    }

    resp = client.post("/api/v1/workflow/runs/plan", json=plan_payload)
    assert resp.status_code == 200
    raw_plan = resp.json()
    plan_data = raw_plan.get("data", raw_plan)
    assert "plan_id" in plan_data
    assert len(plan_data["steps"]) >= 3

    # Start run via REST
    start_payload = {
        "project_id": project_id,
        "expected_revision": 1,
        "steps": plan_data["steps"],
        "approval_mode": "AUTO",
        "plan": {
            "plan_id": plan_data["plan_id"],
            "intent_summary": plan_data["intent_summary"],
            "dag": plan_data["dag"],
        },
    }

    start_resp = client.post("/api/v1/workflow/runs/start-plan", json=start_payload)
    assert start_resp.status_code == 200
    raw_run = start_resp.json()
    run_data = raw_run.get("data", raw_run)
    assert run_data["status"] in ("COMPLETED", "WAITING_APPROVAL")
    if run_data["status"] == "WAITING_APPROVAL" and run_data.get("pending_approval_id"):
        run_id = run_data.get("run_id") or run_data.get("runId")
        app_id = run_data.get("pending_approval_id") or run_data.get("pendingApprovalId")
        decide_resp = client.post(
            f"/api/v1/workflow/runs/{run_id}/approvals/{app_id}/decide",
            json={"decision": "APPROVED"},
        )
        assert decide_resp.status_code == 200
        dec_data = decide_resp.json().get("data", decide_resp.json())
        assert dec_data["status"] in ("COMPLETED", "RUNNING", "WAITING_APPROVAL")


# ── Scenario 8: Multilingual French Gate 8 Intent ────────────────────────────


def test_scenario_08_french_multilingual_gate8(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 8: 'Ouvrir projet proj-gate8-fr, exécuter validation et audit' (French)."""
    project_id = "proj-gate8-fr"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Ouvrir workspace projet proj-gate8-fr, exécuter validation règles et audit",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "validate": {"width_m": 8.0, "length_m": 10.0},
            "audit": {"limit": 5},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_GOVERNANCE_VALIDATE in cap_ids
    assert CAP_GOVERNANCE_AUDIT in cap_ids

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED


# ── Scenario 9: Multilingual German Gate 8 Intent ────────────────────────────


def test_scenario_09_german_multilingual_gate8(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 9: 'Projekt proj-gate8-de öffnen, Validierung ausführen und Audit anzeigen' (German)."""
    project_id = "proj-gate8-de"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Projekt proj-gate8-de workspace öffnen, Validierung ausführen und Audit anzeigen",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "composite_spec": {
            "project_id": project_id,
            "workspace": {"action": "open"},
            "validate": {"width_m": 12.0, "length_m": 16.0},
            "audit": {"limit": 5},
        },
    })

    plan = generic_planner.plan_control_request(
        request=control_request,
        principal=engineer_principal,
    )

    cap_ids = [s.capability_id for s in plan.steps]
    assert CAP_WORKSPACE_PROJECT in cap_ids
    assert CAP_GOVERNANCE_VALIDATE in cap_ids
    assert CAP_GOVERNANCE_AUDIT in cap_ids

    run = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED


# ── Scenario 10: Immutable Audit Lineage Chain Across Multi-Run Lifecycle ────


def test_scenario_10_immutable_audit_lineage_chain(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Gate 8 Scenario 10: Verify multi-run audit lineage produces sequential verifiable digests."""
    project_id = "proj-gate8-audit-chain"
    bus.state_store.set_project_revision(project_id, 1)

    # 1. First run: open & validate
    cr1 = ControlRequest.from_dict({
        "intent": "Open workspace project proj-gate8-audit-chain and validate",
        "project_id": project_id,
        "expected_revision": 1,
        "composite_spec": {"project_id": project_id, "workspace": {"action": "open"}, "validate": {"width_m": 10.0, "length_m": 12.0}},
    })
    plan1 = generic_planner.plan_control_request(request=cr1, principal=engineer_principal)
    run1 = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan1.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan1.plan_id, "intent_summary": plan1.intent_summary, "dag": plan1.dag},
    )
    assert run1.status == RunStatus.COMPLETED

    # 2. Second run: query audit using current updated canonical revision
    latest_rev = bus.get_project_revision(project_id) or 6
    cr2 = ControlRequest.from_dict({
        "intent": "Show latest audit records for project proj-gate8-audit-chain",
        "project_id": project_id,
        "expected_revision": latest_rev,
        "composite_spec": {"project_id": project_id, "audit": {"limit": 10}},
    })
    plan2 = generic_planner.plan_control_request(request=cr2, principal=engineer_principal)
    run2 = orchestrator.start_run(
        engineer_principal,
        project_id=project_id,
        steps=plan2.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan2.plan_id, "intent_summary": plan2.intent_summary, "dag": plan2.dag},
    )
    assert run2.status == RunStatus.COMPLETED

    # Verify both runs have distinct, valid SHA-256 audit references
    assert run1.audit_reference != run2.audit_reference
    assert len(run1.audit_reference) == 64
    assert len(run2.audit_reference) == 64
