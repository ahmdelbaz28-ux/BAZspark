"""
test_project_rbac_isolation.py — Project RBAC and Tenant Authorization Tests (Phase 8 Gate 5).

Verifies:
1. Endpoint permission enforcement on project endpoints (VIEWER, ENGINEER, ADMIN).
2. Role checking via require_permission dependency.
3. Access denial for unprivileged roles (e.g. VIEWER attempting PROJECT_CREATE/DELETE).
4. Safe isolation of project access paths:
   - Non-existent or foreign project lookup strictly returns None / raises HTTP 404.
   - Principal project scoping & isolation across distinct project IDs.
   - Cascading boundary isolation (deletion scopes strictly to project's children).
5. Real Endpoint Tenant Authorization Boundary:
   - Tenant A reading own Project A -> ALLOWED (HTTP 200).
   - Tenant A reading Project B owned by Tenant B -> DENIED (HTTP 404).
   - Tenant B reading own Project B -> ALLOWED (HTTP 200).
   - Tenant A updating Project B -> DENIED (HTTP 404).
   - Tenant A deleting Project B -> DENIED (HTTP 404).
   - Admin cross-tenant oversight -> ALLOWED (HTTP 200).
   - Cross-project entity injection into workflow execution -> DENIED (HTTP 400).
"""

import asyncio
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from backend.auth import require_permission
from backend.rbac import Permission, Role, has_permission, ROLE_PERMISSIONS
from backend.database import Database, get_db
from backend.core.state_store import CommandStateStore
from backend.models import CreateProjectInput, UpdateProjectInput
from backend.routers.projects import create_project, get_project, list_projects, update_project, delete_project
from backend.routers.workflow import plan_autonomous_workflow, PlanWorkflowRequest


class TestProjectRBACAuthorization:
    """RBAC validation for project lifecycle and access boundaries."""

    def test_viewer_cannot_create_project(self) -> None:
        """VIEWER role lacks PROJECT_CREATE permission."""
        assert not has_permission(Role.VIEWER, Permission.PROJECT_CREATE)

    def test_viewer_cannot_delete_project(self) -> None:
        """VIEWER role lacks PROJECT_DELETE permission."""
        assert not has_permission(Role.VIEWER, Permission.PROJECT_DELETE)

    def test_viewer_cannot_update_project(self) -> None:
        """VIEWER role lacks PROJECT_UPDATE permission."""
        assert not has_permission(Role.VIEWER, Permission.PROJECT_UPDATE)

    def test_engineer_has_project_read_and_create(self) -> None:
        """ENGINEER role has PROJECT_READ and PROJECT_CREATE permissions."""
        assert has_permission(Role.ENGINEER, Permission.PROJECT_READ)
        assert has_permission(Role.ENGINEER, Permission.PROJECT_CREATE)

    def test_admin_has_full_project_permissions(self) -> None:
        """ADMIN role has all project permissions."""
        assert has_permission(Role.ADMIN, Permission.PROJECT_READ)
        assert has_permission(Role.ADMIN, Permission.PROJECT_CREATE)
        assert has_permission(Role.ADMIN, Permission.PROJECT_UPDATE)
        assert has_permission(Role.ADMIN, Permission.PROJECT_DELETE)

    def test_require_permission_blocks_unauthorized_role(self) -> None:
        """require_permission dependency raises HTTP 403 when role lacks required permission."""
        checker = require_permission(Permission.PROJECT_CREATE)
        mock_req = Mock()
        mock_req.state.fireai_role = Role.VIEWER
        mock_req.scope = {}
        with pytest.raises(HTTPException) as exc_info:
            checker(mock_req)
        assert exc_info.value.status_code == 403
        assert "Permission denied" in str(exc_info.value.detail)

    def test_require_permission_allows_authorized_role(self) -> None:
        """require_permission dependency succeeds when role possesses required permission."""
        checker = require_permission(Permission.PROJECT_CREATE)
        mock_req = Mock()
        mock_req.state.fireai_role = Role.ENGINEER
        mock_req.scope = {}
        role = checker(mock_req)
        assert role == Role.ENGINEER


