"""Add billing & Meeza payment tables (orders, payment_transactions, payment_events).

Revision ID: 006
Revises: 005
Create Date: 2026-08-04

This migration creates the three tables required by the Meeza (ميزة) payment
gateway integration:

  - orders              — billing orders created by users
  - payment_transactions — per-attempt payment records (one order → N txns)
  - payment_events      — idempotent log of every webhook delivery

The runtime CRUD in backend/services/meeza_payment_service.py uses raw SQL with
`CREATE TABLE IF NOT EXISTS` (mirroring the FDS queue pattern), so this migration
is mainly for PostgreSQL / managed-DB deployments that use Alembic exclusively.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create billing & Meeza payment tables."""
    # ── orders ──────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_principal", sa.Text, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="EGP"),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Text, nullable=True),
        sa.Column("paid_at", sa.Text, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','paid','failed','expired','cancelled','refunded')",
            name="ck_orders_status",
        ),
        if_not_exists=True,
    )
    op.create_index("idx_orders_user",    "orders", ["user_principal"], if_not_exists=True)
    op.create_index("idx_orders_status",  "orders", ["status"],          if_not_exists=True)
    op.create_index("idx_orders_created", "orders", ["created_at"],      if_not_exists=True)

    # ── payment_transactions ────────────────────────────────────────────
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("order_id", sa.Text, nullable=False),
        sa.Column("psp_name", sa.Text, nullable=False),
        sa.Column("psp_order_id", sa.Text, nullable=True),
        sa.Column("psp_payment_key", sa.Text, nullable=True),
        sa.Column("psp_txn_id", sa.Text, nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="EGP"),
        sa.Column("status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.Text, nullable=False),
        sa.Column("raw_payload", sa.Text, nullable=False, server_default="{}"),
        sa.Column("hmac_signature", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("completed_at", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('PENDING','SUCCESS','FAILED','EXPIRED','CANCELLED')",
            name="ck_payment_transactions_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_transactions_idempotency_key"),
        if_not_exists=True,
    )
    op.create_index("idx_txn_order",  "payment_transactions", ["order_id"],   if_not_exists=True)
    op.create_index("idx_txn_status", "payment_transactions", ["status"],     if_not_exists=True)
    op.create_index("idx_txn_psp",    "payment_transactions", ["psp_txn_id"], if_not_exists=True)

    # ── payment_events ──────────────────────────────────────────────────
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("transaction_id", sa.Text, nullable=True),
        sa.Column("order_id", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("psp_name", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.Text, nullable=False),
        sa.Column("raw_payload", sa.Text, nullable=False, server_default="{}"),
        sa.Column("hmac_signature", sa.Text, nullable=True),
        sa.Column("processed_at", sa.Text, nullable=False),
        sa.Column("response_code", sa.Integer, nullable=False, server_default="200"),
        sa.ForeignKeyConstraint(["transaction_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_events_idempotency_key"),
        if_not_exists=True,
    )
    op.create_index("idx_evt_order", "payment_events", ["order_id"],        if_not_exists=True)
    op.create_index("idx_evt_idem",  "payment_events", ["idempotency_key"], if_not_exists=True)


def downgrade() -> None:
    """Drop billing tables in reverse dependency order."""
    op.drop_table("payment_events", if_exists=True)
    op.drop_table("payment_transactions", if_exists=True)
    op.drop_table("orders", if_exists=True)
