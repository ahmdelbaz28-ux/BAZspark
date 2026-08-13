"""
backend/auth_utils.py — Shared authentication utilities.
=========================================================================

Extracts duplicated auth logic from security_middleware.py and routers/auth.py
into a single, well-tested module. Eliminates the circular dependency between
those two modules (auth.py → security_middleware → auth.py).

Provides:
  1. Cookie parsing — extract_session_token_from_headers()
      Parses raw ASGI headers to find the __Host-fireai_session cookie value.
      Used by both ApiKeyMiddleware and the logout endpoint.

  2. API key credential validation — validate_api_key_credential()
      Checks FIREAI_API_KEY env var bypass, then delegates to api_keys.validate_api_key.
      Returns a Role or None. Used by both ApiKeyMiddleware and the login endpoint.

  3. Session token verification — verify_session_token()
      Validates a signed session token (cookie or header) and returns the session_id.
      Used by WebSocket auth and other cross-module flows (T20).

DESIGN NOTES:
  - This module has ZERO imports from security_middleware or routers/auth,
    breaking the circular dependency chain.
  - Imports only from: api_keys (key validation), rbac (Role enum),
    os (env var), hmac (constant-time compare).
  - All functions are pure (no side effects beyond logging) and stateless.
"""

from __future__ import annotations

import hashlib as _hashlib
import hmac as _hmac
import logging
import os
import time
from typing import Optional, Tuple

from backend.api_keys import validate_api_key as _validate_api_key
from backend.rbac import Role
from backend.session_secret import get_secret_manager as _get_secret_manager
from backend.session_store import session_store as _session_store

logger = logging.getLogger(__name__)

# Cookie name for session tokens (must match routers/auth.py)
_SESSION_COOKIE_NAME = "__Host-fireai_session"


def extract_session_token_from_headers(
    headers: list[tuple[bytes, bytes]],
) -> Optional[str]:
    """
    Parse raw ASGI headers to extract the session cookie token.

    Finds the ``Cookie`` header, locates the ``__Host-fireai_session``
    cookie within it, and returns the token value (the part after ``=``).

    Returns None if:
      - No Cookie header is present
      - The session cookie is not found
      - The cookie value is empty

    This is the single implementation used by both:
      - security_middleware.py (ApiKeyMiddleware)
      - routers/auth.py (logout endpoint)
    """
    cookie_header: str | None = None
    for name, value in headers:
        if name == b"cookie":
            cookie_header = value.decode("utf-8", errors="replace")
            break

    if not cookie_header:
        return None

    for pair in cookie_header.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k.strip() == _SESSION_COOKIE_NAME:
                token = v.strip()
                return token if token else None

    return None


def validate_api_key_credential(api_key: str) -> Optional[Role]:
    """
    Validate an API key credential and return the associated Role.

    Checks in order:
      1. FIREAI_API_KEY env var bypass (constant-time comparison)
      2. RBAC key store via api_keys.validate_api_key()

    Returns the Role if the key is valid, None otherwise.

    This is the single implementation used by both:
      - security_middleware.py (ApiKeyMiddleware.__call__)
      - routers/auth.py (login endpoint)
    """
    env_key = os.getenv("FIREAI_API_KEY")
    if env_key and api_key and _hmac.compare_digest(api_key, env_key):
        return Role.ADMIN

    info = _validate_api_key(api_key)
    if info is not None:
        return info.role

    return None


def resolve_credential(api_key: str) -> Optional[Tuple[Role, str]]:
    """
    Validate an API key credential and return ``(role, principal)``.

    The **principal** is an opaque, stable per-credential identifier used to
    scope user-owned resources (e.g. Mem0 memories). It is derived from
    server-side material only and is NOT reversible:

      - RBAC store key  -> ``info.key_hash`` (HMAC-SHA256 lookup hash)
      - env bypass key  -> ``"env:" + sha256(key)[:32]`` (deterministic)

    Two different credentials ALWAYS produce two different principals, so
    resources scoped by principal can never leak across credentials.

    Returns None for invalid/empty keys. This is the single implementation
    used by both ApiKeyMiddleware (stamping scope) and routers/auth.py
    (storing the principal in the session at login).
    """
    env_key = os.getenv("FIREAI_API_KEY")
    if env_key and api_key and _hmac.compare_digest(api_key, env_key):
        principal = "env:" + _hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:32]
        return (Role.ADMIN, principal)

    info = _validate_api_key(api_key)
    if info is not None:
        return (info.role, info.key_hash)

    return None


def verify_session_token(token: str) -> Optional[str]:
    """
    Verify a signed session token and return the session_id if valid.

    Returns None if:
      - Token format is invalid
      - HMAC signature does not match
      - Token has expired
      - Session ID is not in the session store
    """
    if "." not in token:
        return None

    parts = token.split(".", 2)
    if len(parts) != 3:
        return None

    session_id, expires_at_str, signature = parts
    try:
        expires_at = int(expires_at_str)
    except ValueError:
        return None

    # Client-side expiration check
    if time.time() > expires_at:
        return None

    # Verify signature against primary AND previous secrets
    secret_mgr = _get_secret_manager()
    if not secret_mgr.verify_signature(f"{session_id}.{expires_at}", signature):
        return None

    # Check that session exists in store (server-side validation)
    session_id_hash = _hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    session = _session_store.get(session_id_hash)
    if session is None:
        return None

    # Server-side expiration check
    if time.time() > session.get("expires_at", 0):
        _session_store.delete(session_id_hash)
        return None

    return session_id
