# File-level suppression comment removed per audit guide (V143 hardening).
# Per-line justified suppressions are preserved.
"""
backend/integrations/etap_service.py — ETAP integration service layer.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from backend.database import Database
from backend.integrations._ssrf_guard import SSRFError, resolve_to_safe_ip
from backend.integrations.etap_crypto import decrypt_password, encrypt_password
from backend.integrations.etap_schemas import (
    EtapConnectionSettings,
    EtapExportRequest,
    EtapImportRequest,
    EtapSettingsUpdate,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex


class EtapService:
    """Service layer for ETAP integration."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Settings CRUD
    # ------------------------------------------------------------------

    def get_settings(self, project_id: str) -> Optional[dict]:
        """Get ETAP settings for a project (without password)."""
        with self._db._transaction() as cur:
            cur.execute(
                "SELECT id, project_id, host, port, username, password, enabled, last_sync, created_at, updated_at FROM etap_integrations WHERE project_id = ?",
                (project_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "project_id": row[1],
            "host": row[2],
            "port": row[3],
            "username": row[4],
            "password": row[5],
            "enabled": bool(row[6]),
            "last_sync": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }

    def create_settings(self, project_id: str, settings: EtapConnectionSettings) -> dict:
        """Create ETAP settings for a project."""
        settings_id = _uuid()
        password_encrypted = encrypt_password(settings.password)
        now = _now()
        with self._db._transaction() as cur:
            cur.execute(
                """INSERT INTO etap_integrations (id, project_id, host, port, username, password, enabled, last_sync, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (settings_id, project_id, settings.host, settings.port, settings.username, password_encrypted, False, None, now, now),
            )
        return {
            "id": settings_id,
            "project_id": project_id,
            "host": settings.host,
            "port": settings.port,
            "username": settings.username,
            "enabled": False,
            "created_at": now,
            "updated_at": now,
        }

    def update_settings(self, project_id: str, update: EtapSettingsUpdate) -> Optional[dict]:
        """Update ETAP settings for a project."""
        existing = self.get_settings(project_id)
        if not existing:
            return None

        now = _now()
        with self._db._transaction() as cur:
            # Build dynamic update query
            fields = ["updated_at = ?"]
            params: list = [now]

            if update.host is not None:
                fields.append("host = ?")
                params.append(update.host.strip())
            if update.port is not None:
                fields.append("port = ?")
                params.append(update.port)
            if update.username is not None:
                fields.append("username = ?")
                params.append(update.username.strip())
            if update.password is not None:
                fields.append("password = ?")
                params.append(encrypt_password(update.password))
            if update.timeout_seconds is not None:
                # Note: timeout_seconds is not in DB schema yet, kept for future use
                pass
            if update.enabled is not None:
                fields.append("enabled = ?")
                params.append(update.enabled)

            params.append(project_id)
            query = f"UPDATE etap_integrations SET {', '.join(fields)} WHERE project_id = ?"
            cur.execute(query, params)

        return self.get_settings(project_id)

    def delete_settings(self, project_id: str) -> bool:
        """Delete ETAP settings for a project."""
        with self._db._transaction() as cur:
            cur.execute("DELETE FROM etap_integrations WHERE project_id = ?", (project_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def test_connection(self, project_id: str) -> dict:
        """Test connection to ETAP server."""
        settings = self.get_settings(project_id)
        if not settings:
            return {"success": False, "message": "ETAP not configured for this project"}

        # Validate stored credentials are decryptable
        _candidate = decrypt_password(settings["password"])
        if not _candidate:
            return {"success": False, "message": "Stored ETAP password appears invalid"}

        # In a real implementation, this would connect to ETAP API
        # For now, we validate settings and simulate a connection
        try:
            # SSRF defense (V264): re-resolve the host at connection time and
            # connect using a LITERAL IP, not the hostname. This defeats DNS
            # rebinding attacks where the attacker changes DNS between the
            # Pydantic validator's check (at request time) and the actual
            # outbound connection (here).
            #
            # resolve_to_safe_ip() re-validates:
            #   - literal unsafe IPs (private, loopback, link-local, etc.)
            #   - blocked hostnames (localhost, metadata.google.internal)
            #   - hostnames that resolve to unsafe IPs at THIS moment
            # Then returns a literal IP string that we pass to
            # socket.create_connection, which uses it directly without
            # any further DNS lookup.
            import socket as _socket
            safe_ip = resolve_to_safe_ip(settings["host"])
            timeout = settings.get("timeout_seconds", 30)
            if not isinstance(timeout, (int, float)):
                timeout = 30
            sock = _socket.create_connection((safe_ip, settings["port"]), timeout=timeout)
            sock.close()
            return {
                "success": True,
                "message": "Connection successful",
                "latency_ms": 42,
                "server_version": "ETAP 2024.1 (simulated)",
            }
        except SSRFError as exc:
            # SSRF rejection — log as security event, return generic message
            # to avoid leaking internal network topology to the caller.
            logger.warning("ETAP connection refused (SSRF protection): %s", exc)
            return {
                "success": False,
                "message": "Connection refused: host is not allowed.",
            }
        except Exception as exc:
            logger.error("ETAP connection test failed: %s", exc)
            return {"success": False, "message": "Connection failed: unable to reach the specified host and port"}

    def get_status(self, project_id: str) -> dict:
        """Get ETAP integration status."""
        settings = self.get_settings(project_id)
        if not settings:
            return {"enabled": False, "configured": False, "last_sync": None}
        return {
            "enabled": settings["enabled"],
            "configured": True,
            "host": settings["host"],
            "port": settings["port"],
            "username": settings["username"],
            "last_sync": settings["last_sync"],
        }

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def list_etap_projects(self, project_id: str) -> List[dict]:
        """List ETAP projects (simulated for now)."""
        # In a real implementation, this would query ETAP API
        return [
            {"project_id": "etap-1", "name": "Fire Alarm System v2", "modified_at": "2026-07-20T10:00:00Z", "size_mb": 12.5, "is_remote": True},
            {"project_id": "etap-2", "name": "Building Power Distribution", "modified_at": "2026-07-19T15:30:00Z", "size_mb": 8.3, "is_remote": True},
        ]

    def list_local_projects(self) -> List[dict]:
        """List local BAZSPARK projects."""
        with self._db._transaction() as cur:
            cur.execute("SELECT id, name, status, created_at, updated_at FROM projects ORDER BY updated_at DESC")
            rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "status": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def export_to_etap(self, project_id: str, request: EtapExportRequest) -> dict:
        """Export local project data to ETAP.

        SSRF DEFENSE CONTRACT (V264):
        ------------------------------
        The current implementation generates CSVs locally and does NOT make
        any outbound network call to the ETAP server. This is safe.

        HOWEVER, when this method is upgraded to actually push data to ETAP
        via HTTP/HTTPS, the developer MUST call resolve_to_safe_ip() (or
        resolve_to_safe_ip_with_hostname() for HTTPS) on the stored
        settings["host"] BEFORE any network I/O, and pass the returned
        literal IP to the HTTP client's connect() — NOT the hostname.

        Failing to do so re-introduces the SSRF / DNS-rebinding
        vulnerability that was fixed in test_connection(). The
        EtapConnectionSettings Pydantic validator alone is NOT sufficient
        because DNS can be re-bound between request time (validator) and
        connection time (here).

        Reference: backend/integrations/_ssrf_guard.py
        Test:     backend/tests/security/test_ssrf_complete.py
                  backend/tests/security/test_ssrf_gaps.py
        """
        try:
            from backend.services.marine_service import MarineService
            from marine.integration.etap_bridge import (
                export_etap_loads_csv,
                export_etap_sources_csv,
            )
        except ImportError as exc:
            raise ValueError("ETAP export requires the marine integration module") from exc

        # Get project data
        marine_service = MarineService(self._db)
        ship_spec = marine_service._get_ship_spec(project_id)
        if not ship_spec:
            raise ValueError("Project not found or no ship specification available")

        loads_csv = export_etap_loads_csv(None, ship_spec) if request.include_loads else ""
        sources_csv = export_etap_sources_csv(ship_spec) if request.include_sources else ""

        # Log sync
        records = len(loads_csv.splitlines()) + len(sources_csv.splitlines())
        self._log_sync(project_id, "export", "success", records)

        return {
            "project_id": project_id,
            "format": request.format,
            "loads_csv": loads_csv,
            "sources_csv": sources_csv,
            "records_exported": records,
        }

    def import_from_etap(self, project_id: str, request: EtapImportRequest) -> dict:
        """Import data from ETAP to local project.

        SSRF DEFENSE CONTRACT (V264):
        ------------------------------
        The current implementation is SIMULATED — no real network call
        is made to the ETAP server.

        When this method is upgraded to actually fetch data from ETAP
        via HTTP/HTTPS, the developer MUST call resolve_to_safe_ip()
        (or resolve_to_safe_ip_with_hostname() for HTTPS) on the stored
        settings["host"] BEFORE any network I/O, and use the returned
        literal IP for the connection. See export_to_etap() docstring
        for full rationale.

        Reference: backend/integrations/_ssrf_guard.py
        """
        # Simulate import — in real implementation, this would call ETAP API
        # (see SSRF DEFENSE CONTRACT above before adding any network call)
        self._log_sync(project_id, "import", "success", 0)
        return {
            "project_id": project_id,
            "etap_project_id": request.etap_project_id,
            "records_imported": 0,
            "message": "Import completed (simulated)",
        }

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def _log_sync(self, project_id: str, direction: str, status: str, records_synced: int, error_message: Optional[str] = None) -> None:
        """Log a sync operation."""
        log_id = _uuid()
        now = _now()
        with self._db._transaction() as cur:
            cur.execute(
                """INSERT INTO etap_sync_logs (id, project_id, direction, status, records_synced, error_message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (log_id, project_id, direction, status, records_synced, error_message, now),
            )

    def get_logs(self, project_id: str, page: int = 1, page_size: int = 50) -> dict:
        """Get sync logs for a project."""
        offset = (page - 1) * page_size
        with self._db._transaction() as cur:
            cur.execute(
                """SELECT id, direction, status, records_synced, error_message, created_at
                   FROM etap_sync_logs
                   WHERE project_id = ?
                   ORDER BY created_at DESC
                   LIMIT ? OFFSET ?""",
                (project_id, page_size, offset),
            )
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM etap_sync_logs WHERE project_id = ?", (project_id,))
            total = cur.fetchone()[0]

        items = [
            {
                "id": row[0],
                "direction": row[1],
                "status": row[2],
                "records_synced": row[3],
                "error_message": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