class TestProjectResolutionAndTenantIsolation:
    """Project resolution boundary and multi-tenant data isolation tests."""

    @pytest.fixture
    def isolated_db(self):
        """Create an isolated in-memory database."""
        db = Database(":memory:")
        yield db
        db.close()

    def test_foreign_project_lookup_returns_none(self, isolated_db: Database) -> None:
        """Querying a foreign / non-existent project ID returns None without data leakage."""
        project = isolated_db.get_project("foreign-tenant-project-uuid-9999")
        assert project is None

    def test_tenant_project_isolation(self, isolated_db: Database) -> None:
        """Projects created under distinct tenant/author scopes remain strictly isolated."""
        # Tenant A creates Project A
        proj_a = isolated_db.create_project({
            "id": "tenant-a-project-001",
            "name": "Facility Alpha",
            "description": "Tenant A Facility",
            "author": "principal-tenant-a@fireai.internal",
        })
        assert proj_a["id"] == "tenant-a-project-001"
        assert proj_a["author"] == "principal-tenant-a@fireai.internal"

        # Tenant B creates Project B
        proj_b = isolated_db.create_project({
            "id": "tenant-b-project-002",
            "name": "Facility Beta",
            "description": "Tenant B Facility",
            "author": "principal-tenant-b@fireai.internal",
        })
        assert proj_b["id"] == "tenant-b-project-002"
        assert proj_b["author"] == "principal-tenant-b@fireai.internal"

        # Fetch Project A — verify Tenant B metadata cannot be accessed via Project A
        fetched_a = isolated_db.get_project("tenant-a-project-001")
        assert fetched_a is not None
        assert fetched_a["name"] == "Facility Alpha"
        assert fetched_a["author"] == "principal-tenant-a@fireai.internal"
        assert fetched_a["id"] != proj_b["id"]

        # Verify foreign project ID query does not return Tenant A or Tenant B data
        unauthorized_lookup = isolated_db.get_project("tenant-c-project-003")
        assert unauthorized_lookup is None

    def test_project_deletion_cascades_strictly_to_own_scope(self, isolated_db: Database) -> None:
        """Deleting Project A removes its devices without touching Project B devices."""
        isolated_db.create_project({"id": "proj-iso-1", "name": "Project 1", "author": "User 1"})
        isolated_db.create_project({"id": "proj-iso-2", "name": "Project 2", "author": "User 2"})

        # Add device to Project 1 and Project 2 (scoped by project_id)
        isolated_db.create_device("proj-iso-1", {
            "id": "dev-p1-01",
            "name": "Detector 1",
            "type": "smoke_detector",
            "zone": "Z1",
            "status": "active",
        })
        isolated_db.create_device("proj-iso-2", {
            "id": "dev-p2-01",
            "name": "Detector 2",
            "type": "heat_detector",
            "zone": "Z2",
            "status": "active",
        })

        # Verify device counts
        p1 = isolated_db.get_project("proj-iso-1")
        p2 = isolated_db.get_project("proj-iso-2")
        assert p1["deviceCount"] == 1
        assert p2["deviceCount"] == 1

        # Delete Project 1
        deleted = isolated_db.delete_project("proj-iso-1")
        assert deleted is True

        # Project 1 and its device are gone
        assert isolated_db.get_project("proj-iso-1") is None
        assert isolated_db.get_device("proj-iso-1", "dev-p1-01") is None

        # Cross-project query cannot fetch Project 2's device under Project 1 ID
        assert isolated_db.get_device("proj-iso-1", "dev-p2-01") is None

        # Project 2 and its device remain intact
        p2_after = isolated_db.get_project("proj-iso-2")
        assert p2_after is not None
        assert p2_after["deviceCount"] == 1
        dev_p2 = isolated_db.get_device("proj-iso-2", "dev-p2-01")
        assert dev_p2 is not None
        assert dev_p2["projectId"] == "proj-iso-2"


