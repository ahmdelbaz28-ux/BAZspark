"""
backend/config.py — Centralized Configuration for Multi-Database Setup
========================================================

Configuration management for:
- PostgreSQL (primary database)
- Qdrant (vector database)
- Neo4j (graph database)
- Redis (cache/database)
"""

from __future__ import annotations

import os

# Load .env file before reading any configuration values.
# This ensures environment variables from .env are available to os.environ.get()
# throughout the Config class and any module that imports config.
# Falls back gracefully if python-dotenv is not installed.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)  # Never override real environment variables
except ImportError:
    pass


class Config:
    """Centralized configuration for all database connections."""

    # relative "sqlite:///./db/digital_twin.db" (CWD-dependent, outside /app/data
    # volume) while DIGITAL_TWIN_DB_PATH defaulted to an absolute path. This
    # caused data loss on container restart. Now both default to /app/data/.
    _DEFAULT_DB_DIR = os.environ.get("FIREAI_DATA_DIR", "/app/data")
    _DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "digital_twin.db")

    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{_DEFAULT_DB_PATH}",  # Default: absolute path inside /app/data
    )

    # Digital Twin Database Path (for the existing system)
    DIGITAL_TWIN_DB_PATH: str = os.environ.get(
        "DIGITAL_TWIN_DB_PATH",
        _DEFAULT_DB_PATH,  # Same path as DATABASE_URL — no more divergence
    )

    # Qdrant Configuration (Vector Database)
    QDRANT_HOST: str | None = os.environ.get("QDRANT_HOST")  # V257: was 'localhost'
    QDRANT_PORT: int = int(os.environ.get("QDRANT_PORT", 6333))
    QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY")
    QDRANT_URL: str | None = os.environ.get("QDRANT_URL")  # For cloud instances

    # Neo4j Configuration (Graph Database)
    NEO4J_URI: str | None = os.environ.get("NEO4J_URI")  # V257: was 'bolt://localhost:7687'
    NEO4J_USERNAME: str = os.environ.get("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.environ.get("NEO4J_PASSWORD", "")
    NEO4J_DATABASE: str = os.environ.get("NEO4J_DATABASE", "neo4j")

    # Redis Configuration (Cache/Temporary Storage)
    REDIS_URL: str | None = os.environ.get("REDIS_URL")  # V257: was 'redis://localhost:6379'
    REDIS_HOST: str | None = os.environ.get("REDIS_HOST")  # V257: was 'localhost'
    REDIS_PORT: int = int(os.environ.get("REDIS_PORT", 6379))
    REDIS_PASSWORD: str | None = os.environ.get("REDIS_PASSWORD")
    REDIS_DB: int = int(os.environ.get("REDIS_DB", 0))

    # ── Akamai Edge Integration ────────────────────────────────────────────
    # When AKAMAI_ENABLED=true, the backend trusts Akamai headers
    # (True-Client-IP, Akamai-Internal, Akamai-Bot-Score, Akamai-Geo-Country)
    # and rejects direct origin access in production.
    # See backend/akamai_middleware.py for the full integration.
    AKAMAI_ENABLED: bool = os.environ.get("AKAMAI_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
        "on",
    )
    # Shared secret injected by Akamai EdgeWorker / Property Manager.
    # When set, requests without this header are rejected in production.
    AKAMAI_REQUIRE_ORIGIN_TOKEN: str = os.environ.get("AKAMAI_REQUIRE_ORIGIN_TOKEN", "").strip()
    # Comma-separated ISO 3166-1 alpha-2 country codes to block (e.g. "CN,RU,IR,KP")
    AKAMAI_BLOCKED_COUNTRIES: str = os.environ.get("AKAMAI_BLOCKED_COUNTRIES", "")
    # Bot score threshold (0-100, 0=human, 100=bot) for sensitive endpoints.
    # Requests above this score on /api/v1/auth/* are rejected.
    AKAMAI_ALLOWED_BOT_SCORE: int = int(os.environ.get("AKAMAI_ALLOWED_BOT_SCORE", "30"))
    # Forward Akamai's X-RateLimit-* response headers to the client
    AKAMAI_RATE_LIMIT_HEADER: bool = os.environ.get("AKAMAI_RATE_LIMIT_HEADER", "true").lower() in (
        "true",
        "1",
        "yes",
        "on",
    )

    # Additional settings
    # V246 fail-safe: default "production" — a safety-critical fire alarm system
    # MUST fail closed. If FIREAI_ENV is unset, assume production (strictest
    # posture). All real production deployments EXPLICITLY set FIREAI_ENV=production
    # (Dockerfile ENV, docker-compose.yml, HF Space). CI sets it to "development"
    # in conftest.py. Previously changed to "development" in audit P1-2, but
    # self-critique revealed this creates split-brain with 12+ other files that
    # use default="production" (V246 hardening). Reverted for consistency.
    ENVIRONMENT: str = os.environ.get("FIREAI_ENV", "production")
    DEBUG: bool = ENVIRONMENT.lower() == "development"

    @classmethod
    def validate_config(cls) -> list[str]:
        """Validate configuration and return list of warnings/errors."""
        issues = []

        # Check if PostgreSQL connection string format is valid (if using PostgreSQL)
        if cls.DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
            if not all(part in cls.DATABASE_URL for part in ["//", "@"]):
                issues.append("DATABASE_URL may have invalid PostgreSQL format")

        is_prod = cls.ENVIRONMENT.lower() in ("production", "prod")
        if is_prod:
            # Enforce production strict database configuration check
            if "sqlite" in cls.DATABASE_URL.lower() and os.environ.get(
                "ALLOW_SQLITE_IN_PROD", ""
            ).lower() not in ("true", "1"):
                issues.append(
                    "CRITICAL: SQLite is in use for production without ALLOW_SQLITE_IN_PROD=true. Consider PostgreSQL."
                )

        # Neo4j — password required when a URI is configured
        if cls.NEO4J_URI and not cls.NEO4J_PASSWORD:
            issues.append(
                "CRITICAL: NEO4J_URI is set but NEO4J_PASSWORD is missing or empty. "
                "Neo4j connections require authentication."
            )

        return issues


# ── STARTUP FAIL-FAST: secrets must be present and secure at import time ──
_jwt_secret = (
    os.environ.get("JWT_SECRET")
    or os.environ.get("SESSION_SECRET")
    or os.environ.get("FIREAI_SESSION_SECRET")
    or os.environ.get("FIREAI_SESSION_SECRET_FILE")
)

if not _jwt_secret:
    raise RuntimeError(
        "FATAL: Environment secrets missing.\n"
        "Set JWT_SECRET (or SESSION_SECRET / FIREAI_SESSION_SECRET) before starting.\n"
        "Generate a strong secret with:\n"
        "  python3 -m backend.session_secret generate\n"
        "Then export it:\n"
        "  export JWT_SECRET='<generated>'\n"
        "The application cannot start without a signing secret."
    )

_WEAK_SECRETS = {
    "secret",
    "change-me",
    "default",
    "test",
    "123456",
    "admin",
    "jwt_secret",
    "password",
}
# V246 fail-safe: default "production" — mirrors Config.ENVIRONMENT above.
_env_name = os.environ.get("FIREAI_ENV", "production").lower()
if _env_name in ("production", "prod"):
    if _jwt_secret.strip().lower() in _WEAK_SECRETS or len(_jwt_secret.strip()) < 32:
        raise RuntimeError(
            "FATAL: Insecure or default JWT_SECRET / SESSION_SECRET detected in production.\n"
            "Placeholder/weak secrets are strictly forbidden in production.\n"
            "Generate a strong 256-bit secret with:\n"
            '  python3 -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

# Singleton instance
config = Config()
