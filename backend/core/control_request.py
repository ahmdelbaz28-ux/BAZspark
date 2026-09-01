"""backend/core/control_request.py — Universal ControlRequest Contract.

BAZspark V2.2 Phase 6 Universal ControlRequest Specification:
- Single authoritative definition source for all execution intents across all surfaces.
- Consumes UniversalSessionContext (Phase 3 canonical model — reused, not redefined).
- Single source of truth for Pydantic validation and JSON Schema derivation.
- Uniformly consumable by Web Chat, REST APIs, WebSocket streams, and future CLI/adapters.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.session_context import UniversalSessionContext


class ControlRequestValidationError(ValueError):
    """Raised when ControlRequest validation fails."""


class ControlRequest(BaseModel):
    """Universal ControlRequest Model per BAZSPARK_PLAN_V2_2 §5 Phase 6.

    Attributes:
        intent: Natural language prompt, instruction, or explicit intent summary.
        capability_ref: Optional target capability identifier reference.
        context: Canonical UniversalSessionContext (project_id, model_id, entity_ids, expected_revision, ui_surface).
        params: Execution parameters, payload spec, or template overrides.
        policy_hints: Execution policy preferences (approval_mode, governance_policy, dry_run flag).
        metadata: Extensible request metadata (trace_id, timestamp, client_version).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    intent: str = Field(..., min_length=1, description="Natural language prompt or explicit intent summary")
    capability_ref: str | None = Field(default=None, description="Optional target capability identifier reference")
    context: UniversalSessionContext = Field(..., description="Canonical Universal Session Context")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters or payload specification")
    policy_hints: dict[str, Any] = Field(default_factory=dict, description="Policy and governance hints")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extensible telemetry/trace metadata")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ControlRequest:
        """Parse a ControlRequest from a dictionary with comprehensive polymorphic key support."""
        if not data or not isinstance(data, dict):
            raise ControlRequestValidationError("ControlRequest data must be a non-empty dictionary")

        # 1. Resolve intent
        intent = str(data.get("intent") or data.get("prompt") or data.get("message") or "").strip()
        if not intent:
            raise ControlRequestValidationError("ControlRequest requires a non-empty 'intent' or 'prompt'")

        # 2. Resolve capability_ref
        raw_cap = data.get("capability_ref") or data.get("capabilityRef") or data.get("capability_id") or data.get("capabilityId")
        capability_ref = str(raw_cap).strip() if raw_cap else None

        # 3. Resolve context (nested or flat)
        raw_ctx = data.get("context")
        if isinstance(raw_ctx, UniversalSessionContext):
            context = raw_ctx
        elif isinstance(raw_ctx, dict):
            context = UniversalSessionContext.from_dict(raw_ctx)
        else:
            # Reconstruct from flat top-level keys
            context = UniversalSessionContext.from_dict(data)

        # 4. Resolve params
        raw_params = data.get("params") or data.get("composite_spec") or data.get("compositeSpec") or data.get("spec") or data.get("payload")
        params = dict(raw_params) if isinstance(raw_params, dict) else {}
        if "explicit_capabilities" in data and "explicit_capabilities" not in params:
            params["explicit_capabilities"] = data["explicit_capabilities"]
        elif "explicitCapabilities" in data and "explicit_capabilities" not in params:
            params["explicit_capabilities"] = data["explicitCapabilities"]

        # 5. Resolve policy_hints
        raw_hints = data.get("policy_hints") or data.get("policyHints")
        hints = dict(raw_hints) if isinstance(raw_hints, dict) else {}
        if "approval_mode" in data and "approval_mode" not in hints:
            hints["approval_mode"] = data["approval_mode"]
        elif "approvalMode" in data and "approval_mode" not in hints:
            hints["approval_mode"] = data["approvalMode"]
        if "governance_policy" in data and "governance_policy" not in hints:
            hints["governance_policy"] = data["governance_policy"]
        elif "governancePolicy" in data and "governance_policy" not in hints:
            hints["governance_policy"] = data["governancePolicy"]
        if "dry_run" in data and "dry_run" not in hints:
            hints["dry_run"] = bool(data["dry_run"])
        elif "is_dry_run" in data and "dry_run" not in hints:
            hints["dry_run"] = bool(data["is_dry_run"])

        # 6. Resolve metadata
        raw_meta = data.get("metadata")
        metadata = dict(raw_meta) if isinstance(raw_meta, dict) else {}

        return cls(
            intent=intent,
            capability_ref=capability_ref,
            context=context,
            params=params,
            policy_hints=hints,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert ControlRequest into a canonical dictionary representation."""
        return {
            "intent": self.intent,
            "capability_ref": self.capability_ref,
            "context": self.context.to_dict() if hasattr(self.context, "to_dict") else self.context,
            "params": dict(self.params),
            "policy_hints": dict(self.policy_hints),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def get_json_schema(cls) -> dict[str, Any]:
        """Derive JSON Schema directly from the Pydantic ControlRequest model (single source of truth)."""
        return cls.model_json_schema()
