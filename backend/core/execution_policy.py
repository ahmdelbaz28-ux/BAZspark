"""backend/core/execution_policy.py — Centralized, Deterministic Execution Policy.

Phase 1 (AI-FIRST transformation) foundation — the SINGLE authoritative
execution-policy abstraction for the entire backend.

Guarantees:
- Deterministic: pure function of the policy context. No LLM calls, no
  natural-language interpretation, no randomness, no I/O.
- Centralized: all approval/denial decisions flow through
  :func:`evaluate_execution_policy`. Routers MUST NOT scatter equivalent
  policy decisions.
- Safety dominates convenience: the order of precedence is
  INVALID/UNAUTHORIZED → DENIED, MANDATORY HUMAN REVIEW →
  MANDATORY_HUMAN_REVIEW, GOVERNED MUTATION → REQUIRES_APPROVAL, SAFE
  GOVERNED OPERATION → AUTO_APPROVED.
- Auto Approval is NOT a safety bypass: ``execution_mode = AUTO`` only
  proceeds automatically when the policy returns ``AUTO_APPROVED``.
  ``MANDATORY_HUMAN_REVIEW`` always halts the run and insufficient
  authorization is always DENIED (never converted into an approval request).

Capability metadata is obtained from the existing
``backend.core.capability_registry`` — capability definitions are NOT
duplicated here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.core.capability_registry import CapabilityDefinition
    from backend.core.command_bus import AuthenticatedPrincipal


class PolicyResult(StrEnum):
    """The exactly-one outcome of a policy evaluation."""

    AUTO_APPROVED = "AUTO_APPROVED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    MANDATORY_HUMAN_REVIEW = "MANDATORY_HUMAN_REVIEW"
    DENIED = "DENIED"


class ExecutionMode(StrEnum):
    """Run-level execution mode requested by the caller (convenience only)."""

    AUTO = "AUTO"
    STEP_BY_STEP = "STEP_BY_STEP"


class MutationType(StrEnum):
    """Engineering classification of what a capability does to canonical state."""

    READ_ONLY = "READ_ONLY"
    REVERSIBLE_MUTATION = "REVERSIBLE_MUTATION"
    ENGINEERING_MUTATION = "ENGINEERING_MUTATION"
    SAFETY_CRITICAL = "SAFETY_CRITICAL"


@dataclass(frozen=True)
class ExecutionPolicyDecision:
    """Structured, deterministic policy decision."""

    result: PolicyResult
    reason: str
    mandatory_human_review: bool
    risk_class: str
    capability_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "reason": self.reason,
            "mandatoryHumanReview": self.mandatory_human_review,
            "riskClass": self.risk_class,
            "capabilityId": self.capability_id,
        }


@dataclass(frozen=True)
class PolicyContext:
    """Immutable input to the policy evaluator.

    All fields are server-derived or server-validated. Client-supplied values
    (risk class, scopes, capability metadata) MUST NOT be trusted — build the
    context via :func:`build_policy_context` from the capability registry.
    """

    execution_mode: ExecutionMode
    capability_id: str
    capability_known: bool
    risk_class: str
    project_id: str
    principal_id: str
    principal_authenticated: bool
    principal_scopes: tuple[str, ...]
    required_scopes: tuple[str, ...]
    mutation_type: MutationType
    reversibility: bool
    mandatory_review: bool
    governance_policy: Mapping[str, Any] = field(default_factory=dict)
    environment: str = "production"


# Risk classes used by the existing capability registry.
_RISK_READ_ONLY = frozenset({"LOW"})
_RISK_REVERSIBLE = frozenset({"MEDIUM"})
_RISK_ENGINEERING = frozenset({"HIGH", "ENGINEERING_MUTATION"})
_RISK_SAFETY_CRITICAL = frozenset({"CRITICAL", "SAFETY_CRITICAL"})


def _default_environment() -> str:
    """Resolve the deployment environment from server configuration only."""
    env = (
        os.environ.get("FIREAI_ENV")
        or os.environ.get("NODE_ENV")
        or "production"
    )
    return str(env).strip().lower()


def build_policy_context(
    capability_registry: Any,
    capability_id: str,
    principal: AuthenticatedPrincipal,
    *,
    execution_mode: ExecutionMode | str = ExecutionMode.AUTO,
    project_id: str = "",
    governance_policy: Mapping[str, Any] | None = None,
    environment: str | None = None,
    mutation_type: MutationType | str | None = None,
    reversibility: bool | None = None,
    mandatory_review: bool | None = None,
) -> PolicyContext:
    """Build a :class:`PolicyContext` from authoritative capability metadata.

    Capability metadata (risk class, required scopes) is loaded from the
    capability registry — never from the client. Explicit overrides exist for
    callers that hold richer server-side metadata; they must not be fed from
    untrusted input.
    """
    cap: CapabilityDefinition | None = capability_registry.get(capability_id)
    if cap is not None:
        risk_class = str(cap.risk_class).upper()
        required_scopes = tuple(cap.required_scopes)
    else:
        risk_class = "UNKNOWN"
        required_scopes = ()

    if mutation_type is not None:
        mt = MutationType(mutation_type)
    elif risk_class in _RISK_SAFETY_CRITICAL:
        mt = MutationType.SAFETY_CRITICAL
    elif risk_class in _RISK_ENGINEERING:
        mt = MutationType.ENGINEERING_MUTATION
    elif risk_class in _RISK_REVERSIBLE:
        mt = MutationType.REVERSIBLE_MUTATION
    elif risk_class in _RISK_READ_ONLY:
        mt = MutationType.READ_ONLY
    else:
        mt = MutationType.ENGINEERING_MUTATION  # unknown risk → treat as mutation

    if reversibility is not None:
        rev = bool(reversibility)
    else:
        rev = mt in (MutationType.READ_ONLY, MutationType.REVERSIBLE_MUTATION)

    if mandatory_review is not None:
        mhr = bool(mandatory_review)
    else:
        mhr = mt == MutationType.SAFETY_CRITICAL

    return PolicyContext(
        execution_mode=ExecutionMode(execution_mode),
        capability_id=capability_id,
        capability_known=cap is not None,
        risk_class=risk_class,
        project_id=project_id,
        principal_id=principal.user_id,
        principal_authenticated=bool(principal.is_authenticated),
        principal_scopes=tuple(principal.scopes),
        required_scopes=required_scopes,
        mutation_type=mt,
        reversibility=rev,
        mandatory_review=mhr,
        governance_policy=dict(governance_policy or {}),
        environment=(environment or _default_environment()).strip().lower(),
    )


def _has_scope(principal_scopes: tuple[str, ...], scope: str) -> bool:
    return "*" in principal_scopes or scope in principal_scopes


def evaluate_execution_policy(ctx: PolicyContext) -> ExecutionPolicyDecision:
    """Evaluate the execution policy deterministically.

    Order of precedence (safety dominates convenience):

    1. Unauthenticated principal                          → DENIED
    2. Unknown capability                                 → DENIED
    3. Governance explicitly denies the capability        → DENIED
    4. Insufficient scope / authorization                 → DENIED
       (NEVER converted into an approval request)
    5. Mandatory human review triggers                    → MANDATORY_HUMAN_REVIEW
       (capability flag, SAFETY_CRITICAL risk, governance
       mandatory-review list, or production + safety-critical)
       Auto Approval can NEVER downgrade this result.
    6. Read-only operation                                → AUTO_APPROVED
    7. STEP_BY_STEP mode + any mutation                   → REQUIRES_APPROVAL
    8. Governance requires approval for all mutations     → REQUIRES_APPROVAL
    9. Non-reversible / engineering mutation              → REQUIRES_APPROVAL
    10. Safe governed, reversible mutation                → AUTO_APPROVED
    """
    cap_id = ctx.capability_id

    # 1. Authentication
    if not ctx.principal_authenticated:
        return ExecutionPolicyDecision(
            result=PolicyResult.DENIED,
            reason="PRINCIPAL_NOT_AUTHENTICATED",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 2. Capability existence
    if not ctx.capability_known:
        return ExecutionPolicyDecision(
            result=PolicyResult.DENIED,
            reason="UNKNOWN_CAPABILITY",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    gov = ctx.governance_policy or {}

    # 3. Governance explicit denial
    denied_caps = gov.get("deniedCapabilities") or gov.get("denied_capabilities") or []
    if isinstance(denied_caps, (list, tuple, set)) and cap_id in set(denied_caps):
        return ExecutionPolicyDecision(
            result=PolicyResult.DENIED,
            reason="GOVERNANCE_DENIED_CAPABILITY",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 4. Authorization (scope) — denial, never an approval request
    missing = [s for s in ctx.required_scopes if not _has_scope(ctx.principal_scopes, s)]
    if missing:
        return ExecutionPolicyDecision(
            result=PolicyResult.DENIED,
            reason=f"INSUFFICIENT_SCOPE:{missing[0]}",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    is_mutation = ctx.mutation_type != MutationType.READ_ONLY

    # 5. Mandatory human review — cannot be bypassed by AUTO mode
    mhr_list = (
        gov.get("mandatoryReviewCapabilities")
        or gov.get("mandatory_review_capabilities")
        or []
    )
    governance_mhr = isinstance(mhr_list, (list, tuple, set)) and cap_id in set(mhr_list)
    production_safety_critical = (
        ctx.environment in ("production", "prod") and ctx.mutation_type == MutationType.SAFETY_CRITICAL
    )
    mandatory_review = bool(
        ctx.mandatory_review
        or ctx.mutation_type == MutationType.SAFETY_CRITICAL
        or governance_mhr
        or production_safety_critical
    )
    if mandatory_review:
        if governance_mhr:
            reason = "GOVERNANCE_MANDATORY_REVIEW"
        elif ctx.mutation_type == MutationType.SAFETY_CRITICAL:
            reason = (
                "SAFETY_CRITICAL_CAPABILITY"
                if production_safety_critical
                else "SAFETY_CRITICAL_REQUIRES_HUMAN_REVIEW"
            )
        else:
            reason = "CAPABILITY_MANDATORY_REVIEW_FLAG"
        return ExecutionPolicyDecision(
            result=PolicyResult.MANDATORY_HUMAN_REVIEW,
            reason=reason,
            mandatory_human_review=True,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 6. Read-only operations are safe in every mode
    if not is_mutation:
        return ExecutionPolicyDecision(
            result=PolicyResult.AUTO_APPROVED,
            reason="READ_ONLY_OPERATION",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 7. STEP_BY_STEP mode: every mutation requires explicit approval
    if ctx.execution_mode == ExecutionMode.STEP_BY_STEP:
        return ExecutionPolicyDecision(
            result=PolicyResult.REQUIRES_APPROVAL,
            reason="STEP_BY_STEP_MODE_MUTATION",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 8. Governance-wide approval requirement for mutations
    require_all = gov.get(
        "requireApprovalForAllMutations", gov.get("require_approval_for_all_mutations", False)
    )
    if bool(require_all):
        return ExecutionPolicyDecision(
            result=PolicyResult.REQUIRES_APPROVAL,
            reason="GOVERNANCE_REQUIRES_APPROVAL",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 9. Non-reversible / engineering mutations require approval
    if not ctx.reversibility or ctx.mutation_type == MutationType.ENGINEERING_MUTATION:
        return ExecutionPolicyDecision(
            result=PolicyResult.REQUIRES_APPROVAL,
            reason="ENGINEERING_MUTATION_REQUIRES_APPROVAL"
            if ctx.mutation_type == MutationType.ENGINEERING_MUTATION
            else "NON_REVERSIBLE_MUTATION_REQUIRES_APPROVAL",
            mandatory_human_review=False,
            risk_class=ctx.risk_class,
            capability_id=cap_id,
        )

    # 10. Safe governed reversible mutation under AUTO mode
    return ExecutionPolicyDecision(
        result=PolicyResult.AUTO_APPROVED,
        reason="SAFE_GOVERNED_OPERATION",
        mandatory_human_review=False,
        risk_class=ctx.risk_class,
        capability_id=cap_id,
    )


class ExecutionPolicyEvaluator:
    """Thin stateless façade over :func:`evaluate_execution_policy`.

    Exists so callers can inject/patch the policy as a collaborator without
    touching call sites.
    """

    def build_context(self, *args: Any, **kwargs: Any) -> PolicyContext:
        return build_policy_context(*args, **kwargs)

    def evaluate(self, ctx: PolicyContext) -> ExecutionPolicyDecision:
        return evaluate_execution_policy(ctx)


default_execution_policy = ExecutionPolicyEvaluator()
