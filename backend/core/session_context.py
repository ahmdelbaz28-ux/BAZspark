"""backend/core/session_context.py — Universal Session Context and Wire Contract.

BAZspark V2.2 Phase 3 Universal Context Specification:
- UniversalSessionContext is the single canonical server-side model for execution context.
- Matrix fields: (project_id, model_id, entity_ids, expected_revision, ui_surface).
- Automatic revision_binding derivation via default_capability_registry (no hardcoded lists).
- Hard <=1500 token budget enforcement for semantic LLM context aggregation.
- Zero raw project/CAD state sent to the LLM.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.core.capability_registry import CapabilityRegistry, default_capability_registry


class MissingExpectedRevisionError(ValueError):
    """Raised when a mutation requiring canonical project state revision is executed without expected_revision."""

    def __init__(self, message: str = "expected_revision is required for state mutating capabilities.") -> None:
        super().__init__(message)
        self.error_code = "MISSING_EXPECTED_REVISION"
        self.status_code = 400


class ContextBudgetExceededError(ValueError):
    """Raised when semantic LLM context aggregation exceeds the hard <=1500 token budget ceiling."""

    def __init__(self, token_count: int, max_tokens: int = 1500) -> None:
        super().__init__(
            f"Context budget exceeded: aggregated context is {token_count} tokens (limit is {max_tokens} tokens)."
        )
        self.token_count = token_count
        self.max_tokens = max_tokens
        self.error_code = "CONTEXT_BUDGET_EXCEEDED"
        self.status_code = 400


@dataclass
class UniversalSessionContext:
    """Canonical Universal Session Context model per BAZSPARK_PLAN_V2_2 §5 Phase 3.

    Fields:
    1. project_id: Target project identifier (canonical aggregate root).
    2. model_id: Optional digital twin / BIM model identity bound to project_id.
    3. entity_ids: Optional list of selected entity IDs (devices, circuits, elements).
    4. expected_revision: Authoritative OCC revision token required for state-mutating capabilities.
    5. ui_surface: Optional client surface indicator (navigational metadata with ZERO execution side-effects).
    """

    project_id: str
    model_id: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    expected_revision: int | None = None
    ui_surface: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str):
            raise TypeError(f"project_id must be a string, got {type(self.project_id).__name__}")
        if self.model_id is not None and not isinstance(self.model_id, str):
            raise TypeError(f"model_id must be a string or None, got {type(self.model_id).__name__}")
        if not isinstance(self.entity_ids, list) or not all(isinstance(e, str) for e in self.entity_ids):
            raise TypeError("entity_ids must be a list of strings")
        if self.expected_revision is not None:
            if not isinstance(self.expected_revision, int) or isinstance(self.expected_revision, bool):
                raise TypeError(f"expected_revision must be an integer, got {type(self.expected_revision).__name__}")
            if self.expected_revision < 0:
                raise ValueError("expected_revision cannot be negative")
        if self.ui_surface is not None and not isinstance(self.ui_surface, str):
            raise TypeError(f"ui_surface must be a string or None, got {type(self.ui_surface).__name__}")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> UniversalSessionContext:
        """Parse UniversalSessionContext from a wire dictionary with backward compatibility."""
        if not data or not isinstance(data, dict):
            raise ValueError("Context data must be a dictionary")

        project_id = str(data.get("project_id") or data.get("projectId") or "")

        raw_model = data.get("model_id") if "model_id" in data else data.get("modelId")
        model_id = str(raw_model) if raw_model is not None and raw_model != "" else None

        # Resolve entity_ids with fallback to single entity_id / entityId
        raw_entity_ids = data.get("entity_ids") if "entity_ids" in data else data.get("entityIds")
        if raw_entity_ids is not None and isinstance(raw_entity_ids, list):
            entity_ids = [str(e) for e in raw_entity_ids if e]
        else:
            single_entity = data.get("entity_id") if "entity_id" in data else data.get("entityId")
            if single_entity and isinstance(single_entity, str):
                entity_ids = [single_entity]
            else:
                entity_ids = []

        raw_rev = data.get("expected_revision") if "expected_revision" in data else data.get("expectedRevision")
        expected_revision: int | None = None
        if raw_rev is not None and raw_rev != "":
            try:
                expected_revision = int(raw_rev)
            except (ValueError, TypeError) as err:
                raise ValueError(f"Invalid expected_revision '{raw_rev}': must be an integer") from err

        raw_ui = data.get("ui_surface") if "ui_surface" in data else data.get("uiSurface")
        ui_surface = str(raw_ui) if raw_ui is not None and raw_ui != "" else None

        return cls(
            project_id=project_id,
            model_id=model_id,
            entity_ids=entity_ids,
            expected_revision=expected_revision,
            ui_surface=ui_surface,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert UniversalSessionContext to dictionary representation."""
        return asdict(self)


def estimate_token_count(text_or_dict: str | dict[str, Any] | list[Any]) -> int:
    """Accurately estimate token count for JSON/string payloads (~3.8 chars per token)."""
    if isinstance(text_or_dict, (dict, list)):
        serialized = json.dumps(text_or_dict, separators=(",", ":"))
    else:
        serialized = str(text_or_dict)
    return max(1, int(len(serialized) / 3.8))


def check_context_budget(payload: Any, max_tokens: int = 1500) -> tuple[bool, int]:
    """Check if the context payload fits within the hard token budget ceiling."""
    tokens = estimate_token_count(payload)
    return tokens <= max_tokens, tokens


def enforce_context_budget(payload: Any, max_tokens: int = 1500) -> int:
    """Enforce that the context payload fits within the token budget. Raises ContextBudgetExceededError on overflow."""
    is_valid, tokens = check_context_budget(payload, max_tokens)
    if not is_valid:
        raise ContextBudgetExceededError(tokens, max_tokens)
    return tokens


def is_revision_required_for_capability(
    capability_id: str,
    registry: CapabilityRegistry | None = None,
) -> bool:
    """Derive whether a capability requires expected_revision based on its contract revision_binding.

    Automatically derived from CapabilityRegistry:
    - revision_binding == 'canonical_project_state' -> True
    - revision_binding == 'none' -> False
    """
    reg = registry or default_capability_registry
    cap = reg.get(capability_id)
    if cap is None or cap.contract is None:
        return False
    return cap.contract.revision_binding == "canonical_project_state"


def validate_mutation_revision(
    context: UniversalSessionContext,
    capability_ids: list[str],
    registry: CapabilityRegistry | None = None,
) -> None:
    """Validate that expected_revision is present if any target capability requires canonical revision binding."""
    reg = registry or default_capability_registry
    for cid in capability_ids:
        if is_revision_required_for_capability(cid, reg):
            if context.expected_revision is None:
                raise MissingExpectedRevisionError(
                    f"Capability '{cid}' requires canonical project state revision binding, "
                    f"but expected_revision was not provided for project '{context.project_id}'."
                )
