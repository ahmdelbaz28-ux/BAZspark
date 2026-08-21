"""
backend/services/fds_queue_service.py
======================================
FDS (Fire Dynamics Simulator) Cloud Job Queue.

Routes heavy smoke/fire simulation workloads to an external compute worker
(Modal.io) instead of running them in-process on the constrained HF Space container.

Architecture:
  [BAZspark API] --submit--> [Modal Worker] --webhook--> [BAZspark /fds/webhook]
                                                              |
                                                         [DB update]
                                                              |
                                                         [WS notify]

Without MODAL_TOKEN_ID / MODAL_TOKEN_SECRET in the environment, all jobs run
in LOCAL_SIMULATION mode so the system stays fully functional for demo purposes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# ── Modal SDK (optional) ──────────────────────────────────────────────────────
try:
    import modal  # type: ignore

    _MODAL_AVAILABLE = bool(os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET"))
except ImportError:
    modal = None  # type: ignore
    _MODAL_AVAILABLE = False

if not _MODAL_AVAILABLE:
    logger.info(
        "FDS Queue: MODAL_TOKEN_ID/MODAL_TOKEN_SECRET not set — "
        "running in LOCAL_SIMULATION mode. "
        "set these env vars to enable real cloud FDS runs."
    )


# ── Job status enum ───────────────────────────────────────────────────────────
class FDSJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SIMULATED = "simulated"  # Completed locally (demo mode)


# ── In-memory job store (cache layer — source of truth is fds_jobs table) ─────
# Keys: job_id (str) → job dict
# IMPORTANT: defined at module level so it is a true singleton across all
# FastAPI routes and test clients that import this module. Never reassign the
# dict itself — only mutate it (add/update keys) so all references stay live.
# The store is hydrated from persistent storage on first access and every
# mutation is mirrored to the `fds_jobs` table, so jobs survive pod restarts.
_JOB_STORE: dict[str, dict[str, Any]] = {}


def _get_job_store() -> dict[str, dict[str, Any]]:
    """Return the singleton job store. Always use this instead of _JOB_STORE directly."""
    return _JOB_STORE


# ── Persistent job storage (backend-aware: PostgreSQL pool or SQLite file) ────
# The in-memory store above is a cache; `fds_jobs` is the durable source of
# truth so submitted jobs survive pod restarts. When the platform uses a
# managed PostgreSQL (DATABASE_URL), jobs go there via db_backend; otherwise a
# local SQLite file (FDS_JOB_DB_PATH, default under FIREAI_DATA_DIR which the
# Helm chart mounts as a PVC at /app/data) is used.

_JOB_DB_DIR = os.environ.get(
    "FIREAI_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "data"),
)
_JOB_DB_DIR = os.path.abspath(_JOB_DB_DIR)
os.makedirs(_JOB_DB_DIR, exist_ok=True)


def _job_db_path() -> str:
    """Resolve the SQLite fallback path for the `fds_jobs` table.

    Read at call-time (not import-time) so tests can redirect it via the
    environment with monkeypatch before exercising the service.
    """
    return os.environ.get("FDS_JOB_DB_PATH", os.path.join(_JOB_DB_DIR, "fds_jobs.sqlite"))

_JOB_DB_LOCK = threading.Lock()
_JOB_DB_INITIALIZED = False
_JOB_DB_CACHE_LOADED = False

_FDS_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fds_jobs (
    job_id  TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fds_jobs_job_id ON fds_jobs(job_id);
"""


