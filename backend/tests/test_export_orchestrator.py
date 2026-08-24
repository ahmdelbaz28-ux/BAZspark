"""backend/tests/test_export_orchestrator.py — Tests for Unified Export Orchestrator.

Covers:
- Export planning for all supported formats (.dxf, .revit, .ifc, .xlsx, .csv, .json, .pdf)
- Loss / Mapping analysis (LOSSLESS, PARTIALLY_LOSSLESS, LOSSY, UNSUPPORTED_MAPPING)
- Unsupported format rejection
- Deterministic artifact generation and structural validation
- OCC revision verification and drift protection (PROJECT_REVISION_CHANGED)
- Canonical state immutability (zero mutation side effects)
- SHA-256 checksum and tamper-evident audit logging
- Idempotent execution caching
- AgentRun orchestrator export pipeline integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.agent_run_orchestrator import AgentRunOrchestrator
from backend.core.agent_run_store import AgentRunStore, RunStatus
from backend.core.capability_registry import CapabilityRegistry
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus
from backend.core.export_orchestrator import (
    ExportOrchestrator,
    ProjectRevisionChangedError,
    StagedArtifactNotFoundError,
    UnsupportedExportFormatError,
    sanitize_export_filename,
)
from backend.core.state_store import CommandStateStore
from backend.database import Database

# ── Shared Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def test_db(tmp_path: Path) -> Database:
    db = Database(db_path=str(tmp_path / "export_test.db"))
    # Seed a test project with devices
    db.create_project({"id": "proj-exp-01", "name": "Fire Station Alpha", "author": "Chief Engineer"})
    db.create_device("proj-exp-01", {
        "id": "dev-01",
        "name": "Optical Smoke Detector",
        "type": "smoke_detector",
        "category": "FIRE_ALARM",
        "x": 10.0,
        "y": 15.0,
        "z": 3.0,
        "voltage": 24.0,
        "current": 0.05,
        "zone": "Zone 1",
    })
    db.create_device("proj-exp-01", {
        "id": "dev-02",
        "name": "Heat Detector",
        "type": "heat_detector",
        "category": "FIRE_ALARM",
        "x": 20.0,
        "y": 15.0,
        "z": 3.0,
        "voltage": 24.0,
        "current": 0.04,
        "zone": "Zone 1",
    })
    return db


@pytest.fixture
def state_store(test_db: Database) -> CommandStateStore:
    return CommandStateStore(test_db)


@pytest.fixture
def export_orchestrator(test_db: Database, state_store: CommandStateStore, tmp_path: Path) -> ExportOrchestrator:
    artifact_dir = tmp_path / "artifacts"
    return ExportOrchestrator(db=test_db, state_store=state_store, artifact_dir=artifact_dir)


@pytest.fixture
def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="eng-export-01",
        email="exporter@bazspark.io",
        role="engineer",
        scopes=["export:read", "export:write", "project:read", "project:write"],
        is_authenticated=True,
    )


# ── Format Planning & Mapping Tests ─────────────────────────────────────────


class TestExportPlanningAndMapping:
    @pytest.mark.parametrize("fmt", ["dxf", "revit", "ifc", "xlsx", "csv", "json", "pdf"])
    def test_plan_supported_formats(self, export_orchestrator: ExportOrchestrator, principal: AuthenticatedPrincipal, fmt: str):
        plan = export_orchestrator.plan_export("proj-exp-01", target_format=fmt, principal=principal)
        assert plan.project_id == "proj-exp-01"
        assert plan.target_format == fmt
        assert plan.estimated_devices == 2
        assert plan.mapping_status in ("LOSSLESS", "PARTIALLY_LOSSLESS", "LOSSY")
        assert plan.summary != ""

    def test_unsupported_format_raises_error(self, export_orchestrator: ExportOrchestrator, principal: AuthenticatedPrincipal):
        with pytest.raises(UnsupportedExportFormatError):
            export_orchestrator.plan_export("proj-exp-01", target_format="unknown_format", principal=principal)

    def test_csv_mapping_is_lossy(self, export_orchestrator: ExportOrchestrator, principal: AuthenticatedPrincipal):
        plan = export_orchestrator.plan_export("proj-exp-01", target_format="csv", principal=principal)
        assert plan.mapping_status == "LOSSY"
        assert len(plan.mapping_report.warnings) > 0

    def test_sanitize_filename(self):
        clean = sanitize_export_filename("../../../malicious_path/Project 1", "dxf")
        assert "/" not in clean and ".." not in clean
        assert clean.endswith(".dxf")


# ── Deterministic Execution & Generation Tests ──────────────────────────────


class TestExportExecutionLifecycle:
    @pytest.mark.parametrize("fmt", ["dxf", "revit", "ifc", "xlsx", "csv", "json", "pdf"])
    def test_execute_export_all_formats(
        self,
        export_orchestrator: ExportOrchestrator,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
        fmt: str,
    ):
        rev = state_store.get_project_revision("proj-exp-01")
        result = export_orchestrator.execute_export(
            project_id="proj-exp-01",
            expected_revision=rev,
            target_format=fmt,
            principal=principal,
        )

        assert result.success is True
        assert result.artifact.target_format == fmt
        assert result.artifact.file_size_bytes > 0
        assert len(result.artifact.sha256_hash) == 64
        assert result.artifact.validation_status == "VALID"
        assert Path(result.artifact.artifact_path).exists()

    def test_execute_export_enforces_occ_revision_match(
        self,
        export_orchestrator: ExportOrchestrator,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        rev = state_store.get_project_revision("proj-exp-01")
        # Pass wrong expected revision
        with pytest.raises(ProjectRevisionChangedError):
            export_orchestrator.execute_export(
                project_id="proj-exp-01",
                expected_revision=rev + 5,
                target_format="dxf",
                principal=principal,
            )

    def test_canonical_state_is_never_mutated(
        self,
        export_orchestrator: ExportOrchestrator,
        test_db: Database,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        rev_before = state_store.get_project_revision("proj-exp-01")
        devices_before = test_db.get_all_devices_for_project("proj-exp-01")

        export_orchestrator.execute_export(
            project_id="proj-exp-01",
            expected_revision=rev_before,
            target_format="dxf",
            principal=principal,
        )

        rev_after = state_store.get_project_revision("proj-exp-01")
        devices_after = test_db.get_all_devices_for_project("proj-exp-01")

        assert rev_before == rev_after
        assert len(devices_before) == len(devices_after)

    def test_idempotent_export_caching(
        self,
        export_orchestrator: ExportOrchestrator,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        rev = state_store.get_project_revision("proj-exp-01")
        res1 = export_orchestrator.execute_export("proj-exp-01", rev, "xlsx", principal)
        res2 = export_orchestrator.execute_export("proj-exp-01", rev, "xlsx", principal)

        assert res1.artifact.artifact_id == res2.artifact.artifact_id
        assert res1.artifact.sha256_hash == res2.artifact.sha256_hash

    def test_get_nonexistent_artifact_raises_error(self, export_orchestrator: ExportOrchestrator):
        with pytest.raises(StagedArtifactNotFoundError):
            export_orchestrator.get_artifact("art-nonexistent")


# ── AgentRun Integration Tests ──────────────────────────────────────────────


class TestAgentRunExportPipeline:
    def test_agent_run_export_pipeline_auto_mode(
        self,
        test_db: Database,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        registry = CapabilityRegistry()
        command_bus = CommandBus(capability_registry=registry, state_store=state_store)
        run_store = AgentRunStore(test_db)
        orchestrator = AgentRunOrchestrator(command_bus, registry, run_store)

        rev = state_store.get_project_revision("proj-exp-01")
        steps = [
            {
                "step_id": "step-1-plan",
                "capability_id": "export.plan_export",
                "description": "Plan DXF export",
                "payload": {"project_id": "proj-exp-01", "target_format": "dxf"},
            },
            {
                "step_id": "step-2-exec",
                "capability_id": "export.execute_export",
                "description": "Execute DXF export",
                "payload": {
                    "project_id": "proj-exp-01",
                    "expected_revision": rev,
                    "target_format": "dxf",
                },
            },
        ]

        run = orchestrator.start_run(
            principal,
            project_id="proj-exp-01",
            steps=steps,
            approval_mode="AUTO",
        )

        assert run.status == RunStatus.COMPLETED
        assert len(run.completed_steps) == 2
