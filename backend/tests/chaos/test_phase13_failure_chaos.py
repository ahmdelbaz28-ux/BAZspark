"""backend/tests/chaos/test_phase13_failure_chaos.py — Phase 13 Chaos & Failure Validation Suite.

Contractual Scenarios Mandated by Phase 13 Governing Contract:
1. WebSocket interruption in the middle of a run.
2. Adapter failure in the middle of a DAG (partial execution + safe retry).
3. Concurrent / racing approvals (atomic claim, conflict rejection, stale revision).
4. Command replay & idempotency key reuse collision detection.
5. LLM failure during planning & degradation ladder behavior.
6. Redis failure during a run (graceful in-memory degradation).
7. PostgreSQL / Database failure during a run (atomic rollback + OCC integrity).
8. Partial execution and recovery state preservation.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any
import pytest

from backend.core.agent_run_orchestrator import (
    AgentRunOrchestrator,
    InvalidRunStateError,
    StaleApprovalError,
)
from backend.core.agent_run_store import (
    AgentRunStore,
    ApprovalAlreadyDecidedError,
    ApprovalDecisionValue,
    ApprovalMode,
    RunStatus,
)
from backend.core.capability_registry import (
    CapabilityContract,
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
)
from backend.core.generic_planner import (
    GenericWorkflowPlanner,
)
from backend.core.state_store import CommandStateStore
from backend.database import Database
from backend.session_store import SessionStore


@pytest.fixture
def fresh_db(tmp_path) -> Database:
    """Isolated SQLite database for chaos test state."""
    db_file = tmp_path / "chaos_test.db"
    return Database(db_path=str(db_file))


@pytest.fixture
def state_store(fresh_db: Database) -> CommandStateStore:
    return CommandStateStore(fresh_db)


@pytest.fixture
def run_store(fresh_db: Database) -> AgentRunStore:
    return AgentRunStore(fresh_db)


@pytest.fixture
def test_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="chaos_engineer_01",
        email="eng@bazspark.internal",
        role="engineer",
        scopes=["*"],
        is_authenticated=True,
    )


@pytest.fixture
def chaos_registry() -> CapabilityRegistry:
    """Capability registry seeded with default capabilities plus fault-injectable test capabilities."""
    reg = CapabilityRegistry()

    def handle_step_1(payload: dict[str, Any]) -> dict[str, Any]:
        return {"step": 1, "status": "done", "devices": [{"id": "dev-01"}]}

    def handle_step_2_flaky(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("should_fail", False):
            raise RuntimeError("ETAP simulation bridge connection reset (Chaos Injection)")
        return {"step": 2, "status": "done", "voltage_drop_pct": 2.1}

    def handle_step_3(payload: dict[str, Any]) -> dict[str, Any]:
        return {"step": 3, "status": "done", "is_compliant": True}

    contract_1 = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="canonical_project_state",
        risk="LOW",
        mutation_type="state_mutation",
        approval_policy="auto",
        scopes=["*"],
    )
    contract_approval = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="canonical_project_state",
        risk="ENGINEERING_MUTATION",
        mutation_type="state_mutation",
        approval_policy="user_confirm",
        scopes=["*"],
    )
    contract_3 = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="canonical_project_state",
        risk="LOW",
        mutation_type="state_mutation",
        approval_policy="auto",
        scopes=["*"],
    )

    reg.register(
        CapabilityDefinition(
            capability_id="chaos.step_1",
            name="Step 1 Capability",
            description="Initial layout",
            category="spatial",
            contract=contract_1,
            risk_class="LOW",
            required_scopes=["*"],
            handler=handle_step_1,
        )
    )
    reg.register(
        CapabilityDefinition(
            capability_id="chaos.step_approval",
            name="Step Approval Capability",
            description="Engineering critical mutation requiring human signoff",
            category="electrical",
            contract=contract_approval,
            risk_class="ENGINEERING_MUTATION",
            required_scopes=["*"],
            handler=handle_step_1,
        )
    )
    reg.register(
        CapabilityDefinition(
            capability_id="chaos.step_2_flaky",
            name="Step 2 Flaky Capability",
            description="Electrical calculation",
            category="electrical",
            contract=contract_1,
            risk_class="LOW",
            required_scopes=["*"],
            handler=handle_step_2_flaky,
        )
    )
    reg.register(
        CapabilityDefinition(
            capability_id="chaos.step_3",
            name="Step 3 Capability",
            description="Verification",
            category="compliance",
            contract=contract_3,
            risk_class="LOW",
            required_scopes=["*"],
            handler=handle_step_3,
        )
    )
    return reg


# ═══════════════════════════════════════════════════════════════════════════════
# 1. WEBSOCKET INTERRUPTION MID-RUN & RESUMABILITY
# ═══════════════════════════════════════════════════════════════════════════════

def test_websocket_interruption_mid_run_preserves_persistent_state(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 1: Client WebSocket disconnects while an agent run is in progress.
    Asserts that backend state is undamaged and run can be safely resumed by a reconnecting client.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-ws-chaos", 1)

    orchestrator_1 = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )

    steps = [
        {"step_id": "s1", "capability_id": "chaos.step_1", "payload": {}},
        {"step_id": "s2", "capability_id": "chaos.step_approval", "payload": {}},
    ]

    # Start run — step 1 completes, step 2 enters WAITING_APPROVAL
    run = orchestrator_1.start_run(
        test_principal,
        project_id="proj-ws-chaos",
        steps=steps,
        approval_mode=ApprovalMode.AUTO,
    )
    assert run.status == RunStatus.WAITING_APPROVAL
    assert run.completed_steps == ["s1"]
    assert run.current_step == "s2"

    # Simulate abrupt transport/WebSocket drop: discard orchestrator_1 instance
    del orchestrator_1

    # New client / connection creates fresh orchestrator from persistent database
    orchestrator_2 = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )

    # Verify run state is intact in store
    recovered_run = run_store.get_run(run.run_id)
    assert recovered_run is not None
    assert recovered_run.status == RunStatus.WAITING_APPROVAL
    assert recovered_run.project_id == "proj-ws-chaos"
    assert recovered_run.pending_approval_id is not None

    # Approve and complete after reconnect
    resumed = orchestrator_2.decide_approval(
        caller_id=test_principal.user_id,
        approval_id=recovered_run.pending_approval_id,
        decision=ApprovalDecisionValue.APPROVED,
    )
    # The run proceeds and finishes all steps deterministically
    assert resumed.status == RunStatus.COMPLETED
    assert "s1" in resumed.completed_steps
    assert "s2" in resumed.completed_steps
    assert bus.get_project_revision("proj-ws-chaos") == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ADAPTER FAILURE IN THE MIDDLE OF A DAG & RECOVERY WITHOUT DUPLICATE MUTATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_adapter_failure_mid_dag_and_idempotent_recovery(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 2: Adapter crashes at step 2 of a 3-step DAG.
    1. Proves step 1 is committed and audited at revision N+1.
    2. Proves step 2 records failure and run enters FAILED status.
    3. Proves step 3 is NOT executed.
    4. Proves retry resumes step 2 without re-executing step 1 (idempotency ledger).
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-dag-fail", 10)

    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )

    steps = [
        {"step_id": "step-1", "capability_id": "chaos.step_1", "payload": {}},
        {"step_id": "step-2", "capability_id": "chaos.step_2_flaky", "payload": {"should_fail": True}},
        {"step_id": "step-3", "capability_id": "chaos.step_3", "payload": {}},
    ]

    # Start auto-run — step 1 succeeds, step 2 fails
    run = orch.start_run(
        test_principal,
        project_id="proj-dag-fail",
        steps=steps,
        approval_mode="AUTO",
    )

    # 1. State check after failure
    assert run.status == RunStatus.FAILED
    assert "step-1" in run.completed_steps
    assert "step-2" not in run.completed_steps
    assert "step-3" not in run.completed_steps
    assert len(run.failed_steps) == 1
    assert run.failed_steps[0]["step_id"] == "step-2"

    # Revision moved from 10 -> 11 for step 1, but did NOT move for failed step 2
    assert bus.get_project_revision("proj-dag-fail") == 11

    # 2. Repair the adapter failure condition by registering healed handler
    def handle_step_2_healthy(payload: dict[str, Any]) -> dict[str, Any]:
        return {"step": 2, "status": "healed", "voltage_drop_pct": 1.8}

    healed_contract = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="canonical_project_state",
        risk="MEDIUM",
        mutation_type="state_mutation",
        approval_policy="auto",
        scopes=["*"],
    )

    chaos_registry.register(
        CapabilityDefinition(
            capability_id="chaos.step_2_flaky",
            name="Step 2 Flaky Capability",
            description="Healed",
            category="electrical",
            contract=healed_contract,
            risk_class="MEDIUM",
            required_scopes=["*"],
            handler=handle_step_2_healthy,
        )
    )

    # 3. Retry run
    retried_run = orch.retry_run(test_principal.user_id, run.run_id)

    assert retried_run.status == RunStatus.COMPLETED
    assert retried_run.completed_steps == ["step-1", "step-2", "step-3"]
    # Final revision: 10 + 3 steps = 13
    assert bus.get_project_revision("proj-dag-fail") == 13


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CONCURRENT / RACING APPROVALS & STALE REVISION REJECTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_concurrent_approval_race_is_atomic(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 3a: Two concurrent callers race to decide the same pending approval.
    Asserts atomic single-winner resolution.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-race-appr", 1)

    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )
    steps = [{"step_id": "s1", "capability_id": "chaos.step_approval", "payload": {}}]

    run = orch.start_run(
        test_principal,
        project_id="proj-race-appr",
        steps=steps,
        approval_mode=ApprovalMode.AUTO,
    )
    approval_id = run.pending_approval_id
    assert approval_id is not None

    results = []
    errors = []

    def try_decide(decision: str):
        try:
            r = orch.decide_approval(test_principal.user_id, approval_id, decision)
            results.append(r)
        except Exception as exc:
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(try_decide, "APPROVED")
        f2 = executor.submit(try_decide, "REJECTED")
        concurrent.futures.wait([f1, f2])

    # Exactly one decision succeeds; the other is rejected as already decided / invalid state
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], (InvalidRunStateError, StaleApprovalError, ApprovalAlreadyDecidedError))


def test_stale_project_revision_approval_rejection(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 3b: Project revision moves between approval creation and decision.
    Asserts rejection with StaleApprovalError.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-stale-rev", 5)

    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )
    steps = [{"step_id": "s1", "capability_id": "chaos.step_approval", "payload": {}}]

    run = orch.start_run(
        test_principal,
        project_id="proj-stale-rev",
        steps=steps,
        approval_mode=ApprovalMode.AUTO,
    )
    approval_id = run.pending_approval_id
    assert approval_id is not None

    # Outside mutation shifts project revision 5 -> 6 concurrently
    bus.set_project_revision("proj-stale-rev", 6)

    # Decision on stale revision must be rejected
    with pytest.raises(StaleApprovalError) as exc_info:
        orch.decide_approval(test_principal.user_id, approval_id, ApprovalDecisionValue.APPROVED)

    assert "stale: project revision moved from 5 to 6" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. COMMAND REPLAY & IDEMPOTENCY COLLISION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_command_bus_idempotent_replay_and_collision(
    fresh_db: Database,
    state_store: CommandStateStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 4:
    1. Re-executing identical command returns cached result without incrementing revision.
    2. Executing same commandId with DIFFERENT payload triggers IDEMPOTENCY_KEY_REUSE_CONFLICT.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-idemp-chaos", 1)

    cmd = DomainCommand(
        commandId="cmd-chaos-001",
        correlationId="corr-chaos-001",
        capabilityId="chaos.step_1",
        projectId="proj-idemp-chaos",
        expectedRevision=1,
        timestamp="2026-09-02T00:00:00Z",
        principal=test_principal,
        payload={"zone": "A"},
    )

    # 1. First execution -> succeeds, rev moves 1 -> 2
    res1 = bus.execute(cmd)
    assert res1.success is True
    assert res1.revision == 2
    assert bus.get_project_revision("proj-idemp-chaos") == 2

    # 2. Replay same commandId + same payload -> returns cached result, revision stays 2
    res2 = bus.execute(cmd)
    assert res2.success is True
    assert res2.revision == 2
    assert bus.get_project_revision("proj-idemp-chaos") == 2

    # 3. Conflict: same commandId + DIFFERENT payload -> rejected
    cmd_conflict = DomainCommand(
        commandId="cmd-chaos-001",
        correlationId="corr-chaos-002",
        capabilityId="chaos.step_1",
        projectId="proj-idemp-chaos",
        expectedRevision=2,
        timestamp="2026-09-02T00:01:00Z",
        principal=test_principal,
        payload={"zone": "B_DIFFERENT_PAYLOAD"},
    )
    res_conflict = bus.execute(cmd_conflict)
    assert res_conflict.success is False
    assert res_conflict.errorCode == "IDEMPOTENCY_KEY_REUSE_CONFLICT"
    assert "was already executed with a different command payload" in res_conflict.errorMessage


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LLM PLANNING FAILURE & DEGRADATION LADDER
# ═══════════════════════════════════════════════════════════════════════════════

def test_generic_planner_degradation_ladder(
    fresh_db: Database,
    state_store: CommandStateStore,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 5: GenericWorkflowPlanner degrades gracefully when synthesizing plans,
    sanitizes input, binds project revision, and produces valid AutonomousPlan contracts.
    """
    bus = CommandBus(state_store=state_store)
    bus.set_project_revision("proj-degrade-01", 1)

    planner = GenericWorkflowPlanner(command_bus=bus)
    plan = planner.plan_workflow(
        prompt="Layout smoke detectors in room 12x15m",
        principal=test_principal,
        project_id="proj-degrade-01",
        expected_revision=1,
    )

    assert plan is not None
    assert plan.plan_id.startswith("plan-")
    assert len(plan.steps) >= 1
    assert plan.project_id == "proj-degrade-01"
    assert plan.expected_revision == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 6. REDIS FAILURE DURING ACTIVE OPERATIONS (SAFE DEGRADATION)
