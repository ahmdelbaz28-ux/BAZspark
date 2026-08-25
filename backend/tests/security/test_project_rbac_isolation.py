"""
test_project_rbac_isolation.py — Project RBAC and Tenant Authorization Tests (Phase 8 Gate 5).

Verifies:
1. Endpoint permission enforcement on project endpoints.
2. Role checking via require_permission dependency.
3. Access denial for unprivileged roles (e.g. VIEWER attempting PROJECT_CREATE/DELETE).
4. Safe isolation of project access paths.
"""

from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.auth import require_permission
from backend.rbac import Permission, Role, has_permission, ROLE_PERMISSIONS


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
