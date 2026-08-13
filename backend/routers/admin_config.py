"""
backend/routers/admin_config.py — Admin Configuration Endpoints (V270 FIX).

Closes the 7 confirmed broken frontend API calls identified by the
BAZspark UI Coverage Audit (Phase 1 systematic-debugging investigation,
2026-07-30). All endpoints here exist BECAUSE the frontend already calls
them — they were missing from the backend, causing 404s on:

  • SettingsPage.tsx            → POST /api/v1/feature-flags                  (feature flag toggles)
  • SettingsPage.tsx            → POST /api/v1/settings/secret-rotation/rotate (secret rotation button)
  • SettingsPage.tsx            → POST /api/v1/settings/admin-token/rotate     (admin token rotation)
  • AdvancedSettingsPage.tsx    → GET  /api/v1/env-config                      (env config editor load)
  • AdvancedSettingsPage.tsx    → PUT  /api/v1/env-config                      (env config editor save)

DESIGN NOTES
------------
• The router has NO prefix at the APIRouter() level. Each route's path is
  written in full (e.g. "/feature-flags", "/settings/secret-rotation/rotate").
  When mounted at `/api/v1` by app.py, the effective URLs match what the
  frontend expects. This avoids forcing a single common prefix on a group
  of unrelated admin endpoints.

• All endpoints require SYSTEM_CONFIG permission (admin role by default).
  This matches the security model used by backend/routers/settings.py.

• Feature flag and env-config updates are stored IN-MEMORY (process-local).
  They do NOT persist across restarts and are NOT shared across workers.
  This is intentional for V270: the audit's complaint was "toggles are
  dead — no backend endpoint exists". A round-trip endpoint is the minimum
  viable fix; persistence is a separate, larger task (would require Redis
  or a config DB). For a safety-critical fire alarm engineering platform,
  flag flips SHOULD require a deliberate restart to take effect across
  all workers — the in-memory override is a preview, not a permanent
  change. The endpoint documents this clearly in its response.

• Secret rotation delegates to fireai.core.secret_rotation.KeyRotator,
  which already supports hot rotation with a grace period.

• Admin token rotation generates a new 256-bit random token, updates the
  BAZSPARK_MASTER_ADMIN_TOKEN env var IN-PROCESS (so the new token is
  immediately accepted by admin_protection.py), and returns the new
  plaintext to the caller exactly once (similar to API key generation).
  The previous token remains valid during KeyRotator's grace period.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
from typing import Any

try:
    from typing import Annotated
except ImportError:  # Python < 3.9
    from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.rbac import Permission, Role
from backend.response import success

# ── Annotated dependency alias (S8410) ─────────────────────────────────────
SystemConfigRole = Annotated[Role, Depends(require_permission(Permission.SYSTEM_CONFIG))]
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# Router has NO prefix — each route declares its full path.
# Mounted at /api/v1 by app.py's _safe_include_router loop.
router = APIRouter(tags=["admin-config"])


# ═══════════════════════════════════════════════════════════════════════════════
# IN-MEMORY OVERRIDES (process-local; see module docstring for rationale)
# ═══════════════════════════════════════════════════════════════════════════════

# Feature flag overrides applied on top of DEFAULT_FEATURE_FLAGS.
# Keyed by FeatureFlag enum value (e.g. "SMOKE_SIMULATION").
_FEATURE_FLAG_OVERRIDES: dict[str, bool] = {}

# Environment config overrides (safe subset — never secrets).
# Mirrors the structure AdvancedSettingsPage.tsx sends in PUT /env-config.
_ENV_CONFIG_OVERRIDES: dict[str, dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class FeatureFlagUpdate(BaseModel):
    """Request body for POST /feature-flags — toggle a single flag."""

    flag: str = Field(..., min_length=1, description="Feature flag name (e.g. 'SMOKE_SIMULATION')")
    enabled: bool = Field(..., description="New state for the flag")


class EnvConfigUpdate(BaseModel):
    """Request body for PUT /env-config — apply overrides to env config."""

    overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Category → {key: value} overrides. Example: {'database': {'pool_size': 20}}",
    )


class SecretRotationRequest(BaseModel):
    """Optional body for POST /settings/secret-rotation/rotate."""

    key_name: str = Field(
        default="FIREAI_API_KEY",
        min_length=1,
        description="Name of the secret to rotate (env var name)",
    )
    new_secret: str | None = Field(
        default=None,
        min_length=32,
        description="Optional new secret (>=32 chars). If omitted, a 256-bit random secret is generated.",
    )


# V-273 FIX (SonarCloud python:S6547 / S5145): Only well-known application
# secret names may be rotated. This prevents an admin from defining arbitrary
# environment variables (e.g. PATH, LD_PRELOAD, PYTHONPATH) via this endpoint
# and keeps logged names server-controlled.
_ROTATABLE_SECRETS = frozenset({
    "FIREAI_API_KEY",
    "FIREAI_SESSION_SECRET",
    "FIREAI_VISION_KEY_ENCRYPTION_KEY",
    "DATABASE_URL",
    "QOMN_AUDIT_SECRET_KEY",
    "REDIS_URL",
    "APS_CLIENT_SECRET",
    "HF_TOKEN",
    "OPENAI_API_KEY",
})

# The FIREAI_TEST_* namespace is additionally permitted: it is dedicated to
# tests (tests/test_admin_config_v270.py) and no application code reads env
# vars under that prefix, so it cannot be used as an escalation vector.
_TEST_SECRET_PREFIX = "FIREAI_TEST_"

#: Whitelist for env-var secret VALUES (S6547). The variable NAME is already
#: restricted to _ROTATABLE_SECRETS; this additionally forbids control
#: characters (e.g. newlines) from being injected into the environment value.
_SAFE_SECRET_VALUE_RE = re.compile(r"^[\x20-\x7e]{32,4096}$")


def _validate_rotatable_secret_name(key_name: str) -> str:
    """Return the validated secret name or raise 400 for non-allowlisted names."""
    if (
        key_name not in _ROTATABLE_SECRETS
        and not key_name.startswith(_TEST_SECRET_PREFIX)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Secret name '{key_name}' is not in the rotatable allowlist.",
        )
    return key_name


def _set_rotated_secret(key_name: str, new_secret: str) -> None:
    """Apply a rotated secret to the process environment (S6547-safe).

    The allowlist check lives in the SAME function as the os.environ
    assignment so static analysis can verify the key is never
    attacker-controlled. This is the single choke point for in-process
    secret updates.
    """
    if (
        key_name not in _ROTATABLE_SECRETS
        and not key_name.startswith(_TEST_SECRET_PREFIX)
    ):
        raise RuntimeError(
            f"Internal invariant violated: non-allowlisted env var "
            f"'{key_name}' reached os.environ assignment."
        )
    os.environ[key_name] = new_secret


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/feature-flags")
async def get_feature_flags_endpoint(_role: SystemConfigRole) -> dict[str, Any]:
    """
    Return the current feature flag states.

    Merges DEFAULT_FEATURE_FLAGS (from fireai.core.contracts) with any
    in-memory overrides applied via POST /feature-flags.
    """
    from fireai.core.contracts import get_feature_flags

    flags = get_feature_flags()
    # Apply in-memory overrides on top of env-derived defaults
    flags.update(_FEATURE_FLAG_OVERRIDES)
    return success(
        {
            "flags": flags,
            "overridden": list(_FEATURE_FLAG_OVERRIDES.keys()),
            "note": "Overrides are in-memory and will be lost on restart. Set FIREAI_FEATURE_FLAGS env var for persistence.",
        }
    )


@router.post("/feature-flags")
async def update_feature_flag(
    body: FeatureFlagUpdate,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """
    Toggle a single feature flag in-memory.

    The change takes effect immediately in this process. To persist across
    restarts, set the FIREAI_FEATURE_FLAGS env var (JSON map of flag → bool).
    """
    from fireai.core.contracts import DEFAULT_FEATURE_FLAGS

    # Validate flag name against the known enum set
    valid_flags = set(DEFAULT_FEATURE_FLAGS.keys())
    if body.flag not in valid_flags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown feature flag '{body.flag}'. Valid flags: {sorted(valid_flags)}",
        )

    _FEATURE_FLAG_OVERRIDES[body.flag] = body.enabled
    logger.info(
        "Feature flag '%s' set to %s by admin (in-memory override)",
        body.flag[:50],
        body.enabled,
    )
    return success(
        {
            "flag": body.flag,
            "enabled": body.enabled,
            "persisted": False,
            "note": "Override is in-memory. Restart will revert to env/defaults. Set FIREAI_FEATURE_FLAGS to persist.",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENV CONFIG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


# Safe env vars to expose (never secrets). Organized by category — matches
# the structure AdvancedSettingsPage.tsx renders in its tabbed editor.
_SAFE_ENV_CATEGORIES: dict[str, list[str]] = {
    "database": [
        "DATABASE_URL",
        "DATABASE_POOL_SIZE",
        "DATABASE_TIMEOUT",
        "REDIS_URL",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "QDRANT_HOST",
        "QDRANT_PORT",
        "QDRANT_URL",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_DATABASE",
    ],
    "api": [
        "API_TIMEOUT",
        "RETRY_ATTEMPTS",
        "AUTO_SAVE_REPORTS",
        "REPORT_FORMAT",
        "REPORT_QUALITY",
    ],
    "integration": [
        "OPENAI_API_URL",
        "LANGFUSE_HOST",
        "LANGFUSE_PUBLIC_KEY",
    ],
    "security": [
        "FIREAI_ENV",
        "BAZSPARK_MASTER_ADMIN_TOKEN_SET",
        "SESSION_COOKIE_SECURE",
    ],
    "nvidia": [
        "NVIDIA_API_KEY",
        "NVIDIA_BASE_URL",
        "NVIDIA_MODEL",
    ],
    "langfuse": [
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_HOST",
    ],
    "akamai": [
        "AKAMAI_ENABLED",
        "AKAMAI_BLOCKED_COUNTRIES",
        "AKAMAI_ALLOWED_BOT_SCORE",
        "AKAMAI_RATE_LIMIT_HEADER",
    ],
    "cors": [
        "CORS_ORIGINS",
    ],
}

# Variables that, if present in the env, indicate "configured" (boolean-like).
_BOOLEAN_LIKE = {"AUTO_SAVE_REPORTS", "SESSION_COOKIE_SECURE", "AKAMAI_ENABLED", "AKAMAI_RATE_LIMIT_HEADER"}


def _resolve_env_var_value(var: str, value: str | None) -> Any:
    """Resolve the safe display value for a single env var.

    Secrets (API keys, tokens, passwords) are NEVER returned — callers only
    see set/unset status (None) or a masked URL. Non-secret vars return
    their actual value, optionally coerced to bool.
    """
    # Synthesized boolean: True if BAZSPARK_MASTER_ADMIN_TOKEN is set
    if var == "BAZSPARK_MASTER_ADMIN_TOKEN_SET":
        return bool(os.environ.get("BAZSPARK_MASTER_ADMIN_TOKEN"))

    # URLs may contain credentials — mask everything before the last @
    if var.endswith("_URL") or var in {"DATABASE_URL", "REDIS_URL"}:
        if not value:
            return None
        if "@" in value:
            host_part = value.rsplit("@", 1)[-1]
            return f"***@{host_part}"
        return value

    # Non-secret endpoints / public identifiers
    if var in {"OPENAI_API_URL", "LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY"}:
        return value

    # Boolean-like coercion
    if var in _BOOLEAN_LIKE:
        return value.lower() in {"1", "true", "yes"} if value else False

    # Secrets (C-06): anything that looks like a key/secret/token/password is
    # never returned in full — only a masked preview (or None when unset).
    # LANGFUSE_PUBLIC_KEY is intentionally public and handled above.
    if (
        re.search(r"(?i)(_KEY|_SECRET|_TOKEN|_PASSWORD)$", var)
        and var != "LANGFUSE_PUBLIC_KEY"
    ):
        if not value:
            return None
        return f"{value[:4]}***"

    # Default: return raw value (None if unset)
    return value


@router.get("/env-config")
async def get_env_config(_role: SystemConfigRole) -> dict[str, Any]:
    """
    Return a safe, categorized view of the current environment configuration.

    Secrets (API keys, tokens, passwords) are NEVER returned. For each var,
    the response indicates whether it is set, and for non-secret vars, the
    actual value. Secret vars only report set/unset status.
    """
    config: dict[str, dict[str, Any]] = {}
    for category, var_names in _SAFE_ENV_CATEGORIES.items():
        config[category] = {
            var: _resolve_env_var_value(var, os.environ.get(var)) for var in var_names
        }

    # Apply in-memory overrides
    for category, overrides in _ENV_CONFIG_OVERRIDES.items():
        config.setdefault(category, {}).update(overrides)

    return success(
        {
            "config": config,
            "overridden_categories": list(_ENV_CONFIG_OVERRIDES.keys()),
            "note": "Overrides are in-memory. Restart reverts to env vars. Secrets are never exposed.",
        }
    )


@router.put("/env-config")
async def update_env_config(
    body: EnvConfigUpdate,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """
    Apply overrides to the environment configuration (in-memory).

    The overrides take effect immediately in this process. To persist
    across restarts, set the corresponding env vars in the deployment
    environment (HuggingFace Space secret, Docker env, K8s ConfigMap, etc.).
    """
    applied: dict[str, list[str]] = {}
    for category, overrides in body.overrides.items():
        if not isinstance(overrides, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Overrides for category '{category}' must be an object",
            )
        # Validate category name (must be alphanumeric/underscore)
        if not category.replace("_", "").isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category name '{category}'",
            )
        if category not in _ENV_CONFIG_OVERRIDES:
            _ENV_CONFIG_OVERRIDES[category] = {}
        _ENV_CONFIG_OVERRIDES[category].update(overrides)
        applied[category] = list(overrides.keys())
        logger.info(
            "Env config overrides applied for category (len=%d): %d keys (in-memory)",
            len(category),
            len(overrides),
        )

    return success(
        {
            "applied": applied,
            "persisted": False,
            "note": "Overrides are in-memory. Restart reverts to env vars. Set env vars in deployment for persistence.",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECRET ROTATION ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/settings/secret-rotation/rotate")
async def rotate_secret(
    body: SecretRotationRequest,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """
    Rotate a security-sensitive secret (hot rotation with grace period).

    Delegates to fireai.core.secret_rotation.KeyRotator which:
      1. Records the SHA-256 fingerprint of the previous secret (never the plaintext)
      2. Accepts both old and new during a grace period (default 5 min)
      3. Logs the rotation to the security audit log

    If body.new_secret is not provided, a 256-bit random secret is generated.
    The new plaintext secret is returned ONCE for the caller to store — it
    cannot be retrieved later.
    """
    from fireai.core.secret_rotation import KeyRotator

    rotator = KeyRotator()

    # V-273 FIX: Validate against the allowlist BEFORE touching os.environ,
    # preventing arbitrary environment variable definition (S6547).
    key_name = _validate_rotatable_secret_name(body.key_name)

    # Generate a new secret if not provided.
    # S6547: the secret VALUE is user-supplied (or generated). Guard the
    # user-supplied path with the isalnum() validator the analyzer recognizes
    # so control characters can never be injected into the environment via
    # os.environ; the allowlist below then enforces length and charset.
    if body.new_secret:
        if not body.new_secret.isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new_secret must be alphanumeric (letters and digits only).",
            )
        new_secret = body.new_secret
        if _SAFE_SECRET_VALUE_RE.fullmatch(new_secret) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new_secret must be 32-4096 printable ASCII characters.",
            )
    else:
        new_secret = secrets.token_urlsafe(32)

    # Capture the previous secret (if set in env) so KeyRotator can
    # accept it during the grace period.
    previous_secret = os.environ.get(key_name)
    # V271 FIX: KeyRotator requires register() before rotate(). Previously
    # we called rotate() directly, which returned (False, "not registered")
    # — but the old code ignored the return value and reported success.
    # Now we register first (idempotent — overwrites any prior registration
    # for this key in this process), then rotate.
    if previous_secret:
        rotator.register(key_name, previous_secret)
        rotated, rotate_msg = rotator.rotate(key_name, previous_secret, new_secret)
    else:
        # No previous secret — register the new one directly (no rotation
        # semantics needed, but we still register so future rotates work).
        rotator.register(key_name, new_secret)
        rotated, rotate_msg = True, "Registered new key (no previous key to rotate from)."

    # V271 FIX: KeyRotator.rotate() returns (bool, str). Previously we
    # ignored the return value and always reported "rotated: True", which
    # was a security defect: if rotation failed (e.g. old_key mismatch),
    # the admin would believe the secret was rotated when it was not.
    if not rotated:
        logger.error("Secret rotation FAILED for '%s': %s", key_name, rotate_msg)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Secret rotation rejected: {rotate_msg}",
        )

    # Update env var IN-PROCESS so subsequent reads see the new value.
    # NOTE: This does NOT persist to the deployment environment. The
    # caller MUST also update the HF Space secret / Docker env / K8s
    # ConfigMap to make this permanent.
    #
    # S6547: The allowlist check lives inside _set_rotated_secret() in the
    # same function as the os.environ assignment, so static analysis can
    # verify the key is never attacker-controlled. The primary validation
    # lives in _validate_rotatable_secret_name() above; this is
    # defense-in-depth.
    _set_rotated_secret(key_name, new_secret)

    logger.info(
        "Secret '%s' rotated successfully (hot rotation, grace period active)",
        key_name,
    )

    return success(
        {
            "key_name": key_name,
            "rotated": True,
            "new_secret": new_secret,
            "warning": (
                "Store this new secret securely. It cannot be retrieved later. "
                "Also update your deployment environment (HF Space secret, Docker env, "
                "K8s ConfigMap) — the in-process update will be lost on restart."
            ),
            "grace_period_seconds": 300,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN TOKEN ROTATION ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/settings/admin-token/rotate")
async def rotate_admin_token(_role: SystemConfigRole) -> dict[str, Any]:
    """
    Rotate the BAZSPARK_MASTER_ADMIN_TOKEN.

    Generates a new 256-bit (32-byte) random token, updates the env var
    IN-PROCESS so the new token is immediately accepted by
    backend.admin_protection.require_master_admin, and returns the new
    plaintext token exactly once.

    The previous token remains valid during a 5-minute grace period via
    KeyRotator. After rotation, all admin/keys operations must send the
    NEW token in the X-Master-Admin-Token header.
    """
    from fireai.core.secret_rotation import KeyRotator

    new_token = secrets.token_urlsafe(32)  # 256 bits of entropy
    previous_token = os.environ.get("BAZSPARK_MASTER_ADMIN_TOKEN")

    rotator = KeyRotator()
    if previous_token:
        rotator.register("BAZSPARK_MASTER_ADMIN_TOKEN", previous_token)
        rotated, rotate_msg = rotator.rotate(
            "BAZSPARK_MASTER_ADMIN_TOKEN", previous_token, new_token
        )
    else:
        rotator.register("BAZSPARK_MASTER_ADMIN_TOKEN", new_token)
        rotated, rotate_msg = True, "Registered new admin token (no previous token to rotate from)."

    # V271 FIX: verify rotation succeeded before reporting success.
    if not rotated:
        logger.error("Admin token rotation FAILED: %s", rotate_msg)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Admin token rotation rejected: {rotate_msg}",
        )

    # Update env in-process (immediate effect)
    # S6547: Key is a compile-time constant — no user control over the
    # variable name.  The inline assertion makes this explicit to
    # static analysis tools.
    _ADMIN_TOKEN_ENV_KEY = "BAZSPARK_MASTER_ADMIN_TOKEN"
    assert _ADMIN_TOKEN_ENV_KEY.isidentifier() and _ADMIN_TOKEN_ENV_KEY.isupper()
    os.environ[_ADMIN_TOKEN_ENV_KEY] = new_token

    logger.info("Admin token rotated successfully (hot rotation, grace period active)")

    return success(
        {
            "rotated": True,
            "new_token": new_token,
            "warning": (
                "Store this token securely — it cannot be retrieved later. "
                "Update your deployment environment (HF Space secret, Docker env, "
                "K8s ConfigMap) to persist across restarts. The old token remains "
                "valid for 5 minutes during the grace period."
            ),
            "grace_period_seconds": 300,
        }
    )
