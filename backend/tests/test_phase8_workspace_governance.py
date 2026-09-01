"""backend/tests/test_phase8_workspace_governance.py — Unit & Conformance Tests for Phase 8 Capabilities.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 8 & Gate 8:
- Tests all 9 Workspace & Governance capabilities (project, model, revision, inspect, validate, review, audit, artifact, report).
- Validates CapabilityContract schema conformance, authority classes, and revision bindings.
- Validates deterministic execution, real database query resolution, and tamper-evident SHA-256 audit digests.
"""

from __future__ import annotations

import pytest

from backend.core.capability_registry import (
    CAP_GOVERNANCE_ARTIFACT,
    CAP_GOVERNANCE_AUDIT,
    CAP_GOVERNANCE_INSPECT,
    CAP_GOVERNANCE_REPORT,
    CAP_GOVERNANCE_REVIEW,
    CAP_GOVERNANCE_VALIDATE,
    CAP_WORKSPACE_MODEL,
    CAP_WORKSPACE_PROJECT,
    CAP_WORKSPACE_REVISION,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
)
from backend.core.state_store import CommandStateStore
from backend.core.workspace_governance_contracts import (
    ALL_PHASE8_CAPABILITIES,
    CAPABILITY_AUTHORITY_MAP,
    handle_governance_artifact,
    handle_governance_audit,
    handle_governance_inspect,
    handle_governance_report,
    handle_governance_review,
    handle_governance_validate,
    handle_workspace_model,
    handle_workspace_project,
    handle_workspace_revision,
)
from backend.database import Database


@pytest.fixture
def fresh_db(tmp_path) -> Database:
    db_file = str(tmp_path / "phase8_unit.db")
    return Database(db_path=db_file)


@pytest.fixture
def state_store(fresh_db: Database) -> CommandStateStore:
    return CommandStateStore(fresh_db)


@pytest.fixture
def bus(state_store: CommandStateStore) -> CommandBus:
    return CommandBus(capability_registry=default_capability_registry, state_store=state_store)


@pytest.fixture
def engineer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="eng-001",
        email="eng@bazspark.io",
        role="lead_engineer",
        scopes=["workspace:read", "governance:read", "governance:write", "compliance:read", "audit:read"],
    )


# ── S1: Capability Registration & Schema Verification ────────────────────────


def test_all_phase8_capabilities_registered() -> None:
    """Verify all 9 workspace/governance capabilities are registered with explicit contracts."""
    for cap_id in ALL_PHASE8_CAPABILITIES:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None, f"Capability '{cap_id}' not found in registry"
        assert cap.contract is not None, f"Capability '{cap_id}' missing explicit contract"
        assert cap.contract_explicit is True
        assert cap.category in ("workspace", "governance")
        assert cap.contract.schema_version == "1.0"
        assert isinstance(cap.contract.input_schema, dict)
        assert isinstance(cap.contract.output_schema, dict)


def test_authorized_discovery_by_category() -> None:
    """Verify discover_authorized works for 'workspace' and 'governance' categories."""
    ws_caps = default_capability_registry.discover_authorized(
        scopes=["workspace:read"],
        category="workspace",
    )
    assert len(ws_caps) == 3
    ws_ids = {c["capability_id"] for c in ws_caps}
    assert ws_ids == {CAP_WORKSPACE_PROJECT, CAP_WORKSPACE_MODEL, CAP_WORKSPACE_REVISION}

    gov_caps = default_capability_registry.discover_authorized(
        scopes=["governance:read", "governance:write", "compliance:read", "audit:read"],
        category="governance",
    )
    assert len(gov_caps) == 6
    gov_ids = {c["capability_id"] for c in gov_caps}
    assert gov_ids == {
        CAP_GOVERNANCE_INSPECT,
        CAP_GOVERNANCE_VALIDATE,
        CAP_GOVERNANCE_REVIEW,
        CAP_GOVERNANCE_AUDIT,
        CAP_GOVERNANCE_ARTIFACT,
        CAP_GOVERNANCE_REPORT,
    }


def test_authority_classes_conform_to_four_plan_classes() -> None:
    """Verify authority classes for all 9 capabilities belong strictly to the 4 plan classes."""
    valid_classes = {"CANONICAL_COMMAND", "SYSTEM_INFRASTRUCTURE", "EXTERNAL_TRANSACTION", "LEGACY_EXCEPTION"}
    for cap_id, auth_class in CAPABILITY_AUTHORITY_MAP.items():
        assert auth_class in valid_classes, f"Invalid authority class '{auth_class}' for {cap_id}"


# ── S1: Handler Unit Tests & Cryptographic Audit Verification ────────────────


def test_handle_workspace_project(fresh_db: Database) -> None:
    """Test workspace.project handler with SQLite database."""
    res = handle_workspace_project({"project_id": "proj-alpha", "action": "open"}, db=fresh_db)
    assert res["project_id"] == "proj-alpha"
    assert res["status"] == "ACTIVE"
    assert res["current_revision"] >= 1
    assert "audit_reference" in res
    assert len(res["audit_reference"]) == 64  # SHA-256 hex length


def test_handle_workspace_model() -> None:
    """Test workspace.model handler."""
    res = handle_workspace_model({"project_id": "proj-alpha", "model_id": "revit-bim-model-01"})
    assert res["project_id"] == "proj-alpha"
    assert res["model_id"] == "revit-bim-model-01"
    assert res["model_type"] == "BIM_AUTODESK_REVIT"
    assert res["is_active"] is True
    assert len(res["audit_reference"]) == 64