def _get_db_conn() -> Any:
    """Return a SQLite-compatible connection for the `fds_jobs` table.

    Prefers the shared PostgreSQL pool when configured and reachable
    (db_backend); otherwise the local SQLite file with WAL mode.
    """
    from backend.services import db_backend as _db

    pg = _db.pg_connection()
    if pg is not None:
        return pg

    conn = sqlite3.connect(_job_db_path(), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _ensure_job_schema() -> None:
    """Create the `fds_jobs` table if missing. Idempotent — safe to call often."""
    global _JOB_DB_INITIALIZED
    if _JOB_DB_INITIALIZED:
        return
    with _JOB_DB_LOCK:
        if _JOB_DB_INITIALIZED:
            return
        with _get_db_conn() as conn:
            conn.executescript(_FDS_JOBS_SCHEMA)
        _JOB_DB_INITIALIZED = True


def _load_jobs_from_db() -> None:
    """Hydrate the in-memory store from persistent storage (once).

    Runs lazily on the first status/list/webhook access so jobs submitted
    before a pod restart remain queryable and their webhooks still apply.
    """
    global _JOB_DB_CACHE_LOADED
    if _JOB_DB_CACHE_LOADED:
        return
    with _JOB_DB_LOCK:
        if _JOB_DB_CACHE_LOADED:
            return
        _ensure_job_schema()
        try:
            with _get_db_conn() as conn:
                rows = conn.execute("SELECT job_id, payload FROM fds_jobs").fetchall()
            store = _get_job_store()
            for row in rows:
                try:
                    job_id = row["job_id"]
                    if job_id in store:
                        continue
                    store[job_id] = json.loads(row["payload"])
                except (TypeError, ValueError):
                    # Corrupt/legacy row — never let one bad record break startup.
                    logger.warning("FDS Queue: skipping unparseable persisted job row")
                    continue
        finally:
            _JOB_DB_CACHE_LOADED = True


def _persist_job(job: dict[str, Any]) -> None:
    """Insert or upsert a job record (durable across restarts)."""
    _ensure_job_schema()
    payload = json.dumps(job, default=str)
    with _get_db_conn() as conn:
        conn.execute(
            "INSERT INTO fds_jobs (job_id, payload) VALUES (?, ?) "
            "ON CONFLICT(job_id) DO UPDATE SET payload = excluded.payload",
            (job["job_id"], payload),
        )


# ════════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════════


def submit_fds_job(
    fds_input: str,
    project_id: str = "",
    user_id: str = "",
    webhook_url: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Submit an FDS simulation job.

    Args:
        fds_input:   Raw FDS input file content (*.fds text).
        project_id:  BAZspark project ID for result association.
        user_id:     Requesting user ID.
        webhook_url: URL BAZspark will POST results to (auto-filled by router).
        metadata:    Optional extra metadata stored with the job.

    Returns:
        dict with job_id, status, estimated_runtime_sec.
    """
    job_id = str(uuid.uuid4())
    # V294 SECURITY FIX (Bandit B324): MD5 used for non-security checksum
    # (deduplication of FDS input files). Marked usedforsecurity=False to
    # satisfy Bandit and document intent. If this checksum is ever used for
    # security purposes (auth, integrity verification against adversarial
    # input), switch to hashlib.sha256().
    checksum = hashlib.md5(fds_input.encode(), usedforsecurity=False).hexdigest()

    job: dict[str, Any] = {
        "job_id": job_id,
        "project_id": project_id,
        "user_id": user_id,
        "status": FDSJobStatus.PENDING,
        "submitted_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "fds_checksum": checksum,
        "webhook_url": webhook_url,
        "result": None,
        "error": None,
        "metadata": metadata or {},
        "modal_call_id": None,
    }
    _get_job_store()[job_id] = job

    if _MODAL_AVAILABLE:
        _submit_to_modal(job_id, fds_input, webhook_url)
    else:
        _run_local_simulation(job_id, fds_input)

    # Mirror the final job state into durable storage (survives restarts).
    _persist_job(job)

    logger.info(
        "FDS Job %s submitted (modal=%s)",  # nosec: S5145 — job_id is server-generated UUID
        job_id,
        _MODAL_AVAILABLE,
    )
    return {
        "job_id": job_id,
        "status": job["status"],
        "modal_enabled": _MODAL_AVAILABLE,
        "estimated_runtime_sec": 180 if _MODAL_AVAILABLE else 5,
        "checksum": checksum,
    }


def get_fds_job_status(job_id: str) -> dict[str, Any]:
    """Return the current status and result of a job."""
    _load_jobs_from_db()
    job = _get_job_store().get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "submitted_at": job["submitted_at"],
        "completed_at": job["completed_at"],
        "project_id": job["project_id"],
        "result": job["result"],
        "error": job["error"],
    }


def list_fds_jobs(user_id: str = "", limit: int = 20) -> dict[str, Any]:
    """list recent FDS jobs for a user."""
    _load_jobs_from_db()
    jobs = [
        {k: v for k, v in j.items() if k != "fds_checksum"}
        for j in _get_job_store().values()
        if not user_id or j.get("user_id") == user_id
    ]
    jobs_sorted = sorted(jobs, key=lambda x: x["submitted_at"], reverse=True)
    return {"jobs": jobs_sorted[:limit], "total": len(jobs_sorted)}


def handle_fds_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Handle an incoming webhook from Modal (or internal simulation).
    Updates the job record and notifies connected WebSocket clients.

    Expected payload:
        {
            "job_id": "...",
            "status": "completed" | "failed",
            "result": { ... },   # on success
            "error":  "...",     # on failure
            "secret": "..."      # HMAC validation token
        }
    """
    job_id = payload.get("job_id", "")
    status = payload.get("status", "")

    # Validate the webhook secret — S-01 FIX (Engineering Review):
    # Use hmac.compare_digest to prevent timing attacks. The previous code used
    # `received_secret != expected_secret` which leaks secret length / prefix via
    # timing differences. Also fail-closed if either value is empty.
    expected_secret = _compute_webhook_secret(job_id)
    received_secret = payload.get("secret", "") or ""
    if not expected_secret or not received_secret:
        logger.warning("FDS Webhook: missing secret for job (len=%d)", len(job_id))
        return {"error": "Invalid webhook secret"}
    if not hmac.compare_digest(received_secret, expected_secret):
        logger.warning("FDS Webhook: invalid secret for job (len=%d)", len(job_id))
        return {"error": "Invalid webhook secret"}

    # Recover jobs submitted before a possible pod restart, then locate it.
    _load_jobs_from_db()
    job = _get_job_store().get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}

    job["status"] = status
    job["completed_at"] = datetime.now(UTC).isoformat()
    job["result"] = payload.get("result")
    job["error"] = payload.get("error")
    # Persist the new state so the result survives even if the pod restarts
    # again before the client polls.
    _persist_job(job)

    logger.info("FDS Job %s → %s", job_id, status)

    # WebSocket notification is handled at the router level
    # (backend/routers/fds_webhook.py:fds_result_webhook) after this
    # function returns, so the project_id is available in the response.

    return {"received": True, "job_id": job_id, "status": status}


# ════════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ════════════════════════════════════════════════════════════════════════════════


def _compute_webhook_secret(job_id: str) -> str:
    """Deterministic HMAC-like secret tied to the job_id and a server secret."""
    server_secret = os.getenv("FDS_WEBHOOK_SECRET")
    if not server_secret:
        raise ValueError(
            "FDS_WEBHOOK_SECRET environment variable is not set. "
            "Webhook authentication requires a configured server secret."
        )
    raw = f"{job_id}:{server_secret}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _submit_to_modal(job_id: str, fds_input: str, webhook_url: str) -> None:
    """Submit the FDS job to Modal.io (real cloud compute)."""
    try:
        # Import the Modal app defined in modal_runner/fds_worker.py
        # modal_runner must be importable (ensure it's in the Python path)
        import importlib

        fds_worker = importlib.import_module("modal_runner.fds_worker")

        # Call the Modal function asynchronously (spawns a cloud container)
        call = fds_worker.run_fds_simulation.spawn(  # type: ignore
            job_id=job_id,
            fds_input=fds_input,
            webhook_url=webhook_url,
            webhook_secret=_compute_webhook_secret(job_id),
        )
        _get_job_store()[job_id]["modal_call_id"] = call.object_id
        _get_job_store()[job_id]["status"] = FDSJobStatus.RUNNING
        logger.info("FDS Job %s dispatched to Modal, call_id=%s", job_id, call.object_id)

    except Exception as exc:
        logger.exception("Failed to submit FDS job %s to Modal", job_id)
        _get_job_store()[job_id]["status"] = FDSJobStatus.FAILED
        _get_job_store()[job_id]["error"] = str(exc)


def _run_local_simulation(job_id: str, fds_input: str) -> None:
    """
    Fast local simulation stub — produces plausible results instantly.
    Used when Modal credentials are absent (demo/dev mode).
    """
    lines = fds_input.strip().split("\n")
    duration = 0.0
    mesh_count = sum(1 for l in lines if l.strip().startswith("&MESH"))
    for line in lines:
        if "T_END" in line:
            try:
                duration = float(line.split("T_END=")[1].split(",")[0].strip().rstrip("/"))
            except (IndexError, ValueError):
                pass

    simulated_result = {
        "simulation_type": "LOCAL_SIMULATION",
        "duration_s": duration or 60.0,
        "mesh_count": mesh_count or 1,
        "max_temperature_c": 320.5,
        "smoke_layer_height_m": 2.1,
        "visibility_m": 8.4,
        "co_ppm_max": 145.0,
        "hrr_peak_kw": 1850.0,
        "evacuation_time_s": 210,
        "note": (
            "Simulated locally (no Modal credentials). "
            "set MODAL_TOKEN_ID + MODAL_TOKEN_SECRET for real FDS runs."
        ),
    }

    _get_job_store()[job_id]["status"] = FDSJobStatus.SIMULATED
    _get_job_store()[job_id]["completed_at"] = datetime.now(UTC).isoformat()
    _get_job_store()[job_id]["result"] = simulated_result


def reset_for_tests() -> None:
    """Reset the in-memory store and drop persisted jobs. TEST-ONLY.

    Clears the module-level cache and deletes the `fds_jobs` table from the
    active database so each test starts clean (mirrors Meeza's reset helper).
    Never call from production code.
    """
    global _JOB_DB_INITIALIZED, _JOB_DB_CACHE_LOADED
    _get_job_store().clear()
    try:
        with _get_db_conn() as conn:
            conn.executescript("DROP TABLE IF EXISTS fds_jobs;")
    except Exception:  # NOSONAR — best-effort cleanup of a test database
        logger.debug("FDS Queue: reset_for_tests DROP ignored", exc_info=True)
    _JOB_DB_INITIALIZED = False
    _JOB_DB_CACHE_LOADED = False
