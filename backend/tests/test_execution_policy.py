"""backend/tests/test_execution_policy.py — Phase 1 centralized Execution Policy tests.

Covers all four policy results (AUTO_APPROVED, REQUIRES_APPROVAL,
MANDATORY_HUMAN_REVIEW, DENIED) across: safe read, reversible mutation,
engineering mutation, safety-critical capability, missing scope, mandatory
human review, auto mode, step-by-step mode, and production environment.
"""

from __future__ import annotations

import pytest

from backend.core.capability_registry import CapabilityRegistry
from backend.core.command_bus import AuthenticatedPrincipal
from backend.core.execution_policy import (
    ExecutionMode,
    MutationType,
    PolicyContext,
    PolicyResult,
    build_policy_context,
    evaluate_execution_policy,
)


def _principal(scopes: list[str] | None = None, authenticated: bool = True) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="engineer-01",
        email="e@bazspark.io",
        role="engineer",
        scopes=scopes if scopes is not None else ["*"],
        is_authenticated=authenticated,
    )


def _ctx(**overrides) -> PolicyContext:
    base: dict = {
        "execution_mode": ExecutionMode.AUTO,
        "capability_id": "spatial.place_devices",
        "capability_known": True,
        "risk_class": "MEDIUM",
        "project_id": "proj-1",
        "principal_id": "engineer-01",
        "principal_authenticated": True,
        "principal_scopes": ("spatial:write",),
        "required_scopes": ("spatial:write",),
        "mutation_type": MutationType.REVERSIBLE_MUTATION,
        "reversibility": True,
        "mandatory_review": False,
        "governance_policy": {},
        "environment": "development",
    }
    base.update(overrides)
    return PolicyContext(**base)


# ── AUTO_APPROVED ────────────────────────────────────────────────────────────


def test_safe_read_auto_approved_in_both_modes() -> None:
    for mode in (ExecutionMode.AUTO, ExecutionMode.STEP_BY_STEP):
        decision = evaluate_execution_policy(
            _ctx(
                capability_id="compliance.verify_detector_spacing",
                risk_class="LOW",
                mutation_type=MutationType.READ_ONLY,
                reversibility=True,
                required_scopes=("compliance:read",),
                principal_scopes=("compliance:read",),
                execution_mode=mode,
            )
        )
        assert decision.result == PolicyResult.AUTO_APPROVED
        assert decision.mandatory_human_review is False


def test_reversible_mutation_auto_mode_auto_approved() -> None:
    decision = evaluate_execution_policy(_ctx())
    assert decision.result == PolicyResult.AUTO_APPROVED
    assert decision.reason == "SAFE_GOVERNED_OPERATION"


def test_auto_mode_does_not_downgrade_mandatory_review() -> None:
    """AUTO mode must NEVER turn MANDATORY_HUMAN_REVIEW into AUTO_APPROVED."""
    decision = evaluate_execution_policy(_ctx(mandatory_review=True))
    assert decision.result == PolicyResult.MANDATORY_HUMAN_REVIEW
    assert decision.mandatory_human_review is True


# ── REQUIRES_APPROVAL ────────────────────────────────────────────────────────


def test_reversible_mutation_step_by_step_requires_approval() -> None:
    decision = evaluate_execution_policy(_ctx(execution_mode=ExecutionMode.STEP_BY_STEP))
    assert decision.result == PolicyResult.REQUIRES_APPROVAL
    assert decision.reason == "STEP_BY_STEP_MODE_MUTATION"


def test_engineering_mutation_requires_approval_even_in_auto_mode() -> None:
    decision = evaluate_execution_policy(
        _ctx(
            capability_id="electrical.calculate_voltage_drop",
            risk_class="ENGINEERING_MUTATION",
            mutation_type=MutationType.ENGINEERING_MUTATION,
            reversibility=False,
            required_scopes=("electrical:write",),
            principal_scopes=("electrical:write",),
        )
    )
    assert decision.result == PolicyResult.REQUIRES_APPROVAL
    assert decision.reason == "ENGINEERING_MUTATION_REQUIRES_APPROVAL"


def test_non_reversible_mutation_requires_approval() -> None:
    decision = evaluate_execution_policy(
        _ctx(mutation_type=MutationType.REVERSIBLE_MUTATION, reversibility=False)
    )
    assert decision.result == PolicyResult.REQUIRES_APPROVAL
    assert decision.reason == "NON_REVERSIBLE_MUTATION_REQUIRES_APPROVAL"


def test_governance_require_all_mutations_requires_approval() -> None:
    decision = evaluate_execution_policy(
        _ctx(governance_policy={"requireApprovalForAllMutations": True})
    )
    assert decision.result == PolicyResult.REQUIRES_APPROVAL
    assert decision.reason == "GOVERNANCE_REQUIRES_APPROVAL"


# ── MANDATORY_HUMAN_REVIEW ───────────────────────────────────────────────────


