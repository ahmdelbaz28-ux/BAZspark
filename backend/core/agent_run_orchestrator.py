"""backend/core/agent_run_orchestrator.py — Server-Authoritative Agent Run Lifecycle.

Phase 1 (AI-FIRST transformation): binds the durable :class:`AgentRunStore`,
the centralized :mod:`execution_policy`, and the existing deterministic
``CommandBus`` into a resumable, persistent Agent Run lifecycle.

Pipeline implemented around the EXISTING deterministic spine:

    Intent → Plan/Steps → Execution Policy → AUTO_APPROVED / REQUIRES_APPROVAL /
    MANDATORY_HUMAN_REVIEW / DENIED → Dry-Run-free deterministic Commit (OCC) →
    Persistent State → Audit

Non-negotiable rules enforced here:
- The backend is the security authority: every lifecycle operation
  (start/resume/pause/cancel/retry/approve/reject) authenticates and
  authorizes the caller server-side.
- Auto Approval is NOT a safety bypass: ``AUTO`` mode proceeds automatically
  ONLY when policy returns ``AUTO_APPROVED``. ``MANDATORY_HUMAN_REVIEW`` and
  ``REQUIRES_APPROVAL`` always halt the run into ``WAITING_APPROVAL``;
  ``DENIED`` fails the run.
- Approvals are bound server-side to run + step + project revision +
  capability + principal + plan/payload hashes. A client CANNOT alter the
  executed command through an approval request.
- Retry never blindly replays a mutation: the deterministic per-step
  ``commandId`` plus the CommandBus persistent idempotency ledger guarantees
  a committed step is replayed from cache, never double-committed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.agent_run_store import (
    TERMINAL_STATUSES,
    AgentRun,
    AgentRunStore,
    ApprovalDecisionValue,
    ApprovalMode,
    InvalidTransitionError,
    PendingApprovalStatus,
    RunConcurrencyConflictError,
    RunNotFoundError,
    RunStatus,
    default_agent_run_store,
)
from backend.core.capability_registry import default_capability_registry
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
    default_command_bus,
)
from backend.core.execution_policy import (
    ExecutionPolicyDecision,
    PolicyResult,
    build_policy_context,
    evaluate_execution_policy,
)

logger = logging.getLogger(__name__)


class RunPermissionError(Exception):
    """Caller is not authorized to operate on the Agent Run."""


class InvalidRunStateError(Exception):
    """Operation is not valid for the run's current persisted state."""


