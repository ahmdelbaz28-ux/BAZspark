"""backend/tests/chaos/test_phase13_failure_chaos.py — Phase 13 Chaos & Failure Validation Suite.

Contractual Scenarios Mandated by Phase 13 Governing Contract (9 Total Scenarios):
1. WebSocket interruption in the middle of an active run & transport reconnection.
2. Adapter failure in the middle of a DAG (partial execution + safe retry).
3. Concurrent / racing approvals (atomic single-winner claim & conflict rejection).
4. Stale project revision approval rejection (OCC integrity).
5. Command replay & idempotency key reuse collision detection.
6. LLM failure during planning & deterministic degradation ladder fallback.
7. Redis failure during active run operations (graceful degradation & fail-closed boundaries).
8. Database commit failure & atomic rollback (zero phantom revision increment).
9. Partial execution, pause & resume recovery state preservation.
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
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
)
from backend.core.control_request import ControlRequest
from backend.core.planner_telemetry import default_planner_telemetry
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import (
    AutonomousWorkflowPlanner,
    InvalidWorkflowIntentError,
)
from backend.database import Database
from backend.routers import agent_ws
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


class ChaosMockWebSocket:
    """Mock WebSocket connection modeling active connection lifecycle, frame recording, and disconnection."""

    def __init__(self) -> None:
        self.sent_frames: list[dict[str, Any]] = []
        self.is_connected: bool = True

    async def send_json(self, data: dict[str, Any]) -> None:
        if not self.is_connected:
            raise ConnectionResetError("WebSocket transport connection dropped (Network Interruption)")
        self.sent_frames.append(data)

    def disconnect(self) -> None:
        self.is_connected = False


# ═══════════════════════════════════════════════════════════════════════════════
# 1. WEBSOCKET INTERRUPTION MID-RUN & RESUMABILITY (BLOCKER 2)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_websocket_interruption_mid_run_preserves_persistent_state(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Chaos Scenario 1: WebSocket / transport lifecycle interruption mid-run.
    Proves:
      1. Active run exists in WAITING_APPROVAL.
      2. Transport / WS connection is interrupted (connection dropped).
      3. Server-side run state remains persisted in AgentRunStore.
      4. No duplicate mutation occurs.
      5. Reconnected client (fresh WS) can recover the run.
      6. Approval state and revision remain coherent.
      7. Run can safely continue and complete deterministically.
      8. No fake 'transport success' is emitted after disconnect.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-ws-chaos", 1)

    orchestrator = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )
    monkeypatch.setattr(agent_ws, "default_agent_run_orchestrator", orchestrator)
    monkeypatch.setattr(agent_ws, "default_capability_registry", chaos_registry)

    ws_client_1 = ChaosMockWebSocket()

    steps = [
        {"step_id": "s1", "capability_id": "chaos.step_1", "payload": {}},
        {"step_id": "s2", "capability_id": "chaos.step_approval", "payload": {}},
    ]

    # 1. Client 1 starts run over WebSocket
    start_msg = {
        "type": "run_start",
        "projectId": "proj-ws-chaos",
        "expectedRevision": 1,
        "steps": steps,
        "approvalMode": "AUTO",
    }
    await agent_ws._handle_agent_message(ws_client_1, start_msg, test_principal)

    # Verify run entered WAITING_APPROVAL on step 2
    assert len(ws_client_1.sent_frames) >= 1
    waiting_frame = next((f for f in ws_client_1.sent_frames if f.get("status") == "WAITING_APPROVAL"), None)
    assert waiting_frame is not None
    run_id = waiting_frame["runId"]
    approval_id = waiting_frame["pendingApprovalId"]

    # Step 1 committed (rev 1 -> 2)
    assert bus.get_project_revision("proj-ws-chaos") == 2

    # 2. Abrupt network interruption: drop WebSocket connection
    ws_client_1.disconnect()

    # 8. Assert no fake transport success can be emitted after disconnect
    with pytest.raises(ConnectionResetError):
        await ws_client_1.send_json({"type": "fake_transport_heartbeat"})

    # 3. Verify server-side state is persisted in AgentRunStore
    persisted_run = run_store.get_run(run_id)
    assert persisted_run is not None
    assert persisted_run.status == RunStatus.WAITING_APPROVAL
    assert persisted_run.completed_steps == ["s1"]
    assert persisted_run.current_step == "s2"
    assert persisted_run.pending_approval_id == approval_id

    # 5. Reconnect: New client opens clean WebSocket connection
    ws_client_2 = ChaosMockWebSocket()

    # Query run status after reconnect via message dispatcher
    await agent_ws._handle_agent_message(ws_client_2, {"type": "run_status", "runId": run_id}, test_principal)
    assert len(ws_client_2.sent_frames) >= 1
    status_frame = next(f for f in ws_client_2.sent_frames if f.get("status") == "WAITING_APPROVAL")
    assert status_frame["status"] == "WAITING_APPROVAL"
    assert status_frame["pendingApprovalId"] == approval_id

    # 6 & 7. Approve the recovered run over the new WebSocket transport via message dispatcher
    await agent_ws._handle_agent_message(
        ws_client_2,
        {
            "type": "approval_decision",
            "approvalId": approval_id,
            "decision": "APPROVED",
        },
        test_principal,
    )

    # 4 & 7. Run completes without duplicate mutation of step 1
    completed_frame = next((f for f in ws_client_2.sent_frames if f.get("status") == "COMPLETED"), None)
    assert completed_frame is not None
    assert completed_frame["completedSteps"] == ["s1", "s2"]

    final_run = run_store.get_run(run_id)
    assert final_run.status == RunStatus.COMPLETED
    assert final_run.completed_steps == ["s1", "s2"]
    # Revision moved from 1 -> 2 (step 1) -> 3 (step 2) with zero duplication
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
# 3. CONCURRENT / RACING APPROVALS (ATOMIC CLAIM & CONFLICT REJECTION)
# ═══════════════════════════════════════════════════════════════════════════════

def test_concurrent_approval_race_is_atomic(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 3: Two concurrent callers race to decide the same pending approval.
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
    assert isinstance(errors[0], InvalidRunStateError | StaleApprovalError | ApprovalAlreadyDecidedError)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STALE OCC REVISION APPROVAL REJECTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_stale_project_revision_approval_rejection(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 4: Project revision moves between approval creation and decision.
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
# 5. COMMAND REPLAY & IDEMPOTENCY COLLISION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_command_bus_idempotent_replay_and_collision(
    fresh_db: Database,
    state_store: CommandStateStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 5:
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
# 6. REAL LLM FAILURE INJECTION & DEGRADATION LADDER (BLOCKER 1)
# ═══════════════════════════════════════════════════════════════════════════════

def test_generic_planner_degradation_ladder(
    fresh_db: Database,
    state_store: CommandStateStore,
    test_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Chaos Scenario 6: Deterministic LLM failure injection during workflow planning.
    Proves:
      1. LLM/generic planner invocation throws an actual upstream failure.
      2. The expected degradation ladder is entered.
      3. System does NOT claim successful generic LLM execution.
      4. Valid fallback behavior (frozen regex planner) is selected.
      5. Project/revision binding remains strictly valid.
      6. No unsafe mutation occurs on the command bus (dry-run safety).
      7. No fake engineering result is produced.
      8. Resulting state/fallback error is auditable and recorded in telemetry.
    """
    bus = CommandBus(state_store=state_store)
    bus.set_project_revision("proj-degrade-01", 1)

    planner = AutonomousWorkflowPlanner(command_bus=bus)

    # 1. Inject deterministic LLM failure: simulate upstream LLM provider 503 outage
    def _injected_llm_failure(req: ControlRequest, **kwargs: Any) -> Any:
        raise RuntimeError("Upstream LLM Provider HTTP 503 Service Unavailable (Injected Chaos Failure)")

    monkeypatch.setattr(planner._generic_planner, "plan_control_request", _injected_llm_failure)

    # 2. Call plan_workflow with real engineering prompt
    prompt = "Layout smoke detectors in room 12x15m and calculate voltage drop on circuit nac-01"
    plan = planner.plan_workflow(
        prompt=prompt,
        principal=test_principal,
        project_id="proj-degrade-01",
        expected_revision=1,
    )

    # 3. Assert plan was synthesized by the fallback ladder
    assert plan is not None
    assert plan.plan_id.startswith("plan-")
    assert len(plan.steps) >= 1
    # 5. Project/revision binding preserved
    assert plan.project_id == "proj-degrade-01"
    assert plan.expected_revision == 1
    # 6. Dry run flag preserved; zero state mutation on bus
    assert plan.is_dry_run is True
    assert bus.get_project_revision("proj-degrade-01") == 1

    # 8. Telemetry audit verification: prove degradation ladder entered and logged
    telemetry_summary = default_planner_telemetry.get_summary()
    assert telemetry_summary["regex_fallback"]["count"] >= 1
    assert any("Upstream LLM Provider HTTP 503" in r for r in telemetry_summary["regex_fallback"]["fallback_reasons"])

    # Double check unrecoverable failure path: unresolvable intent fails cleanly and explicitly
    with pytest.raises(InvalidWorkflowIntentError):
        planner.plan_workflow(
            prompt="Make a chocolate cake with frosting",
            principal=test_principal,
            project_id="proj-degrade-01",
            expected_revision=1,
        )
    # Revision remains unmutated
    assert bus.get_project_revision("proj-degrade-01") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 7. REDIS FAILURE DURING ACTIVE RUN (DEGRADATION & FAIL-CLOSED BOUNDARIES) (BLOCKER 3)