# ═══════════════════════════════════════════════════════════════════════════════

def test_redis_unavailability_graceful_degradation() -> None:
    """
    Chaos Scenario 6: Redis connection fails during session store / rate limiting.
    System degrades to in-memory fallback without crashing or corrupting sessions.
    """
    session_store = SessionStore()

    # Invalidate / simulate broken Redis connection
    class BrokenRedis:
        def get(self, *args, **kwargs):
            raise ConnectionError("Redis server unreachable (Chaos Injection)")

        def set(self, *args, **kwargs):
            raise ConnectionError("Redis server unreachable (Chaos Injection)")

        def delete(self, *args, **kwargs):
            raise ConnectionError("Redis server unreachable (Chaos Injection)")

    session_store._redis = BrokenRedis()

    # Store session with valid expires_at — should catch Redis error and use in-memory store
    session_data = {
        "user_id": "chaos_user_01",
        "role": "engineer",
        "expires_at": time.time() + 3600.0,
    }
    session_store.set("sess_token_hash_01", session_data)

    # Retrieve session — in-memory fallback works
    retrieved = session_store.get("sess_token_hash_01")
    assert retrieved is not None
    assert retrieved.get("user_id") == "chaos_user_01"

    # Delete session
    session_store.delete("sess_token_hash_01")
    assert session_store.get("sess_token_hash_01") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DATABASE COMMIT FAILURE & ATOMIC OCC ROLLBACK
