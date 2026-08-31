"""backend/tests/intent_suite/test_disambiguation_and_degradation.py — Disambiguation & Degradation Tests.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 (S2 & S3 Deliverables):
- Missing parameter -> explicit question (no guessing).
- Ambiguous parameter -> explicit question with choices.
- Non-silent fallthrough -> explicit explanation of what was not understood.
- JSON Schema validation -> rejection of invalid plans.
"""

from __future__ import annotations

import pytest
from backend.core.disambiguation import DisambiguationEngine, DisambiguationRequest
from backend.core.planner_schema import PlanSchemaValidationError, validate_plan_dict


def test_disambiguation_missing_spatial_parameters() -> None:
    """Missing room dimensions must trigger clarification with missing_fields."""
    res = DisambiguationEngine.evaluate_intent("Layout smoke detectors in room")
    assert res.is_clarification_required is True
    assert res.clarification_type == "missing_parameter"
    assert "width_m" in res.missing_fields
    assert len(res.question) > 0


def test_disambiguation_ambiguous_export_format() -> None:
    """Ambiguous export format without target specification must provide options."""
    res = DisambiguationEngine.evaluate_intent("Export project deliverable")
    assert res.is_clarification_required is True
    assert res.clarification_type == "ambiguous_parameter"
    assert "target_format" in res.missing_fields
    assert "DXF" in res.options
    assert "IFC" in res.options
    assert "PDF" in res.options


def test_disambiguation_empty_prompt_non_silent_fallthrough() -> None:
    """Empty or uninterpretable prompt must produce non-silent diagnostic choices."""
    res = DisambiguationEngine.evaluate_intent("   ")
    assert res.is_clarification_required is True
    assert res.clarification_type == "intent_unclear"
    assert len(res.options) >= 3
    assert len(res.question) > 0


def test_schema_validation_rejects_empty_steps() -> None:
    """Plan schema validator must reject plan with empty steps list."""
    invalid_plan = {
        "plan_id": "plan-empty",
        "project_id": "proj-1",
        "steps": [],
    }
    with pytest.raises(PlanSchemaValidationError):
        validate_plan_dict(invalid_plan)


def test_schema_validation_rejects_missing_capability_id() -> None:
    """Plan schema validator must reject step missing capability_id."""
    invalid_plan = {
        "plan_id": "plan-bad-step",
        "project_id": "proj-1",
        "steps": [
            {
                "step_id": "step-1",
                "capability_id": "",  # Empty
                "dependencies": [],
            }
        ],
    }
    with pytest.raises(PlanSchemaValidationError):
        validate_plan_dict(invalid_plan)


def test_schema_validation_rejects_cyclic_dependency() -> None:
    """Plan schema validator must reject cyclic self-dependency."""
    invalid_plan = {
        "plan_id": "plan-cyclic",
        "project_id": "proj-1",
        "steps": [
            {
                "step_id": "step-1",
                "capability_id": "spatial.place_devices",
                "dependencies": ["step-1"],  # Self-dependency
            }
        ],
    }
    with pytest.raises(PlanSchemaValidationError):
        validate_plan_dict(invalid_plan)


def test_schema_validation_rejects_unresolved_dependency() -> None:
    """Plan schema validator must reject reference to non-existent step."""
    invalid_plan = {
        "plan_id": "plan-unresolved",
        "project_id": "proj-1",
        "steps": [
            {
                "step_id": "step-1",
                "capability_id": "spatial.place_devices",
                "dependencies": ["step-nonexistent"],
            }
        ],
    }
    with pytest.raises(PlanSchemaValidationError):
        validate_plan_dict(invalid_plan)
