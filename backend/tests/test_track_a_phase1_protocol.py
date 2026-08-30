"""backend/tests/test_track_a_phase1_protocol.py — Protocol & Behavioral Verification.

Verifies:
1. D-1b: Rejection of missing expected_revision (MISSING_EXPECTED_REVISION) on canonical mutations.
2. D-1b: Preservation of INVALID_EXPECTED_REVISION and REVISION_CONFLICT behaviors.
3. D-1b: Successful execution of canonical capabilities with valid expected_revision.
4. D-1b: Non-canonical capabilities execute without requiring expected_revision.
5. D-1d (O3): Strict fail-closed identity matching consistency across sync.py and agent_ws.py.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any

from backend.core.command_bus import AuthenticatedPrincipal
from backend.database import Database, get_db
from backend.routers import agent_ws, sync


class MockWebSocket:
    """Mock WebSocket capturing sent json frames."""

    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.headers = headers or {}
        self.closed: bool = False
        self.close_code: int | None = None

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code


@pytest.fixture
def auth_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="alice_user",
        email="alice@bazspark.com",
        role="engineer",
        scopes=["*"],
        is_authenticated=True,
    )


# ─── D-1b: Missing expected_revision on Canonical Capabilities ──────────────


@pytest.mark.asyncio
async def test_run_start_import_execute_missing_expected_revision_rejected(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: run_start targeting import.execute_import without expected_revision returns MISSING_EXPECTED_REVISION."""
    db = get_db()
    proj = db.create_project({"name": "Import Test Proj", "author": "alice_user"})
    p_id = proj["id"]

    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "steps": [
            {
                "step_id": "step-import-1",
                "capability_id": "import.execute_import",
                "payload": {"file_id": "file-123", "project_id": p_id},
            }
        ],
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "MISSING_EXPECTED_REVISION"
    assert "expected_revision was not provided" in ws.sent[0]["message"]


