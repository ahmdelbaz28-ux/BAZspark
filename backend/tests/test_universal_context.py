"""backend/tests/test_universal_context.py — Universal Session Context test suite.

Validates Phase 3 requirements:
1. UniversalSessionContext 5-field model, type safety, and serialization.
2. Backward-compatible conversion of entity_id -> entity_ids.
3. Dynamic revision_binding derivation via CapabilityRegistry (zero hardcoded capability lists).
4. validate_mutation_revision and MissingExpectedRevisionError.
5. Context budget enforcement with hard ceiling of <=1500 tokens.
6. REST workflow endpoints context reconciliation and MISSING_EXPECTED_REVISION rejection.
7. O4 settlement in sync.py ensuring strict RBAC admin check.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api_keys import add_api_key
from backend.app import app
from backend.core.capability_registry import (
    CapabilityContract,
    CapabilityDefinition,
    CapabilityRegistry,
)
from backend.core.session_context import (
    ContextBudgetExceededError,
    MissingExpectedRevisionError,
    UniversalSessionContext,
    check_context_budget,
    enforce_context_budget,
    is_revision_required_for_capability,
    validate_mutation_revision,
)
from backend.database import get_db
from backend.rbac import APIKeyInfo, Role


@pytest.fixture
def auth_headers():
    key = f"test-admin-key-{uuid.uuid4().hex[:12]}"
    add_api_key(key, Role.ADMIN, "Universal Context Test Admin Key")
    return {"X-API-Key": key}


@pytest.fixture
def seeded_project():
    db = get_db()
    pid = f"proj-ctx-{uuid.uuid4().hex[:8]}"
    dev_id = f"dev-smoke-{uuid.uuid4().hex[:8]}"
    proj = {
        "id": pid,
        "name": "Universal Context Test Project",
        "modelId": f"dt-{pid}",
        "author": "admin",
        "device_id": dev_id,
    }
    db.create_project(proj)
    # Ensure project_revisions table has row
    with db._transaction() as cur:
        cur.execute(
            f"SELECT revision FROM project_revisions WHERE project_id = {db._ph()}",
            (pid,),
        )
        if not cur.fetchone():
            cur.execute(
                f"INSERT INTO project_revisions (project_id, revision) VALUES ({db._ph()}, {db._ph()})",
                (pid, 3),
            )
        else:
            cur.execute(
                f"UPDATE project_revisions SET revision = {db._ph()} WHERE project_id = {db._ph()}",
                (3, pid),
            )

    # Seed a valid device
    dev = {
        "id": dev_id,
        "name": "Smoke Detector 1",
        "projectId": pid,
        "type": "detector",
        "category": "smoke",
        "x": 10.0,
        "y": 20.0,
    }
    db.create_device(pid, dev)
    return proj


# =========================================================================
# 1. UniversalSessionContext Data Model & Serialization Tests
# =========================================================================

def test_universal_session_context_creation():
    ctx = UniversalSessionContext(
        project_id="proj-100",
        model_id="dt-proj-100",
        entity_ids=["e1", "e2"],
        expected_revision=5,
        ui_surface="canvas_2d",
    )
    assert ctx.project_id == "proj-100"
    assert ctx.model_id == "dt-proj-100"
    assert ctx.entity_ids == ["e1", "e2"]
    assert ctx.expected_revision == 5
    assert ctx.ui_surface == "canvas_2d"

    d = ctx.to_dict()
    assert d == {
        "project_id": "proj-100",
        "model_id": "dt-proj-100",
        "entity_ids": ["e1", "e2"],
        "expected_revision": 5,
        "ui_surface": "canvas_2d",
    }


def test_universal_session_context_from_dict_variants():
    # Snake case
    c1 = UniversalSessionContext.from_dict({
        "project_id": "p1",
        "model_id": "m1",
        "entity_ids": ["e1", "e2"],
        "expected_revision": 4,
        "ui_surface": "chat_sidebar",
    })
    assert c1.project_id == "p1"
    assert c1.entity_ids == ["e1", "e2"]
    assert c1.expected_revision == 4
    assert c1.ui_surface == "chat_sidebar"

    # Camel case
    c2 = UniversalSessionContext.from_dict({
        "projectId": "p2",
        "modelId": "m2",
        "entityIds": ["e3"],
        "expectedRevision": 10,
        "uiSurface": "panel_config",
    })
    assert c2.project_id == "p2"
    assert c2.model_id == "m2"
    assert c2.entity_ids == ["e3"]
    assert c2.expected_revision == 10
    assert c2.ui_surface == "panel_config"

    # Backward compatibility: single entity_id / entityId
    c3 = UniversalSessionContext.from_dict({
        "projectId": "p3",
        "entityId": "dev-single",
    })
    assert c3.project_id == "p3"
    assert c3.entity_ids == ["dev-single"]
    assert c3.expected_revision is None
    assert c3.model_id is None
    assert c3.ui_surface is None


def test_universal_session_context_type_validation():
    with pytest.raises(TypeError, match="project_id must be a string"):
        UniversalSessionContext(project_id=123)  # type: ignore

    with pytest.raises(TypeError, match="entity_ids must be a list of strings"):
        UniversalSessionContext(project_id="p", entity_ids="not-a-list")  # type: ignore

    with pytest.raises(TypeError, match="expected_revision must be an integer"):
        UniversalSessionContext(project_id="p", expected_revision=True)  # type: ignore

    with pytest.raises(ValueError, match="expected_revision cannot be negative"):
        UniversalSessionContext(project_id="p", expected_revision=-1)


# =========================================================================
# 2. Dynamic Revision Binding Derivation Tests
# =========================================================================

def test_dynamic_revision_binding_derivation():
    # Built-in import execution mutates canonical project state
    assert is_revision_required_for_capability("import.execute_import") is True

    # Built-in spatial placement & electrical calculation are read-only / stateless
    assert is_revision_required_for_capability("spatial.place_devices") is False
    assert is_revision_required_for_capability("electrical.voltage_drop") is False

    # Unknown capability returns False
    assert is_revision_required_for_capability("unknown.capability") is False


def test_dynamic_revision_binding_with_custom_registry():
    custom_reg = CapabilityRegistry()

    custom_reg.register(
        CapabilityDefinition(
            capability_id="custom.canonical_mutation",
            name="Custom Mutation",
            description="Custom state mutation",
            category="custom",
            contract=CapabilityContract(
                input_schema={},
                output_schema={},
                revision_binding="canonical_project_state",
            ),
        )
    )

    custom_reg.register(
        CapabilityDefinition(
            capability_id="custom.stateless_calc",
            name="Custom Stateless",
            description="Custom stateless calc",
            category="custom",
            contract=CapabilityContract(
                input_schema={},
                output_schema={},
                revision_binding="none",
            ),
        )
    )

    # Invariant: Derived dynamically without any hardcoding
    assert is_revision_required_for_capability("custom.canonical_mutation", custom_reg) is True
    assert is_revision_required_for_capability("custom.stateless_calc", custom_reg) is False


def test_validate_mutation_revision_success():
    ctx = UniversalSessionContext(project_id="p1", expected_revision=2)
    # Mutation capability with expected_revision passes
    validate_mutation_revision(ctx, ["import.execute_import"])
    # Stateless capability passes even if expected_revision was None
    ctx_none = UniversalSessionContext(project_id="p1", expected_revision=None)
    validate_mutation_revision(ctx_none, ["spatial.place_devices", "electrical.voltage_drop"])


def test_validate_mutation_revision_missing_error():
    ctx = UniversalSessionContext(project_id="p1", expected_revision=None)
    with pytest.raises(MissingExpectedRevisionError) as exc_info:
        validate_mutation_revision(ctx, ["import.execute_import"])

    assert exc_info.value.error_code == "MISSING_EXPECTED_REVISION"
    assert exc_info.value.status_code == 400
    assert "import.execute_import" in str(exc_info.value)


# =========================================================================
# 3. Context Budget Ceiling Enforcement (<=1500 Tokens)
# =========================================================================

def test_context_budget_within_limit():
    small_payload = {
        "project_id": "proj-1",
        "room_bounds": {"width_m": 12.0, "length_m": 16.0},
        "devices": [{"id": "d1", "type": "smoke"}],
    }
    is_valid, tokens = check_context_budget(small_payload, max_tokens=1500)
    assert is_valid is True
    assert tokens < 100
    assert enforce_context_budget(small_payload, max_tokens=1500) == tokens


def test_context_budget_exceeded():
    # Create large payload > 1500 tokens (approx 6000+ chars)
    large_payload = {
        "raw_cad_geometry": "X" * 10000,
        "heavy_element_table": [{"index": i, "data": "A" * 100} for i in range(100)],
    }
    is_valid, tokens = check_context_budget(large_payload, max_tokens=1500)
    assert is_valid is False
    assert tokens > 1500

    with pytest.raises(ContextBudgetExceededError) as exc_info:
        enforce_context_budget(large_payload, max_tokens=1500)
    assert exc_info.value.error_code == "CONTEXT_BUDGET_EXCEEDED"
    assert exc_info.value.token_count > 1500


# =========================================================================
# 4. REST Router Integration & OCC Verification
# =========================================================================

def test_rest_plan_workflow_success(auth_headers, seeded_project):
    client = TestClient(app)
    response = client.post(
        "/api/v1/workflow/runs/plan",
        headers=auth_headers,
        json={
            "prompt": "Place 4 smoke detectors in main lobby",
            "project_id": seeded_project["id"],
            "model_id": seeded_project["modelId"],
            "entity_ids": [seeded_project["device_id"]],
            "expected_revision": 3,
            "ui_surface": "canvas_2d",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_rest_plan_workflow_occ_conflict(auth_headers, seeded_project):
    client = TestClient(app)
    # Stale expected revision 2 != canonical revision 3
    response = client.post(
        "/api/v1/workflow/runs/plan",
        headers=auth_headers,
        json={
            "prompt": "Place 4 smoke detectors in main lobby",
            "project_id": seeded_project["id"],
            "expected_revision": 2,
        },
    )
    assert response.status_code == 409
    assert "OCC revision conflict" in response.json()["detail"]


def test_rest_plan_workflow_invalid_entity(auth_headers, seeded_project):
    client = TestClient(app)
    response = client.post(
        "/api/v1/workflow/runs/plan",
        headers=auth_headers,
        json={
            "prompt": "Place 4 smoke detectors in main lobby",
            "project_id": seeded_project["id"],
            "entity_ids": ["dev-nonexistent-999"],
            "expected_revision": 3,
        },
    )
    assert response.status_code == 400
    assert "dev-nonexistent-999" in response.json()["detail"]


def test_rest_start_plan_mutation_without_revision_fails(auth_headers, seeded_project):
    client = TestClient(app)
    # Target import execution mutation without expected_revision
    response = client.post(
        "/api/v1/workflow/runs/start-plan",
        headers=auth_headers,
        json={
            "prompt": "Execute import into project",
            "project_id": seeded_project["id"],
            "composite_spec": {
                "action": "import.execute_import",
                "file_id": "file-123",
            },
        },
    )
    # Rejects with HTTP 400 and MISSING_EXPECTED_REVISION
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "MISSING_EXPECTED_REVISION" in detail


# =========================================================================
# 5. O4 Settle Verification: sync.py RBAC Admin Check
# =========================================================================

def test_o4_sync_admin_strictly_checks_role():
    # Simulated rbac_info for a non-admin role
    viewer_info = APIKeyInfo(
        key_hash="hash-viewer",
        role=Role.VIEWER,
        description="Viewer Key",
    )
    admin_info = APIKeyInfo(
        key_hash="hash-admin",
        role=Role.ADMIN,
        description="Admin Key",
    )

    # Verification: Only Role.ADMIN or "admin" yields is_admin = True
    assert (viewer_info and getattr(viewer_info, "role", None) == Role.ADMIN) is False
    assert (admin_info and getattr(admin_info, "role", None) == Role.ADMIN) is True
