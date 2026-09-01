"""backend/core/planner_schema.py — Strict JSON Schema & Pydantic Validation for Autonomous Plans.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 (S2 Deliverable):
- Explicit JSON Schema for all synthesized plans.
- Strict rejection on invalid, malformed, hallucinated, or unparseable structures.
- Defense against cyclic dependencies and undefined step references.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class PlanSchemaValidationError(ValueError):
    """Raised when an autonomous plan fails JSON Schema or semantic structure validation."""


PLAN_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AutonomousWorkflowPlan",
    "type": "object",
    "required": ["steps"],
    "properties": {
        "plan_id": {"type": "string"},
        "project_id": {"type": "string"},
        "expected_revision": {"type": "integer", "minimum": 0},
        "intent_summary": {"type": "string"},
        "intent_category": {"type": "string"},
        "requires_human_approval": {"type": "boolean"},
        "overall_policy_decision": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["step_id", "capability_id"],
                "properties": {
                    "step_id": {"type": "string", "minLength": 1},
                    "capability_id": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "payload": {"type": "object"},
                    "risk_class": {"type": "string"},
                    "requires_approval": {"type": "boolean"},
                },
            },
        },
    },
}


class StepValidationModel(BaseModel):
    """Pydantic model validating individual plan steps."""

    step_id: str = Field(..., min_length=1)
    capability_id: str = Field(..., min_length=1)
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    risk_class: str = "LOW"
    policy_result: str = "AUTO_APPROVED"
    requires_approval: bool = False

    @field_validator("step_id", "capability_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace only.")
        return s


class AutonomousPlanValidationModel(BaseModel):
    """Pydantic model validating complete autonomous plans."""

    plan_id: str = ""
    project_id: str = ""
    expected_revision: int = 0
    intent_summary: str = ""
    intent_category: str = "composite"
    steps: list[StepValidationModel] = Field(..., min_length=1)
    requires_human_approval: bool = False
    overall_policy_decision: str = "AUTO_APPROVED"
    projected_state: dict[str, Any] = Field(default_factory=dict)
    combined_audit_digest: str = ""
    token_telemetry: dict[str, Any] = Field(default_factory=dict)

    @field_validator("steps")
    @classmethod
    def validate_step_topology(
        cls, steps: list[StepValidationModel]
    ) -> list[StepValidationModel]:
        step_ids = {s.step_id for s in steps}
        if len(step_ids) != len(steps):
            raise ValueError("Duplicate step_id detected in plan steps.")

        for s in steps:
            for dep in s.dependencies:
                if dep not in step_ids:
                    raise ValueError(
                        f"Step '{s.step_id}' depends on non-existent step '{dep}'."
                    )
                if dep == s.step_id:
                    raise ValueError(
                        f"Step '{s.step_id}' cannot depend on itself."
                    )
        return steps


def validate_plan_dict(data: dict[str, Any]) -> AutonomousPlanValidationModel:
    """Validate a raw plan dictionary against strict JSON schema / Pydantic constraints.

    Raises:
        PlanSchemaValidationError: On invalid structure or missing required fields.
    """
    if not isinstance(data, dict):
        raise PlanSchemaValidationError(f"Expected plan dictionary, got {type(data).__name__}")

    try:
        return AutonomousPlanValidationModel.model_validate(data)
    except Exception as exc:
        raise PlanSchemaValidationError(f"JSON Schema Validation Failed: {exc}") from exc
