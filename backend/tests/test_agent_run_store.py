"""backend/tests/test_agent_run_store.py — Phase 1 AgentRunStore persistence tests.

Covers: create/read/update, invalid transition rejection, concurrent update
protection (CAS), persistence across store recreation, pending approval
persistence, approval decision persistence/immutability, and audit reference
persistence.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.core.agent_run_store import (
    VALID_TRANSITIONS,
    AgentRunStore,
    ApprovalAlreadyDecidedError,
    ApprovalDecisionValue,
    ApprovalMode,
    InvalidTransitionError,
    PendingApprovalNotFoundError,
    PendingApprovalStatus,
    RunConcurrencyConflictError,
    RunNotFoundError,
    RunStatus,
    validate_transition,
)
from backend.database import Database


@pytest.fixture
def fresh_db(tmp_path: Path) -> Database:
    return Database(db_path=str(tmp_path / "agent_run_store_test.db"))


@pytest.fixture
def store(fresh_db: Database) -> AgentRunStore:
    return AgentRunStore(fresh_db)


def _make_run(store: AgentRunStore, **overrides):
    kwargs: dict = {
        "user_id": "engineer-01",
        "project_id": "proj-store-1",
        "approval_mode": ApprovalMode.AUTO,
        "plan": {"goal": "test"},
        "steps": [{"step_id": "s1", "capability_id": "spatial.place_devices", "payload": {}}],
    }
    kwargs.update(overrides)
    return store.create_run(**kwargs)


# ── Create / Read ────────────────────────────────────────────────────────────


def test_create_and_read_run(store: AgentRunStore) -> None:
    run = _make_run(store)
    assert run.run_id.startswith("run-")
    assert run.status == RunStatus.PLANNING
    assert run.user_id == "engineer-01"
    assert run.project_id == "proj-store-1"
    assert run.approval_mode == ApprovalMode.AUTO
    assert run.steps[0]["step_id"] == "s1"
    assert run.version == 1

    loaded = store.get_run(run.run_id)
    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.status == RunStatus.PLANNING


def test_get_missing_run_returns_none(store: AgentRunStore) -> None:
    assert store.get_run("run-does-not-exist") is None
    with pytest.raises(RunNotFoundError):
        store.require_run("run-does-not-exist")


def test_list_runs_filters(store: AgentRunStore) -> None:
    r1 = _make_run(store, project_id="proj-a")
    _make_run(store, project_id="proj-b", user_id="other-user")
    runs = store.list_runs(project_id="proj-a")
    assert [r.run_id for r in runs] == [r1.run_id]
    runs = store.list_runs(user_id="other-user")
    assert len(runs) == 1


# ── State transitions ────────────────────────────────────────────────────────


def test_valid_transition_updates_state(store: AgentRunStore) -> None:
    run = _make_run(store)
    run = store.transition_run(run.run_id, RunStatus.READY)
    assert run.status == RunStatus.READY
    assert run.version == 2

    run = store.transition_run(run.run_id, RunStatus.RUNNING)
    assert run.status == RunStatus.RUNNING
    assert run.version == 3


def test_invalid_transition_rejected(store: AgentRunStore) -> None:
    run = _make_run(store)
    with pytest.raises(InvalidTransitionError):
        store.transition_run(run.run_id, RunStatus.COMPLETED)
    # State must be unchanged after rejection.
    assert store.get_run(run.run_id).status == RunStatus.PLANNING


def test_terminal_states_are_frozen(store: AgentRunStore) -> None:
    run = _make_run(store)
    store.transition_run(run.run_id, RunStatus.CANCELLED)
    for target in RunStatus:
        if target == RunStatus.CANCELLED:
            continue
        with pytest.raises(InvalidTransitionError):
            store.transition_run(run.run_id, target)


def test_transition_table_matches_spec() -> None:
    """The transition table must exactly implement the Phase 1 state model."""
    expected = {
        RunStatus.PLANNING: {RunStatus.READY, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.READY: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
        RunStatus.RUNNING: {
            RunStatus.WAITING_APPROVAL,
            RunStatus.PAUSED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.COMPLETED,
        },
        RunStatus.WAITING_APPROVAL: {
            RunStatus.RUNNING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.PAUSED,
        },
        RunStatus.PAUSED: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
        RunStatus.FAILED: {RunStatus.RUNNING, RunStatus.CANCELLED},
        RunStatus.CANCELLED: set(),
        RunStatus.COMPLETED: set(),
    }
    for status, targets in expected.items():
        assert set(VALID_TRANSITIONS[status]) == targets
    # validate_transition helper agrees
    validate_transition(RunStatus.RUNNING, RunStatus.PAUSED)
    with pytest.raises(InvalidTransitionError):
        validate_transition(RunStatus.COMPLETED, RunStatus.RUNNING)


# ── Concurrency protection (CAS) ─────────────────────────────────────────────


def test_stale_version_update_rejected(store: AgentRunStore) -> None:
    run = _make_run(store)
    stale_version = run.version  # 1
    store.transition_run(run.run_id, RunStatus.READY)  # version → 2
    with pytest.raises(RunConcurrencyConflictError):
        store.transition_run(
            run.run_id, RunStatus.RUNNING, expected_version=stale_version
        )


def test_concurrent_transitions_exactly_one_wins(store: AgentRunStore) -> None:
    """Two threads racing the same CAS transition: exactly one succeeds."""
    run = _make_run(store)
    version = run.version
    results: list[str] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _worker() -> None:
        barrier.wait()
        try:
            store.transition_run(
                run.run_id, RunStatus.READY, expected_version=version
            )
            results.append("won")
        except Exception as exc:  # noqa: BLE001 — race loser is expected here
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 1
    assert len(errors) == 1
    # The loser is rejected deterministically — either by the CAS version
    # guard or by transition validation against the freshly-read state
    # (e.g. READY -> READY after the winner already transitioned).
    assert isinstance(errors[0], RunConcurrencyConflictError | InvalidTransitionError)
    final = store.get_run(run.run_id)
    assert final.status == RunStatus.READY
    assert final.version == version + 1


# ── Persistence across store recreation ──────────────────────────────────────


def test_persisted_state_survives_store_recreation(fresh_db: Database) -> None:
    store_a = AgentRunStore(fresh_db)
    run = _make_run(store_a)
    store_a.transition_run(run.run_id, RunStatus.READY)
    store_a.transition_run(run.run_id, RunStatus.RUNNING)
    store_a.update_progress(
        run.run_id, expected_version=3, completed_steps=["s1"], current_step=None
    )

    # Simulate process restart: brand-new store instance over the same DB.
    store_b = AgentRunStore(fresh_db)
    reloaded = store_b.get_run(run.run_id)
    assert reloaded is not None
    assert reloaded.status == RunStatus.RUNNING
    assert reloaded.completed_steps == ["s1"]
    assert reloaded.plan.get("goal") == "test"


# ── Pending approvals ────────────────────────────────────────────────────────


def test_pending_approval_persisted(store: AgentRunStore) -> None:
    run = _make_run(store)
    pa = store.create_pending_approval(
        run_id=run.run_id,
        step_id="s1",
        project_id=run.project_id,
        project_revision=7,
        capability_id="electrical.calculate_voltage_drop",
        principal_id=run.user_id,
        approval_mode=ApprovalMode.AUTO,
        policy_result="REQUIRES_APPROVAL",
        plan_hash="planhash",
        step_payload_hash="payloadhash",
    )
    loaded = store.get_pending_approval(pa.approval_id)
    assert loaded is not None
    assert loaded.status == PendingApprovalStatus.PENDING
    assert loaded.project_revision == 7
    assert loaded.step_payload_hash == "payloadhash"

    by_step = store.get_pending_approval_for_step(run.run_id, "s1")
    assert by_step is not None
    assert by_step.approval_id == pa.approval_id


def test_decide_approval_persists_immutable_decision(store: AgentRunStore) -> None:
    run = _make_run(store)
    pa = store.create_pending_approval(
        run_id=run.run_id,
        step_id="s1",
        project_id=run.project_id,
        project_revision=1,
        capability_id="electrical.calculate_voltage_drop",
        principal_id=run.user_id,
        approval_mode=ApprovalMode.AUTO,
        policy_result="REQUIRES_APPROVAL",
    )
    decided, decision = store.decide_pending_approval(
        pa.approval_id,
        decision=ApprovalDecisionValue.APPROVED,
        principal_id=run.user_id,
        reason="ok",
    )
    assert decided.status == PendingApprovalStatus.APPROVED
    assert decided.decided_at is not None
    assert decision.decision == ApprovalDecisionValue.APPROVED
    assert decision.project_revision == 1

    decisions = store.list_decisions(run.run_id)
    assert len(decisions) == 1
    assert decisions[0].decision_id == decision.decision_id

    # Duplicate decision on the same approval is rejected atomically.
    with pytest.raises(ApprovalAlreadyDecidedError):
        store.decide_pending_approval(
            pa.approval_id,
            decision=ApprovalDecisionValue.REJECTED,
            principal_id=run.user_id,
        )
    # The historical record was NOT mutated.
    decisions = store.list_decisions(run.run_id)
    assert len(decisions) == 1
    assert decisions[0].decision == ApprovalDecisionValue.APPROVED


def test_cancel_pending_approvals(store: AgentRunStore) -> None:
    run = _make_run(store)
    pa = store.create_pending_approval(
        run_id=run.run_id,
        step_id="s1",
        project_id=run.project_id,
        project_revision=1,
        capability_id="electrical.calculate_voltage_drop",
        principal_id=run.user_id,
        approval_mode=ApprovalMode.AUTO,
        policy_result="REQUIRES_APPROVAL",
    )
    cancelled = store.cancel_pending_approvals(run.run_id)
    assert cancelled == 1
    assert store.get_pending_approval(pa.approval_id).status == PendingApprovalStatus.CANCELLED
    with pytest.raises(ApprovalAlreadyDecidedError):
        store.decide_pending_approval(
            pa.approval_id,
            decision=ApprovalDecisionValue.APPROVED,
            principal_id=run.user_id,
        )


def test_missing_pending_approval_raises(store: AgentRunStore) -> None:
    with pytest.raises(PendingApprovalNotFoundError):
        store.require_pending_approval("appr-missing")


# ── Audit reference ──────────────────────────────────────────────────────────


def test_audit_reference_persisted(store: AgentRunStore) -> None:
    run = _make_run(store)
    updated = store.set_audit_reference(run.run_id, "abc123audit")
    assert updated.audit_reference == "abc123audit"
    reloaded = store.get_run(run.run_id)
    assert reloaded.audit_reference == "abc123audit"