def test_safety_critical_capability_mandatory_review() -> None:
    decision = evaluate_execution_policy(
        _ctx(
            risk_class="CRITICAL",
            mutation_type=MutationType.SAFETY_CRITICAL,
            reversibility=False,
            mandatory_review=True,
        )
    )
    assert decision.result == PolicyResult.MANDATORY_HUMAN_REVIEW
    assert decision.mandatory_human_review is True


def test_production_environment_safety_critical_mandatory_review() -> None:
    """Production + safety-critical always halts for human review."""
    decision = evaluate_execution_policy(
        _ctx(
            environment="production",
            mutation_type=MutationType.SAFETY_CRITICAL,
            risk_class="CRITICAL",
        )
    )
    assert decision.result == PolicyResult.MANDATORY_HUMAN_REVIEW


def test_governance_mandatory_review_list_holds_in_auto_mode() -> None:
    decision = evaluate_execution_policy(
        _ctx(
            governance_policy={"mandatoryReviewCapabilities": ["spatial.place_devices"]},
        )
    )
    assert decision.result == PolicyResult.MANDATORY_HUMAN_REVIEW
    assert decision.reason == "GOVERNANCE_MANDATORY_REVIEW"


# ── DENIED ───────────────────────────────────────────────────────────────────


def test_missing_scope_denied_not_converted_to_approval() -> None:
    """Insufficient authorization is DENIED — never an approval request."""
    decision = evaluate_execution_policy(
        _ctx(required_scopes=("electrical:write",), principal_scopes=("spatial:read",))
    )
    assert decision.result == PolicyResult.DENIED
    assert decision.reason.startswith("INSUFFICIENT_SCOPE")


def test_unauthenticated_principal_denied() -> None:
    decision = evaluate_execution_policy(_ctx(principal_authenticated=False))
    assert decision.result == PolicyResult.DENIED
    assert decision.reason == "PRINCIPAL_NOT_AUTHENTICATED"


def test_unknown_capability_denied() -> None:
    decision = evaluate_execution_policy(_ctx(capability_known=False, risk_class="UNKNOWN"))
    assert decision.result == PolicyResult.DENIED
    assert decision.reason == "UNKNOWN_CAPABILITY"


def test_governance_denied_capability() -> None:
    decision = evaluate_execution_policy(
        _ctx(governance_policy={"deniedCapabilities": ["spatial.place_devices"]})
    )
    assert decision.result == PolicyResult.DENIED
    assert decision.reason == "GOVERNANCE_DENIED_CAPABILITY"


# ── build_policy_context derives metadata from the registry (no duplication) ─


def test_build_context_from_real_registry() -> None:
    registry = CapabilityRegistry()
    principal = _principal(["spatial:write"])

    ctx = build_policy_context(
        registry,
        "spatial.place_devices",
        principal,
        execution_mode=ExecutionMode.AUTO,
        project_id="proj-1",
        environment="development",
    )
    assert ctx.capability_known is True
    assert ctx.risk_class == "MEDIUM"
    assert ctx.required_scopes == ("spatial:write",)
    assert ctx.mutation_type == MutationType.REVERSIBLE_MUTATION
    decision = evaluate_execution_policy(ctx)
    assert decision.result == PolicyResult.AUTO_APPROVED

    # Engineering-mutating capability from the registry requires approval.
    ctx2 = build_policy_context(
        registry,
        "electrical.calculate_voltage_drop",
        _principal(["electrical:write"]),
        execution_mode=ExecutionMode.AUTO,
        environment="development",
    )
    assert ctx2.mutation_type == MutationType.ENGINEERING_MUTATION
    assert evaluate_execution_policy(ctx2).result == PolicyResult.REQUIRES_APPROVAL

    # Read-only compliance capability auto-approves.
    ctx3 = build_policy_context(
        registry,
        "compliance.verify_detector_spacing",
        _principal(["compliance:read"]),
        environment="development",
    )
    assert ctx3.mutation_type == MutationType.READ_ONLY
    assert evaluate_execution_policy(ctx3).result == PolicyResult.AUTO_APPROVED


def test_build_context_unknown_capability_denies() -> None:
    ctx = build_policy_context(
        CapabilityRegistry(), "does.not.exist", _principal(["*"]), environment="development"
    )
    assert ctx.capability_known is False
    assert evaluate_execution_policy(ctx).result == PolicyResult.DENIED


def test_decision_is_deterministic() -> None:
    ctx = _ctx()
    d1 = evaluate_execution_policy(ctx)
    d2 = evaluate_execution_policy(ctx)
    assert d1 == d2


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"mutation_type": MutationType.READ_ONLY}, PolicyResult.AUTO_APPROVED),
        ({"execution_mode": ExecutionMode.STEP_BY_STEP}, PolicyResult.REQUIRES_APPROVAL),
        ({"mandatory_review": True}, PolicyResult.MANDATORY_HUMAN_REVIEW),
        ({"principal_authenticated": False}, PolicyResult.DENIED),
    ],
)
def test_precedence_matrix(overrides: dict, expected: PolicyResult) -> None:
    assert evaluate_execution_policy(_ctx(**overrides)).result == expected
