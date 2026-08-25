"""backend/tests/test_import_orchestrator.py — Tests for Unified Import Orchestrator.

Covers:
- Format sniffing & magic byte detection (.dwg, .dxf, .pdf, .ifc, .rvt, .xlsx, .csv, .json)
- Path traversal & filename sanitization
- Size limits & resource exhaustion protection
- Staging, deterministic inspection, and metadata extraction
- Import planning bound to project revision
- OCC validation & atomic canonical commit with SHA-256 audit logging
- Rollback on concurrency conflict / revision mismatch
- AgentRun orchestrator multi-step import pipeline integration
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.agent_run_orchestrator import AgentRunOrchestrator
from backend.core.agent_run_store import AgentRunStore, RunStatus
from backend.core.capability_registry import CapabilityRegistry
from backend.core.command_bus import AuthenticatedPrincipal, CommandBus
from backend.core.import_orchestrator import (
    ImportOrchestrator,
    InvalidFileError,
    ProjectRevisionChangedError,
    ResourceLimitExceededError,
    StagedFileNotFoundError,
    UnsupportedFormatError,
    default_import_orchestrator,
    detect_file_format,
    sanitize_filename,
)
from backend.core.state_store import CommandStateStore
from backend.database import Database

# ── Shared Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def test_db(tmp_path: Path) -> Database:
    return Database(db_path=str(tmp_path / "import_test.db"))


@pytest.fixture
def state_store(test_db: Database) -> CommandStateStore:
    return CommandStateStore(test_db)


@pytest.fixture
def import_orchestrator(
    test_db: Database, state_store: CommandStateStore, tmp_path: Path
) -> ImportOrchestrator:
    staging_dir = tmp_path / "staging"
    return ImportOrchestrator(db=test_db, state_store=state_store, staging_dir=staging_dir)


@pytest.fixture
def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="eng-01",
        email="engineer@bazspark.io",
        role="engineer",
        scopes=["import:read", "import:write", "project:read", "project:write", "spatial:write"],
        is_authenticated=True,
    )


# ── Format Sniffing & Validation Tests ──────────────────────────────────────


class TestFormatSniffingAndSanitization:
    def test_detect_dwg_magic_bytes(self):
        content = b"AC1032\x00\x00AutoCAD Drawing Binary"
        assert detect_file_format(content, "floorplan.dwg") == "dwg"

    def test_detect_dxf_header(self):
        content = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF"
        assert detect_file_format(content, "drawing.dxf") == "dxf"

    def test_detect_pdf_header(self):
        content = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n"
        assert detect_file_format(content, "schematic.pdf") == "pdf"

    def test_detect_ifc_header(self):
        content = b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('IFC4'),'2;1');\n"
        assert detect_file_format(content, "model.ifc") == "ifc"

    def test_detect_rvt_ole2_header(self):
        content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00\x00\x00\x00"
        assert detect_file_format(content, "building.rvt") == "rvt"

    def test_detect_xlsx_zip_header(self):
        content = b"PK\x03\x04\x14\x00\x06\x00"
        assert detect_file_format(content, "schedules.xlsx") == "xlsx"

    def test_detect_json_payload(self):
        content = json.dumps({"devices": [{"id": "d1", "type": "smoke"}]}).encode("utf-8")
        assert detect_file_format(content, "devices.json") == "json"

    def test_detect_csv_text(self):
        content = b"device_id,type,location\nd1,smoke,Room 101\n"
        assert detect_file_format(content, "devices.csv") == "csv"

    def test_unsupported_format_raises_error(self):
        content = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00"  # Linux binary
        with pytest.raises(UnsupportedFormatError) as exc_info:
            detect_file_format(content, "malware.exe")
        assert exc_info.value.error_code == "UNSUPPORTED_FORMAT"

    def test_empty_content_raises_invalid_file(self):
        with pytest.raises(InvalidFileError) as exc_info:
            detect_file_format(b"", "empty.dwg")
        assert exc_info.value.error_code == "INVALID_FILE"

    def test_sanitize_filename_prevents_path_traversal(self):
        assert sanitize_filename("../../../etc/passwd") == "passwd"
        assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
        assert sanitize_filename("safe_drawing-v1.2.dwg") == "safe_drawing-v1.2.dwg"
        assert "staged_file_" in sanitize_filename("...")


# ── Staging, Inspection, Planning & Execution Tests ─────────────────────────


class TestImportOrchestratorLifecycle:
    def test_stage_and_inspect_dxf(
        self, import_orchestrator: ImportOrchestrator, principal: AuthenticatedPrincipal
    ):
        dxf_content = (
            b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n"
            b"  0\nSECTION\n  2\nENTITIES\n  0\nLWPOLYLINE\n  0\nENDSEC\n  0\nEOF"
        )
        record = import_orchestrator.stage_file(
            content=dxf_content,
            filename="level1_fire.dxf",
            principal=principal,
        )

        assert record.file_id.startswith("imp-")
        assert record.detected_format == "dxf"
        assert record.file_size_bytes == len(dxf_content)
        assert record.sanitized_filename == "level1_fire.dxf"

        # Inspect staged file
        inspection = import_orchestrator.inspect_file(record.file_id, principal=principal)
        assert inspection["file_id"] == record.file_id
        assert inspection["detected_format"] == "dxf"
        assert inspection["confidence_score"] >= 0.7
        assert inspection["rooms_count"] >= 1

    def test_stage_file_exceeds_size_limit(
        self, import_orchestrator: ImportOrchestrator, principal: AuthenticatedPrincipal
    ):
        oversized = b"%PDF-" + b"0" * (26 * 1024 * 1024)  # 26 MB > 25 MB limit for PDF
        with pytest.raises(ResourceLimitExceededError) as exc_info:
            import_orchestrator.stage_file(oversized, "big.pdf", principal=principal)
        assert exc_info.value.error_code == "RESOURCE_LIMIT_EXCEEDED"

    def test_plan_import_binds_to_canonical_revision(
        self,
        import_orchestrator: ImportOrchestrator,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        project_id = "proj-p3-01"
        state_store.set_project_revision(project_id, revision=3)

        pdf_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        record = import_orchestrator.stage_file(pdf_content, "fire_alarm.pdf", principal=principal)

        plan = import_orchestrator.plan_import(record.file_id, project_id, principal=principal)
        assert plan.file_id == record.file_id
        assert plan.project_id == project_id
        assert plan.expected_revision == 3
        assert plan.detected_format == "pdf"
        assert "Revision 3" in plan.summary

    def test_execute_import_advances_revision_and_audits(
        self,
        import_orchestrator: ImportOrchestrator,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        project_id = "proj-p3-02"
        state_store.set_project_revision(project_id, revision=1)

        dxf_content = b"  0\nSECTION\n  2\nENTITIES\n  0\nINSERT\n  0\nENDSEC\n  0\nEOF"
        record = import_orchestrator.stage_file(dxf_content, "detectors.dxf", principal=principal)

        # Plan import
        plan = import_orchestrator.plan_import(record.file_id, project_id, principal=principal)
        assert plan.expected_revision == 1

        # Execute import
        result = import_orchestrator.execute_import(
            file_id=record.file_id,
            project_id=project_id,
            expected_revision=1,
            principal=principal,
        )

        assert result.success is True
        assert result.previous_revision == 1
        assert result.new_revision == 2
        assert result.imported_devices >= 1
        assert len(result.audit_hash) == 64

        # Canonical state in DB should now have revision 2
        assert state_store.get_project_revision(project_id) == 2
        state = state_store.get_canonical_state(project_id)
        assert len(state.get("devices", [])) >= 1

    def test_execute_import_rejects_on_occ_conflict(
        self,
        import_orchestrator: ImportOrchestrator,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        project_id = "proj-p3-conflict"
        state_store.set_project_revision(project_id, revision=2)

        content = b"AC1032\x00\x00test"
        record = import_orchestrator.stage_file(content, "test.dwg", principal=principal)

        # Execute with stale expected_revision=1 when real revision is 2
        with pytest.raises(ProjectRevisionChangedError) as exc_info:
            import_orchestrator.execute_import(
                file_id=record.file_id,
                project_id=project_id,
                expected_revision=1,
                principal=principal,
            )
        assert exc_info.value.error_code == "PROJECT_REVISION_CHANGED"
        # State unchanged
        assert state_store.get_project_revision(project_id) == 2

    def test_get_nonexistent_staged_file_raises_error(
        self, import_orchestrator: ImportOrchestrator
    ):
        with pytest.raises(StagedFileNotFoundError) as exc_info:
            import_orchestrator.get_staged_file("imp-nonexistent-uuid")
        assert exc_info.value.error_code == "STAGED_FILE_NOT_FOUND"


# ── AgentRun Orchestrator Integration Tests ─────────────────────────────────


class TestAgentRunImportPipeline:
    def test_agent_run_import_pipeline_in_auto_mode(
        self,
        test_db: Database,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        registry = CapabilityRegistry()
        run_store = AgentRunStore(test_db)
        bus = CommandBus(state_store=state_store)
        agent_orch = AgentRunOrchestrator(
            command_bus=bus,
            capability_registry=registry,
            run_store=run_store,
            environment="development",
        )

        project_id = "proj-agent-import"
        state_store.set_project_revision(project_id, revision=1)

        dxf_content = b"  0\nSECTION\n  2\nENTITIES\n  0\nENDSEC\n  0\nEOF"
        record = default_import_orchestrator.stage_file(
            dxf_content, "floor_plan.dxf", principal=principal
        )

        steps = [
            {
                "step_id": "step-1",
                "capability_id": "import.inspect_file",
                "payload": {"file_id": record.file_id},
            },
            {
                "step_id": "step-2",
                "capability_id": "import.plan_import",
                "payload": {"file_id": record.file_id, "project_id": project_id},
            },
            {
                "step_id": "step-3",
                "capability_id": "import.execute_import",
                "payload": {
                    "file_id": record.file_id,
                    "project_id": project_id,
                    "expected_revision": 1,
                },
            },
        ]

        run = agent_orch.start_run(
            principal=principal,
            project_id=project_id,
            steps=steps,
            approval_mode="AUTO",
        )

        # In AUTO mode with full write scopes, all steps complete
        assert run.status == RunStatus.COMPLETED
        assert len(run.completed_steps) == 3

    def test_agent_run_import_pipeline_in_step_by_step_mode_halts_for_approval(
        self,
        test_db: Database,
        state_store: CommandStateStore,
        principal: AuthenticatedPrincipal,
    ):
        registry = CapabilityRegistry()
        run_store = AgentRunStore(test_db)
        bus = CommandBus(state_store=state_store)
        agent_orch = AgentRunOrchestrator(
            command_bus=bus,
            capability_registry=registry,
            run_store=run_store,
            environment="development",
        )

        project_id = "proj-step-import"
        state_store.set_project_revision(project_id, revision=1)

        dxf_content = b"  0\nSECTION\n  2\nENTITIES\n  0\nENDSEC\n  0\nEOF"
        record = default_import_orchestrator.stage_file(
            dxf_content, "floor.dxf", principal=principal
        )

        steps = [
            {
                "step_id": "step-1",
                "capability_id": "import.inspect_file",
                "payload": {"file_id": record.file_id},
            },
            {
                "step_id": "step-2",
                "capability_id": "import.plan_import",
                "payload": {"file_id": record.file_id, "project_id": project_id},
            },
            {
                "step_id": "step-3",
                "capability_id": "import.execute_import",
                "payload": {
                    "file_id": record.file_id,
                    "project_id": project_id,
                    "expected_revision": 1,
                },
            },
        ]

        run = agent_orch.start_run(
            principal=principal,
            project_id=project_id,
            steps=steps,
            approval_mode="STEP_BY_STEP",
        )

        # Step 3 (import.execute_import) is a mutation, so STEP_BY_STEP halts in WAITING_APPROVAL
        assert run.status == RunStatus.WAITING_APPROVAL
        assert run.current_step == "step-3"
        assert run.pending_approval_id is not None

        # Decide approval to resume and complete
        resumed = agent_orch.decide_approval(
            caller_id=principal.user_id,
            approval_id=run.pending_approval_id,
            decision="APPROVED",
            caller_is_admin=True,
        )

        assert resumed.status == RunStatus.COMPLETED
        assert len(resumed.completed_steps) == 3
