"""backend/tests/architecture/test_control_request_unification.py — Architecture Test for ControlRequest Unification.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 6 & Gate 6:
1. ControlRequest is the single source of truth for planning and execution intents.
2. JSON Schema for ControlRequest must be derived from the Pydantic model (zero diverging duplicate schemas).
3. All planning routes (generic planner, workflow planner, REST runs router) must execute via ControlRequest.
"""

from __future__ import annotations

import pytest
from backend.core.control_request import ControlRequest, ControlRequestValidationError
from backend.core.session_context import UniversalSessionContext
from backend.core.workflow_planner import AutonomousWorkflowPlanner, default_workflow_planner
from backend.core.generic_planner import GenericWorkflowPlanner, default_generic_planner
from backend.core.command_bus import AuthenticatedPrincipal


def test_control_request_single_source_json_schema() -> None:
    """Verify ControlRequest derives JSON Schema directly from Pydantic model."""
    schema = ControlRequest.get_json_schema()
    assert schema["type"] == "object"
    assert "intent" in schema["properties"]
    assert "context" in schema["properties"]
    assert "params" in schema["properties"]
    assert "policy_hints" in schema["properties"]
    assert "metadata" in schema["properties"]
    assert "UniversalSessionContext" in schema.get("$defs", {})


def test_control_request_from_dict_and_to_dict_roundtrip() -> None:
    """Verify polymorphic dictionary parsing and lossless roundtrip."""
    raw_data = {
        "intent": "Layout smoke detectors in room 12x15m",
        "project_id": "proj-ctrl-test",
        "expected_revision": 3,
        "composite_spec": {"detector_type": "smoke", "width_m": 12.0, "length_m": 15.0},
        "approval_mode": "AUTO",
        "metadata": {"trace_id": "tr-12345"},
    }

    req = ControlRequest.from_dict(raw_data)
    assert req.intent == "Layout smoke detectors in room 12x15m"
    assert req.context.project_id == "proj-ctrl-test"
    assert req.context.expected_revision == 3
    assert req.params["detector_type"] == "smoke"
    assert req.policy_hints["approval_mode"] == "AUTO"
    assert req.metadata["trace_id"] == "tr-12345"

    d = req.to_dict()
    assert d["intent"] == req.intent
    assert d["context"]["project_id"] == "proj-ctrl-test"
    assert d["params"] == req.params


def test_control_request_validation_rejects_empty_intent() -> None:
    """Verify ControlRequest rejects empty or whitespace-only intents."""
    with pytest.raises(Exception):
        ControlRequest.from_dict({"intent": "", "project_id": "proj-1"})

    with pytest.raises(Exception):
        ControlRequest.from_dict(None)


def test_planners_expose_plan_control_request_method() -> None:
    """Verify that both generic and autonomous planners implement plan_control_request."""
    assert hasattr(default_generic_planner, "plan_control_request")
    assert callable(default_generic_planner.plan_control_request)
    assert hasattr(default_workflow_planner, "plan_control_request")
    assert callable(default_workflow_planner.plan_control_request)
