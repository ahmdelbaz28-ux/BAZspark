"""
backend/services/db_backend.py
===============================
Shared backend-agnostic database connection layer for the raw-SQL service
modules in this package that historically ran against an isolated SQLite
file (the Meeza billing service and the FDS job queue).

When `DATABASE_URL` points at a reachable PostgreSQL **and** psycopg2 is
importable, connections are served from a psycopg2 thread pool and the
modules' `?` placeholders are transparently translated to psycopg2 `%s`, so
the same SQL runs unchanged on either backend. When PostgreSQL is unavailable
(psycopg2 not installed / host unreachable), `pg_connection()` returns `None`
and each caller falls back to its own SQLite file — mirroring the graceful
"degrade to SQLite" pattern already established in `backend/database.py`.

This module is NOT a replacement for `backend/database.py` (the Digital Twin
REST API CRUD layer). It is a small, dedicated primitive shared by the two raw
SQL services so production deployments can route billing and FDS jobs into
the same managed PostgreSQL as the rest of the platform instead of keeping
them isolated in per-service SQLite files.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Optional PostgreSQL driver (mirrors backend/database.py) ─────────────────
try:  # pragma: no cover — psycopg2 is optional on slim / SQLite-only installs
    import psycopg2  # type: ignore
    from psycopg2 import extras as _pg_extras  # type: ignore
    from psycopg2 import pool as _pg_pool_mod  # type: ignore

    _PG_AVAILABLE = True
except Exception:  # NOSONAR — broad on purpose; optional third-party driver
    psycopg2 = None  # type: ignore[assignment]
    _pg_extras = None  # type: ignore[assignment]
    _pg_pool_mod = None  # type: ignore[assignment]
    _PG_AVAILABLE = False

# Integrity errors raised by either backend. Services catch this tuple so the
# same duplicate-detection logic works on SQLite and PostgreSQL.
INTEGRITY_ERRORS: tuple[type[Exception], ...] = (sqlite3.IntegrityError,)
if _PG_AVAILABLE:
    INTEGRITY_ERRORS = (*INTEGRITY_ERRORS, psycopg2.IntegrityError)  # type: ignore[union-attr]


# ══════════════════════════════════════════════════════════════════════════════
# Backend selection
# ══════════════════════════════════════════════════════════════════════════════


def pg_backend_enabled() -> bool:
    """Return True when `DATABASE_URL` targets PostgreSQL AND psycopg2 loads.

    Mirrors the URL sniffing in `backend.database.Database.__init__`
    (`postgres://`, `postgresql://`, `postgresql+asyncpg://` prefixes).
    """
    if not _PG_AVAILABLE:
        return False
    url = os.environ.get("DATABASE_URL", "").strip()
    return url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://"))


# ══════════════════════════════════════════════════════════════════════════════
# PostgreSQL connection pool (lazy; configured at first use)
# ══════════════════════════════════════════════════════════════════════════════

_PG_POOL: Any = None
_PG_POOL_LOCK = threading.Lock()


def _get_pg_pool() -> Any:
    """Return the psycopg2 `ThreadedConnectionPool`, creating it on first use.

    Tries `DATABASE_URL` first, then `NEON_DATABASE_URL` (same fallback chain
    as `backend/database.py`). Re-raises only when every configured URL is
    exhausted; `pg_connection()` converts that into a SQLite fallback.
    """
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL
    with _PG_POOL_LOCK:
        if _PG_POOL is not None:
            return _PG_POOL
        primary = os.environ.get("DATABASE_URL", "").strip()
        neon = os.environ.get("NEON_DATABASE_URL", "").strip()
        candidates = [url for url in (primary, neon) if url]
        last_exc: Exception | None = None
        for url in candidates:
            try:
                pool = _pg_pool_mod.ThreadedConnectionPool(  # type: ignore[union-attr]
                    minconn=1,
                    maxconn=10,
                    dsn=url,
                )
                # Smoke-test the connection — pool creation is lazy on some drivers.
                probe = pool.getconn()
                try:
                    cur = probe.cursor()
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    cur.close()
                finally:
                    pool.putconn(probe)
                _PG_POOL = pool
                logger.info("db_backend: PostgreSQL pool ready (%s)", url.split("@")[-1])
                return _PG_POOL
            except Exception as exc:  # NOSONAR — classification + fallback chain
                last_exc = exc
                logger.warning(
                    "db_backend: PostgreSQL unreachable via %s (%s); trying next configured URL",
                    url.split("@")[-1],
                    type(exc).__name__,
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No PostgreSQL URL configured (DATABASE_URL / NEON_DATABASE_URL)")


# ══════════════════════════════════════════════════════════════════════════════
# Placeholder translation + connection wrappers
# ══════════════════════════════════════════════════════════════════════════════


def sql_to_pg(sql: str) -> str:
    """Translate sqlite3 `?` placeholders → psycopg2 `%s`.

    Safe for this codebase: the billing/FDS SQL strings embed no `?` inside a
    string literal, so a positional replace is unambiguous.
    """
    return sql.replace("?", "%s")


class PgCursor:
    """Minimal psycopg2 cursor wrapper exposing the sqlite3-style cursor API
    the shared services rely on (execute / fetchone / fetchall / iteration)."""

    def __init__(self, real: Any) -> None:
        self._real = real

    def execute(self, sql: str, params: Any = None) -> PgCursor:
        self._real.execute(sql_to_pg(sql), params or ())
        return self

    def fetchone(self) -> Any:
        return self._real.fetchone()

    def fetchall(self) -> Any:
        return self._real.fetchall()

    def __iter__(self) -> Any:
        return iter(self._real.fetchall())

    def close(self) -> None:
        self._real.close()


class PgConnection:
    """A duck-typed `sqlite3.Connection` backed by a borrowed psycopg2 pooled
    connection.

    Exposes exactly the subset of the sqlite3 API used by the shared services:
      - `with conn:`   → commits (or rolls back) and returns the lease to the
                         pool on context exit (never exhausts the pool)
      - conn.execute(sql, params)  → `PgCursor` over RealDictCursor rows
      - conn.executescript(script) → runs multi-statement DDL and commits
      - conn.close()               → returns the lease to the pool

    Result rows are `RealDictRow` (dict-like), so `dict(row)` / `row["col"]`
    work identically to `sqlite3.Row` in the consuming services.
    """

    def __init__(self, raw: Any, pool: Any) -> None:
        self._raw = raw
        self._pool = pool

    def _healthy(self) -> Any:
        """Return the raw connection, replacing stale/closed pooled connections.

        PgBouncer can hand back an idle connection that the server has already
        dropped (`conn.closed` becomes truthy). Matching `backend/database.py`,
        a dead lease is discarded and a fresh one is requested so a single bad
        pooled connection cannot break a request.
        """
        if getattr(self._raw, "closed", False):
            try:
                self._pool.putconn(self._raw, close=True)
            except Exception:  # NOSONAR — best-effort cleanup of a dead lease
                pass
            self._raw = self._pool.getconn()
        return self._raw

    def __enter__(self) -> PgConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        finally:
            self._pool.putconn(self._raw)

    def execute(self, sql: str, params: Any = None) -> PgCursor:
        raw = self._healthy()
        cur = raw.cursor(cursor_factory=_pg_extras.RealDictCursor)  # type: ignore[union-attr]
        try:
            return PgCursor(cur).execute(sql, params)
        except Exception:
            cur.close()
            raise

    def executescript(self, script: str) -> None:
        raw = self._healthy()
        real = raw.cursor()
        try:
            real.execute(script)  # non-parameterized DDL: psycopg2 runs multi-statement
            self._raw.commit()
        except Exception:
            self._raw.rollback()
            raise
        finally:
            real.close()

    def close(self) -> None:
        self._pool.putconn(self._raw)


def pg_connection() -> PgConnection | None:
    """Return a pooled PostgreSQL-backed connection, or `None` so the caller
    can fall back to its local SQLite file.

    Returns `None` (never raises) when PostgreSQL is not configured OR psycopg2
    is not installed OR every configured URL is unreachable. This mirrors the
    graceful degradation behavior in `backend/database.py` — the app keeps
    running (single-instance SQLite) instead of crashing at request time.
    """
    if not pg_backend_enabled():
        return None
    try:
        pool = _get_pg_pool()
        return PgConnection(pool.getconn(), pool)
    except Exception as exc:  # NOSONAR — optional backend; callers degrade
        logger.warning(
            "db_backend: PostgreSQL unavailable (%s); caller will use SQLite fallback.",
            type(exc).__name__,
        )
        return None


__all__ = [
    "INTEGRITY_ERRORS",
    "PgConnection",
    "PgCursor",
    "pg_backend_enabled",
    "pg_connection",
    "sql_to_pg",
]