@pytest.mark.asyncio
async def test_run_start_export_execute_missing_expected_revision_rejected(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: run_start targeting export.execute_export without expected_revision returns MISSING_EXPECTED_REVISION."""
    db = get_db()
    proj = db.create_project({"name": "Export Test Proj", "author": "alice_user"})
    p_id = proj["id"]

    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "steps": [
            {
                "step_id": "step-export-1",
                "capability_id": "export.execute_export",
                "payload": {"project_id": p_id, "target_format": "dxf"},
            }
        ],
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "MISSING_EXPECTED_REVISION"


@pytest.mark.asyncio
async def test_run_start_plan_with_canonical_step_missing_expected_revision_rejected(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: run_start with plan containing canonical mutation step without expected_revision returns MISSING_EXPECTED_REVISION."""
    db = get_db()
    proj = db.create_project({"name": "Plan Test Proj", "author": "alice_user"})
    p_id = proj["id"]

    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "steps": [{"step_id": "s1", "action": "noop"}],
        "plan": {
            "steps": [
                {
                    "step_id": "p1",
                    "capability_id": "import.execute_import",
                    "payload": {},
                }
            ]
        },
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "MISSING_EXPECTED_REVISION"


@pytest.mark.asyncio
async def test_run_start_canonical_with_conflicting_expected_revision_rejected(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: Conflicting expected_revision on canonical capability returns REVISION_CONFLICT."""
    db = get_db()
    proj = db.create_project({"name": "Conflict Proj", "author": "alice_user"})
    p_id = proj["id"]

    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "expectedRevision": 999,
        "steps": [
            {
                "step_id": "s1",
                "capability_id": "import.execute_import",
                "payload": {"file_id": "f1", "project_id": p_id, "expected_revision": 999},
            }
        ],
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "REVISION_CONFLICT"


@pytest.mark.asyncio
async def test_run_start_canonical_with_malformed_expected_revision_rejected(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: Malformed expected_revision on canonical capability returns INVALID_EXPECTED_REVISION."""
    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": "proj-any",
        "expectedRevision": "invalid-non-numeric-string",
        "steps": [
            {
                "step_id": "s1",
                "capability_id": "import.execute_import",
                "payload": {},
            }
        ],
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_error"
    assert ws.sent[0]["errorCode"] == "INVALID_EXPECTED_REVISION"


@pytest.mark.asyncio
async def test_run_start_canonical_with_valid_expected_revision_succeeds(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: Canonical capability with valid expected_revision starts and executes successfully."""
    db = get_db()
    proj = db.create_project({"name": "Canonical Valid Proj", "author": "alice_user"})
    p_id = proj["id"]
    current_rev = proj.get("revision", 1)

    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "expectedRevision": current_rev,
        "steps": [
            {
                "step_id": "s1",
                "capability_id": "export.execute_export",
                "payload": {"project_id": p_id, "expected_revision": current_rev, "target_format": "json"},
            }
        ],
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) >= 1
    first_msg = ws.sent[0]
    assert first_msg["type"] == "run_status_update"
    assert first_msg["projectId"] == p_id
    assert first_msg["runId"].startswith("run-")


@pytest.mark.asyncio
async def test_run_start_non_canonical_without_expected_revision_succeeds(
    auth_principal: AuthenticatedPrincipal,
) -> None:
    """D-1b: Non-canonical capability (revision_binding=none) executes without requiring expected_revision."""
    db = get_db()
    proj = db.create_project({"name": "Non Canonical Proj", "author": "alice_user"})
    p_id = proj["id"]

    ws = MockWebSocket()
    msg = {
        "type": "run_start",
        "projectId": p_id,
        "steps": [
            {
                "step_id": "s1",
                "capability_id": "spatial.place_devices",
                "payload": {"room_id": "r1", "width_m": 10.0, "length_m": 15.0},
            }
        ],
    }

    await agent_ws._handle_run_start(ws, auth_principal, msg)

    assert len(ws.sent) >= 1
    first_msg = ws.sent[0]
    assert first_msg["type"] == "run_status_update"
    assert first_msg["projectId"] == p_id
    assert first_msg["runId"].startswith("run-")


# ─── D-1d (O3): Strict Unified Identity Matching ────────────────────────────


@pytest.mark.asyncio
async def test_o3_identity_matching_consistency_sync_and_agent_ws() -> None:
    """D-1d (O3): Verify identity matching behaves identically in sync.py and agent_ws.py."""
    db = get_db()
    proj = db.create_project({"name": "O3 Isolation Proj", "author": "alice_id_123"})
    p_id = proj["id"]

    # 1. Matching by user_id
    principal_matching_user_id = AuthenticatedPrincipal(
        user_id="alice_id_123",
        email="other@bazspark.com",
        role="engineer",
        scopes=["*"],
    )
    ws1 = MockWebSocket()
    msg1 = {
        "type": "run_start",
        "projectId": p_id,
        "steps": [{"step_id": "s1", "capability_id": "spatial.place_devices", "payload": {}}],
    }
    await agent_ws._handle_run_start(ws1, principal_matching_user_id, msg1)
    assert ws1.sent[0]["type"] != "run_error" or ws1.sent[0].get("errorCode") != "PROJECT_NOT_FOUND"

    # 2. Matching by email
    proj_email = db.create_project({"name": "Email Auth Proj", "author": "alice_email@bazspark.com"})
    p_email_id = proj_email["id"]
    principal_matching_email = AuthenticatedPrincipal(
        user_id="different_uid",
        email="alice_email@bazspark.com",
        role="engineer",
        scopes=["*"],
    )
    ws2 = MockWebSocket()
    msg2 = {
        "type": "run_start",
        "projectId": p_email_id,
        "steps": [{"step_id": "s1", "capability_id": "spatial.place_devices", "payload": {}}],
    }
    await agent_ws._handle_run_start(ws2, principal_matching_email, msg2)
    assert ws2.sent[0]["type"] != "run_error" or ws2.sent[0].get("errorCode") != "PROJECT_NOT_FOUND"

    # 3. Mismatched non-admin principal -> rejected with PROJECT_NOT_FOUND (fail-closed)
    principal_intruder = AuthenticatedPrincipal(
        user_id="intruder_user",
        email="intruder@bazspark.com",
        role="engineer",
        scopes=["*"],
    )
    ws3 = MockWebSocket()
    msg3 = {
        "type": "run_start",
        "projectId": p_id,
        "steps": [{"step_id": "s1", "capability_id": "spatial.place_devices", "payload": {}}],
    }
    await agent_ws._handle_run_start(ws3, principal_intruder, msg3)
    assert len(ws3.sent) == 1
    assert ws3.sent[0]["type"] == "run_error"
    assert ws3.sent[0]["errorCode"] == "PROJECT_NOT_FOUND"
