# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
backend/db_models.py — SQLAlchemy ORM models for Alembic autogenerate support.

These models mirror the exact schema defined in database.py (_init_schema / _init_schema_pg).
They are used ONLY by Alembic for `alembic revision --autogenerate` to detect schema changes.
The runtime CRUD operations in database.py use raw SQL with parameterized placeholders.

When you modify the schema in database.py, you MUST also update the corresponding
SQLAlchemy model here, then run `alembic revision --autogenerate -m "description"`.
"""

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""



class Project(Base):
    """A fire alarm engineering project."""

    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False, server_default="")
    author = Column(String, nullable=False, server_default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        String,
        nullable=False,
        server_default="draft",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'draft')",
            name="ck_projects_status",
        ),
    )

    # Relationships
    devices = relationship("Device", back_populates="project", cascade="all, delete-orphan")  # NOSONAR — S1192: duplicated literal acceptable in this localized context
    connections = relationship("Connection", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")


class Device(Base):
    """A fire alarm device within a project."""

    __tablename__ = "devices"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)  # NOSONAR — S1192: duplicated literal acceptable in this localized context
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False, server_default="0.0")
    rotation = Column(Float, nullable=False, server_default="0.0")
    voltage = Column(Float, nullable=False, server_default="0.0")
    current = Column(Float, nullable=False, server_default="0.0")
    load = Column(Float, nullable=False, server_default="0.0")
    properties = Column(Text, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="devices")

    __table_args__ = (
        Index("idx_devices_project", "project_id"),
        Index("idx_devices_type", "type"),
    )


class Connection(Base):
    """A cable connection between two devices."""

    __tablename__ = "connections"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    from_id = Column(String, nullable=False)
    to_id = Column(String, nullable=False)
    cable_size = Column(String, nullable=False, server_default="1.5mm²")
    length = Column(Float, nullable=False, server_default="0.0")
    type = Column(String, nullable=False, server_default="power")
    created_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="connections")

    __table_args__ = (
        Index("idx_connections_project", "project_id"),
        Index("idx_connections_from", "from_id"),
        Index("idx_connections_to", "to_id"),
    )


class Report(Base):
    """An engineering report for a project."""

    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False, server_default="")
    parameters = Column(Text, nullable=False, server_default="{}")
    status = Column(
        String,
        nullable=False,
        server_default="pending",
    )
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="reports")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_reports_status",
        ),
        Index("idx_reports_project", "project_id"),
        Index("idx_reports_status", "status"),
    )


class SyncStatus(Base):
    """Status of project synchronization."""

    __tablename__ = "sync_status"

    project_id = Column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status = Column(
        String,
        nullable=False,
        server_default="synced",
    )
    last_sync = Column(DateTime(timezone=True), nullable=False)
    pending_changes = Column(Integer, nullable=False, server_default="0")
    error = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('syncing', 'synced', 'error')",
            name="ck_sync_status_status",
        ),
    )


class SyncOperation(Base):
    """Granular per-entity sync tracking."""

    __tablename__ = "sync_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    target_db = Column(String, nullable=False)
    status = Column(String, server_default="pending")
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, server_default="0")

    __table_args__ = (
        Index("idx_sync_ops_entity", "entity_type", "entity_id"),
        Index("idx_sync_ops_status", "status"),
    )


class ETAPIntegration(Base):
    """ETAP electrical system integration configuration."""

    __tablename__ = "etap_integrations"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    enabled = Column(sa.Boolean, nullable=False, server_default="false")
    last_sync = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_etap_integrations_project", "project_id"),
    )


class ETAPSyncLog(Base):
    """Log of ETAP synchronization operations."""

    __tablename__ = "etap_sync_logs"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    direction = Column(String, nullable=False)
    status = Column(String, nullable=False)
    records_synced = Column(Integer, nullable=False, server_default="0")
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_etap_sync_logs_project", "project_id"),
        Index("idx_etap_sync_logs_created", "created_at"),
    )


class AuditLog(Base):
    """Audit log for tracking safety-critical operations per NFPA 72."""

    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # CREATE, UPDATE, DELETE, VIEW
    entity_type = Column(String, nullable=False)  # projects, devices, etc.
    entity_id = Column(String, nullable=False)
    old_values = Column(Text)  # JSON string of old values
    new_values = Column(Text)  # JSON string of new values
    ip_address = Column(String)
    user_agent = Column(String)

    __table_args__ = (
        Index("idx_audit_log_timestamp", "timestamp"),
        Index("idx_audit_log_user", "user_id"),
        Index("idx_audit_log_entity", "entity_type", "entity_id"),
        Index("idx_audit_log_action", "action"),
    )


# ── Billing & Meeza Payment models ──────────────────────────────────────────
# Added for Meeza (ميزة) payment gateway integration. See
# backend/services/meeza_payment_service.py for runtime CRUD (raw SQL) and
# backend/routers/billing.py for the FastAPI endpoints.

class Order(Base):
    """A billing order. Created by the caller, paid via a Meeza transaction."""

    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    user_principal = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, server_default="EGP")
    status = Column(
        String,
        nullable=False,
        server_default="pending",
    )
    description = Column(String, nullable=False, server_default="")
    # SQLAlchemy reserves 'metadata' for Declarative; use metadata_ as the
    # attribute name but keep the DB column name as 'metadata'.
    metadata_ = Column("metadata", Text, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','paid','failed','expired','cancelled','refunded')",
            name="ck_orders_status",
        ),
        Index("idx_orders_user", "user_principal"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_created", "created_at"),
    )

    transactions = relationship(
        "PaymentTransaction", back_populates="order", cascade="all, delete-orphan"
    )


class PaymentTransaction(Base):
    """A single payment attempt for an order. Multiple transactions may exist
    per order (e.g. a failed attempt followed by a successful one)."""

    __tablename__ = "payment_transactions"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    psp_name = Column(String, nullable=False)
    psp_order_id = Column(String)
    psp_payment_key = Column(String)
    psp_txn_id = Column(String)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, server_default="EGP")
    status = Column(String, nullable=False, server_default="PENDING")
    idempotency_key = Column(String, nullable=False, unique=True)
    raw_payload = Column(Text, nullable=False, server_default="{}")
    hmac_signature = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','SUCCESS','FAILED','EXPIRED','CANCELLED')",
            name="ck_payment_transactions_status",
        ),
        Index("idx_txn_order", "order_id"),
        Index("idx_txn_status", "status"),
        Index("idx_txn_psp", "psp_txn_id"),
    )

    order = relationship("Order", back_populates="transactions")
    events = relationship(
        "PaymentEvent", back_populates="transaction", cascade="all, delete-orphan"
    )


class PaymentEvent(Base):
    """A webhook event received from the PSP. Idempotent by `idempotency_key`."""

    __tablename__ = "payment_events"

    id = Column(String, primary_key=True)
    transaction_id = Column(
        String, ForeignKey("payment_transactions.id", ondelete="SET NULL")
    )
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    psp_name = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=False, unique=True)
    raw_payload = Column(Text, nullable=False, server_default="{}")
    hmac_signature = Column(String)
    processed_at = Column(DateTime(timezone=True), nullable=False)
    response_code = Column(Integer, nullable=False, server_default="200")

    __table_args__ = (
        Index("idx_evt_order", "order_id"),
        Index("idx_evt_idem", "idempotency_key"),
    )

    transaction = relationship("PaymentTransaction", back_populates="events")
