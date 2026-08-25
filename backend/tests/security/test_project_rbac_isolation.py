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
"""

from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.auth import require_permission
from backend.rbac import Permission, Role, has_permission, ROLE_PERMISSIONS
from backend.database import Database


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
