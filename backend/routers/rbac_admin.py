"""
backend/routers/rbac_admin.py — RBAC introspection endpoint (V270 FIX).

Closes the confirmed broken frontend API call identified by the
BAZspark UI Coverage Audit (Phase 1 systematic-debugging investigation,
2026-07-30):

  • RbacPage.tsx → GET /api/v1/admin/rbac/permissions → was 404

The existing api_keys.py router has prefix `/admin/keys`, so it cannot
host `/admin/rbac/*` paths. Rather than mutate api_keys.py's prefix
(which would break every existing /admin/keys/* caller), we create a
separate router here with prefix `/admin/rbac`. When mounted at
`/api/v1` by app.py, the effective URL is `/api/v1/admin/rbac/permissions`
— exactly what RbacPage.tsx expects.

PERMISSIONS MODEL
-----------------
Returns the ROLE_PERMISSIONS map from backend/rbac.py, grouped by role.
The frontend uses this to render the role-permission matrix in the RBAC
admin page. Read-only — there is no setter endpoint because role
permissions are a code-level contract (changing them at runtime would
invalidate every permission check in the system).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.auth import require_permission
from backend.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    get_role_permissions,
    has_permission,
)
from backend.response import success

# ── Annotated dependency alias (S8410) ─────────────────────────────────────
SystemConfigRole = Annotated[Role, Depends(require_permission(Permission.SYSTEM_CONFIG))]
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/rbac", tags=["rbac"])


@router.get("/permissions")
async def get_role_permission_matrix(_role: SystemConfigRole) -> dict[str, Any]:
    """
    Return the full role-permission matrix.

    Response shape:
    {
      "roles": [
        {
          "role": "admin",
          "permissions": ["project:read", "project:create", ...]
        },
        ...
      ],
      "permissions": ["project:read", "project:create", ...],
      "matrix": {
        "admin":    {"project:read": true, ...},
        "engineer": {"project:read": true, ...},
        "viewer":   {"project:read": true, ...}
      }
    }
    """
    # Build the matrix: role → {permission_string: bool}
    matrix: dict[str, dict[str, bool]] = {}
    roles_list: list[dict[str, Any]] = []
    for role in Role:
        role_perms = get_role_permissions(role)
        perm_strings = sorted({p.value for p in role_perms})
        roles_list.append({"role": role.value, "permissions": perm_strings})
        matrix[role.value] = {
            perm.value: has_permission(role, perm) for perm in Permission
        }

    all_permissions = sorted({p.value for p in Permission})

    return success(
        {
            "roles": roles_list,
            "permissions": all_permissions,
            "matrix": matrix,
            "note": "Role-permission mapping is a code-level contract (backend/rbac.py). Changes require a code deploy.",
        }
    )
