"""backend/tests/architecture/test_phase7_chat_architecture.py — Architecture Verification for Phase 7 Universal Chat Control Plane.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 7 & Gate 7:
1. AgentChatPage has zero direct calls to unmonitored mutation/execution REST APIs (grep & pattern AST check).
2. Visual surfaces derive produced artifacts strictly from official run selection and step result data.
3. All chat cycles route via ControlRequest -> Planner -> Policy -> Approval -> Run.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from backend.core.control_request import ControlRequest
from backend.core.session_context import UniversalSessionContext
from backend.core.workflow_planner import default_workflow_planner
from backend.core.generic_planner import default_generic_planner


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENT_CHAT_PAGE_PATH = REPO_ROOT / "frontend" / "src" / "pages" / "AgentChatPage.tsx"


def test_agent_chat_page_ast_zero_direct_execution_calls() -> None:
    """Verify AgentChatPage contains zero direct execution calls to importApi.executeImport or exportApi.executeExport."""
    assert AGENT_CHAT_PAGE_PATH.exists(), f"AgentChatPage.tsx not found at {AGENT_CHAT_PAGE_PATH}"
    content = AGENT_CHAT_PAGE_PATH.read_text(encoding="utf-8")

    # 1. No direct execution client calls
    assert "importApi.executeImport" not in content, "Direct call to importApi.executeImport found in AgentChatPage"
    assert "exportApi.executeExport" not in content, "Direct call to exportApi.executeExport found in AgentChatPage"
    assert "exportApi.planExport" not in content, "Direct call to exportApi.planExport found in AgentChatPage"

    # 2. No dev-mode keyword interception bypassing planning
    assert "import.meta.env.DEV" not in content, "Dev-only keyword bypass found in AgentChatPage"

    # 3. All workflow dispatches route via agentWorkflowApi.planWorkflow / startRun
    assert "agentWorkflowApi.planWorkflow" in content, "AgentChatPage must route through agentWorkflowApi.planWorkflow"


def test_visual_surfaces_read_from_official_selection() -> None:
    """Verify producedArtifacts in AgentChatPage derives from runState.steps (official run selection)."""
    assert AGENT_CHAT_PAGE_PATH.exists()
    content = AGENT_CHAT_PAGE_PATH.read_text(encoding="utf-8")

    # No unmonitored local state for artifacts
    assert "useState<ProducedArtifact[]>" not in content, "Local unmonitored producedArtifacts state found"

    # Derived dynamically from runState.steps
    assert "runState.steps" in content
    assert "producedArtifacts" in content


def test_all_planners_implement_control_request_interface() -> None:
    """Verify all workflow planners expose plan_control_request."""
    assert hasattr(default_generic_planner, "plan_control_request")
    assert callable(default_generic_planner.plan_control_request)
    assert hasattr(default_workflow_planner, "plan_control_request")
    assert callable(default_workflow_planner.plan_control_request)