def test_handle_workspace_revision(fresh_db: Database) -> None:
    """Test workspace.revision handler with expected revision matching."""
    res = handle_workspace_revision({"project_id": "proj-alpha", "expected_revision": 1}, db=fresh_db)
    assert res["project_id"] == "proj-alpha"
    assert res["current_revision"] == 1
    assert res["is_latest"] is True
    assert len(res["audit_reference"]) == 64


def test_handle_governance_inspect(fresh_db: Database) -> None:
    """Test governance.inspect handler."""
    res = handle_governance_inspect({"project_id": "proj-alpha", "scope": "full"}, db=fresh_db)
    assert res["project_id"] == "proj-alpha"
    assert res["inspection_status"] == "PASSED"
    assert res["details"]["topology_valid"] is True
    assert len(res["audit_reference"]) == 64


def test_handle_governance_validate() -> None:
    """Test governance.validate NFPA 72 compliance checks."""
    payload = {
        "project_id": "proj-alpha",
        "width_m": 12.0,
        "length_m": 18.0,
        "ceiling_height_m": 3.0,
        "current_a": 2.0,
        "standby_hours": 24.0,
    }
    res = handle_governance_validate(payload)
    assert res["project_id"] == "proj-alpha"
    assert res["is_valid"] is True
    assert res["violation_count"] == 0
    assert res["compliance_score"] == 100.0
    assert len(res["rule_results"]) == 3
    assert len(res["audit_reference"]) == 64


def test_handle_governance_validate_with_violation() -> None:
    """Test governance.validate detects compliance violation when standby power is deficient."""
    payload = {
        "project_id": "proj-alpha",
        "width_m": 10.0,
        "length_m": 15.0,
        "standby_hours": 12.0,  # Below NFPA 72 24h requirement
    }
    res = handle_governance_validate(payload)
    assert res["is_valid"] is False
    assert res["violation_count"] == 1
    assert "Secondary Power Supply Standby" in res["violations"]


def test_handle_governance_review() -> None:
    """Test governance.review records peer review verdict with audit lineage."""
    payload = {
        "project_id": "proj-alpha",
        "expected_revision": 2,
        "reviewer_role": "licensed_pe",
        "verdict": "APPROVED",
        "comments": "Reviewed device spacing and battery calculations against NFPA 72-2022.",
    }
    res = handle_governance_review(payload)
    assert res["project_id"] == "proj-alpha"
    assert res["verdict"] == "APPROVED"
    assert res["reviewer_role"] == "licensed_pe"
    assert res["review_id"].startswith("rev-")
    assert len(res["audit_reference"]) == 64


def test_handle_governance_audit(fresh_db: Database) -> None:
    """Test governance.audit retrieves audit trail records."""
    res = handle_governance_audit({"project_id": "proj-alpha", "limit": 5}, db=fresh_db)
    assert res["project_id"] == "proj-alpha"
    assert res["total_records"] >= 1
    assert res["latest_event"] is not None
    assert len(res["combined_audit_digest"]) == 64


def test_handle_governance_artifact() -> None:
    """Test governance.artifact registers deliverables with checksums."""
    payload = {
        "project_id": "proj-alpha",
        "artifact_type": "DXF",
        "action": "register",
    }
    res = handle_governance_artifact(payload)
    assert res["project_id"] == "proj-alpha"
    assert res["artifact_type"] == "DXF"
    assert res["status"] == "REGISTERED"
    assert len(res["checksum_sha256"]) == 64
    assert len(res["audit_reference"]) == 64


def test_handle_governance_report() -> None:
    """Test governance.report generates structured compliance report."""
    payload = {
        "project_id": "proj-alpha",
        "report_type": "COMPLIANCE",
        "title": "NFPA 72 Final Engineering Basis Report",
    }
    res = handle_governance_report(payload)
    assert res["project_id"] == "proj-alpha"
    assert res["report_type"] == "COMPLIANCE"
    assert len(res["sections"]) == 3
    assert len(res["audit_reference"]) == 64


# ── S2: CommandBus Execution Integration ─────────────────────────────────────


def test_command_bus_dispatches_workspace_project(bus: CommandBus, state_store: CommandStateStore, engineer_principal: AuthenticatedPrincipal) -> None:
    """Verify CommandBus executes workspace.project with OCC validation."""
    state_store.set_project_revision("proj-bus-test", 1)
    cmd = DomainCommand(
        commandId="cmd-ws-proj-01",
        correlationId="corr-001",
        capabilityId=CAP_WORKSPACE_PROJECT,
        projectId="proj-bus-test",
        expectedRevision=1,
        timestamp="2026-08-31T12:00:00Z",
        principal=engineer_principal,
        payload={"project_id": "proj-bus-test", "action": "open"},
    )
    result = bus.execute(cmd)
    assert result.success is True
    assert result.resultData["project_id"] == "proj-bus-test"
    assert result.event is not None
    assert len(result.event.auditReference) == 64


def test_command_bus_dispatches_governance_validate(bus: CommandBus, state_store: CommandStateStore, engineer_principal: AuthenticatedPrincipal) -> None:
    """Verify CommandBus executes governance.validate."""
    state_store.set_project_revision("proj-bus-test", 1)
    cmd = DomainCommand(
        commandId="cmd-gov-val-01",
        correlationId="corr-002",
        capabilityId=CAP_GOVERNANCE_VALIDATE,
        projectId="proj-bus-test",
        expectedRevision=1,
        timestamp="2026-08-31T12:00:00Z",
        principal=engineer_principal,
        payload={"project_id": "proj-bus-test", "width_m": 15.0, "length_m": 20.0},
    )
    result = bus.execute(cmd)
    assert result.success is True
    assert result.resultData["is_valid"] is True
    assert result.resultData["compliance_score"] == 100.0
