"""BLK-02 Remediation Verification Test Suite.

Proves that:
1. MISSING canonical revision != REVISION 1
2. A missing persistent revision row remains None.
3. State store commit_transaction and commit_composite_transaction fail closed on missing project revision.
4. CommandBus, WorkflowPlanner, AgentRunOrchestrator, ExportOrchestrator, ImportOrchestrator,
   and Workflow context reconciliation reject execution when canonical revision is missing.
5. Database._row_to_project preserves None revision without fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from backend.core.agent_run_orchestrator import AgentRunOrchestrator
from backend.core.capability_registry import default_capability_registry
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus, DomainCommand, DomainEvent
from backend.core.export_orchestrator import ExportOrchestrator
from backend.core.export_orchestrator import ProjectNotFoundError as ExportProjectNotFoundError
from backend.core.import_orchestrator import ImportOrchestrator
from backend.core.import_orchestrator import ProjectNotFoundError as ImportProjectNotFoundError
from backend.core.state_store import CommandStateStore
from backend.core.workflow_planner import AutonomousPlannerError, AutonomousWorkflowPlanner
from backend.database import Database
from backend.routers.workflow import _reconcile_and_validate_execution_context


@pytest.fixture
def fresh_db(tmp_path) -> Database:
    db_path = str(tmp_path / "blk02_test.db")
    db = Database(db_path=db_path)
    return db


@pytest.fixture
def test_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="lead-engineer-01",
        email="lead@bazspark.io",
        role="lead_engineer",
        scopes=[
            "spatial:read",
            "spatial:write",
            "electrical:read",
            "electrical:write",
            "hydraulics:read",
            "hydraulics:write",
            "project:read",
            "project:write",
            "workflow:execute",
        ],
        is_authenticated=True,
    )


class TestBLK02CanonicalRevisionRemediation:
    """Rigorous verification suite for BLK-02 remediation."""

    def test_01_state_store_missing_project_returns_none(self, fresh_db: Database) -> None:
        """1. Missing canonical revision must return None, not 1 or a synthetic dict."""
        store = CommandStateStore(fresh_db)
        missing_id = "missing-project-uuid-001"

        rev = store.get_project_revision(missing_id)
        assert rev is None, f"Expected None for missing project revision, got {rev}"

        state = store.get_canonical_state(missing_id)
        assert state is None, f"Expected None for missing canonical state, got {state}"

    def test_02_state_store_commit_transaction_rejects_missing_project(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ) -> None:
        """2. commit_transaction must fail closed (CONCURRENCY_CONFLICT) on missing project."""
        store = CommandStateStore(fresh_db)
        missing_id = "missing-project-uuid-002"

        cmd = DomainCommand(
            commandId="cmd-test-missing-01",
            correlationId="corr-01",
            capabilityId="spatial.place_devices",
            projectId=missing_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-1"},
        )
        event = DomainEvent(
            eventId="evt-01",
            commandId="cmd-test-missing-01",
            correlationId="corr-01",
            projectId=missing_id,
            revision=2,
            actor=test_principal.user_id,
            eventType="DEVICES_PLACED",
            timestamp=datetime.now(UTC).isoformat(),
            verificationResult={},
            auditReference="a" * 64,
            payload={},
        )

        committed, err = store.commit_transaction(
            command=cmd,
            new_revision=2,
            exec_result={"devices": []},
            event=event,
            payload_hash="hash123",
        )
        assert committed is False
        assert err == "CONCURRENCY_CONFLICT"

    def test_03_state_store_commit_composite_transaction_rejects_missing_project(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ) -> None:
        """3. commit_composite_transaction must fail closed on missing project."""
        store = CommandStateStore(fresh_db)
        missing_id = "missing-project-uuid-003"

        committed, err = store.commit_composite_transaction(
            project_id=missing_id,
            expected_revision=1,
            commands=[],
            exec_results=[],
            combined_audit_digest="digest123",
        )
        assert committed is False
        assert err == "CONCURRENCY_CONFLICT"

    def test_04_command_bus_execute_rejects_missing_project_revision(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ) -> None:
        """4. CommandBus.execute must reject execution for missing project revision."""
        store = CommandStateStore(fresh_db)
        bus = CommandBus(default_capability_registry, store)
        missing_id = "missing-project-uuid-004"

        cmd = DomainCommand(
            commandId="cmd-test-bus-01",
            correlationId="corr-01",
            capabilityId="spatial.place_devices",
            projectId=missing_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-1", "width_m": 10.0, "length_m": 10.0},
        )

        result = bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "PROJECT_REVISION_NOT_FOUND"
        assert result.revision is None
        assert "uninitialized or missing canonical revision" in (result.errorMessage or "")

    def test_05_workflow_planner_rejects_missing_project_revision(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ) -> None:
        """5. WorkflowPlanner.plan_workflow must raise AutonomousPlannerError for missing project."""
        store = CommandStateStore(fresh_db)
        bus = CommandBus(default_capability_registry, store)
        planner = AutonomousWorkflowPlanner(command_bus=bus, capability_registry=default_capability_registry)
        missing_id = "missing-project-uuid-005"

        with pytest.raises(AutonomousPlannerError) as exc_info:
            planner.plan_workflow(
                prompt="Place smoke detectors in hall",
                principal=test_principal,
                project_id=missing_id,
            )
        assert "uninitialized or missing canonical revision" in str(exc_info.value)

    def test_06_agent_run_orchestrator_rejects_missing_project_revision(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ) -> None:
        """6. AgentRunOrchestrator must fail execution steps for missing project revision."""
        store = CommandStateStore(fresh_db)
        bus = CommandBus(default_capability_registry, store)
        orchestrator = AgentRunOrchestrator(command_bus=bus)
        missing_id = "missing-project-uuid-006"

        steps = [
            {
                "step_id": "step-1",
                "capability_id": "spatial.place_devices",
                "payload": {"room_id": "room-1", "width_m": 10.0, "length_m": 10.0},
            }
        ]

        run = orchestrator.start_run(
            principal=test_principal,
            project_id=missing_id,
            steps=steps,
        )
        assert run.status.value == "FAILED"
        assert any(
            (s.get("step_id") == "step-1" and s.get("error_code") == "PROJECT_REVISION_NOT_FOUND")
            if isinstance(s, dict)
            else (s == "step-1")
            for s in run.failed_steps
        )
        assert run.recovery_state.get("failure_error_code") == "PROJECT_REVISION_NOT_FOUND"

    def test_07_export_orchestrator_rejects_missing_project_revision(
        self, fresh_db: Database
    ) -> None:
        """7. ExportOrchestrator must raise ProjectNotFoundError for missing project."""
        store = CommandStateStore(fresh_db)
        orchestrator = ExportOrchestrator(fresh_db, store)
        missing_id = "missing-project-uuid-007"

        with pytest.raises(ExportProjectNotFoundError):
            orchestrator.plan_export(missing_id, "dxf")

        with pytest.raises(ExportProjectNotFoundError):
            orchestrator.execute_export(missing_id, expected_revision=1, target_format="dxf")

    def test_08_import_orchestrator_rejects_missing_project_revision(
        self, fresh_db: Database, test_principal: AuthenticatedPrincipal
    ) -> None:
        """8. ImportOrchestrator must raise ProjectNotFoundError when project has no canonical revision."""
        store = CommandStateStore(fresh_db)
        orchestrator = ImportOrchestrator(fresh_db, store)
        missing_id = "missing-project-uuid-008"

        # Stage a dummy DXF file
        staged = orchestrator.stage_file(
            content=b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n",
            filename="floorplan.dxf",
            principal=test_principal,
        )

        with pytest.raises(ImportProjectNotFoundError):
            orchestrator.plan_import(staged.file_id, missing_id, principal=test_principal)

        with pytest.raises(ImportProjectNotFoundError):
            orchestrator.execute_import(
                file_id=staged.file_id,
                project_id=missing_id,
                expected_revision=1,
                principal=test_principal,
            )

    def test_09_workflow_context_reconcile_missing_project_returns_400_or_404(
        self, fresh_db: Database
    ) -> None:
        """9. Workflow execution context reconciliation raises HTTP 400/404 for missing project."""
        class DummyRequest:
            headers = Headers({"content-type": "application/json"})
            state = type("State", (), {"user": {"sub": "lead-engineer-01", "role": "lead_engineer"}})()

        req = DummyRequest()

        with pytest.raises(HTTPException) as exc_info:
            _reconcile_and_validate_execution_context(
                request=req,
                project_id="missing-project-uuid-009",
                model_id="dt-missing-project-uuid-009",
            )
        assert exc_info.value.status_code in (400, 404)
        assert "not found" in exc_info.value.detail.lower()

    def test_10_database_row_to_project_preserves_none_revision(self) -> None:
        """10. Database._row_to_project preserves None revision without fallback to 1."""
        raw_row = {
            "id": "proj-none-rev",
            "name": "Uninitialized Project",
            "description": "No revision row",
            "author": "tester",
            "created_at": "2026-08-26T00:00:00Z",
            "updated_at": "2026-08-26T00:00:00Z",
            "status": "draft",
            "revision": None,
        }
        res = Database._row_to_project(raw_row)
        assert res["revision"] is None, f"Expected None revision, got {res['revision']}"
