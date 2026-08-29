"""Add durable Agent Run lifecycle tables (agent_runs, pending_approvals, approval_decisions).

Revision ID: 007
Revises: 006
Create Date: 2026-08-23

Phase 1 — AI-FIRST transformation: durable Agent Run + centralized Execution
Policy foundation.

Tables created:

  - agent_runs           — persistent server-authoritative Agent Run lifecycle state
  - pending_approvals    — server-side persisted pending-approval records bound to
                           run + step + project revision + capability + principal
  - approval_decisions   — immutable, append-only approval decision ledger

NOTE: The runtime store (backend/core/agent_run_store.py) also bootstraps these
tables via ``CREATE TABLE IF NOT EXISTS`` (mirroring the FDS queue / Meeza
payment pattern), so this migration is mainly for PostgreSQL / managed-DB
deployments that use Alembic exclusively. Column definitions MUST stay in sync
between this migration and the runtime bootstrap.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Agent Run lifecycle tables."""
    # ── agent_runs ──────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.Text, primary_key=True),
        sa.Column("conversation_id", sa.Text, nullable=False, server_default=""),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("project_id", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default="PLANNING",
        ),
        sa.Column("approval_mode", sa.Text, nullable=False, server_default="AUTO"),
        sa.Column("plan", sa.Text, nullable=False, server_default="{}"),
        sa.Column("steps", sa.Text, nullable=False, server_default="[]"),
        sa.Column("current_step", sa.Text, nullable=True),
        sa.Column("completed_steps", sa.Text, nullable=False, server_default="[]"),
        sa.Column("pending_approval_id", sa.Text, nullable=True),
        sa.Column("failed_steps", sa.Text, nullable=False, server_default="[]"),
        sa.Column("recovery_state", sa.Text, nullable=False, server_default="{}"),
        sa.Column("artifacts", sa.Text, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("completed_at", sa.Text, nullable=True),
        sa.Column("audit_reference", sa.Text, nullable=True),
        # Optimistic-concurrency version for atomic compare-and-swap updates
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status IN ('PLANNING','READY','RUNNING','WAITING_APPROVAL',"
            "'PAUSED','FAILED','CANCELLED','COMPLETED')",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint(
            "approval_mode IN ('AUTO','STEP_BY_STEP')",
            name="ck_agent_runs_approval_mode",
        ),
        if_not_exists=True,
    )
    op.create_index("idx_agent_runs_project", "agent_runs", ["project_id"], if_not_exists=True)
    op.create_index("idx_agent_runs_user", "agent_runs", ["user_id"], if_not_exists=True)
    op.create_index("idx_agent_runs_status", "agent_runs", ["status"], if_not_exists=True)
    op.create_index(
        "idx_agent_runs_conversation", "agent_runs", ["conversation_id"], if_not_exists=True
    )

    # ── pending_approvals ───────────────────────────────────────────────
    op.create_table(
        "pending_approvals",
        sa.Column("approval_id", sa.Text, primary_key=True),
        sa.Column("run_id", sa.Text, nullable=False),
        sa.Column("step_id", sa.Text, nullable=False),
        sa.Column("project_id", sa.Text, nullable=False),
        sa.Column("project_revision", sa.Integer, nullable=False),
        sa.Column("capability_id", sa.Text, nullable=False),
        sa.Column("principal_id", sa.Text, nullable=False),
        sa.Column("approval_mode", sa.Text, nullable=False),
        sa.Column("policy_result", sa.Text, nullable=False),
        sa.Column("plan_hash", sa.Text, nullable=False, server_default=""),
        sa.Column("step_payload_hash", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("decided_at", sa.Text, nullable=True),
        sa.Column("expires_at", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CANCELLED')",
            name="ck_pending_approvals_status",
        ),
        if_not_exists=True,
    )
    # At most ONE PENDING approval per (run_id, step_id); historical
    # decided/cancelled approvals are preserved immutably.
    op.create_index(
        "uq_pending_approvals_run_step_pending",
        "pending_approvals",
        ["run_id", "step_id"],
        unique=True,
        if_not_exists=True,
        postgresql_where=sa.text("status = 'PENDING'"),
        sqlite_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "idx_pending_approvals_run", "pending_approvals", ["run_id"], if_not_exists=True
    )
    op.create_index(
        "idx_pending_approvals_status", "pending_approvals", ["status"], if_not_exists=True
    )

    # ── approval_decisions (immutable, append-only) ─────────────────────
    op.create_table(
        "approval_decisions",
        sa.Column("decision_id", sa.Text, primary_key=True),
        sa.Column("approval_id", sa.Text, nullable=False),
        sa.Column("run_id", sa.Text, nullable=False),
        sa.Column("step_id", sa.Text, nullable=False),
        sa.Column("principal_id", sa.Text, nullable=False),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("timestamp", sa.Text, nullable=False),
        sa.Column("project_revision", sa.Integer, nullable=False),
        sa.Column("policy_result", sa.Text, nullable=False, server_default=""),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.ForeignKeyConstraint(
            ["approval_id"], ["pending_approvals.approval_id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVED','REJECTED')",
            name="ck_approval_decisions_decision",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "idx_approval_decisions_run", "approval_decisions", ["run_id"], if_not_exists=True
    )
    op.create_index(
        "idx_approval_decisions_approval",
        "approval_decisions",
        ["approval_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop Agent Run lifecycle tables in reverse dependency order."""
    op.drop_index(
        "uq_pending_approvals_run_step_pending", table_name="pending_approvals", if_exists=True
    )
    op.drop_index(
        "idx_approval_decisions_approval", table_name="approval_decisions", if_exists=True
    )
    op.drop_index("idx_approval_decisions_run", table_name="approval_decisions", if_exists=True)
    op.drop_table("approval_decisions", if_exists=True)

    op.drop_index("idx_pending_approvals_status", table_name="pending_approvals", if_exists=True)
    op.drop_index("idx_pending_approvals_run", table_name="pending_approvals", if_exists=True)
    op.drop_table("pending_approvals", if_exists=True)

    op.drop_index("idx_agent_runs_conversation", table_name="agent_runs", if_exists=True)
    op.drop_index("idx_agent_runs_status", table_name="agent_runs", if_exists=True)
    op.drop_index("idx_agent_runs_user", table_name="agent_runs", if_exists=True)
    op.drop_index("idx_agent_runs_project", table_name="agent_runs", if_exists=True)
    op.drop_table("agent_runs", if_exists=True)