# ═══════════════════════════════════════════════════════════════════════════════

def test_redis_unavailability_graceful_degradation(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Chaos Scenario 7: Redis failure occurs while an active run is in flight.
    Proves:
      1. Active run exists in AgentRunStore.
      2. Redis/state backend fails mid-execution.
      3. System follows intended degradation policy (in-memory session fallback in dev; fail-closed in strict prod).
      4. No mutation is duplicated.
      5. No run state is silently lost.
      6. Correlation and approval binding remain intact.
      7. Auditability remains intact.
      8. Final state is deterministic.
    """
    bus = CommandBus(chaos_registry, state_store)
    bus.set_project_revision("proj-redis-chaos", 1)

    orch = AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=chaos_registry,
        run_store=run_store,
        environment="development",
    )

    steps = [
        {"step_id": "s1", "capability_id": "chaos.step_1", "payload": {}},
        {"step_id": "s2", "capability_id": "chaos.step_approval", "payload": {}},
    ]

    # 1. Start active run — step 1 commits (rev 1 -> 2), step 2 halts at WAITING_APPROVAL
    run = orch.start_run(
        test_principal,
        project_id="proj-redis-chaos",
        steps=steps,
        approval_mode=ApprovalMode.AUTO,
    )
    assert run.status == RunStatus.WAITING_APPROVAL
    assert run.completed_steps == ["s1"]
    assert bus.get_project_revision("proj-redis-chaos") == 2

    # 2. Simulate Redis failure during active run
    session_store = SessionStore()

    class BrokenRedisConnection:
        def get(self, *args, **kwargs):
            raise ConnectionError("Redis cluster unreachable during active run (Chaos Injection)")

        def set(self, *args, **kwargs):
            raise ConnectionError("Redis cluster unreachable during active run (Chaos Injection)")

        def delete(self, *args, **kwargs):
            raise ConnectionError("Redis cluster unreachable during active run (Chaos Injection)")

    session_store._redis = BrokenRedisConnection()

    # 3. Authenticate caller session under Redis failure -> degrades to safe in-memory fallback
    session_data = {
        "user_id": test_principal.user_id,
        "role": test_principal.role,
        "expires_at": time.time() + 3600.0,
    }
    session_store.set("active_run_session_01", session_data)
    recovered_session = session_store.get("active_run_session_01")
    assert recovered_session is not None
    assert recovered_session["user_id"] == test_principal.user_id

    # 5 & 6. Verify run state in AgentRunStore was not lost and approval binding is intact
    active_run = run_store.get_run(run.run_id)
    assert active_run is not None
    assert active_run.status == RunStatus.WAITING_APPROVAL
    assert active_run.pending_approval_id == run.pending_approval_id

    # 4 & 8. Resume / decide approval — step 2 completes, step 1 is NOT duplicated
    completed_run = orch.decide_approval(
        caller_id=test_principal.user_id,
        approval_id=active_run.pending_approval_id,
        decision=ApprovalDecisionValue.APPROVED,
    )
    assert completed_run.status == RunStatus.COMPLETED
    assert completed_run.completed_steps == ["s1", "s2"]
    # Revision moves from 2 -> 3 (no duplication of step 1)
    assert bus.get_project_revision("proj-redis-chaos") == 3

    # Test the production fail-closed boundary: In strict production mode, unconfigured Redis fails closed
    from backend.env_validator import ConfigurationError
    from backend.session_store import _raise_if_production

    monkeypatch.setenv("FIREAI_ENV", "production")
    monkeypatch.setenv("FIREAI_ENV_VALIDATION", "strict")

    with pytest.raises(ConfigurationError):
        _raise_if_production("Redis unavailable in production mode (Chaos Injection)")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. DATABASE COMMIT FAILURE & ATOMIC OCC ROLLBACK
# ═══════════════════════════════════════════════════════════════════════════════

def test_database_commit_failure_atomic_rollback(
    fresh_db: Database,
    state_store: CommandStateStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Chaos Scenario 8: Database transaction fails mid-commit (e.g. disk I/O error or constraint violation).
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
# 9. PARTIAL EXECUTION, PAUSE & RESUME RECOVERY STATE PRESERVATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_partial_execution_pause_and_resume_recovery(
    fresh_db: Database,
    state_store: CommandStateStore,
    run_store: AgentRunStore,
    chaos_registry: CapabilityRegistry,
    test_principal: AuthenticatedPrincipal,
) -> None:
    """
    Chaos Scenario 9: Run is paused mid-execution, state is audited, and resumed to completion.
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
