"""backend/core/agent_run_store.py — Durable, Server-Authoritative Agent Run Persistence.

Phase 1 (AI-FIRST transformation) foundation:

- Persistent Agent Run lifecycle state backed by the SAME database
  infrastructure as ``CommandStateStore`` (``backend.database.Database``).
  No second persistence framework is introduced.
- Strongly typed run statuses / approval modes with an explicit,
  server-authoritative state-transition table. Illegal transitions are
  rejected; state is never silently overwritten.
- Concurrency-safe updates via a monotonic ``version`` column used as an
  atomic compare-and-swap (CAS) token inside the database transaction.
- Server-side persisted pending-approval records bound to the exact
  run_id + step_id + project_id + project_revision + capability_id +
  principal + policy decision + plan/payload hashes.
- Immutable append-only approval-decision ledger (decisions are never
  mutated; a retry creates a NEW decision record).

In-memory caches are NOT used: the database is the single source of truth so
that browser refresh, WebSocket disconnect, and process/worker restart do not
destroy an Agent Run.

Schema bootstrap note:
    Tables are created with ``CREATE TABLE IF NOT EXISTS`` at store
    initialization (mirroring the FDS queue / Meeza payment runtime pattern)
    so fresh SQLite test databases work without running Alembic. The Alembic
    migration ``007_add_agent_run_tables.py`` carries the identical schema for
    managed PostgreSQL deployments. Column definitions MUST stay in sync.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from backend.database import Database, get_db

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Typed enums
# ─────────────────────────────────────────────────────────────────────────────


class RunStatus(StrEnum):
    """Server-authoritative Agent Run lifecycle statuses."""

    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ApprovalMode(StrEnum):
    """How the run requests approval for governed steps."""

    AUTO = "AUTO"
    STEP_BY_STEP = "STEP_BY_STEP"


class PendingApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ApprovalDecisionValue(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ─────────────────────────────────────────────────────────────────────────────
# State transition safety (server-authoritative)
# ─────────────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PLANNING: frozenset({RunStatus.READY, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.READY: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_APPROVAL,
            RunStatus.PAUSED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.COMPLETED,
        }
    ),
    RunStatus.WAITING_APPROVAL: frozenset(
        {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.PAUSED}
    ),
    RunStatus.PAUSED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED}),
    # FAILED → RUNNING only through an explicit retry/recovery operation.
    RunStatus.FAILED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    # Terminal states
    RunStatus.CANCELLED: frozenset(),
    RunStatus.COMPLETED: frozenset(),
}

TERMINAL_STATUSES = frozenset({RunStatus.CANCELLED, RunStatus.COMPLETED})


class InvalidTransitionError(Exception):
    """Raised when a lifecycle transition is not permitted by the transition table."""


class RunConcurrencyConflictError(Exception):
    """Raised when a compare-and-swap update loses a race with a concurrent writer."""


class RunNotFoundError(Exception):
    """Raised when the referenced Agent Run does not exist."""


class ApprovalAlreadyDecidedError(Exception):
    """Raised when a pending approval was already decided/cancelled (stale or duplicate)."""


class PendingApprovalNotFoundError(Exception):
    """Raised when the referenced pending approval does not exist."""


def validate_transition(current: RunStatus | str, to: RunStatus | str) -> None:
    """Raise :class:`InvalidTransitionError` if ``current → to`` is illegal."""
    cur = RunStatus(current)
    nxt = RunStatus(to)
    if nxt not in VALID_TRANSITIONS[cur]:
        raise InvalidTransitionError(f"Illegal Agent Run transition: {cur.value} -> {nxt.value}")


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AgentRun:
    """Persistent Agent Run aggregate (database is the source of truth)."""

    run_id: str
    conversation_id: str
    user_id: str
    project_id: str
    status: RunStatus
    approval_mode: ApprovalMode
    plan: dict[str, Any]
    steps: list[dict[str, Any]]
    current_step: str | None
    completed_steps: list[str]
    pending_approval_id: str | None
    failed_steps: list[dict[str, Any]]
    recovery_state: dict[str, Any]
    artifacts: dict[str, Any]
    started_at: str
    updated_at: str
    completed_at: str | None
    audit_reference: str | None
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "conversationId": self.conversation_id,
            "userId": self.user_id,
            "projectId": self.project_id,
            "status": self.status.value,
            "approvalMode": self.approval_mode.value,
            "plan": self.plan,
            "steps": self.steps,
            "currentStep": self.current_step,
            "completedSteps": self.completed_steps,
            "pendingApprovalId": self.pending_approval_id,
            "failedSteps": self.failed_steps,
            "recoveryState": self.recovery_state,
            "artifacts": self.artifacts,
            "startedAt": self.started_at,
            "updatedAt": self.updated_at,
            "completedAt": self.completed_at,
            "auditReference": self.audit_reference,
            "version": self.version,
        }


@dataclass
class PendingApproval:
    """Server-side persisted approval record bound to an exact execution context."""

    approval_id: str
    run_id: str
    step_id: str
    project_id: str
    project_revision: int
    capability_id: str
    principal_id: str
    approval_mode: ApprovalMode
    policy_result: str
    plan_hash: str
    step_payload_hash: str
    status: PendingApprovalStatus
    created_at: str
    decided_at: str | None
    expires_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "approvalId": self.approval_id,
            "runId": self.run_id,
            "stepId": self.step_id,
            "projectId": self.project_id,
            "projectRevision": self.project_revision,
            "capabilityId": self.capability_id,
            "principalId": self.principal_id,
            "approvalMode": self.approval_mode.value,
            "policyResult": self.policy_result,
            "planHash": self.plan_hash,
            "stepPayloadHash": self.step_payload_hash,
            "status": self.status.value,
            "createdAt": self.created_at,
            "decidedAt": self.decided_at,
            "expiresAt": self.expires_at,
        }


@dataclass
class ApprovalDecision:
    """Immutable audit record of one approval decision."""

    decision_id: str
    approval_id: str
    run_id: str
    step_id: str
    principal_id: str
    decision: ApprovalDecisionValue
    timestamp: str
    project_revision: int
    policy_result: str
    reason: str
    audit_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id,
            "approvalId": self.approval_id,
            "runId": self.run_id,
            "stepId": self.step_id,
            "principalId": self.principal_id,
            "decision": self.decision.value,
            "timestamp": self.timestamp,
            "projectRevision": self.project_revision,
            "policyResult": self.policy_result,
            "reason": self.reason,
            "auditReference": self.audit_reference,
        }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _json_loads(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, dict | list):
        return raw
    try:
        parsed = json.loads(raw)
    except Exception:
        return default
    return parsed if isinstance(parsed, type(default)) else default


# ─────────────────────────────────────────────────────────────────────────────
# Store
# ─────────────────────────────────────────────────────────────────────────────


class AgentRunStore:
    """Durable persistence adapter for the Agent Run lifecycle.

    Uses the existing ``backend.database.Database`` infrastructure (SQLite WAL /
    PostgreSQL pool) — no second persistence framework.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_db()
        self._ensure_schema()

    @property
    def db(self) -> Database:
        return self._db

    def _ph(self) -> str:
        return self._db._ph()

    # ── Schema bootstrap (idempotent; mirrors migration 007) ────────────

    def _ensure_schema(self) -> None:
        with self._db._transaction() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL DEFAULT '',
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PLANNING'
                        CHECK (status IN ('PLANNING','READY','RUNNING','WAITING_APPROVAL',
                                          'PAUSED','FAILED','CANCELLED','COMPLETED')),
                    approval_mode TEXT NOT NULL DEFAULT 'AUTO'
                        CHECK (approval_mode IN ('AUTO','STEP_BY_STEP')),
                    plan TEXT NOT NULL DEFAULT '{}',
                    steps TEXT NOT NULL DEFAULT '[]',
                    current_step TEXT,
                    completed_steps TEXT NOT NULL DEFAULT '[]',
                    pending_approval_id TEXT,
                    failed_steps TEXT NOT NULL DEFAULT '[]',
                    recovery_state TEXT NOT NULL DEFAULT '{}',
                    artifacts TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    audit_reference TEXT,
                    version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_project ON agent_runs(project_id)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    approval_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    project_revision INTEGER NOT NULL,
                    capability_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    approval_mode TEXT NOT NULL,
                    policy_result TEXT NOT NULL,
                    plan_hash TEXT NOT NULL DEFAULT '',
                    step_payload_hash TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CANCELLED')),
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    expires_at TEXT
                )
                """
            )
            # At most ONE PENDING approval per (run_id, step_id); historical
            # decided/cancelled approvals are preserved immutably.
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_approvals_run_step_pending "
                "ON pending_approvals(run_id, step_id) WHERE status = 'PENDING'"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pending_approvals_run ON pending_approvals(run_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pending_approvals_status ON pending_approvals(status)"
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_decisions (
                    decision_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
                    timestamp TEXT NOT NULL,
                    project_revision INTEGER NOT NULL,
                    policy_result TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    audit_reference TEXT
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_approval_decisions_run ON approval_decisions(run_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_approval_decisions_approval "
                "ON approval_decisions(approval_id)"
            )

    # ── Row hydration ────────────────────────────────────────────────────

    @staticmethod
    def _row_to_run(row: Any) -> AgentRun:
        if isinstance(row, dict):
            d = row
        else:
            d = {
                "run_id": row[0],
                "conversation_id": row[1],
                "user_id": row[2],
                "project_id": row[3],
                "status": row[4],
                "approval_mode": row[5],
                "plan": row[6],
                "steps": row[7],
                "current_step": row[8],
                "completed_steps": row[9],
                "pending_approval_id": row[10],
                "failed_steps": row[11],
                "recovery_state": row[12],
                "artifacts": row[13],
                "started_at": row[14],
                "updated_at": row[15],
                "completed_at": row[16],
                "audit_reference": row[17],
                "version": row[18],
            }
        return AgentRun(
            run_id=d["run_id"],
            conversation_id=d.get("conversation_id", ""),
            user_id=d["user_id"],
            project_id=d["project_id"],
            status=RunStatus(d["status"]),
            approval_mode=ApprovalMode(d["approval_mode"]),
            plan=_json_loads(d.get("plan"), {}),
            steps=_json_loads(d.get("steps"), []),
            current_step=d.get("current_step"),
            completed_steps=_json_loads(d.get("completed_steps"), []),
            pending_approval_id=d.get("pending_approval_id"),
            failed_steps=_json_loads(d.get("failed_steps"), []),
            recovery_state=_json_loads(d.get("recovery_state"), {}),
            artifacts=_json_loads(d.get("artifacts"), {}),
            started_at=d["started_at"],
            updated_at=d["updated_at"],
            completed_at=d.get("completed_at"),
            audit_reference=d.get("audit_reference"),
            version=int(d.get("version", 1)),
        )

    _RUN_COLUMNS = (
        "run_id, conversation_id, user_id, project_id, status, approval_mode, plan, steps, "
        "current_step, completed_steps, pending_approval_id, failed_steps, recovery_state, "
        "artifacts, started_at, updated_at, completed_at, audit_reference, version"
    )

    # ── Agent Run CRUD ───────────────────────────────────────────────────

    def create_run(
        self,
        *,
        run_id: str | None = None,
        conversation_id: str = "",
        user_id: str,
        project_id: str,
        approval_mode: ApprovalMode | str = ApprovalMode.AUTO,
        plan: dict[str, Any] | None = None,
        steps: list[dict[str, Any]] | None = None,
        status: RunStatus | str = RunStatus.PLANNING,
        recovery_state: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> AgentRun:
        """Persist a new Agent Run in its initial state."""
        ph = self._ph()
        rid = run_id or f"run-{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        mode = ApprovalMode(approval_mode)
        st = RunStatus(status)
        with self._db._transaction() as cur:
            cur.execute(
                f"""
                INSERT INTO agent_runs (
                    run_id, conversation_id, user_id, project_id, status, approval_mode,
                    plan, steps, current_step, completed_steps, pending_approval_id,
                    failed_steps, recovery_state, artifacts, started_at, updated_at,
                    completed_at, audit_reference, version
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
                          {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    rid,
                    conversation_id,
                    user_id,
                    project_id,
                    st.value,
                    mode.value,
                    json.dumps(plan or {}),
                    json.dumps(steps or []),
                    None,
                    json.dumps([]),
                    None,
                    json.dumps([]),
                    json.dumps(recovery_state or {}),
                    json.dumps(artifacts or {}),
                    now,
                    now,
                    None,
                    None,
                    1,
                ),
            )
        run = self.get_run(rid)
        assert run is not None  # just inserted
        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT {self._RUN_COLUMNS} FROM agent_runs WHERE run_id = {ph}",
                (run_id,),
            )
            row = cur.fetchone()
        return self._row_to_run(row) if row is not None else None

    def require_run(self, run_id: str) -> AgentRun:
        run = self.get_run(run_id)
        if run is None:
            raise RunNotFoundError(f"Agent Run '{run_id}' does not exist.")
        return run

    def list_runs(
        self,
        *,
        project_id: str | None = None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        ph = self._ph()
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append(f"project_id = {ph}")
            params.append(project_id)
        if user_id:
            clauses.append(f"user_id = {ph}")
            params.append(user_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT {self._RUN_COLUMNS} FROM agent_runs {where} "
            f"ORDER BY started_at DESC LIMIT {int(limit)}"
        )
        with self._db._transaction() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [self._row_to_run(r) for r in rows]

    def transition_run(
        self,
        run_id: str,
        to_status: RunStatus | str,
        *,
        expected_version: int | None = None,
        current_step: str | None = ...,
        completed_steps: list[str] | None = None,
        failed_steps: list[dict[str, Any]] | None = None,
        recovery_state: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        pending_approval_id: str | None = ...,
        audit_reference: str | None = ...,
        set_completed_at: bool = False,
    ) -> AgentRun:
        """Atomically transition the run's status with validation + CAS.

        - Validates the transition against ``VALID_TRANSITIONS`` (loaded fresh
          inside the transaction — no stale read can bypass validation).
        - Uses the monotonic ``version`` column as a CAS token: the UPDATE only
          applies when the stored version matches ``expected_version`` (or the
          freshly-read version when not supplied), preventing lost updates
          between simultaneous approve/reject/cancel/resume/retry operations.
        """
        ph = self._ph()
        nxt = RunStatus(to_status)
        now = _now_iso()

        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT status, version FROM agent_runs WHERE run_id = {ph}",
                (run_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise RunNotFoundError(f"Agent Run '{run_id}' does not exist.")
            cur_status_raw, stored_version = (
                (row["status"], int(row["version"]))
                if isinstance(row, dict)
                else (row[0], int(row[1]))
            )
            cur_status = RunStatus(cur_status_raw)

            # Validate transition against the authoritative table.
            validate_transition(cur_status, nxt)

            cas_version = stored_version if expected_version is None else int(expected_version)

            sets: list[str] = [
                f"status = {ph}",
                f"updated_at = {ph}",
                f"version = {ph}",
            ]
            params: list[Any] = [nxt.value, now, cas_version + 1]

            if current_step is not ...:
                sets.append(f"current_step = {ph}")
                params.append(current_step)
            if completed_steps is not None:
                sets.append(f"completed_steps = {ph}")
                params.append(json.dumps(completed_steps))
            if failed_steps is not None:
                sets.append(f"failed_steps = {ph}")
                params.append(json.dumps(failed_steps))
            if recovery_state is not None:
                sets.append(f"recovery_state = {ph}")
                params.append(json.dumps(recovery_state))
            if artifacts is not None:
                sets.append(f"artifacts = {ph}")
                params.append(json.dumps(artifacts))
            if pending_approval_id is not ...:
                sets.append(f"pending_approval_id = {ph}")
                params.append(pending_approval_id)
            if audit_reference is not ...:
                sets.append(f"audit_reference = {ph}")
                params.append(audit_reference)
            if set_completed_at:
                sets.append(f"completed_at = {ph}")
                params.append(now)

            where_extra = f" AND version = {ph}"
            params.extend([run_id, cas_version])

            cur.execute(
                f"UPDATE agent_runs SET {', '.join(sets)} WHERE run_id = {ph}{where_extra}",
                tuple(params),
            )
            if cur.rowcount == 0:
                raise RunConcurrencyConflictError(
                    f"Concurrent modification detected on Agent Run '{run_id}' "
                    f"(expected version {cas_version})."
                )

        return self.require_run(run_id)

    def update_progress(
        self,
        run_id: str,
        *,
        expected_version: int,
        current_step: str | None = ...,
        completed_steps: list[str] | None = None,
        failed_steps: list[dict[str, Any]] | None = None,
        recovery_state: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        pending_approval_id: str | None = ...,
    ) -> AgentRun:
        """Update execution progress fields without changing status (CAS-guarded)."""
        ph = self._ph()
        now = _now_iso()
        sets: list[str] = [f"updated_at = {ph}", f"version = {ph}"]
        params: list[Any] = [now, expected_version + 1]

        if current_step is not ...:
            sets.append(f"current_step = {ph}")
            params.append(current_step)
        if completed_steps is not None:
            sets.append(f"completed_steps = {ph}")
            params.append(json.dumps(completed_steps))
        if failed_steps is not None:
            sets.append(f"failed_steps = {ph}")
            params.append(json.dumps(failed_steps))
        if recovery_state is not None:
            sets.append(f"recovery_state = {ph}")
            params.append(json.dumps(recovery_state))
        if artifacts is not None:
            sets.append(f"artifacts = {ph}")
            params.append(json.dumps(artifacts))
        if pending_approval_id is not ...:
            sets.append(f"pending_approval_id = {ph}")
            params.append(pending_approval_id)

        params.extend([run_id, expected_version])
        with self._db._transaction() as cur:
            cur.execute(
                f"UPDATE agent_runs SET {', '.join(sets)} WHERE run_id = {ph} AND version = {ph}",
                tuple(params),
            )
            if cur.rowcount == 0:
                raise RunConcurrencyConflictError(
                    f"Concurrent modification detected on Agent Run '{run_id}' "
                    f"(expected version {expected_version})."
                )
        return self.require_run(run_id)

    def set_audit_reference(self, run_id: str, audit_reference: str) -> AgentRun:
        ph = self._ph()
        now = _now_iso()
        with self._db._transaction() as cur:
            cur.execute(
                f"UPDATE agent_runs SET audit_reference = {ph}, updated_at = {ph} "
                f"WHERE run_id = {ph}",
                (audit_reference, now, run_id),
            )
            if cur.rowcount == 0:
                raise RunNotFoundError(f"Agent Run '{run_id}' does not exist.")
        return self.require_run(run_id)

    # ── Pending approvals ────────────────────────────────────────────────

    def create_pending_approval(
        self,
        *,
        approval_id: str | None = None,
        run_id: str,
        step_id: str,
        project_id: str,
        project_revision: int,
        capability_id: str,
        principal_id: str,
        approval_mode: ApprovalMode | str,
        policy_result: str,
        plan_hash: str = "",
        step_payload_hash: str = "",
        expires_at: str | None = None,
    ) -> PendingApproval:
        ph = self._ph()
        aid = approval_id or f"appr-{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        with self._db._transaction() as cur:
            cur.execute(
                f"""
                INSERT INTO pending_approvals (
                    approval_id, run_id, step_id, project_id, project_revision,
                    capability_id, principal_id, approval_mode, policy_result,
                    plan_hash, step_payload_hash, status, created_at, decided_at, expires_at
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
                          {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    aid,
                    run_id,
                    step_id,
                    project_id,
                    int(project_revision) if project_revision is not None else 1,
                    capability_id,
                    principal_id,
                    ApprovalMode(approval_mode).value,
                    policy_result,
                    plan_hash,
                    step_payload_hash,
                    PendingApprovalStatus.PENDING.value,
                    now,
                    None,
                    expires_at,
                ),
            )
        pa = self.get_pending_approval(aid)
        assert pa is not None
        return pa

    @staticmethod
    def _row_to_pending_approval(row: Any) -> PendingApproval:
        if isinstance(row, dict):
            d = row
        else:
            d = {
                "approval_id": row[0],
                "run_id": row[1],
                "step_id": row[2],
                "project_id": row[3],
                "project_revision": row[4],
                "capability_id": row[5],
                "principal_id": row[6],
                "approval_mode": row[7],
                "policy_result": row[8],
                "plan_hash": row[9],
                "step_payload_hash": row[10],
                "status": row[11],
                "created_at": row[12],
                "decided_at": row[13],
                "expires_at": row[14],
            }
        return PendingApproval(
            approval_id=d["approval_id"],
            run_id=d["run_id"],
            step_id=d["step_id"],
            project_id=d["project_id"],
            project_revision=int(d["project_revision"]),
            capability_id=d["capability_id"],
            principal_id=d["principal_id"],
            approval_mode=ApprovalMode(d["approval_mode"]),
            policy_result=d["policy_result"],
            plan_hash=d.get("plan_hash", ""),
            step_payload_hash=d.get("step_payload_hash", ""),
            status=PendingApprovalStatus(d["status"]),
            created_at=d["created_at"],
            decided_at=d.get("decided_at"),
            expires_at=d.get("expires_at"),
        )

    _PA_COLUMNS = (
        "approval_id, run_id, step_id, project_id, project_revision, capability_id, "
        "principal_id, approval_mode, policy_result, plan_hash, step_payload_hash, "
        "status, created_at, decided_at, expires_at"
    )

    def get_pending_approval(self, approval_id: str) -> PendingApproval | None:
        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT {self._PA_COLUMNS} FROM pending_approvals WHERE approval_id = {ph}",
                (approval_id,),
            )
            row = cur.fetchone()
        return self._row_to_pending_approval(row) if row is not None else None

    def get_pending_approval_for_step(self, run_id: str, step_id: str) -> PendingApproval | None:
        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT {self._PA_COLUMNS} FROM pending_approvals "
                f"WHERE run_id = {ph} AND step_id = {ph}",
                (run_id, step_id),
            )
            row = cur.fetchone()
        return self._row_to_pending_approval(row) if row is not None else None

    def decide_pending_approval(
        self,
        approval_id: str,
        *,
        decision: ApprovalDecisionValue | str,
        principal_id: str,
        reason: str = "",
        policy_result: str = "",
        audit_reference: str | None = None,
    ) -> tuple[PendingApproval, ApprovalDecision]:
        """Atomically claim a PENDING approval and persist an immutable decision.

        The claim is a conditional UPDATE restricted to ``status = 'PENDING'``;
        concurrent duplicate decisions lose the race deterministically and raise
        :class:`ApprovalAlreadyDecidedError` instead of double-executing.

        The historical decision record is NEVER mutated — a later retry of the
        same step creates a new pending approval and a new decision record.
        """
        ph = self._ph()
        dec = ApprovalDecisionValue(decision)
        now = _now_iso()
        decision_id = f"dec-{uuid.uuid4().hex[:12]}"

        with self._db._transaction() as cur:
            # Load the approval inside the same transaction that claims it.
            cur.execute(
                f"SELECT {self._PA_COLUMNS} FROM pending_approvals WHERE approval_id = {ph}",
                (approval_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise PendingApprovalNotFoundError(
                    f"Pending approval '{approval_id}' does not exist."
                )
            pa = self._row_to_pending_approval(row)

            # Atomic claim: only succeeds while still PENDING.
            cur.execute(
                f"UPDATE pending_approvals SET status = {ph}, decided_at = {ph} "
                f"WHERE approval_id = {ph} AND status = {ph}",
                (dec.value, now, approval_id, PendingApprovalStatus.PENDING.value),
            )
            if cur.rowcount == 0:
                raise ApprovalAlreadyDecidedError(
                    f"Pending approval '{approval_id}' is no longer pending "
                    f"(status={pa.status.value}); stale or duplicate decision rejected."
                )

            # Append immutable decision ledger record.
            cur.execute(
                f"""
                INSERT INTO approval_decisions (
                    decision_id, approval_id, run_id, step_id, principal_id, decision,
                    timestamp, project_revision, policy_result, reason, audit_reference
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    decision_id,
                    approval_id,
                    pa.run_id,
                    pa.step_id,
                    principal_id,
                    dec.value,
                    now,
                    pa.project_revision,
                    policy_result or pa.policy_result,
                    reason,
                    audit_reference,
                ),
            )

        decided = self.require_pending_approval(approval_id)
        decision_rec = ApprovalDecision(
            decision_id=decision_id,
            approval_id=approval_id,
            run_id=pa.run_id,
            step_id=pa.step_id,
            principal_id=principal_id,
            decision=dec,
            timestamp=now,
            project_revision=pa.project_revision,
            policy_result=policy_result or pa.policy_result,
            reason=reason,
            audit_reference=audit_reference,
        )
        return decided, decision_rec

    def require_pending_approval(self, approval_id: str) -> PendingApproval:
        pa = self.get_pending_approval(approval_id)
        if pa is None:
            raise PendingApprovalNotFoundError(f"Pending approval '{approval_id}' does not exist.")
        return pa

    def cancel_pending_approvals(self, run_id: str) -> int:
        """Cancel all PENDING approvals for a run (used on cancel/failure)."""
        ph = self._ph()
        now = _now_iso()
        with self._db._transaction() as cur:
            cur.execute(
                f"UPDATE pending_approvals SET status = {ph}, decided_at = {ph} "
                f"WHERE run_id = {ph} AND status = {ph}",
                (
                    PendingApprovalStatus.CANCELLED.value,
                    now,
                    run_id,
                    PendingApprovalStatus.PENDING.value,
                ),
            )
            return int(cur.rowcount)

    def expire_stale_approvals(self, now_utc: datetime | None = None) -> int:
        """Expire approvals whose ``expires_at`` has passed (expiration policy)."""
        ph = self._ph()
        cutoff = (now_utc or datetime.now(UTC)).isoformat()
        with self._db._transaction() as cur:
            cur.execute(
                f"UPDATE pending_approvals SET status = {ph} "
                f"WHERE status = {ph} AND expires_at IS NOT NULL AND expires_at < {ph}",
                (
                    PendingApprovalStatus.EXPIRED.value,
                    PendingApprovalStatus.PENDING.value,
                    cutoff,
                ),
            )
            return int(cur.rowcount)

    # ── Decision ledger (read-only) ──────────────────────────────────────

    @staticmethod
    def _row_to_decision(row: Any) -> ApprovalDecision:
        if isinstance(row, dict):
            d = row
        else:
            d = {
                "decision_id": row[0],
                "approval_id": row[1],
                "run_id": row[2],
                "step_id": row[3],
                "principal_id": row[4],
                "decision": row[5],
                "timestamp": row[6],
                "project_revision": row[7],
                "policy_result": row[8],
                "reason": row[9],
                "audit_reference": row[10],
            }
        return ApprovalDecision(
            decision_id=d["decision_id"],
            approval_id=d["approval_id"],
            run_id=d["run_id"],
            step_id=d["step_id"],
            principal_id=d["principal_id"],
            decision=ApprovalDecisionValue(d["decision"]),
            timestamp=d["timestamp"],
            project_revision=int(d["project_revision"]),
            policy_result=d.get("policy_result", ""),
            reason=d.get("reason", ""),
            audit_reference=d.get("audit_reference"),
        )

    def list_decisions(self, run_id: str) -> list[ApprovalDecision]:
        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                "SELECT decision_id, approval_id, run_id, step_id, principal_id, decision, "
                "timestamp, project_revision, policy_result, reason, audit_reference "
                f"FROM approval_decisions WHERE run_id = {ph} ORDER BY timestamp ASC",
                (run_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_decision(r) for r in rows]


default_agent_run_store = AgentRunStore()
