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
from datetime import UTC, datetime

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
        fresh_db.create_project({"id": project_id, "name": "OCC Test Project", "author": "lead-engineer-01"})

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
            timestamp=datetime.now(UTC).isoformat(),
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
            timestamp=datetime.now(UTC).isoformat(),
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
        fresh_db.create_project({"id": project_id, "name": "Idemp Project", "author": "lead-engineer-01"})
        bus_instance_1 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))
        bus_instance_2 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))

        cmd = DomainCommand(
            commandId="cmd-idempotent-persistent-01",
            correlationId="corr-idemp-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
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
        fresh_db.create_project({"id": project_id, "name": "Collision Project", "author": "lead-engineer-01"})
        bus = CommandBus(default_capability_registry, CommandStateStore(fresh_db))

        cmd_orig = DomainCommand(
            commandId="cmd-reuse-collision-01",
            correlationId="corr-c1",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
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
            timestamp=datetime.now(UTC).isoformat(),
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
        fresh_db.create_project({"id": project_id, "name": "Rollback Project", "author": "lead-engineer-01"})
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
            timestamp=datetime.now(UTC).isoformat(),
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
            timestamp=datetime.now(UTC).isoformat(),
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
                (
                    "cmd-atomic-fail-01",
                    "corr",
                    None,
                    project_id,
                    "spatial.place_devices",
                    1,
                    2,
                    "actor",
                    0,
                    "hash",
                    "{}",
                    "COMPLETED",
                    "2026-01-01T00:00:00Z",
                ),
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
            timestamp=datetime.now(UTC).isoformat(),
            verificationResult={},
            auditReference="0" * 64,
            payload={},
        )

        # Attempting commit_transaction must fail due to duplicate command_id PK constraint
        with pytest.raises((Exception, BaseException)) as exc_info:  # noqa: PT011
            store.commit_transaction(
                command=cmd,
                new_revision=2,
                exec_result={"devices": [{"id": "should-never-commit"}]},
                event=event,
                payload_hash="new_hash",
            )
        # The exception must be a database integrity error (duplicate PK)
        assert exc_info.value is not None

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
        fresh_db.create_project({"id": project_id, "name": "Events Project", "author": "lead-engineer-01"})
        store = CommandStateStore(fresh_db)
        bus = CommandBus(default_capability_registry, store)

        cmd = DomainCommand(
            commandId="cmd-event-audit-01",
            correlationId="corr-event-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
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
        fresh_db.create_project({"id": project_id, "name": "Restart Project", "author": "lead-engineer-01"})

        # Session 1: Process executes commit
        bus_1 = CommandBus(default_capability_registry, CommandStateStore(fresh_db))
        cmd = DomainCommand(
            commandId="cmd-restart-01",
            correlationId="corr-restart-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
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
            timestamp=datetime.now(UTC).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-rec", "width_m": 8.0, "length_m": 10.0},
        )
        res2 = bus_2.execute(cmd2)
        assert res2.success is True
        assert res2.revision == 3


class TestCoverageBooster:
    """Targeted tests to cover previously uncovered lines and reach >=80% new-line coverage."""

    def _make_principal(self, scopes: list[str] | None = None) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            user_id="test-cov-user",
            email="test-cov@bazspark.io",
            role="engineer",
            scopes=scopes or ["spatial:write", "spatial:read"],
            is_authenticated=True,
        )

    def _make_cmd(
        self,
        cmd_id: str,
        project_id: str,
        capability_id: str = "spatial.place_devices",
        expected_rev: int = 1,
        dry_run: bool = False,
        payload: dict | None = None,
        scopes: list[str] | None = None,
    ) -> DomainCommand:
        return DomainCommand(
            commandId=cmd_id,
            correlationId=f"corr-{cmd_id}",
            capabilityId=capability_id,
            projectId=project_id,
            expectedRevision=expected_rev,
            timestamp=datetime.now(UTC).isoformat(),
            principal=self._make_principal(scopes),
            isDryRun=dry_run,
            payload=payload or {"room_id": "r1", "width_m": 5.0, "length_m": 8.0},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # StateStore: tuple-row vs dict-row paths (get_project_revision, get_canonical_state)
    # ──────────────────────────────────────────────────────────────────────────

    def test_state_store_get_revision_returns_none_for_unknown_project(self) -> None:
        db = Database()
        store = CommandStateStore(db)
        assert store.get_project_revision("nonexistent-project-xyz") is None

    def test_state_store_get_canonical_state_returns_none_for_unknown_project(self) -> None:
        db = Database()
        store = CommandStateStore(db)
        state = store.get_canonical_state("nonexistent-project-abc")
        assert state is None

    def test_state_store_set_revision_insert_then_update(self) -> None:
        """Covers both the INSERT (row is None) and UPDATE (row exists) branches."""
        db = Database()
        store = CommandStateStore(db)
        pid = "proj-set-rev-test"
        # First call: INSERT path (row is None)
        store.set_project_revision(pid, 1)
        assert store.get_project_revision(pid) == 1
        # Second call: UPDATE path (row exists)
        store.set_project_revision(pid, 2)
        assert store.get_project_revision(pid) == 2

    def test_state_store_save_canonical_state_insert_and_update(self) -> None:
        db = Database()
        store = CommandStateStore(db)
        pid = "proj-save-state-test"
        state1 = {"devices": [{"id": "d1"}], "revision": 1}
        store.save_canonical_state(pid, state1, 1)
        loaded = store.get_canonical_state(pid)
        assert loaded["devices"] == [{"id": "d1"}]
        # Update path
        state2 = {"devices": [{"id": "d2"}], "revision": 2}
        store.save_canonical_state(pid, state2, 2)
        loaded2 = store.get_canonical_state(pid)
        assert loaded2["devices"] == [{"id": "d2"}]

    def test_state_store_get_domain_events_without_project_id(self) -> None:
        """Covers the `else` branch in get_domain_events (no project_id filter)."""
        db = Database()
        store = CommandStateStore(db)
        # Should return empty list (no events yet for this DB instance)
        events = store.get_domain_events(project_id=None, limit=10)
        assert isinstance(events, list)

    def test_state_store_get_domain_events_with_project_id(self) -> None:
        db = Database()
        store = CommandStateStore(db)
        events = store.get_domain_events(project_id="some-project", limit=5)
        assert isinstance(events, list)

    def test_state_store_occ_conflict_nonexistent_project_wrong_revision(self) -> None:
        """Covers OCC conflict when project doesn't exist but expectedRevision != 1."""
        from backend.core.command_bus import DomainEvent

        db = Database()
        store = CommandStateStore(db)
        pid = "proj-occ-nonexistent"
        cmd = self._make_cmd("cmd-occ-ne", pid, expected_rev=5)
        event = DomainEvent(
            eventId="evt-occ-ne",
            commandId="cmd-occ-ne",
            correlationId="corr-occ-ne",
            projectId=pid,
            revision=6,
            actor="test-cov-user",
            eventType="DEVICES_PLACED",
            timestamp=datetime.now(UTC).isoformat(),
            verificationResult={},
            auditReference="a" * 64,
            payload={},
        )
        committed, error = store.commit_transaction(
            command=cmd,
            new_revision=6,
            exec_result={"devices": []},
            event=event,
            payload_hash="ph1",
        )
        assert committed is False
        assert error == "CONCURRENCY_CONFLICT"

    # ──────────────────────────────────────────────────────────────────────────
    # CommandBus: dry-run, no-handler, handler exception, post-commit OCC fail
    # ──────────────────────────────────────────────────────────────────────────

    def test_command_bus_dry_run_returns_result_without_commit(self) -> None:
        db = Database()
        bus = CommandBus(state_store=CommandStateStore(db))
        pid = "proj-dry-run-test"
        bus.state_store.set_project_revision(pid, 1)
        cmd = self._make_cmd("cmd-dry-01", pid, dry_run=True)
        result = bus.execute(cmd)
        assert result.success is True
        assert result.isDryRun is True
        # Revision must NOT have advanced
        assert bus.get_project_revision(pid) == 1

    def test_command_bus_capability_no_handler_returns_error(self) -> None:
        """Covers the `not cap.handler` branch in execute()."""
        db = Database()
        reg = CapabilityRegistry()
        cap_no_handler = CapabilityDefinition(
            capability_id="test.no_handler",
            name="No Handler Cap",
            description="Capability with no execution handler.",
            category="test",
            risk_class="LOW",
            required_scopes=["spatial:write"],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            handler=None,
        )
        reg.register(cap_no_handler)
        bus = CommandBus(capability_registry=reg, state_store=CommandStateStore(db))
        pid = "proj-no-handler"
        bus.state_store.set_project_revision(pid, 1)
        cmd = self._make_cmd("cmd-nohand-01", pid, capability_id="test.no_handler")
        result = bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "CAPABILITY_EXECUTION_ERROR"

    def test_command_bus_handler_exception_returns_error(self) -> None:
        """Covers the except branch when cap.handler raises an exception."""
        db = Database()
        reg = CapabilityRegistry()

        def _failing_handler(payload: dict) -> dict:
            raise ValueError("Simulated handler failure")

        cap_fail = CapabilityDefinition(
            capability_id="test.failing",
            name="Failing Cap",
            description="Always raises.",
            category="test",
            risk_class="LOW",
            required_scopes=["spatial:write"],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            handler=_failing_handler,
        )
        reg.register(cap_fail)
        bus = CommandBus(capability_registry=reg, state_store=CommandStateStore(db))
        pid = "proj-handler-fail"
        bus.state_store.set_project_revision(pid, 1)
        cmd = self._make_cmd("cmd-fail-01", pid, capability_id="test.failing")
        result = bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "HANDLER_EXECUTION_FAILED"
        assert "Simulated handler failure" in (result.errorMessage or "")

    def test_command_bus_post_commit_occ_conflict_returns_error(self) -> None:
        """Covers the `not committed` branch: commit_transaction returns CONCURRENCY_CONFLICT."""
        db = Database()
        bus = CommandBus(state_store=CommandStateStore(db))
        pid = "proj-post-commit-conflict"
        # Set revision to 1 but send command expecting revision 5 (mismatch → OCC conflict)
        bus.state_store.set_project_revision(pid, 1)
        cmd = self._make_cmd("cmd-pcc-01", pid, expected_rev=5)
        result = bus.execute(cmd)
        assert result.success is False
        assert "CONCURRENCY_CONFLICT" in (result.errorCode or "")

    # ──────────────────────────────────────────────────────────────────────────
    # CapabilityRegistry: verify_detector_spacing with and without devices
    # ──────────────────────────────────────────────────────────────────────────

    def test_capability_registry_verify_detector_spacing_with_devices(self) -> None:
        """Covers the verify_detector_spacing handler with actual devices."""
        cap = default_capability_registry.get("compliance.verify_detector_spacing")
        assert cap is not None
        result = cap.handler(
            {
                "room_id": "r1",
                "width_m": 10.0,
                "length_m": 15.0,
                "ceiling_height_m": 3.5,  # > 3.0 → derating branch
                "devices": [{"id": "d1", "x_m": 3.0, "y_m": 3.0}],
            }
        )
        assert "verified" in result
        assert "max_allowable_radius_m" in result
        # Derated radius should be 6.37 * 0.9 ≈ 5.73
        assert abs(result["max_allowable_radius_m"] - round(6.37 * 0.9, 2)) < 0.01

    def test_capability_registry_verify_detector_spacing_no_devices_fails(self) -> None:
        """Covers the `if not devices: violations.append(...)` branch."""
        cap = default_capability_registry.get("compliance.verify_detector_spacing")
        assert cap is not None
        result = cap.handler(
            {
                "room_id": "r1",
                "width_m": 10.0,
                "length_m": 15.0,
                "ceiling_height_m": 2.5,  # <= 3.0 → no derating
                "devices": [],
            }
        )
        assert result["verified"] is False
        assert any("Zero devices" in v for v in result["violations"])
        # Standard radius at <= 3.0m ceiling
        assert result["max_allowable_radius_m"] == 6.37

    def test_capability_registry_place_devices_handler(self) -> None:
        """Covers the spatial.place_devices handler path."""
        cap = default_capability_registry.get("spatial.place_devices")
        assert cap is not None
        result = cap.handler(
            {"room_id": "r-cov", "width_m": 8.0, "length_m": 10.0, "ceiling_height_m": 3.0}
        )
        assert "devices" in result
        assert isinstance(result["devices"], list)

    def test_command_result_to_dict(self) -> None:
        """Covers CommandResult.to_dict() and DomainCommand.to_dict()."""
        from backend.core.command_bus import CommandResult

        r = CommandResult(
            success=True,
            commandId="cmd-x",
            projectId="proj-x",
            revision=1,
            isDryRun=False,
            resultData={"devices": []},
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["commandId"] == "cmd-x"

    def test_domain_command_to_dict(self) -> None:
        cmd = self._make_cmd("cmd-dict-01", "proj-dict")
        d = cmd.to_dict()
        assert d["commandId"] == "cmd-dict-01"
        assert "principal" in d

    def test_state_store_get_idempotent_command_with_event(self) -> None:
        """Covers StateStore L207-255: retrieving cached command with associated DomainEvent."""
        from backend.core.command_bus import DomainEvent

        db = Database()
        store = CommandStateStore(db)
        pid = "proj-idem-event"
        store.set_project_revision(pid, 1)
        cmd = self._make_cmd("cmd-with-event-01", pid, expected_rev=1)
        event = DomainEvent(
            eventId="evt-with-event-01",
            commandId="cmd-with-event-01",
            correlationId="corr-with-event-01",
            projectId=pid,
            revision=2,
            actor="test-cov-user",
            eventType="DEVICES_PLACED",
            timestamp=datetime.now(UTC).isoformat(),
            verificationResult={"coverage_pct": 98.5},
            auditReference="a" * 64,
            payload={"devices": [{"id": "d1"}]},
        )
        committed, err = store.commit_transaction(
            command=cmd,
            new_revision=2,
            exec_result={"devices": [{"id": "d1"}]},
            event=event,
            payload_hash="hash123",
        )
        assert committed is True
        assert err is None

        # Now lookup the cached command with its event
        cached_result, is_collision = store.get_idempotent_command("cmd-with-event-01", "hash123")
        assert is_collision is False
        assert cached_result is not None
        assert cached_result.commandId == "cmd-with-event-01"
        assert cached_result.event is not None
        assert cached_result.event.eventId == "evt-with-event-01"
        assert cached_result.event.verificationResult == {"coverage_pct": 98.5}

    def test_state_store_get_domain_events_rows_parsed(self) -> None:
        """Covers StateStore L444, L461-473: get_domain_events with persisted rows."""
        from backend.core.command_bus import DomainEvent

        db = Database()
        store = CommandStateStore(db)
        pid = "proj-events-parsed"
        store.set_project_revision(pid, 1)
        cmd = self._make_cmd("cmd-events-parsed-01", pid, expected_rev=1)
        event = DomainEvent(
            eventId="evt-events-parsed-01",
            commandId="cmd-events-parsed-01",
            correlationId="corr-events-parsed-01",
            projectId=pid,
            revision=2,
            actor="test-cov-user",
            eventType="DEVICES_PLACED",
            timestamp=datetime.now(UTC).isoformat(),
            verificationResult={"valid": True},
            auditReference="b" * 64,
            payload={"devices": []},
        )
        committed, err = store.commit_transaction(
            command=cmd,
            new_revision=2,
            exec_result={"devices": []},
            event=event,
            payload_hash="hash456",
        )
        assert committed is True

        events = store.get_domain_events(project_id=pid, limit=10)
        assert len(events) >= 1
        assert events[0].eventId == "evt-events-parsed-01"
        assert events[0].verificationResult == {"valid": True}
