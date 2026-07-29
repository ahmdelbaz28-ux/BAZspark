"""Phase 5 — M-3 (workflow_service) FIX VERIFICATION.

ORIGINAL CLAIM (from Phase 3 verdict, now RESOLVED):
  "M-3: workflow_service _workflow_locks memory leak (no race, just
   unbounded dict growth)"

FIXES APPLIED (this round):
  1. Added _cleanup_workflow_lock(workflow_id) method that removes a
     lock from _workflow_locks via .pop(workflow_id, None).
  2. Added cleanup_workflow(workflow_id) public method that cleans up
     both _workflow_locks and _workflows dicts.

These tests verify the FIXES are in place. They serve as regression
guards: if someone removes the cleanup logic, the tests will FAIL.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_SERVICE_PY = REPO_ROOT / "backend" / "services" / "workflow_service.py"


# ─── FIX VERIFICATION: cleanup logic exists ─────────────────────────────────


def test_workflow_locks_cleanup_logic_exists_in_source():
    """REGRESSION GUARD: verify cleanup logic exists in workflow_service.py.

    The M-3 fix added `_workflow_locks.pop(workflow_id, None)` calls
    to remove locks when workflows are cleaned up. This test verifies
    those patterns are present.

    If this test FAILS, the cleanup logic has been removed — the memory
    leak has returned. Re-apply the fix.
    """
    source = WORKFLOW_SERVICE_PY.read_text(encoding="utf-8")

    # Verify cleanup patterns exist
    cleanup_patterns = [
        "self._workflow_locks.pop",
    ]

    for pattern in cleanup_patterns:
        assert pattern in source, (
            f"M-3 FIX REVERTED: cleanup pattern '{pattern}' not found "
            "in workflow_service.py. The memory leak has returned — "
            "re-apply the fix."
        )


def test_cleanup_workflow_method_exists():
    """REGRESSION GUARD: verify the public cleanup_workflow() method exists.

    The M-3 fix added a public cleanup_workflow(workflow_id) method
    that callers can invoke when a workflow reaches a terminal state.
    """
    source = WORKFLOW_SERVICE_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(WORKFLOW_SERVICE_PY))

    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "cleanup_workflow":
            found = True
            break

    assert found, (
        "M-3 FIX REVERTED: cleanup_workflow() method not found in "
        "workflow_service.py. The public API for cleaning up workflow "
        "state has been removed — re-apply the fix."
    )


# ─── RUNTIME: cleanup actually works ────────────────────────────────────────


def test_cleanup_workflow_removes_lock_and_workflow():
    """RUNTIME REGRESSION GUARD: verify cleanup_workflow() actually removes
    entries from _workflow_locks and _workflows.

    If this test FAILS, cleanup_workflow() is not actually cleaning up
    — the memory leak persists despite the method existing.
    """
    try:
        from backend.services.workflow_service import WorkflowService
    except ImportError as e:
        if "langgraph" in str(e):
            pytest.skip(f"langgraph not available: {e}")
        raise

    with patch.object(WorkflowService, "__init__", lambda self: None):
        service = WorkflowService()
        service._workflow_locks = {}
        service._workflows = {}

        # Add some locks and workflows
        for i in range(10):
            service._get_workflow_lock(f"wf-{i}")
            service._workflows[f"wf-{i}"] = {"state": "completed"}

        assert len(service._workflow_locks) == 10
        assert len(service._workflows) == 10

        # Clean up one
        service.cleanup_workflow("wf-5")
        assert "wf-5" not in service._workflow_locks, (
            "cleanup_workflow() did not remove the lock for wf-5"
        )
        assert "wf-5" not in service._workflows, (
            "cleanup_workflow() did not remove the workflow state for wf-5"
        )
        assert len(service._workflow_locks) == 9
        assert len(service._workflows) == 9

        # Clean up a non-existent workflow (should be a no-op)
        service.cleanup_workflow("wf-nonexistent")
        assert len(service._workflow_locks) == 9, (
            "cleanup_workflow() should be a no-op for non-existent workflow"
        )


# ─── Part (b): no race condition (unchanged by the fix) ─────────────────────


def test_no_race_condition_in_get_or_create_pattern():
    """REGRESSION GUARD: _get_workflow_lock must remain race-free.

    The M-3 fix added cleanup logic but did NOT change _get_workflow_lock.
    This test verifies the check-then-set pattern still has no `await`
    between the check and the set.

    If this test FAILS, an `await` was inserted — a race condition was
    introduced. Escalate to HIGH.
    """
    source = WORKFLOW_SERVICE_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(WORKFLOW_SERVICE_PY))

    method_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_get_workflow_lock":
            method_node = node
            break

    assert method_node is not None, "_get_workflow_lock method not found"

    await_nodes = []
    for node in ast.walk(method_node):
        if isinstance(node, ast.Await):
            await_nodes.append(node.lineno)

    assert not await_nodes, (
        "M-3 REGRESSION: _get_workflow_lock now contains `await` at "
        f"lines {await_nodes}. This introduces a race condition — "
        "escalate to HIGH."
    )

    assert isinstance(method_node, ast.FunctionDef), (
        "_get_workflow_lock must remain a sync function"
    )


# ─── Claim text regression guard ─────────────────────────────────────────────


def test_m3_claim_text_exists_in_worklog():
    """REGRESSION GUARD: the M-3 claim text must exist in worklog.md."""
    WORKLOG = Path("/home/z/my-project/worklog.md")
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")
    expected_substring = (
        "M-3: workflow_service _workflow_locks memory leak "
        "(no race, just unbounded dict growth)"
    )

    assert expected_substring in worklog_text, (
        "M-3 claim text removed from worklog.md."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
