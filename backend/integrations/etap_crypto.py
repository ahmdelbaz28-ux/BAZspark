# File-level suppression comment removed per audit guide (V143 hardening).
# Per-line justified suppressions are preserved.
"""
backend/integrations/etap_crypto.py — ETAP credential encryption utilities.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_ETAP_ENCRYPTION_KEY_ENV = "ETAP_ENCRYPTION_KEY"
_MASTER_ENCRYPTION_KEY_ENV = "ENCRYPTION_KEY"

logger = logging.getLogger(__name__)


def _get_key() -> bytes:
    """Return the Fernet key.

    Resolution order:
      1. ETAP_ENCRYPTION_KEY (dedicated ETAP key, if set)
      2. ENCRYPTION_KEY (shared master key, already configured in deploy.yml)
      3. Raise OSError if neither is set
    """
    key: Optional[str] = os.getenv(_ETAP_ENCRYPTION_KEY_ENV) or os.getenv(_MASTER_ENCRYPTION_KEY_ENV)
    if not key:
        is_production = os.getenv("FIREAI_ENV", "production").lower() in ("production", "prod")
        if is_production:
            raise RuntimeError(
                f"FAIL-SAFE: Missing required env var {_ETAP_ENCRYPTION_KEY_ENV} or {_MASTER_ENCRYPTION_KEY_ENV} in production. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        raise OSError(
            f"Missing required env var {_ETAP_ENCRYPTION_KEY_ENV} or {_MASTER_ENCRYPTION_KEY_ENV}. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return key.encode("utf-8")



def encrypt_password(plaintext: str) -> str:
    """Encrypt a password for storage."""
    if not plaintext:
        return ""
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_password(ciphertext: str) -> str:
    """Decrypt a stored password."""
    if not ciphertext:
        return ""
    f = Fernet(_get_key())
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Invalid ETAP password ciphertext") from None


def mask_password(ciphertext: str) -> str:
    """Return a masked representation for logging/display."""
    if not ciphertext:
        return ""
    if len(ciphertext) <= 8:
        return "****"
    return f"{ciphertext[:4]}...{ciphertext[-4:]}"
