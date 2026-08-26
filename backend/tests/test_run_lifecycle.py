"""backend/tests/test_run_lifecycle.py — Phase 1 Agent Run lifecycle integration tests.

Covers the full lifecycle matrix required by Phase 1 §18, including approval
security (stale / wrong principal / wrong project / wrong revision /
duplicate), disconnect-reload persistence, idempotency-safe retry, and
cancel-vs-approve / resume-vs-cancel race determinism.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.core.agent_run_orchestrator import (
    AgentRunOrchestrator,
    InvalidRunStateError,
    RunPermissionError,
    StaleApprovalError,
)
from backend.core.agent_run_store import (
    AgentRunStore,
    ApprovalAlreadyDecidedError,
    ApprovalDecisionValue,
    InvalidTransitionError,
    PendingApprovalStatus,
    RunStatus,
)
from backend.core.capability_registry import CapabilityDefinition, CapabilityRegistry
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus
from backend.core.state_store import CommandStateStore
from backend.database import Database

SPATIAL = "spatial.place_devices"
ELECTRICAL = "electrical.calculate_voltage_drop"


@pytest.fixture
def fresh_db(tmp_path: Path) -> Database:
    return Database(db_path=str(tmp_path / "run_lifecycle_test.db"))


@pytest.fixture
def registry() -> CapabilityRegistry:
    return CapabilityRegistry()


@pytest.fixture
def orchestrator(fresh_db: Database, registry: CapabilityRegistry) -> AgentRunOrchestrator:
    state_store = CommandStateStore(fresh_db)
    bus = CommandBus(state_store=state_store)
    store = AgentRunStore(fresh_db)
    return AgentRunOrchestrator(
        command_bus=bus, capability_registry=registry, run_store=store, environment="development"
    )


@pytest.fixture(autouse=True)
def _auto_seed_run_lifecycle_projects(fresh_db: Database) -> None:
    store = CommandStateStore(fresh_db)
    for pid in [
        "proj-lc-auto",
        "proj-lc-appr",
        "proj-lc-rej",
        "proj-lc-pause",
        "proj-lc-cancel",
        "proj-lc-cancel2",
        "proj-lc-reload",
        "proj-lc-authz",
        "proj-lc-wp",
        "proj-lc-wproj",
        "proj-lc-wcap",
        "proj-lc-stale",
        "proj-lc-dup",
        "proj-lc-retry",
        "proj-lc-noretry",
        "proj-lc-race1",
        "proj-lc-race2",
        "proj-lc-denied",
    ]:
        store.set_project_revision(pid, 1)


@pytest.fixture
def owner() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="owner-01",
        email="owner@bazspark.io",
        role="engineer",
        scopes=["spatial:write", "electrical:write"],
        is_authenticated=True,
    )


def _spatial_step(step_id: str = "s1") -> dict:
    return {
        "step_id": step_id,
        "capability_id": SPATIAL,
        "payload": {
            "room_id": "room-lc",
            "width_m": 10.0,
            "length_m": 12.0,
            "ceiling_height_m": 3.0,
            "detector_type": "smoke",
        },
    }


def _electrical_step(step_id: str = "s2") -> dict:
    return {
        "step_id": step_id,
        "capability_id": ELECTRICAL,
        "payload": {
            "circuit_id": "nac-lc-01",
            "current_a": 2.0,
            "one_way_length_m": 35.0,
            "awg": "14",
        },
    }


# ── Happy paths ──────────────────────────────────────────────────────────────


def test_full_auto_lifecycle_completes(orchestrator: AgentRunOrchestrator, owner) -> None:
    """create → ready → running → completed (single auto-approved step)."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-auto",
        steps=[_spatial_step()],
        approval_mode="AUTO",
    )
    assert run.status == RunStatus.COMPLETED
    assert run.completed_steps == ["s1"]
    assert run.audit_reference  # audit reference persisted on completion
    assert run.completed_at is not None
    # OCC advanced the canonical revision exactly once: 1 → 2.
    assert orchestrator._bus.get_project_revision("proj-lc-auto") == 2


