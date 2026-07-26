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

DESIGN NOTES:
  - This module has ZERO imports from security_middleware or routers/auth,
    breaking the circular dependency chain.
  - Imports only from: api_keys (key validation), rbac (Role enum),
    os (env var), hmac (constant-time compare).
  - All functions are pure (no side effects beyond logging) and stateless.
"""

from __future__ import annotations

import hmac as _hmac
import logging
import os
from typing import Optional

from backend.api_keys import validate_api_key as _validate_api_key
from backend.rbac import Role

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
