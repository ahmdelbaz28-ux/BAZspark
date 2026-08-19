"""backend/tests/test_phase2a_persistence.py — Phase 2A Persistence & Distributed OCC Test Suite.

Validates:
- Database-backed Distributed Optimistic Concurrency Control (OCC)
- Persistent Idempotency Across Multiple CommandBus Instances
- Atomic Transaction Commit & Rollback Integrity
- Persistent Domain Event / Audit Ledger
- Application Restart State Recovery
- Multi-Worker Concurrency Simulation
"""

from __future__ import annotations

import concurrent.futures
import json
import time
from datetime import datetime, timezone
import pytest

from backend.core.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
)
from backend.core.state_store import CommandStateStore
from backend.database import Database


@pytest.fixture
def fresh_db(tmp_path) -> Database:
    """Create an isolated, temporary SQLite database for test reproducibility."""
    db_file = str(tmp_path / "test_phase2a.db")
    return Database(db_file)


@pytest.fixture
def state_store(fresh_db: Database) -> CommandStateStore:
    return CommandStateStore(fresh_db)


@pytest.fixture
def command_bus(state_store: CommandStateStore) -> CommandBus:
    return CommandBus(default_capability_registry, state_store)


@pytest.fixture
def test_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="lead-engineer-01",
        email="engineer@bazspark.com",
        role="engineer",
        scopes=["spatial:write", "compliance:read"],
        is_authenticated=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DISTRIBUTED OCC TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDistributedOCC:
    def test_concurrent_conflicting_commands_single_winner(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        """Simulate two concurrent workers attempting to commit against project revision 1.

        Requirement: Exactly one must succeed (advancing revision to 2).
        The other MUST return CONCURRENCY_CONFLICT, leaving final revision at exactly 2.
        """
        project_id = "proj-concurrent-occ-01"

        # Worker A and Worker B separate runtime instances sharing the same DB
        worker_a = CommandBus(default_capability_registry, CommandStateStore(fresh_db))
        worker_b = CommandBus(default_capability_registry, CommandStateStore(fresh_db))

        # Initial revision is 1
        assert worker_a.get_project_revision(project_id) == 1

        cmd_a = DomainCommand(
            commandId="cmd-worker-a-01",
            correlationId="corr-a",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-a", "width_m": 8.0, "length_m": 10.0},
        )

        cmd_b = DomainCommand(
            commandId="cmd-worker-b-01",
            correlationId="corr-b",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-b", "width_m": 12.0, "length_m": 14.0},
        )

        results = []

        def execute_cmd(bus: CommandBus, cmd: DomainCommand):
            return bus.execute(cmd)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(execute_cmd, worker_a, cmd_a)
            fut_b = executor.submit(execute_cmd, worker_b, cmd_b)
            results = [fut_a.result(), fut_b.result()]

        success_results = [r for r in results if r.success is True]
        conflict_results = [r for r in results if r.errorCode == "CONCURRENCY_CONFLICT"]

        # Exactly 1 success and 1 conflict
        assert len(success_results) == 1
        assert len(conflict_results) == 1

        # Final revision must be exactly 2 (not 3)
        final_rev = worker_a.get_project_revision(project_id)
        assert final_rev == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PERSISTENT IDEMPOTENCY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersistentIdempotency:
    def test_duplicate_command_across_separate_instances(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        """Execute the same commandId on separate CommandBus instances (simulating multi-replica restart/routing).

        Requirement:
        - First call executes and commits.
        - Second call returns stored result from database.
        - Revision is NOT incremented twice.
        """
        project_id = "proj-idemp-01"
        bus_instance_1 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))
        bus_instance_2 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))

        cmd = DomainCommand(
            commandId="cmd-idempotent-persistent-01",
            correlationId="corr-idemp-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-idemp", "width_m": 6.0, "length_m": 8.0},
        )

        res1 = bus_instance_1.execute(cmd)
        assert res1.success is True
        assert res1.revision == 2

        # Replay on a completely different CommandBus instance
        res2 = bus_instance_2.execute(cmd)
        assert res2.success is True
        assert res2.revision == 2
        assert res2.commandId == cmd.commandId
        assert len(res2.resultData.get("devices", [])) == len(res1.resultData.get("devices", []))

        # Check DB project revision remains 2
        assert bus_instance_1.get_project_revision(project_id) == 2

    def test_idempotency_key_reuse_collision_detection(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        """When the same commandId is submitted with different payload semantics (collision):

        Requirement:
        - Must NOT silently return cached result.
        - Must return IDEMPOTENCY_KEY_REUSE_CONFLICT.
        - Must NOT mutate state or advance revision.
        """
        project_id = "proj-idemp-collision"
        bus = CommandBus(default_capability_registry, CommandStateStore(fresh_db))

        cmd_orig = DomainCommand(
            commandId="cmd-reuse-collision-01",
            correlationId="corr-c1",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-orig", "width_m": 10.0, "length_m": 10.0},
        )
        res1 = bus.execute(cmd_orig)
        assert res1.success is True
        assert res1.revision == 2

        # Submit same commandId with DIFFERENT payload
        cmd_diff = DomainCommand(
            commandId="cmd-reuse-collision-01",  # Reused key!
            correlationId="corr-c2",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=2,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-different", "width_m": 50.0, "length_m": 50.0},
        )
        res2 = bus.execute(cmd_diff)
        assert res2.success is False
        assert res2.errorCode == "IDEMPOTENCY_KEY_REUSE_CONFLICT"

        # Canonical revision and devices remain unchanged from res1
        assert bus.get_project_revision(project_id) == 2
        canonical = bus.get_canonical_state(project_id)
        assert canonical["revision"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TRANSACTION & ROLLBACK TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransactionRollback:
    def test_handler_failure_rolls_back_transaction(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        """When a capability handler throws an exception during execution:

        Requirement:
        - Revision remains unchanged.
        - No corrupt command_executions row is committed.
        - No domain event is written.
        """
        project_id = "proj-rollback-01"
        store = CommandStateStore(fresh_db)

        # Create custom capability registry with failing handler
        registry = CapabilityRegistry()

        def failing_handler(payload: dict):
            raise RuntimeError("Database connection or physics solver fatal crash!")

        failing_cap = CapabilityDefinition(
            capability_id="failing.test_tool",
            name="Failing Tool",
            description="Throws error",
            category="test",
            risk_class="LOW",
            required_scopes=["spatial:write"],
            input_schema={},
            output_schema={},
            handler=failing_handler,
        )
        registry.register(failing_cap)

        bus = CommandBus(registry, store)
        assert bus.get_project_revision(project_id) == 1

        failing_cmd = DomainCommand(
            commandId="cmd-fail-rollback-01",
            correlationId="corr-fail",
            capabilityId="failing.test_tool",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={},
        )

        res = bus.execute(failing_cmd)
        assert res.success is False
        assert res.errorCode == "HANDLER_EXECUTION_FAILED"

        # Verify revision remains 1
        assert bus.get_project_revision(project_id) == 1

        # Verify no idempotency record exists
        stored_cmd, _ = store.get_idempotent_command(failing_cmd.commandId)
        assert stored_cmd is None

        # Verify no domain events were persisted
        events = store.get_domain_events(project_id)
        assert len(events) == 0

    def test_post_mutation_commit_failure_rolls_back_all_state(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        """When a post-mutation failure occurs during commit (simulated via DB error in transaction):

        Requirement:
        - Neither canonical state nor revision is updated.
        - No command_executions row remains.
        - No domain_events row remains.
        """
        project_id = "proj-rollback-atomic-02"
        store = CommandStateStore(fresh_db)

        # Set initial canonical state
        initial_state = {"devices": [{"id": "initial-1", "x_m": 1.0, "y_m": 1.0}], "revision": 1}
        store.save_canonical_state(project_id, initial_state, 1)

        # Simulate commit failure where commit_transaction encounters a fatal SQL constraint
        # by inserting an invalid duplicate command_id directly or raising an error
        # Let's test that commit_transaction atomic block rolls back everything on error:
        from backend.core.command_bus import DomainEvent

        cmd = DomainCommand(
            commandId="cmd-atomic-fail-01",
            correlationId="corr-atomic",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-fail", "width_m": 10.0, "length_m": 10.0},
        )

        # Pre-seed command_executions with same commandId to trigger duplicate PK violation during commit
        with fresh_db._transaction() as cur:
            cur.execute(
                f"""
                INSERT INTO command_executions (
                    command_id, correlation_id, causation_id, project_id, capability_id,
                    expected_revision, committed_revision, actor, is_dry_run, payload_hash, result_data, status, created_at
                ) VALUES ({fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()},
                          {fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()},
                          {fresh_db._ph()}, {fresh_db._ph()}, {fresh_db._ph()})
                """,
                ("cmd-atomic-fail-01", "corr", None, project_id, "spatial.place_devices", 1, 2, "actor", 0, "hash", "{}", "COMPLETED", "2026-01-01T00:00:00Z"),
            )

        event = DomainEvent(
            eventId="evt-atomic-fail",
            commandId=cmd.commandId,
            correlationId="corr",
            causationId=None,
            projectId=project_id,
            revision=2,
            actor=test_principal.user_id,
            eventType="DEVICES_PLACED",
            timestamp=datetime.now(timezone.utc).isoformat(),
            verificationResult={},
            auditReference="0" * 64,
            payload={},
        )

        # Attempting commit_transaction must fail due to duplicate command_id PK constraint
        with pytest.raises(Exception):
            store.commit_transaction(
                command=cmd,
                new_revision=2,
                exec_result={"devices": [{"id": "should-never-commit"}]},
                event=event,
                payload_hash="new_hash",
            )

        # Invariant check: revision must still be 1, canonical state must still have initial-1
        assert store.get_project_revision(project_id) == 1
        canonical = store.get_canonical_state(project_id)
        assert canonical["devices"] == [{"id": "initial-1", "x_m": 1.0, "y_m": 1.0}]
        assert len(store.get_domain_events(project_id)) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EVENT & AUDIT PERSISTENCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventPersistence:
    def test_domain_events_persisted_to_database(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        project_id = "proj-events-01"
        store = CommandStateStore(fresh_db)
        bus = CommandBus(default_capability_registry, store)

        cmd = DomainCommand(
            commandId="cmd-event-audit-01",
            correlationId="corr-event-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-aud", "width_m": 7.0, "length_m": 9.0},
        )

        res = bus.execute(cmd)
        assert res.success is True
        assert res.event is not None

        # Fetch persisted events directly from database
        events = store.get_domain_events(project_id)
        assert len(events) == 1
        ev = events[0]
        assert ev.commandId == cmd.commandId
        assert ev.projectId == project_id
        assert ev.revision == 2
        assert ev.actor == test_principal.user_id
        assert len(ev.auditReference) == 64  # SHA-256


# ═══════════════════════════════════════════════════════════════════════════════
# 5. RESTART RECOVERY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRestartRecovery:
    def test_state_and_revision_recovery_after_process_restart(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ):
        project_id = "proj-restart-01"

        # Session 1: Process executes commit
        bus_1 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))
        cmd = DomainCommand(
            commandId="cmd-restart-01",
            correlationId="corr-restart-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-rec", "width_m": 8.0, "length_m": 10.0},
        )
        res1 = bus_1.execute(cmd)
        assert res1.success is True
        assert res1.revision == 2

        # Simulate full process death and recreate fresh CommandBus & CommandStateStore
        bus_2 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))

        # Check revision recovered
        assert bus_2.get_project_revision(project_id) == 2

        # Check canonical state recovered
        canonical = bus_2.get_canonical_state(project_id)
        assert canonical["revision"] == 2
        assert len(canonical["devices"]) > 0

        # Check second commit with expectedRevision = 2 advances to 3
        cmd2 = DomainCommand(
            commandId="cmd-restart-02",
            correlationId="corr-restart-02",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=2,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-rec", "width_m": 8.0, "length_m": 10.0},
        )
        res2 = bus_2.execute(cmd2)
        assert res2.success is True
        assert res2.revision == 3
        assert bus_2.get_project_revision(project_id) == 3
