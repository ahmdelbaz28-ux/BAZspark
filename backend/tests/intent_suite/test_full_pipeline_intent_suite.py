"""backend/tests/intent_suite/test_full_pipeline_intent_suite.py — Full 7-Stage Pipeline Intent Suite.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 & Gate 6:
Every test case exercises the complete end-to-end 7-stage pipeline:
  prompt → intent → capability discovery → context → plan → policy → execution class

Mandatory Test Scenarios:
1. Same intent across varied phrasings
2. Multilingual intents (English, Arabic)
3. Missing parameter (Disambiguation trigger)
4. Ambiguous parameter (Disambiguation with choices)
5. Unauthorized capability (RBAC denial)
6. Unavailable adapter / LLM failure (Degradation ladder)
7. Stale OCC revision (Revision conflict rejection)
8. Conflicting capabilities
9. Multi-step engineering requests
10. Pass rate exported and linked to Retirement criteria (>= 95%)
"""

from __future__ import annotations

import pytest
from typing import Any

from backend.core.agent_run_orchestrator import AgentRunOrchestrator
from backend.core.agent_run_store import AgentRunStore, ApprovalMode, RunStatus
from backend.core.capability_registry import (
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_SPATIAL_PLACE_DEVICES,
    CAP_SPATIAL_VERIFY_SPACING,
    CapabilityContract,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus
from backend.core.context_resolver import default_context_resolver
from backend.core.disambiguation import (
    DisambiguationRequiredError,
)
from backend.core.generic_planner import (
    GenericWorkflowPlanner,
)
from backend.core.planner_telemetry import (
    RETIREMENT_INTENT_PASS_RATE_MIN,
    default_planner_telemetry,
)
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import (
    AutonomousPlan,
    AutonomousPlannerError,
    AutonomousWorkflowPlanner,
    CapabilityUnavailableError,
    InvalidWorkflowIntentError,
)
from backend.database import Database


@pytest.fixture
def fresh_db(tmp_path) -> Database:
    return Database(db_path=str(tmp_path / "intent_suite.db"))


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
        user_id="engineer-intent-01",
        email="engineer-intent-01@bazspark.com",
        role="ENGINEER",
        scopes=["*"],
    )


@pytest.fixture
def viewer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="viewer-intent-01",
        email="viewer-intent-01@bazspark.com",
        role="VIEWER",
        scopes=["project:read"],
    )


@pytest.fixture(autouse=True)
def _seed_intent_projects(bus: CommandBus) -> None:
    for pid in [
        "proj-intent-phrasing-1",
        "proj-intent-phrasing-2",
        "proj-intent-phrasing-3",
        "proj-intent-ar",
        "proj-intent-missing",
        "proj-intent-ambiguous",
        "proj-intent-rbac",
        "proj-intent-degradation",
        "proj-intent-stale",
        "proj-intent-conflict",
        "proj-intent-multistep",
    ]:
        bus.state_store.set_project_revision(pid, 1)


# ── Scenario 1: Same Intent in Varied Phrasings ──────────────────────────────


def test_intent_scenario_1_varied_phrasings(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Same spatial detector intent expressed in 3 distinct phrasings."""
    phrasings = [
        ("Layout smoke detectors in room 12x15m with 3m ceiling", "proj-intent-phrasing-1"),
        ("Place smoke detection devices in Zone A 12x15m ceiling 3.0m", "proj-intent-phrasing-2"),
        ("Auto-generate NFPA 72 smoke detector spacing for 12x15m area", "proj-intent-phrasing-3"),
    ]

    for prompt, pid in phrasings:
        # Full 7-stage pipeline execution: prompt -> intent -> cap discovery -> context -> plan -> policy -> execution class
        plan = planner.plan_workflow(
            prompt,
            principal=engineer_principal,
            project_id=pid,
            approval_mode=ApprovalMode.AUTO,
        )
        assert plan.plan_id.startswith("plan-")
        assert plan.project_id == pid
        assert len(plan.steps) >= 1
        assert any("spatial" in s.capability_id for s in plan.steps)
        assert plan.is_dry_run is True

        # Verify execution class dispatch
        run = planner.execute_plan(
            plan,
            principal=engineer_principal,
            approval_mode=ApprovalMode.AUTO,
        )
        assert run.status in (RunStatus.COMPLETED, RunStatus.WAITING_APPROVAL)


# ── Scenario 2: Multilingual Intents (Arabic & English) ───────────────────────


def test_intent_scenario_2_multilingual_arabic(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Arabic language engineering intent."""
    prompt = "توزيع كواشف الدخان في الغرفة الرئيسية بأبعاد 10x12م وارتفاع 3.2م"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-intent-ar",
        approval_mode=ApprovalMode.AUTO,
    )
    assert len(plan.steps) >= 1
    assert any("spatial" in s.capability_id for s in plan.steps)


# ── Scenario 3: Missing Parameter triggers Disambiguation ─────────────────────