class TestEndpointTenantAuthorizationBoundary:
    """Real HTTP endpoint tenant isolation and resource-scope verification tests."""

    @pytest.fixture(autouse=True)
    def setup_projects(self):
        """Seed tenant A and tenant B projects into database."""
        db = get_db()
        db.create_project({
            "id": "endpoint-proj-tenant-a",
            "name": "Tenant A Datacenter",
            "author": "principal:tenant-a",
            "description": "Critical infrastructure",
        })
        db.create_project({
            "id": "endpoint-proj-tenant-b",
            "name": "Tenant B Complex",
            "author": "principal:tenant-b",
            "description": "Commercial space",
        })
        yield
        try:
            db.delete_project("endpoint-proj-tenant-a")
            db.delete_project("endpoint-proj-tenant-b")
        except Exception:
            pass

    def _create_mock_request(self, principal: str, role: Role) -> Request:
        """Create a real starlette Request instance with stamped auth principal and role."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "client": ("127.0.0.1", 8000),
            "app": None,
            "fireai_principal": principal,
            "fireai_role": role,
        }
        req = Request(scope)
        req.state.fireai_principal = principal
        req.state.fireai_role = role
        return req

    @pytest.mark.asyncio
    async def test_tenant_a_reads_own_project_allowed(self) -> None:
        """Tenant A can successfully read Project A."""
        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        res = await get_project(req, "endpoint-proj-tenant-a")
        assert res["success"] is True
        assert res["data"]["name"] == "Tenant A Datacenter"

    @pytest.mark.asyncio
    async def test_tenant_a_reads_tenant_b_project_denied(self) -> None:
        """Tenant A attempting to read Tenant B's project is denied with HTTP 404."""
        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        with pytest.raises(HTTPException) as exc_info:
            await get_project(req, "endpoint-proj-tenant-b")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_b_reads_own_project_allowed(self) -> None:
        """Tenant B can successfully read Project B."""
        req = self._create_mock_request("principal:tenant-b", Role.ENGINEER)
        res = await get_project(req, "endpoint-proj-tenant-b")
        assert res["success"] is True
        assert res["data"]["name"] == "Tenant B Complex"

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_update_tenant_b_project(self) -> None:
        """Tenant A attempting to mutate Tenant B's project is denied with HTTP 404."""
        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        with pytest.raises(HTTPException) as exc_info:
            await update_project(
                req,
                "endpoint-proj-tenant-b",
                UpdateProjectInput(name="Malicious Rename"),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_delete_tenant_b_project(self) -> None:
        """Tenant A attempting to delete Tenant B's project is denied with HTTP 404."""
        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        with pytest.raises(HTTPException) as exc_info:
            await delete_project(req, "endpoint-proj-tenant-b")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_has_global_project_oversight(self) -> None:
        """Admin principal can read projects across any tenant."""
        req = self._create_mock_request("principal:admin-user", Role.ADMIN)
        res_a = await get_project(req, "endpoint-proj-tenant-a")
        res_b = await get_project(req, "endpoint-proj-tenant-b")
        assert res_a["success"] is True
        assert res_b["success"] is True

    def test_cross_project_entity_lookup_is_isolated(self) -> None:
        """Entity lookup strictly requires both matching device ID and target project ID."""
        db = get_db()
        db.create_device("endpoint-proj-tenant-a", {
            "id": "dev-tenant-a-101",
            "name": "Smoke Detector A1",
            "type": "smoke_detector",
            "category": "detection",
        })
        # Tenant A can find device under Project A
        dev = db.get_device("endpoint-proj-tenant-a", "dev-tenant-a-101")
        assert dev is not None
        assert dev["id"] == "dev-tenant-a-101"

        # Querying Project B with Tenant A's device ID returns None (no cross-project leakage)
        cross_dev = db.get_device("endpoint-proj-tenant-b", "dev-tenant-a-101")
        assert cross_dev is None

    @pytest.mark.asyncio
    async def test_project_api_returns_canonical_revision_from_project_revisions(self) -> None:
        """Project response contains authoritative revision from project_revisions table."""
        db = get_db()
        state_store = CommandStateStore(db)
        # Update persistent revision in project_revisions to 5
        state_store.set_project_revision("endpoint-proj-tenant-a", 5)

        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        res = await get_project(req, "endpoint-proj-tenant-a")
        assert res["success"] is True
        assert res["data"]["revision"] == 5
        assert res["data"]["modelId"] == "dt-endpoint-proj-tenant-a"

    @pytest.mark.asyncio
    async def test_model_identity_is_canonical_and_mismatched_model_is_denied(self) -> None:
        """Backend validates model_id against project_id and denies mismatched/forged combinations."""
        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)

        # Mismatched model_id (Project A with Model B) -> HTTP 400
        with pytest.raises(HTTPException) as exc_info:
            await plan_autonomous_workflow(
                req,
                PlanWorkflowRequest(
                    prompt="Analyze power",
                    project_id="endpoint-proj-tenant-a",
                    model_id="dt-endpoint-proj-tenant-b",
                ),
            )
        assert exc_info.value.status_code == 400
        assert "does not belong to project" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_entity_validation_strictly_denies_unowned_elem_and_mock_prefixes(self) -> None:
        """Workflow planning strictly denies nonexistent entities including arbitrary elem-* and mock-*."""
        db = get_db()
        db.create_device("endpoint-proj-tenant-a", {
            "id": "dev-real-a1",
            "name": "Legitimate Sensor A1",
            "type": "smoke_detector",
            "category": "detection",
        })

        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)

        # 1. Project A + Existing Entity A -> ALLOWED
        res = await plan_autonomous_workflow(
            req,
            PlanWorkflowRequest(
                prompt="Verify device placement",
                project_id="endpoint-proj-tenant-a",
                entity_id="dev-real-a1",
            ),
        )
        assert res["success"] is True

        # 2. Project A + Entity B (foreign entity) -> DENIED (HTTP 400)
        with pytest.raises(HTTPException) as exc_info:
            await plan_autonomous_workflow(
                req,
                PlanWorkflowRequest(
                    prompt="Verify device placement",
                    project_id="endpoint-proj-tenant-a",
                    entity_id="dev-tenant-b-nonexistent",
                ),
            )
        assert exc_info.value.status_code == 400

        # 3. Project A + arbitrary elem-* -> DENIED (HTTP 400)
        with pytest.raises(HTTPException) as exc_info:
            await plan_autonomous_workflow(
                req,
                PlanWorkflowRequest(
                    prompt="Verify element",
                    project_id="endpoint-proj-tenant-a",
                    entity_id="elem-forged-device-999",
                ),
            )
        assert exc_info.value.status_code == 400

        # 4. Project A + arbitrary mock-* -> DENIED (HTTP 400)
        with pytest.raises(HTTPException) as exc_info:
            await plan_autonomous_workflow(
                req,
                PlanWorkflowRequest(
                    prompt="Verify mock",
                    project_id="endpoint-proj-tenant-a",
                    entity_id="mock-fake-device-001",
                ),
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_tenant_list_projects_is_strictly_scoped(self) -> None:
        """GET /projects returns only the projects authored by the calling tenant."""
        req_a = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        res_a = await list_projects(req_a)
        assert res_a["success"] is True
        proj_ids_a = [p["id"] for p in res_a["data"]["data"]]
        assert "endpoint-proj-tenant-a" in proj_ids_a
        assert "endpoint-proj-tenant-b" not in proj_ids_a

        req_b = self._create_mock_request("principal:tenant-b", Role.ENGINEER)
        res_b = await list_projects(req_b)
        assert res_b["success"] is True
        proj_ids_b = [p["id"] for p in res_b["data"]["data"]]
        assert "endpoint-proj-tenant-b" in proj_ids_b
        assert "endpoint-proj-tenant-a" not in proj_ids_b

    @pytest.mark.asyncio
    async def test_tenant_cannot_forge_project_author_on_creation(self) -> None:
        """Tenant A submitting author=Tenant B is rejected with HTTP 403 Forbidden."""
        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)
        with pytest.raises(HTTPException) as exc_info:
            await create_project(
                req,
                CreateProjectInput(
                    name="Forged Project",
                    author="principal:tenant-b",
                ),
            )
        assert exc_info.value.status_code == 403

        # Legitimate creation without author or matching author stamps authenticated principal
        created = await create_project(
            req,
            CreateProjectInput(name="Legitimate Project"),
        )
        assert created["success"] is True
        assert created["data"]["author"] == "principal:tenant-a"
        assert created["data"]["revision"] == 1
        assert created["data"]["modelId"] == f"dt-{created['data']['id']}"

        # Clean up
        db = get_db()
        db.delete_project(created["data"]["id"])

    @pytest.mark.asyncio
    async def test_execution_planning_strictly_enforces_occ_expected_revision(self) -> None:
        """Planning fails with HTTP 409 when expected_revision mismatches canonical revision."""
        db = get_db()
        state_store = CommandStateStore(db)
        state_store.set_project_revision("endpoint-proj-tenant-a", 3)

        req = self._create_mock_request("principal:tenant-a", Role.ENGINEER)

        # Matching expected revision -> ALLOWED
        res = await plan_autonomous_workflow(
            req,
            PlanWorkflowRequest(
                prompt="Autonomous battery check",
                project_id="endpoint-proj-tenant-a",
                expected_revision=3,
            ),
        )
        assert res["success"] is True

        # Conflicting expected revision (stale client) -> HTTP 409 Conflict
        with pytest.raises(HTTPException) as exc_info:
            await plan_autonomous_workflow(
                req,
                PlanWorkflowRequest(
                    prompt="Autonomous battery check",
                    project_id="endpoint-proj-tenant-a",
                    expected_revision=2,
                ),
            )
        assert exc_info.value.status_code == 409
        assert "OCC revision conflict" in str(exc_info.value.detail)
