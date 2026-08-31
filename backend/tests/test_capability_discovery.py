"""backend/tests/test_capability_discovery.py — Gate 2 Authorized Discovery Test Suite.

Verifies:
1. RBAC authorization matrix for capability discovery (AND rule, fail-closed, admin bypass).
2. Category and execution_channel filter enforcement and fail-closed validation.
3. Lean schema payload format (all 15 keys present, strict exclusion of handler and raw state).
4. Schema versioning ("major.minor" pattern validation and 1.0 baseline).
5. O-C1 resolution: export.execute_export requires write scope ("export:write").
6. Read-only HTTP surface (/api/v1/capabilities) over TestClient.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.capability_registry import (
    CAP_COMPLIANCE_VERIFY_SPACING,
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_EXPORT_EXECUTE_EXPORT,
    CAP_EXPORT_PLAN_EXPORT,
    CAP_EXPORT_VALIDATE_ARTIFACT,
    CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    CAP_IMPORT_EXECUTE_IMPORT,
    CAP_IMPORT_INSPECT_FILE,
    CAP_IMPORT_PLAN_IMPORT,
    CAP_SPATIAL_PLACE_DEVICES,
    CapabilityContract,
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)

LEAN_PAYLOAD_REQUIRED_KEYS = {
    "capability_id",
    "name",
    "description",
    "category",
    "schema_version",
    "input_schema",
    "output_schema",
    "revision_binding",
    "execution_mode",
    "execution_channel",
    "mutation_type",
    "risk",
    "scopes",
    "approval_policy",
    "ui_handoff",
}


# ─── 1. RBAC × Discovery Matrix (D-2a) ──────────────────────────────────────


def test_discovery_full_scopes_returns_all_11_capabilities() -> None:
    """Principal with wildcard scope receives all canonical capabilities."""
    caps = default_capability_registry.discover_authorized(scopes=["*"])
    assert len(caps) >= 11
    ids = {c["capability_id"] for c in caps}
    assert {
        CAP_SPATIAL_PLACE_DEVICES,
        CAP_COMPLIANCE_VERIFY_SPACING,
        CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
        CAP_ELECTRICAL_CALCULATE_BATTERY,
        CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
        CAP_IMPORT_INSPECT_FILE,
        CAP_IMPORT_PLAN_IMPORT,
        CAP_IMPORT_EXECUTE_IMPORT,
        CAP_EXPORT_PLAN_EXPORT,
        CAP_EXPORT_EXECUTE_EXPORT,
        CAP_EXPORT_VALIDATE_ARTIFACT,
    }.issubset(ids)


def test_discovery_empty_scopes_returns_empty_list() -> None:
    """Non-admin principal with zero scopes receives a valid, empty list (fail-closed, not an error)."""
    caps = default_capability_registry.discover_authorized(scopes=[])
    assert isinstance(caps, list)
    assert len(caps) == 0

    caps_none = default_capability_registry.discover_authorized(scopes=None, is_admin=False)
    assert isinstance(caps_none, list)
    assert len(caps_none) == 0


def test_discovery_partial_scope_spatial_write_only() -> None:
    """Principal with only 'spatial:write' discovers only spatial.place_devices."""
    caps = default_capability_registry.discover_authorized(scopes=["spatial:write"])
    assert len(caps) == 1
    assert caps[0]["capability_id"] == CAP_SPATIAL_PLACE_DEVICES
    assert caps[0]["category"] == "spatial"


def test_discovery_partial_scope_compliance_read_only() -> None:
    """Principal with only 'compliance:read' discovers only compliance.verify_detector_spacing."""
    caps = default_capability_registry.discover_authorized(scopes=["compliance:read"])
    assert len(caps) == 1
    assert caps[0]["capability_id"] == CAP_COMPLIANCE_VERIFY_SPACING
    assert caps[0]["category"] == "compliance"


def test_discovery_and_rule_multi_scope_requirement() -> None:
    """AND rule: Principal possessing only 1 of 2 required scopes cannot discover capability."""
    # import.inspect_file and import.plan_import require both "import:read" AND "project:read"
    caps_partial = default_capability_registry.discover_authorized(scopes=["import:read"])
    assert len(caps_partial) == 0

    caps_other_partial = default_capability_registry.discover_authorized(scopes=["project:read"])
    # export.validate_artifact requires only "export:read", so with only project:read it's 0
    assert len(caps_other_partial) == 0

    # With both scopes, import read capabilities and export read capabilities become available
    caps_full = default_capability_registry.discover_authorized(scopes=["import:read", "project:read"])
    assert len(caps_full) == 2
    discovered_ids = {c["capability_id"] for c in caps_full}
    assert discovered_ids == {CAP_IMPORT_INSPECT_FILE, CAP_IMPORT_PLAN_IMPORT}


def test_discovery_admin_bypass() -> None:
    """is_admin=True or 'admin' in scopes discovers all capabilities regardless of explicit scopes."""
    caps_admin_flag = default_capability_registry.discover_authorized(scopes=[], is_admin=True)
    assert len(caps_admin_flag) >= 11

    caps_admin_scope = default_capability_registry.discover_authorized(scopes=["admin"])
    assert len(caps_admin_scope) >= 11


def test_discovery_category_filter_with_valid_scopes() -> None:
    """Filtering by category returns only authorized capabilities in that category."""
    caps = default_capability_registry.discover_authorized(
        scopes=["electrical:write"], category="electrical"
    )
    assert len(caps) == 2
    assert {c["capability_id"] for c in caps} == {
        CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
        CAP_ELECTRICAL_CALCULATE_BATTERY,
    }

    # Category filter when user lacks scopes returns empty
    caps_no_scope = default_capability_registry.discover_authorized(
        scopes=["spatial:write"], category="electrical"
    )
    assert len(caps_no_scope) == 0


def test_discovery_execution_channel_filter() -> None:
    """Filtering by execution_channel returns matching capabilities."""
    sync_caps = default_capability_registry.discover_authorized(
        scopes=["*"], execution_channel="sync"
    )
    assert len(sync_caps) >= 11

    async_caps = default_capability_registry.discover_authorized(
        scopes=["*"], execution_channel="async"
    )
    assert len(async_caps) == 0


def test_discovery_invalid_category_fail_closed() -> None:
    """Unknown category raises explicit ValueError (fail-closed, not silent empty list)."""
    with pytest.raises(ValueError, match="Invalid category filter 'unknown_domain'"):
        default_capability_registry.discover_authorized(scopes=["*"], category="unknown_domain")


def test_discovery_invalid_execution_channel_fail_closed() -> None:
    """Unknown execution_channel raises explicit ValueError (fail-closed)."""
    with pytest.raises(ValueError, match="Invalid execution_channel filter 'grpc'"):
        default_capability_registry.discover_authorized(scopes=["*"], execution_channel="grpc")


# ─── 2. Lean Payload Integrity & Security (D-2a) ───────────────────────────


def test_discovery_lean_payload_schema_completeness() -> None:
    """Every discovered capability dictionary must contain all 15 required keys."""
    caps = default_capability_registry.discover_authorized(scopes=["*"])
    assert len(caps) >= 11
    for cap in caps:
        for key in LEAN_PAYLOAD_REQUIRED_KEYS:
            assert key in cap, f"Missing key '{key}' in capability payload '{cap.get('capability_id')}'"
        assert isinstance(cap["capability_id"], str)
        assert isinstance(cap["name"], str)
        assert isinstance(cap["description"], str)
        assert isinstance(cap["category"], str)
        assert isinstance(cap["schema_version"], str)
        assert isinstance(cap["input_schema"], dict)
        assert isinstance(cap["output_schema"], dict)
        assert isinstance(cap["revision_binding"], str)
        assert isinstance(cap["execution_mode"], str)
        assert isinstance(cap["execution_channel"], str)
        assert isinstance(cap["mutation_type"], str)
        assert isinstance(cap["risk"], str)
        assert isinstance(cap["scopes"], list)
        assert isinstance(cap["approval_policy"], str)
        assert isinstance(cap["ui_handoff"], dict)


def test_discovery_payload_never_leaks_handler_or_state() -> None:
    """Discovery payload MUST NEVER contain 'handler', callable, or raw CAD/project store."""
    caps = default_capability_registry.discover_authorized(scopes=["*"])
    for cap in caps:
        assert "handler" not in cap, "Security violation: 'handler' callable leaked in discovery payload!"
        assert "_capabilities" not in cap
        assert "raw_state" not in cap
        assert "database" not in cap
        for val in cap.values():
            assert not callable(val), f"Callable object found in discovery payload: {val}"


# ─── 3. Schema Versioning (D-2b) ───────────────────────────────────────────


def test_all_11_capabilities_declare_schema_version_1_0() -> None:
    """All canonical capabilities declare schema_version='1.0'."""
    caps = default_capability_registry.discover_authorized(scopes=["*"])
    assert len(caps) >= 11
    for cap in caps:
        assert cap["schema_version"] == "1.0", f"'{cap['capability_id']}' schema_version is '{cap['schema_version']}'"


def test_register_schema_version_regex_validation() -> None:
    """CapabilityRegistry.register() strictly enforces numeric major.minor regex."""
    registry = CapabilityRegistry()

    invalid_versions = [
        "1",
        "v1.0",
        "1.0.0",
        "-1.0",
        "1.-1",
        "1.0-beta",
        "",
        "abc",
        1.0,  # float instead of str
    ]

    for inv_ver in invalid_versions:
        contract = CapabilityContract(
            schema_version=inv_ver,  # type: ignore[arg-type]
            input_schema={},
            output_schema={},
            revision_binding="none",
        )
        cap_def = CapabilityDefinition(
            capability_id=f"test.version_{inv_ver}",
            name="Version Test",
            description="Testing invalid version rejection",
            category="spatial",
            contract=contract,
        )
        with pytest.raises(ValueError, match="Invalid schema_version"):
            registry.register(cap_def)


def test_register_accepts_valid_semver_minor_increments() -> None:
    """Valid major.minor formats (e.g. '1.1', '2.0', '10.5') are successfully registered."""
    registry = CapabilityRegistry()
    for valid_ver in ["1.0", "1.1", "2.0", "10.15"]:
        contract = CapabilityContract(
            schema_version=valid_ver,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            revision_binding="none",
        )
        cap_def = CapabilityDefinition(
            capability_id=f"test.valid_ver_{valid_ver.replace('.', '_')}",
            name="Valid Version Cap",
            description="Testing valid version acceptance",
            category="spatial",
            contract=contract,
        )
        registry.register(cap_def)
        registered = registry.get(cap_def.capability_id)
        assert registered is not None
        assert registered.contract is not None
        assert registered.contract.schema_version == valid_ver


# ─── 4. O-C1 Resolution: export.execute_export (D-2d) ──────────────────────


def test_export_execute_export_requires_write_scope_oc1() -> None:
    """D-2d (O-C1 Resolution): export.execute_export requires 'export:write' and 'project:read'."""
    export_cap = default_capability_registry.get(CAP_EXPORT_EXECUTE_EXPORT)
    assert export_cap is not None
    assert export_cap.contract is not None
    assert "export:write" in export_cap.contract.scopes
    assert "project:read" in export_cap.contract.scopes
    assert export_cap.contract.mutation_type == "state_mutation"
    assert export_cap.contract.revision_binding == "canonical_project_state"

    # Principal with read-only scopes ("export:read", "project:read") CANNOT discover export.execute_export
    read_only_caps = default_capability_registry.discover_authorized(
        scopes=["export:read", "project:read"]
    )
    read_only_ids = {c["capability_id"] for c in read_only_caps}
    assert CAP_EXPORT_PLAN_EXPORT in read_only_ids
    assert CAP_EXPORT_VALIDATE_ARTIFACT in read_only_ids
    assert CAP_EXPORT_EXECUTE_EXPORT not in read_only_ids

    # Principal with write scope ("export:write", "project:read") CAN discover export.execute_export
    write_caps = default_capability_registry.discover_authorized(
        scopes=["export:write", "project:read"]
    )
    write_ids = {c["capability_id"] for c in write_caps}
    assert CAP_EXPORT_EXECUTE_EXPORT in write_ids


def test_export_execute_export_execution_blocked_without_write_scope() -> None:
    """D-2d (O-C1 Resolution): CommandBus strictly blocks execution of export.execute_export without 'export:write'."""
    from backend.core.command_bus import AuthenticatedPrincipal, DomainCommand, default_command_bus
    from backend.database import get_db

    db = get_db()
    proj = db.create_project({"name": "Export OCC Proj", "author": "alice_export"})
    p_id = proj["id"]
    current_rev = proj.get("revision", 1)

    read_only_principal = AuthenticatedPrincipal(
        user_id="read_user",
        email="read@bazspark.com",
        role="viewer",
        scopes=["export:read", "project:read"],
    )

    cmd = DomainCommand(
        commandId="cmd-test-export-oc1",
        correlationId="corr-test-export-oc1",
        capabilityId=CAP_EXPORT_EXECUTE_EXPORT,
        projectId=p_id,
        expectedRevision=current_rev,
        timestamp="2026-08-30T12:00:00Z",
        payload={"project_id": p_id, "expected_revision": current_rev, "target_format": "json"},
        principal=read_only_principal,
    )

    result = default_command_bus.execute(cmd)
    assert result.success is False
    assert result.errorCode == "UNAUTHORIZED_SCOPE"
    assert "export:write" in (result.errorMessage or "")


# ─── 5. Read-Only HTTP Surface E2E (D-2c) ───────────────────────────────────

from backend.api_keys import add_api_key
from backend.rbac import Role


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def viewer_api_key() -> str:
    key = "test-viewer-key-abc1234567890"
    add_api_key(key, Role.VIEWER, "Test Viewer Key")
    return key


@pytest.fixture
def admin_api_key() -> str:
    key = "test-admin-key-xyz1234567890"
    add_api_key(key, Role.ADMIN, "Test Admin Key")
    return key


def test_http_discovery_unauthenticated_request_rejected(client: TestClient) -> None:
    """Unauthenticated GET /api/v1/capabilities returns 401 from existing ApiKeyMiddleware."""
    res = client.get("/api/v1/capabilities", headers={"X-API-Key": "invalid-unauthorized-key"})
    assert res.status_code == 401
    data = res.json()
    assert data.get("success") is False or "detail" in data


def test_http_discovery_viewer_role_read_only(client: TestClient, viewer_api_key: str) -> None:
    """Viewer role receives only read-permitted capabilities via HTTP."""
    res = client.get(
        "/api/v1/capabilities",
        headers={"X-API-Key": viewer_api_key},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "capabilities" in data
    cap_ids = {c["capability_id"] for c in data["capabilities"]}
    # Viewer must not have access to state-mutating or write capabilities
    assert CAP_SPATIAL_PLACE_DEVICES not in cap_ids
    assert CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP not in cap_ids
    assert CAP_IMPORT_EXECUTE_IMPORT not in cap_ids
    assert CAP_EXPORT_EXECUTE_EXPORT not in cap_ids


def test_http_discovery_admin_role_receives_all_11(client: TestClient, admin_api_key: str) -> None:
    """Admin role receives all capabilities via HTTP."""
    res = client.get(
        "/api/v1/capabilities",
        headers={"X-API-Key": admin_api_key},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["count"] >= 11
    assert len(data["capabilities"]) >= 11


def test_http_discovery_category_filter_via_query_param(
    client: TestClient, admin_api_key: str
) -> None:
    """Category filter query param works correctly over HTTP."""
    res = client.get(
        "/api/v1/capabilities?category=electrical",
        headers={"X-API-Key": admin_api_key},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    assert all(c["category"] == "electrical" for c in data["capabilities"])


def test_http_discovery_invalid_category_returns_400_fail_closed(
    client: TestClient, admin_api_key: str
) -> None:
    """Invalid category query param returns 400 Bad Request (fail-closed)."""
    res = client.get(
        "/api/v1/capabilities?category=invalid_xyz",
        headers={"X-API-Key": admin_api_key},
    )
    assert res.status_code == 400
    assert "Invalid category filter" in res.json().get("detail", "")


def test_http_discovery_invalid_execution_channel_returns_400_fail_closed(
    client: TestClient, admin_api_key: str
) -> None:
    """Invalid execution_channel query param returns 400 Bad Request (fail-closed)."""
    res = client.get(
        "/api/v1/capabilities?execution_channel=grpc",
        headers={"X-API-Key": admin_api_key},
    )
    assert res.status_code == 400
    assert "Invalid execution_channel filter" in res.json().get("detail", "")


def test_http_discovery_zero_state_mutation(client: TestClient, admin_api_key: str) -> None:
    """Multiple discovery invocations produce zero state mutation side effects."""
    res1 = client.get("/api/v1/capabilities", headers={"X-API-Key": admin_api_key})
    res2 = client.get("/api/v1/capabilities", headers={"X-API-Key": admin_api_key})
    assert res1.status_code == 200 and res2.status_code == 200
    assert res1.json() == res2.json()
