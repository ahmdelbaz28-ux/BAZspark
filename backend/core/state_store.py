"""backend/core/state_store.py — Production Persistence Adapter for AI Command Bus.

Frozen Phase 2A Architecture:
- Replaces in-memory process dictionaries with PostgreSQL / SQLite backed persistence.
- Provides atomic Distributed Optimistic Concurrency Control (OCC).
- Provides persistent idempotency storage.
- Provides persistent audit & domain event logging.
- Thread-safe and multi-worker safe across Uvicorn / Gunicorn clusters.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from backend.database import Database, get_db

if TYPE_CHECKING:
    from backend.core.command_bus import (
        CommandResult,
        DomainCommand,
        DomainEvent,
    )

logger = logging.getLogger(__name__)


class CommandStateStore:
    """Production Persistence Adapter for the AI Operating Spine.

    Encapsulates all transactional persistence logic, OCC row locking,
    idempotency checks, and domain event ledger operations.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_db()

    @property
    def db(self) -> Database:
        return self._db

    def _ph(self) -> str:
        return self._db._ph()

    def get_project_revision(self, project_id: str) -> int:
        """Fetch the current canonical revision for a project from persistent storage."""
        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT revision FROM project_revisions WHERE project_id = {ph}",
                (project_id,),
            )
            row = cur.fetchone()
            if row is None:
                return 1
            if isinstance(row, dict):
                return int(row.get("revision", 1))
            return int(row[0])

    def set_project_revision(self, project_id: str, revision: int) -> None:
        """Upsert the canonical project revision in persistent storage."""
        ph = self._ph()
        now_iso = datetime.now(UTC).isoformat()
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT revision, canonical_state FROM project_revisions WHERE project_id = {ph}",
                (project_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    f"""
                    INSERT INTO project_revisions (project_id, revision, canonical_state, updated_at)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                    """,
                    (project_id, revision, json.dumps({"devices": []}), now_iso),
                )
            else:
                cur.execute(
                    f"UPDATE project_revisions SET revision = {ph}, updated_at = {ph} WHERE project_id = {ph}",
                    (revision, now_iso, project_id),
                )

    def get_canonical_state(self, project_id: str) -> dict[str, Any]:
        """Load the authoritative canonical engineering state from persistent storage."""
        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT canonical_state FROM project_revisions WHERE project_id = {ph}",
                (project_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"devices": [], "revision": 1}
            state_raw = row["canonical_state"] if isinstance(row, dict) else row[0]
            try:
                state = json.loads(state_raw) if isinstance(state_raw, str) else state_raw
                return state if isinstance(state, dict) else {"devices": []}
            except Exception:
                return {"devices": [], "revision": 1}

    def save_canonical_state(
        self, project_id: str, state: dict[str, Any], revision: int
    ) -> None:
        """Upsert canonical project state and revision atomically in persistent storage."""
        ph = self._ph()
        now_iso = datetime.now(UTC).isoformat()
        state_json = json.dumps(state)
        with self._db._transaction() as cur:
            cur.execute(
                f"SELECT revision FROM project_revisions WHERE project_id = {ph}",
                (project_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    f"""
                    INSERT INTO project_revisions (project_id, revision, canonical_state, updated_at)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                    """,
                    (project_id, revision, state_json, now_iso),
                )
            else:
                cur.execute(
                    f"""
                    UPDATE project_revisions
                    SET revision = {ph}, canonical_state = {ph}, updated_at = {ph}
                    WHERE project_id = {ph}
                    """,
                    (revision, state_json, now_iso, project_id),
                )

    def get_idempotent_command(
        self, command_id: str, current_payload_hash: str | None = None
    ) -> tuple[CommandResult | None, bool]:
        """Look up a previous execution of this commandId across all workers.

        Returns (cached_result, is_collision):
          - If found and payload matches (or no hash provided): (CommandResult, False)
          - If found and payload hash differs: (None, True) [IDEMPOTENCY_KEY_REUSE_CONFLICT]
          - If not found: (None, False)
        """
        from backend.core.command_bus import CommandResult, DomainEvent

        ph = self._ph()
        with self._db._transaction() as cur:
            cur.execute(
                f"""
                SELECT command_id, correlation_id, causation_id, project_id,
                       expected_revision, committed_revision, is_dry_run, payload_hash, result_data, created_at
                FROM command_executions
                WHERE command_id = {ph}
                """,
                (command_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None, False

            if isinstance(row, dict):
                r_dict = row
            else:
                r_dict = {
                    "command_id": row[0],
                    "correlation_id": row[1],
                    "causation_id": row[2],
                    "project_id": row[3],
                    "expected_revision": row[4],
                    "committed_revision": row[5],
                    "is_dry_run": bool(row[6]),
                    "payload_hash": row[7],
                    "result_data": row[8],
                    "created_at": row[9],
                }

            stored_hash = r_dict.get("payload_hash", "")
            if current_payload_hash and stored_hash and stored_hash != current_payload_hash:
                logger.warning(
                    "Idempotency Collision: commandId '%s' reused with different payload hash (stored=%s, current=%s)",
                    command_id,
                    stored_hash,
                    current_payload_hash,
                )
                return None, True

            result_data = r_dict["result_data"]
            if isinstance(result_data, str):
                try:
                    result_data = json.loads(result_data)
                except Exception:
                    result_data = {}

            # Fetch associated domain event if committed
            cur.execute(
                f"""
                SELECT event_id, command_id, correlation_id, causation_id, project_id,
                       revision, actor, event_type, verification_result, audit_reference, payload, created_at
                FROM domain_events
                WHERE command_id = {ph}
                """,
                (command_id,),
            )
            event_row = cur.fetchone()
            event = None
            if event_row:
                if isinstance(event_row, dict):
                    e_dict = event_row
                else:
                    e_dict = {
                        "event_id": event_row[0],
                        "command_id": event_row[1],
                        "correlation_id": event_row[2],
                        "causation_id": event_row[3],
                        "project_id": event_row[4],
                        "revision": event_row[5],
                        "actor": event_row[6],
                        "event_type": event_row[7],
                        "verification_result": event_row[8],
                        "audit_reference": event_row[9],
                        "payload": event_row[10],
                        "created_at": event_row[11],
                    }

                vr = e_dict["verification_result"]
                if isinstance(vr, str):
                    try:
                        vr = json.loads(vr)
                    except Exception:
                        vr = {}

                pl = e_dict["payload"]
                if isinstance(pl, str):
                    try:
                        pl = json.loads(pl)
                    except Exception:
                        pl = {}

                event = DomainEvent(
                    eventId=e_dict["event_id"],
                    commandId=e_dict["command_id"],
                    correlationId=e_dict["correlation_id"],
                    causationId=e_dict["causation_id"],
                    projectId=e_dict["project_id"],
                    revision=int(e_dict["revision"]),
                    actor=e_dict["actor"],
                    eventType=e_dict["event_type"],
                    timestamp=e_dict["created_at"],
                    verificationResult=vr,
                    auditReference=e_dict["audit_reference"],
                    payload=pl,
                )

            res = CommandResult(
                success=True,
                commandId=r_dict["command_id"],
                projectId=r_dict["project_id"],
                revision=int(r_dict["committed_revision"]),
                isDryRun=bool(r_dict["is_dry_run"]),
                resultData=result_data,
                event=event,
            )
            return res, False

    def commit_transaction(
        self,
        command: DomainCommand,
        new_revision: int,
        exec_result: dict[str, Any],
        event: DomainEvent,
        payload_hash: str = "",
    ) -> tuple[bool, str | None]:
        """Execute transactional distributed OCC commit within a single database transaction.

        Guarantees:
          1. Atomically validates expectedRevision == current_revision in PostgreSQL/SQLite.
          2. Increments revision (N -> N+1) and updates canonical state.
          3. Persists command_execution idempotency record with payload_hash.
          4. Persists domain_events audit ledger record.
          5. If expectedRevision does not match, rolls back cleanly and returns CONCURRENCY_CONFLICT.
        """
        ph = self._ph()
        now_iso = datetime.now(UTC).isoformat()

        with self._db._transaction() as cur:
            # 1. Fetch current revision
            cur.execute(
                f"SELECT revision, canonical_state FROM project_revisions WHERE project_id = {ph}",
                (command.projectId,),
            )
            row = cur.fetchone()

            existing_devices = []
            if row is None:
                if command.expectedRevision != 1:
                    logger.warning(
                        "OCC Conflict: Project '%s' does not exist but expectedRevision is %d (expected 1)",
                        command.projectId,
                        command.expectedRevision,
                    )
                    return False, "CONCURRENCY_CONFLICT"

                new_devices = exec_result.get("devices", [])
                new_circuits = {}
                new_hydraulics = {}
                if "voltage_drop_v" in exec_result:
                    cid = str(exec_result.get("circuit_id", "nac-circuit-01"))
                    new_circuits[cid] = exec_result
                if "head_loss_m" in exec_result:
                    pid = str(exec_result.get("pipe_segment_id", "pipe-seg-01"))
                    new_hydraulics[pid] = exec_result

                updated_state = {
                    "devices": new_devices,
                    "circuits": new_circuits,
                    "hydraulics": new_hydraulics,
                    "last_mutation": command.capabilityId,
                    "revision": new_revision,
                }
                cur.execute(
                    f"""
                    INSERT INTO project_revisions (project_id, revision, canonical_state, updated_at)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                    """,
                    (command.projectId, new_revision, json.dumps(updated_state), now_iso),
                )
            else:
                curr_rev = int(row["revision"] if isinstance(row, dict) else row[0])
                if curr_rev != command.expectedRevision:
                    logger.warning(
                        "OCC Conflict: Project '%s' is at revision %d, command expected %d",
                        command.projectId,
                        curr_rev,
                        command.expectedRevision,
                    )
                    return False, "CONCURRENCY_CONFLICT"

                raw_state = row["canonical_state"] if isinstance(row, dict) else row[1]
                existing_circuits = {}
                existing_hydraulics = {}
                try:
                    loaded = json.loads(raw_state) if isinstance(raw_state, str) else raw_state
                    if isinstance(loaded, dict):
                        existing_devices = loaded.get("devices", [])
                        existing_circuits = loaded.get("circuits", {})
                        existing_hydraulics = loaded.get("hydraulics", {})
                except Exception:
                    existing_devices = []
                    existing_circuits = {}
                    existing_hydraulics = {}

                new_devices = exec_result.get("devices", [])
                if "voltage_drop_v" in exec_result:
                    cid = str(exec_result.get("circuit_id", "nac-circuit-01"))
                    existing_circuits[cid] = exec_result
                if "head_loss_m" in exec_result:
                    pid = str(exec_result.get("pipe_segment_id", "pipe-seg-01"))
                    existing_hydraulics[pid] = exec_result

                updated_state = {
                    "devices": new_devices if new_devices else existing_devices,
                    "circuits": existing_circuits,
                    "hydraulics": existing_hydraulics,
                    "last_mutation": command.capabilityId,
                    "revision": new_revision,
                }

                # Atomic OCC update
                cur.execute(
                    f"""
                    UPDATE project_revisions
                    SET revision = {ph}, canonical_state = {ph}, updated_at = {ph}
                    WHERE project_id = {ph} AND revision = {ph}
                    """,
                    (new_revision, json.dumps(updated_state), now_iso, command.projectId, command.expectedRevision),
                )
                if cur.rowcount == 0:
                    logger.warning(
                        "OCC Conflict: Race condition detected on project '%s' update",
                        command.projectId,
                    )
                    return False, "CONCURRENCY_CONFLICT"

            # 2. Persist Command Execution (enforcing unique commandId and payload_hash across all workers)
            cur.execute(
                f"""
                INSERT INTO command_executions (
                    command_id, correlation_id, causation_id, project_id, capability_id,
                    expected_revision, committed_revision, actor, is_dry_run, payload_hash, result_data, status, created_at
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    command.commandId,
                    command.correlationId,
                    command.causationId,
                    command.projectId,
                    command.capabilityId,
                    command.expectedRevision,
                    new_revision,
                    command.principal.user_id,
                    1 if command.isDryRun else 0,
                    payload_hash,
                    json.dumps(exec_result),
                    "COMPLETED",
                    now_iso,
                ),
            )

            # 3. Persist Domain Event
            cur.execute(
                f"""
                INSERT INTO domain_events (
                    event_id, command_id, correlation_id, causation_id, project_id,
                    revision, actor, event_type, verification_result, audit_reference, payload, created_at
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    event.eventId,
                    event.commandId,
                    event.correlationId,
                    event.causationId,
                    event.projectId,
                    event.revision,
                    event.actor,
                    event.eventType,
                    json.dumps(event.verificationResult),
                    event.auditReference,
                    json.dumps(event.payload),
                    now_iso,
                ),
            )

        return True, None

    def get_domain_events(
        self, project_id: str | None = None, limit: int = 50
    ) -> list[DomainEvent]:
        """Query persistent domain events with audit references."""
        from backend.core.command_bus import DomainEvent

        ph = self._ph()
        events: list[DomainEvent] = []
        with self._db._transaction() as cur:
            if project_id:
                cur.execute(
                    f"""
                    SELECT event_id, command_id, correlation_id, causation_id, project_id,
                           revision, actor, event_type, verification_result, audit_reference, payload, created_at
                    FROM domain_events
                    WHERE project_id = {ph}
                    ORDER BY created_at DESC
                    LIMIT {limit}
                    """,
                    (project_id,),
                )
            else:
                cur.execute(
                    f"""
                    SELECT event_id, command_id, correlation_id, causation_id, project_id,
                           revision, actor, event_type, verification_result, audit_reference, payload, created_at
                    FROM domain_events
                    ORDER BY created_at DESC
                    LIMIT {limit}
                    """
                )
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r, dict):
                    d = r
                else:
                    d = {
                        "event_id": r[0],
                        "command_id": r[1],
                        "correlation_id": r[2],
                        "causation_id": r[3],
                        "project_id": r[4],
                        "revision": r[5],
                        "actor": r[6],
                        "event_type": r[7],
                        "verification_result": r[8],
                        "audit_reference": r[9],
                        "payload": r[10],
                        "created_at": r[11],
                    }
                vr = d["verification_result"]
                if isinstance(vr, str):
                    try:
                        vr = json.loads(vr)
                    except Exception:
                        vr = {}
                pl = d["payload"]
                if isinstance(pl, str):
                    try:
                        pl = json.loads(pl)
                    except Exception:
                        pl = {}

                events.append(
                    DomainEvent(
                        eventId=d["event_id"],
                        commandId=d["command_id"],
                        correlationId=d["correlation_id"],
                        causationId=d["causation_id"],
                        projectId=d["project_id"],
                        revision=int(d["revision"]),
                        actor=d["actor"],
                        eventType=d["event_type"],
                        timestamp=d["created_at"],
                        verificationResult=vr,
                        auditReference=d["audit_reference"],
                        payload=pl,
                    )
                )
        return events


default_state_store = CommandStateStore()