class StaleApprovalError(Exception):
    """Approval is stale (project revision drifted / approval no longer pending)."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_json(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _step_command_id(run_id: str, step_id: str) -> str:
    """Deterministic per-step command id — the idempotency anchor for retries."""
    return f"cmd-{run_id}-{step_id}"


class AgentRunOrchestrator:
    """Server-authoritative Agent Run lifecycle orchestrator."""

    def __init__(
        self,
        command_bus: CommandBus | None = None,
        capability_registry: Any | None = None,
        run_store: AgentRunStore | None = None,
        environment: str | None = None,
    ) -> None:
        self._bus = command_bus or default_command_bus
        self._registry = capability_registry or default_capability_registry
        self._store = run_store or default_agent_run_store
        self._environment = environment

    # ── Authorization ────────────────────────────────────────────────────

    @staticmethod
    def _authorize(run: AgentRun, caller_id: str, caller_is_admin: bool = False) -> None:
        """Only the owning principal (or an admin) may operate on a run."""
        if caller_is_admin or caller_id == run.user_id:
            return
        raise RunPermissionError(
            f"Principal '{caller_id}' is not authorized to operate on run '{run.run_id}' "
            f"(owner: '{run.user_id}')."
        )

    # ── Validation helpers ───────────────────────────────────────────────

    def _validate_steps(self, steps: list[dict[str, Any]]) -> None:
        if not steps:
            raise ValueError("Agent Run plan must contain at least one step.")
        seen: set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("Each plan step must be an object.")
            step_id = str(step.get("step_id", "")).strip()
            capability_id = str(step.get("capability_id", "")).strip()
            if not step_id or not capability_id:
                raise ValueError("Each step requires 'step_id' and 'capability_id'.")
            if step_id in seen:
                raise ValueError(f"Duplicate step_id '{step_id}' in plan.")
            seen.add(step_id)
            if self._registry.get(capability_id) is None:
                raise ValueError(f"Unknown capability '{capability_id}' in plan.")
            if not isinstance(step.get("payload", {}), dict):
                raise ValueError(f"Step '{step_id}' payload must be an object.")

    def _plan_hash(self, plan: dict[str, Any], steps: list[dict[str, Any]]) -> str:
        return _sha256_json({"plan": plan, "steps": steps})

    def _step_payload_hash(self, step: dict[str, Any]) -> str:
        return _sha256_json(step.get("payload", {}))

    def _find_step(self, run: AgentRun, step_id: str) -> dict[str, Any]:
        for step in run.steps:
            if step.get("step_id") == step_id:
                return step
        raise ValueError(f"Step '{step_id}' not found in run '{run.run_id}'.")

    def _evaluate_step_policy(
        self,
        run: AgentRun,
        principal: AuthenticatedPrincipal,
        step: dict[str, Any],
    ) -> ExecutionPolicyDecision:
        governance = run.plan.get("governance_policy") or None
        ctx = build_policy_context(
            self._registry,
            str(step["capability_id"]),
            principal,
            execution_mode=run.approval_mode,
            project_id=run.project_id,
            governance_policy=governance if isinstance(governance, dict) else None,
            environment=self._environment,
        )
        return evaluate_execution_policy(ctx)

    # ── Start ────────────────────────────────────────────────────────────

    def start_run(
        self,
        principal: AuthenticatedPrincipal,
        *,
        project_id: str,
        steps: list[dict[str, Any]],
        approval_mode: ApprovalMode | str = ApprovalMode.AUTO,
        conversation_id: str = "",
        plan: dict[str, Any] | None = None,
        governance_policy: dict[str, Any] | None = None,
    ) -> AgentRun:
        """Create a durable run, validate the plan, and begin execution."""
        if not principal.is_authenticated:
            raise RunPermissionError("Principal is not authenticated.")
        self._validate_steps(steps)

        plan_doc = dict(plan or {})
        if governance_policy:
            plan_doc["governance_policy"] = governance_policy
        # Bind the server-validated principal scopes into the immutable plan
        # fingerprint so resumed/retried continuations re-evaluate policy with
        # the SAME authorization context the run was created under.
        plan_doc["principal_scopes"] = list(principal.scopes)
        plan_doc["plan_hash"] = self._plan_hash(plan_doc, steps)

        run = self._store.create_run(
            conversation_id=conversation_id,
            user_id=principal.user_id,
            project_id=project_id,
            approval_mode=ApprovalMode(approval_mode),
            plan=plan_doc,
            steps=[dict(s) for s in steps],
            status=RunStatus.PLANNING,
        )
        # PLANNING → READY (server-validated transition)
        run = self._store.transition_run(run.run_id, RunStatus.READY)
        return self._advance(run, principal)

    # ── Core execution loop ──────────────────────────────────────────────

    def _advance(self, run: AgentRun, principal: AuthenticatedPrincipal) -> AgentRun:
        """Execute auto-approved steps until the run halts or completes.

        Halts (persisted) on: WAITING_APPROVAL, PAUSED, FAILED, CANCELLED,
        COMPLETED. Re-reads persisted state before EVERY step so concurrent
        cancel/pause operations deterministically prevent subsequent steps.
        """
        while True:
            run = self._store.require_run(run.run_id)

            if run.status in (
                RunStatus.WAITING_APPROVAL,
                RunStatus.PAUSED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.COMPLETED,
            ):
                return run

            if run.status == RunStatus.READY:
                run = self._store.transition_run(run.run_id, RunStatus.RUNNING)
                continue

            # run.status == RUNNING
            completed = set(run.completed_steps)
            next_step = next((s for s in run.steps if s.get("step_id") not in completed), None)

            if next_step is None:
                # All steps completed → finalize.
                run = self._finalize_run(run)
                return run

            step_id = str(next_step["step_id"])
            run = self._store.update_progress(
                run.run_id, expected_version=run.version, current_step=step_id
            )

            # Policy evaluation (deterministic, centralized).
            decision = self._evaluate_step_policy(run, principal, next_step)

            if decision.result == PolicyResult.DENIED:
                return self._fail_step(run, step_id, "POLICY_DENIED", decision.reason)

            if decision.result in (
                PolicyResult.REQUIRES_APPROVAL,
                PolicyResult.MANDATORY_HUMAN_REVIEW,
            ):
                return self._request_approval(run, principal, next_step, decision)

            # AUTO_APPROVED → deterministic execution with OCC.
            result = self._execute_step(run, principal, next_step)
            if not result["success"]:
                return self._fail_step(
                    run,
                    step_id,
                    result.get("errorCode") or "STEP_EXECUTION_FAILED",
                    result.get("errorMessage") or "Step execution failed.",
                    artifacts=result.get("resultData") or {},
                )

            run = self._record_step_completion(run, step_id, result)
            # Loop continues: re-reads persisted state (cancel/pause aware).

    def _execute_step(
        self,
        run: AgentRun,
        principal: AuthenticatedPrincipal,
        step: dict[str, Any],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Execute one step through the existing deterministic CommandBus (OCC).

        Re-checks the persisted run status immediately before dispatch so a
        concurrent cancel prevents unsafe commits. Uses the deterministic
        per-step commandId so retries are protected by the CommandBus
        persistent idempotency ledger (a previously committed step replays
        its cached result instead of duplicating the mutation).
        """
        fresh = self._store.get_run(run.run_id)
        if fresh is None:
            raise RunNotFoundError(run.run_id)
        if fresh.status != RunStatus.RUNNING:
            return {
                "success": False,
                "errorCode": "RUN_NO_LONGER_RUNNING",
                "errorMessage": f"Run status is {fresh.status.value}; step execution aborted.",
                "resultData": {},
            }

        cap = self._registry.get(str(step["capability_id"]))
        if cap is None:
            return {
                "success": False,
                "errorCode": "UNKNOWN_CAPABILITY",
                "errorMessage": f"Capability '{step['capability_id']}' is not registered.",
                "resultData": {},
            }

        if expected_revision is None:
            expected_revision = self._bus.get_project_revision(run.project_id)

        command = DomainCommand(
            commandId=_step_command_id(run.run_id, str(step["step_id"])),
            correlationId=f"corr-{run.run_id}",
            capabilityId=str(step["capability_id"]),
            projectId=run.project_id,
            expectedRevision=int(expected_revision),
            timestamp=_now_iso(),
            principal=principal,
            riskClass=str(cap.risk_class),
            isDryRun=False,
            payload=dict(step.get("payload", {})),
        )
        result = self._bus.execute(command)
        return {
            "success": result.success,
            "errorCode": result.errorCode,
            "errorMessage": result.errorMessage,
            "revision": result.revision,
            "resultData": result.resultData,
            "auditReference": result.event.auditReference if result.event else "",
        }

    def _record_step_completion(
        self, run: AgentRun, step_id: str, result: dict[str, Any]
    ) -> AgentRun:
        completed = list(run.completed_steps) + [step_id]
        artifacts = dict(run.artifacts)
        artifacts[step_id] = {
            "revision": result.get("revision"),
            "auditReference": result.get("auditReference", ""),
        }
        recovery = dict(run.recovery_state)
        recovery["last_completed_revision"] = result.get("revision")
        try:
            return self._store.update_progress(
                run.run_id,
                expected_version=run.version,
                completed_steps=completed,
                artifacts=artifacts,
                recovery_state=recovery,
                current_step=None,
            )
        except RunConcurrencyConflictError:
            # A concurrent lifecycle operation (cancel/pause) won the race
            # after the step committed. The persisted state is authoritative;
            # never clobber it with stale progress.
            logger.info(
                "Run '%s' modified concurrently after step completion; "
                "deferring to persisted state.",
                run.run_id,
            )
            return self._store.require_run(run.run_id)

    def _fail_step(
        self,
        run: AgentRun,
        step_id: str,
        error_code: str,
        error_message: str,
        artifacts: dict[str, Any] | None = None,
    ) -> AgentRun:
        failed = list(run.failed_steps) + [
            {"step_id": step_id, "error_code": error_code, "error_message": error_message[:500]}
        ]
        recovery = dict(run.recovery_state)
        recovery["failed_step"] = step_id
        recovery["failure_error_code"] = error_code
        recovery["recoverable_via"] = "run_retry"
        merged_artifacts = dict(run.artifacts)
        if artifacts:
            merged_artifacts[f"_error_{step_id}"] = artifacts
        try:
            return self._store.transition_run(
                run.run_id,
                RunStatus.FAILED,
                failed_steps=failed,
                recovery_state=recovery,
                artifacts=merged_artifacts,
                current_step=step_id,
            )
        except InvalidTransitionError:
            # A concurrent operation moved the run to a terminal state
            # (e.g. cancelled mid-flight). Never overwrite terminal state —
            # surface the authoritative persisted state instead.
            logger.info(
                "Run '%s' reached terminal state during failure recording; "
                "preserving terminal state.",
                run.run_id,
            )
            return self._store.require_run(run.run_id)

    def _finalize_run(self, run: AgentRun) -> AgentRun:
        audit_payload = {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "user_id": run.user_id,
            "completed_steps": run.completed_steps,
            "finished_at": _now_iso(),
        }
        audit_ref = _sha256_json(audit_payload)
        return self._store.transition_run(
            run.run_id,
            RunStatus.COMPLETED,
            set_completed_at=True,
            current_step=None,
            audit_reference=audit_ref,
            recovery_state={**run.recovery_state, "finalized": True},
        )

    def _request_approval(
        self,
        run: AgentRun,
        principal: AuthenticatedPrincipal,
        step: dict[str, Any],
        decision: ExecutionPolicyDecision,
    ) -> AgentRun:
        """Persist a server-side pending approval bound to the exact context.

        Reuses an existing LIVE (PENDING) approval for the same run+step when
        one exists (e.g. resume after pause) instead of duplicating it; a
        decided/cancelled historical approval is preserved immutably and a NEW
        approval record is created.
        """
        step_id = str(step["step_id"])
        current_rev = self._bus.get_project_revision(run.project_id)
        existing = self._store.get_pending_approval_for_step(run.run_id, step_id)
        if existing is not None and existing.status == PendingApprovalStatus.PENDING:
            pa = existing
        else:
            pa = self._store.create_pending_approval(
                run_id=run.run_id,
                step_id=step_id,
                project_id=run.project_id,
                project_revision=current_rev,
                capability_id=str(step["capability_id"]),
                principal_id=principal.user_id,
                approval_mode=run.approval_mode,
                policy_result=decision.result.value,
                plan_hash=str(run.plan.get("plan_hash", "")),
                step_payload_hash=self._step_payload_hash(step),
            )
        return self._store.transition_run(
            run.run_id,
            RunStatus.WAITING_APPROVAL,
            expected_version=run.version,
            pending_approval_id=pa.approval_id,
            current_step=step_id,
            recovery_state={
                **run.recovery_state,
                "awaiting_approval": pa.approval_id,
                "policy_result": decision.result.value,
                "policy_reason": decision.reason,
            },
        )

    # ── Status ───────────────────────────────────────────────────────────

    def get_run_status(
        self, caller_id: str, run_id: str, caller_is_admin: bool = False
    ) -> AgentRun:
        run = self._store.require_run(run_id)
        self._authorize(run, caller_id, caller_is_admin)
        return run

    # ── Pause / Cancel ───────────────────────────────────────────────────

    def pause_run(self, caller_id: str, run_id: str, caller_is_admin: bool = False) -> AgentRun:
        run = self._store.require_run(run_id)
        self._authorize(run, caller_id, caller_is_admin)
        if run.status not in (RunStatus.RUNNING, RunStatus.WAITING_APPROVAL):
            raise InvalidRunStateError(
                f"Run '{run_id}' cannot be paused from status {run.status.value}."
            )
        return self._store.transition_run(
            run.run_id,
            RunStatus.PAUSED,
            recovery_state={
                **run.recovery_state,
                "paused_at": _now_iso(),
                "paused_from": run.status.value,
            },
        )

    def cancel_run(self, caller_id: str, run_id: str, caller_is_admin: bool = False) -> AgentRun:
        run = self._store.require_run(run_id)
        self._authorize(run, caller_id, caller_is_admin)
        if run.status in TERMINAL_STATUSES:
            raise InvalidRunStateError(f"Run '{run_id}' is already terminal ({run.status.value}).")
        # Invalidate any pending approvals atomically with the cancellation.
        self._store.cancel_pending_approvals(run_id)
        cancelled = self._store.transition_run(
            run.run_id,
            RunStatus.CANCELLED,
            recovery_state={
                **run.recovery_state,
                "cancelled_at": _now_iso(),
                "cancelled_from": run.status.value,
            },
            current_step=None,
        )
        logger.info("Agent Run '%s' cancelled by '%s'", run_id, caller_id)
        return cancelled

    # ── Resume ───────────────────────────────────────────────────────────

    def resume_run(self, caller_id: str, run_id: str, caller_is_admin: bool = False) -> AgentRun:
        """Safe resume: reload persistent state, authorize, validate, continue.

        The resume position is determined ENTIRELY from persisted state
        (completed_steps) — frontend memory is never trusted.
        """
        run = self._store.require_run(run_id)
        self._authorize(run, caller_id, caller_is_admin)

        if run.status in TERMINAL_STATUSES:
            raise InvalidRunStateError(
                f"Run '{run_id}' is terminal ({run.status.value}) and cannot be resumed."
            )

        if run.status == RunStatus.WAITING_APPROVAL:
            # Recover a run whose pending approval died (stale/expired/cancelled).
            pa = (
                self._store.get_pending_approval(run.pending_approval_id)
                if run.pending_approval_id
                else None
            )
            if pa is None or pa.status != PendingApprovalStatus.PENDING:
                run = self._store.transition_run(
                    run.run_id,
                    RunStatus.RUNNING,
                    pending_approval_id=None,
                    recovery_state={
                        **run.recovery_state,
                        "resumed_at": _now_iso(),
                        "approval_recovered": True,
                    },
                )
                return self._advance(run, self._require_principal(run))
            # A live approval is pending — nothing to resume; surface state.
            raise InvalidRunStateError(
                f"Run '{run_id}' is waiting on a live approval '{pa.approval_id}'."
            )

        if run.status not in (RunStatus.PAUSED, RunStatus.RUNNING, RunStatus.READY):
            raise InvalidRunStateError(
                f"Run '{run_id}' cannot be resumed from status {run.status.value}."
            )

        # Project/revision consistency check: the canonical revision must not
        # have moved past what this run's completed work produced.
        recovery_rev = run.recovery_state.get("last_completed_revision")
        if recovery_rev is not None:
            current_rev = self._bus.get_project_revision(run.project_id)
            if int(current_rev) < int(recovery_rev):
                raise InvalidRunStateError(
                    f"Project '{run.project_id}' revision {current_rev} is behind the "
                    f"run's last committed revision {recovery_rev}; refusing unsafe resume."
                )

        if run.status == RunStatus.PAUSED:
            run = self._store.transition_run(
                run.run_id,
                RunStatus.RUNNING,
                recovery_state={**run.recovery_state, "resumed_at": _now_iso()},
            )

        return self._advance(run, self._require_principal(run))

    def _require_principal(self, run: AgentRun) -> AuthenticatedPrincipal:
        """Reconstruct the run owner's principal for continuation.

        The scopes bound into the persisted plan at run creation are reused —
        continuation NEVER escalates to wildcard scopes. The persisted owner
        identity is authoritative for authorization.
        """
        return AuthenticatedPrincipal(
            user_id=run.user_id,
            email="",
            role="engineer",
            scopes=list(run.plan.get("principal_scopes", [])),
            is_authenticated=True,
        )

    # ── Retry ────────────────────────────────────────────────────────────

    def retry_run(self, caller_id: str, run_id: str, caller_is_admin: bool = False) -> AgentRun:
        """Retry a FAILED run from its failed step — never a blind replay.

        - Loads the persisted run and determines the failed step server-side.
        - Validates the CURRENT project revision (OCC will catch drift).
        - Reuses the deterministic per-step commandId so the CommandBus
          idempotency ledger prevents duplicate engineering mutations.
        """
        run = self._store.require_run(run_id)
        self._authorize(run, caller_id, caller_is_admin)

        if run.status != RunStatus.FAILED:
            raise InvalidRunStateError(
                f"Run '{run_id}' is not FAILED (status={run.status.value}); retry refused."
            )

        failed_entries = list(run.failed_steps)
        if not failed_entries:
            raise InvalidRunStateError(f"Run '{run_id}' has no recorded failed step.")
        failed_step_id = str(failed_entries[-1].get("step_id", ""))
        try:
            failed_step = self._find_step(run, failed_step_id)
        except ValueError as exc:
            raise InvalidRunStateError(str(exc)) from exc

        # Re-validate the retry policy for the failed step BEFORE transitioning.
        decision = self._evaluate_step_policy(run, self._require_principal(run), failed_step)
        if decision.result == PolicyResult.DENIED:
            raise InvalidRunStateError(f"Retry denied by execution policy: {decision.reason}")

        # Validate current project revision consistency.
        current_rev = self._bus.get_project_revision(run.project_id)
        last_rev = run.recovery_state.get("last_completed_revision")
        if last_rev is not None and int(current_rev) < int(last_rev):
            raise InvalidRunStateError(
                f"Project revision {current_rev} is behind the run's last committed "
                f"revision {last_rev}; refusing unsafe retry."
            )

        # FAILED → RUNNING (explicit retry/recovery operation).
        run = self._store.transition_run(
            run.run_id,
            RunStatus.RUNNING,
            recovery_state={
                **run.recovery_state,
                "retry_at": _now_iso(),
                "retrying_step": failed_step_id,
                "retry_count": int(run.recovery_state.get("retry_count", 0)) + 1,
            },
        )
        return self._advance(run, self._require_principal(run))

    # ── Approval decisions ───────────────────────────────────────────────

    def decide_approval(
        self,
        caller_id: str,
        approval_id: str,
        decision: ApprovalDecisionValue | str,
        *,
        reason: str = "",
        caller_is_admin: bool = False,
    ) -> AgentRun:
        """Verify the persisted approval binding, record the decision, continue.

        Security checks performed server-side BEFORE any execution:
        - approval exists and is still PENDING (atomic claim);
        - caller is the bound principal (or admin);
        - approval belongs to a live run in WAITING_APPROVAL;
        - approval's project/capability/step/payload-hash match the run's
          persisted plan (client cannot swap the executed command);
        - project revision has not drifted (stale approvals rejected).
        """
        from backend.audit_integrity_helper import record_audit_write

        pa = self._store.require_pending_approval(approval_id)
        run = self._store.require_run(pa.run_id)

        # Principal binding: only the bound principal (or admin) may decide.
        if not (caller_is_admin or caller_id == pa.principal_id):
            raise RunPermissionError(
                f"Principal '{caller_id}' is not the bound approver for approval "
                f"'{approval_id}' (bound: '{pa.principal_id}')."
            )

        # Binding integrity: approval must match the run's persisted plan.
        if pa.project_id != run.project_id:
            raise StaleApprovalError(
                f"Approval '{approval_id}' project '{pa.project_id}' does not match "
                f"run project '{run.project_id}'."
            )
        try:
            step = self._find_step(run, pa.step_id)
        except ValueError as exc:
            raise StaleApprovalError(str(exc)) from exc
        if str(step.get("capability_id")) != pa.capability_id:
            raise StaleApprovalError(
                f"Approval '{approval_id}' capability mismatch for step '{pa.step_id}'."
            )
        if self._step_payload_hash(step) != pa.step_payload_hash:
            raise StaleApprovalError(
                f"Approval '{approval_id}' payload fingerprint mismatch; "
                f"the planned step payload changed after approval creation."
            )

        # Run state: must still be waiting on THIS approval.
        if run.status != RunStatus.WAITING_APPROVAL:
            raise InvalidRunStateError(
                f"Run '{run.run_id}' is {run.status.value}; approval '{approval_id}' is stale."
            )
        if run.pending_approval_id != approval_id:
            raise InvalidRunStateError(
                f"Run '{run.run_id}' is not waiting on approval '{approval_id}'."
            )

        # Staleness: project revision must be unchanged since approval creation.
        current_rev = self._bus.get_project_revision(pa.project_id)
        if int(current_rev) != int(pa.project_revision):
            # Record auditable evidence of the invalidation, then refuse.
            self._store.decide_pending_approval(
                approval_id,
                decision=ApprovalDecisionValue.REJECTED,
                principal_id=caller_id,
                reason=f"STALE_PROJECT_REVISION:{current_rev}!={pa.project_revision}",
            )
            raise StaleApprovalError(
                f"Approval '{approval_id}' is stale: project revision moved from "
                f"{pa.project_revision} to {current_rev}."
            )

        dec = ApprovalDecisionValue(decision)
        _, decision_rec = self._store.decide_pending_approval(
            approval_id,
            decision=dec,
            principal_id=caller_id,
            reason=reason,
        )
        record_audit_write(
            operation="agent_run_approval_decision",
            table="approval_decisions",
            record_id=decision_rec.decision_id,
            details=decision_rec.to_dict(),
        )

        if dec == ApprovalDecisionValue.REJECTED:
            failed = list(run.failed_steps) + [
                {
                    "step_id": pa.step_id,
                    "error_code": "APPROVAL_REJECTED",
                    "error_message": (reason or "Rejected by reviewer.")[:500],
                }
            ]
            recovery = dict(run.recovery_state)
            recovery["failed_step"] = pa.step_id
            recovery["failure_error_code"] = "APPROVAL_REJECTED"
            recovery["recoverable_via"] = "run_retry"
            return self._store.transition_run(
                run.run_id,
                RunStatus.FAILED,
                failed_steps=failed,
                recovery_state=recovery,
                pending_approval_id=None,
                current_step=pa.step_id,
            )

        # APPROVED → resume execution bound to the approved revision.
        run = self._store.transition_run(
            run.run_id,
            RunStatus.RUNNING,
            pending_approval_id=None,
            recovery_state={
                **run.recovery_state,
                "approved_approval_id": approval_id,
                "approved_at": _now_iso(),
            },
        )

        result = self._execute_step(
            run, self._require_principal(run), step, expected_revision=int(pa.project_revision)
        )
        if not result["success"]:
            return self._fail_step(
                run,
                pa.step_id,
                result.get("errorCode") or "STEP_EXECUTION_FAILED",
                result.get("errorMessage") or "Approved step execution failed.",
                artifacts=result.get("resultData") or {},
            )

        run = self._record_step_completion(run, pa.step_id, result)
        return self._advance(run, self._require_principal(run))


default_agent_run_orchestrator = AgentRunOrchestrator()