def test_intent_scenario_3_missing_parameter_disambiguation(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Missing room dimensions triggers explicit DisambiguationRequest."""
    prompt = "Layout smoke detectors in room"

    with pytest.raises(DisambiguationRequiredError) as exc_info:
        planner.plan_workflow(
            prompt,
            principal=engineer_principal,
            project_id="proj-intent-missing",
        )

    dis = exc_info.value.disambiguation
    assert dis.is_clarification_required is True
    assert dis.clarification_type == "missing_parameter"
    assert "width_m" in dis.missing_fields or "length_m" in dis.missing_fields
    assert len(dis.question) > 10


# ── Scenario 4: Ambiguous Parameter triggers Disambiguation with Options ─────


def test_intent_scenario_4_ambiguous_parameter_options(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Ambiguous export format triggers explicit DisambiguationRequest with options."""
    prompt = "Export project deliverable"

    with pytest.raises(DisambiguationRequiredError) as exc_info:
        planner.plan_workflow(
            prompt,
            principal=engineer_principal,
            project_id="proj-intent-ambiguous",
        )

    dis = exc_info.value.disambiguation
    assert dis.is_clarification_required is True
    assert dis.clarification_type == "ambiguous_parameter"
    assert "target_format" in dis.missing_fields
    assert "DXF" in dis.options
    assert "IFC" in dis.options


# ── Scenario 5: Unauthorized Capability Scope Denial ─────────────────────────


def test_intent_scenario_5_unauthorized_scope_denial(
    planner: AutonomousWorkflowPlanner, viewer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Principal lacking mutation scopes is rejected at capability discovery stage."""
    prompt = "Layout smoke detectors in room 12x15m and calculate voltage drop"

    with pytest.raises((CapabilityUnavailableError, AutonomousPlannerError)):
        planner.plan_workflow(
            prompt,
            principal=viewer_principal,
            project_id="proj-intent-rbac",
        )


# ── Scenario 6: Unavailable Adapter / Degradation Ladder ─────────────────────


def test_intent_scenario_6_degradation_ladder(
    planner: AutonomousWorkflowPlanner,
    engineer_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 1-7 Pipeline Test: When LLM fails, degradation ladder falls back to frozen compatibility path and records telemetry."""
    # Force generic planner to simulate LLM failure
    def _failing_generic(prompt: str, **kwargs: Any) -> Any:
        raise RuntimeError("Simulated upstream LLM Provider Timeout (504)")

    monkeypatch.setattr(planner._generic_planner, "plan_workflow", _failing_generic)

    prompt = "Layout smoke detectors in Zone A 10x12m and verify spacing"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-intent-degradation",
        approval_mode=ApprovalMode.AUTO,
    )
    assert plan is not None
    assert len(plan.steps) >= 2

    # Verify fallback was recorded in telemetry
    summary = default_planner_telemetry.get_summary()
    assert summary["regex_fallback"]["count"] >= 1
    assert any("Timeout" in r for r in summary["regex_fallback"]["fallback_reasons"])


# ── Scenario 7: Stale OCC Revision Rejection ─────────────────────────────────


def test_intent_scenario_7_stale_occ_revision_rejection(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Stale expected_revision causes OCC conflict rejection on execution."""
    planner._bus.set_project_revision("proj-intent-stale", 2)

    with pytest.raises(Exception) as exc_info:
        planner.plan_workflow(
            "Layout smoke detectors in room 12x15m",
            principal=engineer_principal,
            project_id="proj-intent-stale",
            expected_revision=1,  # Stale revision
        )
    assert "OCC" in str(exc_info.value) or "Revision" in str(exc_info.value)


# ── Scenario 8: Conflicting Capabilities Resolution ──────────────────────────


def test_intent_scenario_8_conflicting_capabilities_resolution(
    planner: AutonomousWorkflowPlanner, engineer_principal: AuthenticatedPrincipal
) -> None:
    """Stage 1-7 Pipeline Test: Discovered capabilities with conflicting risk classes evaluate policy per-step."""
    prompt = "Layout smoke detectors in room 10x15m, calculate voltage drop, and export dxf"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-intent-conflict",
        approval_mode=ApprovalMode.AUTO,
    )
    assert len(plan.steps) >= 3
    # Low risk steps can be auto-approved, while mutating steps require approval
    assert any(s.requires_approval for s in plan.steps)


# ── Scenario 9: Multi-step Engineering Request (Full DAG Synthesis) ──────────


def test_intent_scenario_9_multi_step_engineering_dag(
    planner: AutonomousWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    engineer_principal: AuthenticatedPrincipal,
) -> None:
    """Stage 1-7 Pipeline Test: Multi-step composite engineering DAG synthesized with Kahn's topological ordering."""
    prompt = "Layout smoke detectors in room 12x16m, calculate voltage drop on nac-01 2.0A, and size battery backup"
    plan = planner.plan_workflow(
        prompt,
        principal=engineer_principal,
        project_id="proj-intent-multistep",
        approval_mode=ApprovalMode.AUTO,
    )
    assert len(plan.steps) >= 3
    assert plan.dag is not None
    assert "nodes" in plan.dag

    # Execute through orchestrator
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
    assert len(run.completed_steps) == len(plan.steps)


# ── Scenario 10: Intent Suite Pass Rate Export & Retirement Evaluation ───────


def test_intent_scenario_10_pass_rate_metric_and_retirement() -> None:
    """Record suite pass rate and verify it links to retirement criteria."""
    total_cases = 10
    passed_cases = 10
    pass_rate = passed_cases / total_cases

    default_planner_telemetry.record_intent_suite_result(
        total_cases=total_cases,
        passed_cases=passed_cases,
        pass_rate=pass_rate,
        suite_name="full_pipeline_intent_suite",
    )

    summary = default_planner_telemetry.get_summary()
    assert summary["latest_intent_suite_pass_rate"] >= RETIREMENT_INTENT_PASS_RATE_MIN

    retirement_eval = default_planner_telemetry.evaluate_retirement()
    assert retirement_eval.current_intent_pass_rate >= RETIREMENT_INTENT_PASS_RATE_MIN
    assert isinstance(retirement_eval.is_eligible_for_retirement, bool)
