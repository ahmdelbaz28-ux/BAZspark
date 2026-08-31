"""backend/core/shared_state.py — Multi-Replica Shared State Store (S5).

Externalizes per-process in-memory state:
1. Single-use WebSocket tickets (ws_tickets) across multi-process workers.
2. Active agent session tracking (active_agents_shared).
3. Idempotent command results (delegating to shared state_store / database).
4. Supports multi-replica deployments (replicas >= 2), officially lifting Containment A6.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from backend.database import get_db

logger = logging.getLogger(__name__)

WS_TICKET_TTL_SECONDS = 60


class SharedStateStore:
    """Database-backed shared state store for multi-replica worker synchronization."""

    def __init__(self, db=None) -> None:
        self._db = db
        self._worker_id = os.environ.get("HOSTNAME") or f"worker-{os.getpid()}-{secrets.token_hex(4)}"

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def _ensure_tables(self) -> None:
        """Ensure shared state tables exist."""
        try:
            with self.db._transaction() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ws_tickets (
                        ticket TEXT PRIMARY KEY,
                        role TEXT NOT NULL,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL DEFAULT '',
                        origin TEXT NOT NULL DEFAULT '',
                        expires_at REAL NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_agents_shared (
                        agent_id TEXT PRIMARY KEY,
                        agent_type TEXT NOT NULL,
                        worker_id TEXT NOT NULL,
                        registered_at TEXT NOT NULL,
                        last_heartbeat TEXT NOT NULL
                    )
                """)
        except Exception as e:
            logger.exception("Error creating shared state tables: %s", e)

    # ── 1. Single-Use WebSocket Tickets ─────────────────────────────────────

    def issue_ws_ticket(self, api_key_info: Any, origin: str | None, ttl_seconds: int = WS_TICKET_TTL_SECONDS) -> str:
        """Create a single-use ticket in the shared database store."""
        self._ensure_tables()
        now_ts = time.time()
        now_iso = datetime.now(UTC).isoformat()
        ticket = secrets.token_urlsafe(32)

        role = getattr(api_key_info, "role", "engineer")
        if hasattr(role, "value"):
            role = role.value
        name = getattr(api_key_info, "name", "browser_user")
        email = getattr(api_key_info, "email", "")
        clean_origin = (origin or "").strip().lower().rstrip("/")

        # Opportunistically purge expired tickets
        with self.db._transaction() as cur:
            cur.execute(
                f"DELETE FROM ws_tickets WHERE expires_at <= {self.db._ph()}",
                (now_ts,),
            )
            cur.execute(
                f"""INSERT INTO ws_tickets (ticket, role, name, email, origin, expires_at, created_at)
                    VALUES ({self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()})""",
                (ticket, str(role), str(name), str(email), clean_origin, now_ts + ttl_seconds, now_iso),
            )
        return ticket

    def consume_ws_ticket(self, ticket: str, origin: str | None) -> SimpleNamespace | None:
        """Atomically read and burn a ticket from the shared store."""
        self._ensure_tables()
        now_ts = time.time()
        clean_origin = (origin or "").strip().lower().rstrip("/")

        with self.db._transaction() as cur:
            cur.execute(
                f"SELECT role, name, email, origin, expires_at FROM ws_tickets WHERE ticket = {self.db._ph()}",
                (ticket,),
            )
            row = cur.fetchone()
            if not row:
                return None

            role, name, email, expected_origin, expires_at = row
            # Burn immediately (single use)
            cur.execute(
                f"DELETE FROM ws_tickets WHERE ticket = {self.db._ph()}",
                (ticket,),
            )

        if expires_at <= now_ts:
            logger.warning("Shared WS ticket expired for ticket=%s", ticket[:8])
            return None

        if expected_origin and clean_origin and clean_origin != expected_origin:
            logger.warning("Shared WS ticket origin mismatch: expected %s, got %s", expected_origin, clean_origin)
            return None

        logger.info("Shared WS ticket accepted for %s across worker %s", name, self._worker_id)
        return SimpleNamespace(role=role, name=name, email=email)

    # ── 2. Active Agent Session Tracking ────────────────────────────────────

    def register_active_agent(self, agent_type: str, agent_id: str | None = None) -> str:
        """Register active agent session in shared store."""
        self._ensure_tables()
        aid = agent_id or f"{agent_type}-{secrets.token_hex(6)}"
        now_iso = datetime.now(UTC).isoformat()

        with self.db._transaction() as cur:
            # Newest-wins replacement for agent_type
            cur.execute(
                f"DELETE FROM active_agents_shared WHERE agent_type = {self.db._ph()}",
                (agent_type,),
            )
            cur.execute(
                f"""INSERT INTO active_agents_shared (agent_id, agent_type, worker_id, registered_at, last_heartbeat)
                    VALUES ({self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()})""",
                (aid, agent_type, self._worker_id, now_iso, now_iso),
            )
        return aid

    def has_active_agent(self, agent_type: str) -> bool:
        """Check if active agent of agent_type is registered across any cluster worker."""
        self._ensure_tables()
        with self.db._transaction() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM active_agents_shared WHERE agent_type = {self.db._ph()}",
                (agent_type,),
            )
            count = cur.fetchone()[0]
            return count > 0

    def unregister_active_agent(self, agent_id: str) -> None:
        """Remove agent registration on disconnect."""
        self._ensure_tables()
        with self.db._transaction() as cur:
            cur.execute(
                f"DELETE FROM active_agents_shared WHERE agent_id = {self.db._ph()}",
                (agent_id,),
            )


default_shared_state = SharedStateStore()