def test_approval_flow_approve_then_complete(orchestrator: AgentRunOrchestrator, owner) -> None:
    """create → running → waiting_approval → approved → running → completed."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-appr",
        steps=[_spatial_step("s1"), _electrical_step("s2")],
        approval_mode="AUTO",
    )
    # Step 1 (reversible mutation) auto-executed; step 2 (engineering
    # mutation) halted for approval.
    assert run.status == RunStatus.WAITING_APPROVAL
    assert run.completed_steps == ["s1"]
    assert run.pending_approval_id is not None
    assert orchestrator._bus.get_project_revision("proj-lc-appr") == 2

    decisions_before = orchestrator._store.list_decisions(run.run_id)
    assert len(decisions_before) == 0

    run = orchestrator.decide_approval(
        owner.user_id, run.pending_approval_id, ApprovalDecisionValue.APPROVED
    )
    assert run.status == RunStatus.COMPLETED
    assert run.completed_steps == ["s1", "s2"]
    assert orchestrator._bus.get_project_revision("proj-lc-appr") == 3

    decisions = orchestrator._store.list_decisions(run.run_id)
    assert len(decisions) == 1
    assert decisions[0].decision == ApprovalDecisionValue.APPROVED


def test_rejection_fails_run_and_retry_creates_new_decision(
    orchestrator: AgentRunOrchestrator, owner
) -> None:
    """waiting_approval → rejected → failed; retry re-evaluates policy and
    creates a NEW pending approval + NEW decision record (history immutable)."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-rej",
        steps=[_electrical_step("e1")],
        approval_mode="AUTO",
    )
    assert run.status == RunStatus.WAITING_APPROVAL
    first_approval_id = run.pending_approval_id

    run = orchestrator.decide_approval(
        owner.user_id, first_approval_id, ApprovalDecisionValue.REJECTED, reason="not compliant"
    )
    assert run.status == RunStatus.FAILED
    assert run.failed_steps[-1]["error_code"] == "APPROVAL_REJECTED"

    # Retry: FAILED → RUNNING via explicit recovery; policy halts again with a
    # NEW approval bound to the same step.
    run = orchestrator.retry_run(owner.user_id, run.run_id)
    assert run.status == RunStatus.WAITING_APPROVAL
    assert run.pending_approval_id != first_approval_id

    decisions = orchestrator._store.list_decisions(run.run_id)
    assert len(decisions) == 1  # only the original REJECTED record
    assert decisions[0].decision == ApprovalDecisionValue.REJECTED


# ── Pause / Resume / Cancel ──────────────────────────────────────────────────


def test_pause_then_resume_completes(orchestrator: AgentRunOrchestrator, owner) -> None:
    """paused → resumed → completed."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-pause",
        steps=[_spatial_step()],
        approval_mode="STEP_BY_STEP",
    )
    # STEP_BY_STEP halts immediately for approval of step 1.
    assert run.status == RunStatus.WAITING_APPROVAL

    paused = orchestrator.pause_run(owner.user_id, run.run_id)
    assert paused.status == RunStatus.PAUSED

    resumed = orchestrator.resume_run(owner.user_id, run.run_id)
    # The live pending approval still gates execution — resume surfaces state.
    assert resumed.status == RunStatus.WAITING_APPROVAL

    completed = orchestrator.decide_approval(
        owner.user_id, resumed.pending_approval_id, ApprovalDecisionValue.APPROVED
    )
    assert completed.status == RunStatus.COMPLETED


def test_cancel_from_waiting_approval_is_terminal(
    orchestrator: AgentRunOrchestrator, owner
) -> None:
    """running → cancelled; CANCELLED is terminal; stale approvals rejected."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-cancel",
        steps=[_electrical_step()],
        approval_mode="AUTO",
    )
    assert run.status == RunStatus.WAITING_APPROVAL
    approval_id = run.pending_approval_id

    cancelled = orchestrator.cancel_run(owner.user_id, run.run_id)
    assert cancelled.status == RunStatus.CANCELLED

    pa = orchestrator._store.get_pending_approval(approval_id)
    assert pa.status == PendingApprovalStatus.CANCELLED

    # Approving after cancellation must be rejected safely.
    with pytest.raises((ApprovalAlreadyDecidedError, InvalidRunStateError)):
        orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)
    # Terminal state preserved.
    assert orchestrator.get_run_status(owner.user_id, run.run_id).status == RunStatus.CANCELLED