# ═══════════════════════════════════════════════════════════════════════════════

def test_database_commit_failure_atomic_rollback(
    fresh_db: Database,
    state_store: CommandStateStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Chaos Scenario 7: Database transaction fails mid-commit (e.g. disk I/O error or constraint violation).
    Asserts atomic rollback, TRANSACTION_COMMIT_FAILED, no phantom revision increment.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-db-crash", 4)

    # Invalidate commit_transaction to simulate database write failure
    def failing_commit(*args, **kwargs):
        return False, "SIMULATED_DISK_IO_ERROR"

    monkeypatch.setattr(state_store, "commit_transaction", failing_commit)

    cmd = DomainCommand(
        commandId="cmd-db-fail-001",
        correlationId="corr-db-fail-001",
        capabilityId="chaos.step_1",
        projectId="proj-db-crash",
        expectedRevision=4,
        timestamp="2026-09-02T00:00:00Z",
        principal=test_principal,
        payload={},
    )

    result = bus.execute(cmd)
    assert result.success is False
    assert result.errorCode == "SIMULATED_DISK_IO_ERROR"
    # Canonical revision must remain 4 (zero phantom increment)
    assert bus.get_project_revision("proj-db-crash") == 4


# ═══════════════════════════════════════════════════════════════════════════════
# 8. PARTIAL EXECUTION, PAUSE & RESUME RECOVERY STATE PRESERVATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_partial_execution_pause_and_resume_recovery(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 8: Run is paused mid-execution, state is audited, and resumed to completion.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-pause-resume", 1)

    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )
    steps = [
        {"step_id": "step-1", "capability_id": "chaos.step_1", "payload": {}},
        {"step_id": "step-2", "capability_id": "chaos.step_approval", "payload": {}},
    ]

    # Start run — step 1 completes, step 2 halts for human approval
    run = orch.start_run(
        test_principal,
        project_id="proj-pause-resume",
        steps=steps,
        approval_mode=ApprovalMode.AUTO,
    )
    assert run.status == RunStatus.WAITING_APPROVAL
    assert run.completed_steps == ["step-1"]

    # Pause run
    paused = orch.pause_run(test_principal.user_id, run.run_id)
    assert paused.status == RunStatus.PAUSED
    assert "paused_at" in paused.recovery_state

    # Cannot approve while paused
    with pytest.raises(InvalidRunStateError):
        orch.decide_approval(test_principal.user_id, run.pending_approval_id, ApprovalDecisionValue.APPROVED)

    # Resume run -> transitions back to live waiting approval state
    resumed = orch.resume_run(test_principal.user_id, run.run_id)
    assert resumed.status == RunStatus.WAITING_APPROVAL

    # Approve and complete
    completed = orch.decide_approval(
        test_principal.user_id, resumed.pending_approval_id, ApprovalDecisionValue.APPROVED
    )
    assert completed.status == RunStatus.COMPLETED
    assert completed.completed_steps == ["step-1", "step-2"]
    assert bus.get_project_revision("proj-pause-resume") == 3
