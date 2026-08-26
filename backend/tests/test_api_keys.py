# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR â€” S3776: ...') are preserved.
"""
test_api_keys.py â€” Direct unit tests for backend/api_keys.py.

Covers key hashing, validation, add/list/delete/update operations,
timing-safe dummy verify, and the O(1) lookup index.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_keys_file(tmp_path, monkeypatch):
    """Redirect the keys file to a temp directory for each test."""
    keys_file = str(tmp_path / "api_keys.json")
    monkeypatch.setenv("FIREAI_API_KEYS_FILE", keys_file)
    monkeypatch.setenv("FIREAI_API_KEYS_SECRET_FILE", str(tmp_path / "api_keys.secret"))
    # Clear any cached server secret and validation cache
    import backend.api_keys as ak

    ak._SERVER_SECRET = b""
    ak._VALIDATED_KEY_CACHE.clear()
    yield keys_file
    ak._VALIDATED_KEY_CACHE.clear()


class TestKeyHashing:
    """Core hashing and verification functions."""

    def test_hash_key_returns_string(self):
        from backend.api_keys import _hash_key

        h = _hash_key("my-secret-key")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_key_is_non_deterministic(self):
        from backend.api_keys import _hash_key

        h1 = _hash_key("my-secret-key")
        h2 = _hash_key("my-secret-key")
        assert h1 != h2

    def test_verify_key_success(self):
        from backend.api_keys import _hash_key, _verify_key

        h = _hash_key("my-secret-key")
        assert _verify_key("my-secret-key", h) is True

    def test_verify_key_wrong_key_fails(self):
        from backend.api_keys import _hash_key, _verify_key

        h = _hash_key("my-secret-key")
        assert _verify_key("wrong-key", h) is False

    def test_verify_key_empty_hash_fails(self):
        from backend.api_keys import _verify_key

        assert _verify_key("key", "") is False

    def test_lookup_key_is_deterministic(self):
        from backend.api_keys import _legacy_hmac_lookup, _lookup_key

        lk1 = _lookup_key("my-secret-key")
        lk2 = _lookup_key("my-secret-key")
        assert lk1 == lk2
        # Post-migration primary index uses keyed BLAKE2b under bk$.
        assert lk1.startswith("bk$")
        # Frozen legacy shim keeps producing the historical hk$ index.
        assert _legacy_hmac_lookup("my-secret-key").startswith("hk$")


class TestCRUDOperations:
    """API key lifecycle operations."""

    def test_add_and_validate_key(self):
        from backend.api_keys import add_api_key, validate_api_key
        from backend.rbac import Role

        plaintext = "test-api-key-12345"
        add_api_key(plaintext, Role.ADMIN, "test key")
        info = validate_api_key(plaintext)
        assert info is not None
        assert info.role == Role.ADMIN

    def test_validate_invalid_key_returns_none(self):
        from backend.api_keys import add_api_key, validate_api_key
        from backend.rbac import Role

        add_api_key("valid-key", Role.ADMIN)
        assert validate_api_key("invalid-key") is None

    def test_generate_api_key(self):
        from backend.api_keys import generate_api_key, validate_api_key
        from backend.rbac import Role

        key = generate_api_key(Role.ENGINEER, "generated")
        assert key.startswith("fireai_")
        assert len(key) > 10
        info = validate_api_key(key)
        assert info is not None
        assert info.role == Role.ENGINEER

    def test_list_api_keys(self):
        from backend.api_keys import add_api_key, list_api_keys
        from backend.rbac import Role

        add_api_key("key-admin", Role.ADMIN, "admin key")
        add_api_key("key-viewer", Role.VIEWER, "viewer key")
        keys = list_api_keys()
        assert len(keys) == 2
        roles = {k["role"] for k in keys}
        assert roles == {"admin", "viewer"}

    def test_delete_api_key(self):
        from backend.api_keys import add_api_key, delete_api_key, validate_api_key
        from backend.rbac import Role

        plaintext = "key-to-delete"
        add_api_key(plaintext, Role.VIEWER)
        info = validate_api_key(plaintext)
        assert info is not None
        deleted = delete_api_key(info.key_hash)
        assert deleted is True
        assert validate_api_key(plaintext) is None

    def test_update_api_key_role(self):
        from backend.api_keys import add_api_key, update_api_key_role, validate_api_key
        from backend.rbac import Role

        plaintext = "key-to-update"
        add_api_key(plaintext, Role.VIEWER)
        info = validate_api_key(plaintext)
        assert info.role == Role.VIEWER
        updated = update_api_key_role(info.key_hash, Role.ADMIN)
        assert updated is True
        new_info = validate_api_key(plaintext)
        assert new_info.role == Role.ADMIN

    def test_validate_too_long_key_returns_none(self):
        from backend.api_keys import validate_api_key

        long_key = "a" * 2000
        assert validate_api_key(long_key) is None

    def test_validate_empty_key_returns_none(self):
        from backend.api_keys import validate_api_key

        assert validate_api_key("") is None
        assert validate_api_key(None) is None  # type: ignore[arg-type]  # NOSONAR â€” S5655: intentional wrong-type arg (test verifies rejection)


# â”€â”€ BLAKE2b primary-index migration (CodeQL durable remediation) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLookupMigration:
    """New bk$ primary index with one-time hk$ re-keying and legacy formats."""

    def test_new_keys_are_indexed_under_bk_primary(self, monkeypatch, tmp_path):
        import backend.api_keys as ak
        from backend.rbac import Role as _Role

        monkeypatch.setattr(ak, "_get_keys_file_path", lambda: str(tmp_path / "k.json"))
        ak._VALIDATED_KEY_CACHE.clear()
        ak.add_api_key("mig-key-1", _Role.ENGINEER)
        keys = ak._load_keys()
        assert any(k.startswith("bk$") for k in keys), dict(keys)

    def test_legacy_hk_entry_validates_and_rekeys(self, monkeypatch, tmp_path):
        import hashlib
        import json as _json

        import backend.api_keys as ak
        from backend.rbac import Role as _Role

        monkeypatch.setattr(ak, "_get_keys_file_path", lambda: str(tmp_path / "k.json"))
        ak._VALIDATED_KEY_CACHE.clear()
        # Simulate a pre-migration store indexed under hk$ with a plain hash.
        legacy_index = ak._legacy_hmac_lookup("old-key")
        plain_hash = hashlib.sha256(b"old-key").hexdigest()
        tmp_path.joinpath("k.json").write_text(
            _json.dumps({legacy_index: {"role": "admin", "description": "old",
                                        "bcrypt_hash": plain_hash, "key_hash": plain_hash}}),
            encoding="utf-8",
        )
        info = ak.validate_api_key("old-key")
        assert info is not None and info.role is _Role.ADMIN
        keys = ak._load_keys()
        assert any(k.startswith("bk$") for k in keys), "entry migrated to primary"
        assert legacy_index not in keys, "legacy index consumed"

    def test_long_key_roundtrip_and_pre_blake2b_compat(self):
        import bcrypt as _b

        from backend.api_keys import (
            HAS_BCRYPT,
            _hash_key,
            _legacy_long_key_bcrypt_input,
            _normalize_key_for_bcrypt,
            _verify_key,
        )

        long_key = "L" * 100
        new_hash = _hash_key(long_key)
        assert _verify_key(long_key, new_hash) is True
        # Hash stored under the OLD normalization still verifies.
        old_norm = _legacy_long_key_bcrypt_input(long_key.encode())
        if HAS_BCRYPT:
            stored_old = _b.hashpw(old_norm, _b.gensalt()).decode()
            assert _verify_key(long_key, stored_old) is True
        # Normalizations differ by construction.
        assert _normalize_key_for_bcrypt(long_key) != old_norm