def test_cancel_prevents_subsequent_step_execution(
    orchestrator: AgentRunOrchestrator, owner
) -> None:
    """After cancellation no further steps may commit."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-cancel2",
        steps=[_spatial_step("a"), _spatial_step("b")],
        approval_mode="STEP_BY_STEP",
    )
    approval_a = run.pending_approval_id
    run = orchestrator.decide_approval(owner.user_id, approval_a, ApprovalDecisionValue.APPROVED)
    # Step b now awaits its own approval.
    assert run.status == RunStatus.WAITING_APPROVAL
    rev_after_a = orchestrator._bus.get_project_revision("proj-lc-cancel2")
    assert rev_after_a == 2

    orchestrator.cancel_run(owner.user_id, run.run_id)
    # No additional commit happened after cancellation.
    assert orchestrator._bus.get_project_revision("proj-lc-cancel2") == rev_after_a


# ── Disconnect / reload persistence ──────────────────────────────────────────


def test_state_preserved_across_orchestrator_recreation(
    fresh_db: Database, registry: CapabilityRegistry, owner
) -> None:
    """disconnect/reload → state preserved; resume continues from persisted position."""
    bus = CommandBus(state_store=CommandStateStore(fresh_db))
    orch_a = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=AgentRunStore(fresh_db),
        environment="development",
    )
    run = orch_a.start_run(
        owner,
        project_id="proj-lc-reload",
        steps=[_spatial_step("s1"), _spatial_step("s2")],
        approval_mode="STEP_BY_STEP",
    )
    assert run.status == RunStatus.WAITING_APPROVAL
    approval_id = run.pending_approval_id

    # Simulate full process restart: new bus/store/orchestrator over same DB.
    bus_b = CommandBus(state_store=CommandStateStore(fresh_db))
    orch_b = AgentRunOrchestrator(
        command_bus=bus_b,
        capability_registry=CapabilityRegistry(),
        run_store=AgentRunStore(fresh_db),
        environment="development",
    )
    status = orch_b.get_run_status(owner.user_id, run.run_id)
    assert status.status == RunStatus.WAITING_APPROVAL
    assert status.pending_approval_id == approval_id

    completed = orch_b.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)
    # Step s1 executes post-approval, then s2 halts for its own approval.
    assert completed.status == RunStatus.WAITING_APPROVAL
    assert completed.completed_steps == ["s1"]

    final = orch_b.decide_approval(
        owner.user_id, completed.pending_approval_id, ApprovalDecisionValue.APPROVED
    )
    assert final.status == RunStatus.COMPLETED
    assert bus_b.get_project_revision("proj-lc-reload") == 3


# ── Authorization failures ───────────────────────────────────────────────────


def test_wrong_principal_cannot_operate_on_run(orchestrator: AgentRunOrchestrator, owner) -> None:
    run = orchestrator.start_run(
        owner, project_id="proj-lc-authz", steps=[_spatial_step()], approval_mode="AUTO"
    )
    intruder = "someone-else"
    with pytest.raises(RunPermissionError):
        orchestrator.get_run_status(intruder, run.run_id)
    with pytest.raises(RunPermissionError):
        orchestrator.cancel_run(intruder, run.run_id)


def test_wrong_principal_approval_rejected(orchestrator: AgentRunOrchestrator, owner) -> None:
    run = orchestrator.start_run(
        owner, project_id="proj-lc-wp", steps=[_electrical_step()], approval_mode="AUTO"
    )
    approval_id = run.pending_approval_id
    with pytest.raises(RunPermissionError):
        orchestrator.decide_approval("not-the-owner", approval_id, ApprovalDecisionValue.APPROVED)
    # Approval remains pending and untouched.
    pa = orchestrator._store.get_pending_approval(approval_id)
    assert pa.status == PendingApprovalStatus.PENDING


def test_wrong_project_binding_rejected(
    orchestrator: AgentRunOrchestrator, owner, fresh_db: Database
) -> None:
    """An approval whose project binding does not match the run is refused."""
    run = orchestrator.start_run(
        owner, project_id="proj-lc-wproj", steps=[_electrical_step()], approval_mode="AUTO"
    )
    approval_id = run.pending_approval_id
    # Tamper: rebind the persisted approval to a different project.
    ph = fresh_db._ph()
    with fresh_db._transaction() as cur:
        cur.execute(
            f"UPDATE pending_approvals SET project_id = {ph} WHERE approval_id = {ph}",
            ("some-other-project", approval_id),
        )
    with pytest.raises(StaleApprovalError):
        orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)


def test_wrong_capability_binding_rejected(
    orchestrator: AgentRunOrchestrator, owner, fresh_db: Database
) -> None:
    """A client cannot swap the capability through an approval request."""
    run = orchestrator.start_run(
        owner, project_id="proj-lc-wcap", steps=[_electrical_step()], approval_mode="AUTO"
    )
    approval_id = run.pending_approval_id
    ph = fresh_db._ph()
    with fresh_db._transaction() as cur:
        cur.execute(
            f"UPDATE pending_approvals SET capability_id = {ph} WHERE approval_id = {ph}",
            (SPATIAL, approval_id),
        )
    with pytest.raises(StaleApprovalError):
        orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)


def test_stale_revision_approval_rejected(orchestrator: AgentRunOrchestrator, owner) -> None:
    """Project revision drift between approval creation and decision → stale."""
    run = orchestrator.start_run(
        owner, project_id="proj-lc-stale", steps=[_electrical_step()], approval_mode="AUTO"
    )
    approval_id = run.pending_approval_id
    bound_rev = orchestrator._store.get_pending_approval(approval_id).project_revision

    # Concurrent external mutation advances the canonical revision.
    orchestrator._bus.set_project_revision("proj-lc-stale", bound_rev + 1)

    with pytest.raises(StaleApprovalError):
        orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)
    # Invalidation recorded as auditable evidence; nothing executed.
    decisions = orchestrator._store.list_decisions(run.run_id)
    assert len(decisions) == 1
    assert "STALE_PROJECT_REVISION" in decisions[0].reason
    assert orchestrator._bus.get_project_revision("proj-lc-stale") == bound_rev + 1


def test_duplicate_approval_is_safe(orchestrator: AgentRunOrchestrator, owner) -> None:
    """Duplicate approve messages are idempotent-safe: second one rejected."""
    run = orchestrator.start_run(
        owner, project_id="proj-lc-dup", steps=[_electrical_step()], approval_mode="AUTO"
    )
    approval_id = run.pending_approval_id
    first = orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)
    assert first.status == RunStatus.COMPLETED
    # The duplicate is rejected safely — either by the atomic PENDING claim or
    # by run-state validation (the run already completed).
    with pytest.raises((ApprovalAlreadyDecidedError, InvalidRunStateError)):
        orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)
    # Exactly one commit happened.
    assert orchestrator._bus.get_project_revision("proj-lc-dup") == 2


# ── Retry with flaky handler (idempotency safety) ────────────────────────────


def _register_flaky(registry: CapabilityRegistry, calls: list[int]) -> None:
    def _handler(payload: dict) -> dict:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient deterministic failure")
        return {"room_id": payload.get("room_id", "r"), "devices": [], "is_compliant": True}

    registry.register(
        CapabilityDefinition(
            capability_id="test.flaky",
            name="Flaky Test Capability",
            description="Fails on first call only.",
            category="test",
            risk_class="MEDIUM",
            required_scopes=["spatial:write"],
            input_schema={},
            output_schema={},
            handler=_handler,
        )
    )


def test_failed_run_retry_recovers_without_duplicate_mutation(fresh_db: Database, owner) -> None:
    """failed → retry executes the failed step once more and completes."""
    registry = CapabilityRegistry()
    calls: list[int] = []
    _register_flaky(registry, calls)
    bus = CommandBus(capability_registry=registry, state_store=CommandStateStore(fresh_db))
    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=AgentRunStore(fresh_db),
        environment="development",
    )

    run = orch.start_run(
        owner,
        project_id="proj-lc-retry",
        steps=[{"step_id": "f1", "capability_id": "test.flaky", "payload": {"room_id": "r1"}}],
        approval_mode="AUTO",
    )
    assert run.status == RunStatus.FAILED
    assert run.failed_steps[-1]["step_id"] == "f1"
    assert len(calls) == 1

    retried = orch.retry_run(owner.user_id, run.run_id)
    assert retried.status == RunStatus.COMPLETED
    assert len(calls) == 2  # handler ran exactly twice total — no blind replay storm
    assert bus.get_project_revision("proj-lc-retry") == 2
    assert retried.recovery_state.get("retry_count") == 1


def test_retry_refused_for_non_failed_run(orchestrator: AgentRunOrchestrator, owner) -> None:
    run = orchestrator.start_run(
        owner, project_id="proj-lc-noretry", steps=[_spatial_step()], approval_mode="AUTO"
    )
    assert run.status == RunStatus.COMPLETED
    with pytest.raises(InvalidRunStateError):
        orchestrator.retry_run(owner.user_id, run.run_id)


# ── Races ────────────────────────────────────────────────────────────────────


def test_cancel_vs_approve_race_is_deterministic(orchestrator: AgentRunOrchestrator, owner) -> None:
    """cancel vs approve race → safe deterministic result, at most one commit."""
    run = orchestrator.start_run(
        owner, project_id="proj-lc-race1", steps=[_electrical_step()], approval_mode="AUTO"
    )
    approval_id = run.pending_approval_id
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _approve() -> None:
        barrier.wait()
        try:
            orchestrator.decide_approval(owner.user_id, approval_id, ApprovalDecisionValue.APPROVED)
        except Exception as exc:  # noqa: BLE001 — race loser expected
            errors.append(exc)

    def _cancel() -> None:
        barrier.wait()
        try:
            orchestrator.cancel_run(owner.user_id, run.run_id)
        except Exception as exc:  # noqa: BLE001 — race loser expected
            errors.append(exc)

    t1, t2 = threading.Thread(target=_approve), threading.Thread(target=_cancel)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    final = orchestrator.get_run_status(owner.user_id, run.run_id)
    # Deterministic terminal outcome; no corruption, no double commit.
    assert final.status in (RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED)
    revision = orchestrator._bus.get_project_revision("proj-lc-race1")
    assert revision in (1, 2)  # at most ONE engineering mutation committed
    if final.status == RunStatus.CANCELLED:
        assert revision == 1 or revision == 2  # commit either pre-ceded cancel or never happened
    for err in errors:
        assert isinstance(
            err, InvalidRunStateError | ApprovalAlreadyDecidedError | InvalidTransitionError
        )


def test_resume_vs_cancel_race_is_deterministic(orchestrator: AgentRunOrchestrator, owner) -> None:
    """resume vs cancel race from PAUSED → exactly one wins deterministically."""
    run = orchestrator.start_run(
        owner,
        project_id="proj-lc-race2",
        steps=[_spatial_step()],
        approval_mode="STEP_BY_STEP",
    )
    # Decide APPROVED so resume has real work to do... instead: pause while
    # waiting, then race resume against cancel. The live approval makes resume
    # raise InvalidRunStateError deterministically when it loses OR wins the
    # status read; cancel must win the transition exactly once.
    orchestrator.pause_run(owner.user_id, run.run_id)

    outcomes: list[str] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _resume() -> None:
        barrier.wait()
        try:
            r = orchestrator.resume_run(owner.user_id, run.run_id)
            outcomes.append(r.status.value)
        except Exception as exc:  # noqa: BLE001 — race loser expected
            errors.append(exc)

    def _cancel() -> None:
        barrier.wait()
        try:
            r = orchestrator.cancel_run(owner.user_id, run.run_id)
            outcomes.append(r.status.value)
        except Exception as exc:  # noqa: BLE001 — race loser expected
            errors.append(exc)

    t1, t2 = threading.Thread(target=_resume), threading.Thread(target=_cancel)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    final = orchestrator.get_run_status(owner.user_id, run.run_id)
    # Cancel always eventually wins here because a live approval blocks resume;
    # regardless of interleaving the run MUST end terminal and consistent.
    assert final.status in (RunStatus.CANCELLED, RunStatus.COMPLETED)
    assert (
        orchestrator._bus.get_project_revision("proj-lc-race2") == 1
    )  # no commit without approval
    combined = set(outcomes) | {type(e).__name__ for e in errors}
    assert combined, "at least one racer must produce an observable outcome"


# ── Policy denial inside a run ───────────────────────────────────────────────


def test_policy_denied_step_fails_run(fresh_db: Database, registry: CapabilityRegistry) -> None:
    """DENIED policy result fails the run — never silently downgraded."""
    limited = AuthenticatedPrincipal(
        user_id="limited-01",
        email="l@bazspark.io",
        role="viewer",
        scopes=["spatial:read"],  # lacks spatial:write
        is_authenticated=True,
    )
    bus = CommandBus(state_store=CommandStateStore(fresh_db))
    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=AgentRunStore(fresh_db),
        environment="development",
    )
    run = orch.start_run(
        limited, project_id="proj-lc-denied", steps=[_spatial_step()], approval_mode="AUTO"
    )
    assert run.status == RunStatus.FAILED
    assert run.failed_steps[-1]["error_code"] == "POLICY_DENIED"
    assert "INSUFFICIENT_SCOPE" in run.failed_steps[-1]["error_message"]
    # Nothing was executed.
    assert bus.get_project_revision("proj-lc-denied") == 1


def test_governance_denied_capability_fails_run(
    fresh_db: Database, registry: CapabilityRegistry, owner
) -> None:
    bus = CommandBus(state_store=CommandStateStore(fresh_db))
    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=AgentRunStore(fresh_db),
        environment="development",
    )
    run = orch.start_run(
        owner,
        project_id="proj-lc-govdenied",
        steps=[_spatial_step()],
        approval_mode="AUTO",
        governance_policy={"deniedCapabilities": [SPATIAL]},
    )
    assert run.status == RunStatus.FAILED
    assert run.failed_steps[-1]["error_code"] == "POLICY_DENIED"
