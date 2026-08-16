"""
test_session_store_failed_attempts.py — C-07 regression tests.

Verifies that failed-attempt counters can be cleared for ONE bucket (IP or
per-credential) without touching other buckets — the property the auth login
path relies on since C-07 replaced the global clear_all_failed_attempts().
"""

from __future__ import annotations

import pytest

import backend.session_store as ss
from backend.session_store import session_store

# Unique keys per test to avoid cross-test pollution of the in-memory store.
_IP_A = "198.51.100.10"
_IP_B = "198.51.100.20"
_CRED_A = "cred:aaa111"
_CRED_B = "cred:bbb222"


@pytest.fixture(autouse=True)
def _clean_redis_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the in-memory path (no REDIS_URL) and reset the shared store."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    # Reset the module-level lazy Redis probe so tests always use memory.
    ss._redis_checked = False
    ss._redis_available = False
    ss._redis_client = None
    session_store.clear_failed_attempts(_IP_A)
    session_store.clear_failed_attempts(_IP_B)
    session_store.clear_failed_attempts(_CRED_A)
    session_store.clear_failed_attempts(_CRED_B)


class TestTargetedClear:
    def test_clear_ip_bucket_does_not_touch_other_ips(self):
        session_store.add_failed_attempt(_IP_A)
        session_store.add_failed_attempt(_IP_B)

        session_store.clear_failed_attempts(_IP_A)

        assert session_store.get_failed_attempts(_IP_A) == []
        assert len(session_store.get_failed_attempts(_IP_B)) == 1

    def test_clear_credential_bucket_does_not_touch_other_credentials(self):
        session_store.add_failed_attempt(_CRED_A)
        session_store.add_failed_attempt(_CRED_B)

        session_store.clear_failed_attempts(_CRED_A)

        assert session_store.get_failed_attempts(_CRED_A) == []
        assert len(session_store.get_failed_attempts(_CRED_B)) == 1

    def test_clear_ip_does_not_touch_credential_bucket(self):
        """C-07: a successful login for key A must not reset key B's counter."""
        session_store.add_failed_attempt(_IP_A)
        session_store.add_failed_attempt(_CRED_B)

        session_store.clear_failed_attempts(_IP_A)

        assert len(session_store.get_failed_attempts(_CRED_B)) == 1

    def test_clear_credential_does_not_touch_ip_bucket(self):
        session_store.add_failed_attempt(_IP_A)
        session_store.add_failed_attempt(_CRED_A)

        session_store.clear_failed_attempts(_CRED_A)

        assert len(session_store.get_failed_attempts(_IP_A)) == 1

    def test_clear_missing_bucket_is_noop(self):
        session_store.clear_failed_attempts("198.51.100.99")
        assert session_store.get_failed_attempts("198.51.100.99") == []


class TestCleanupExpired:
    """C-08: cleanup_expired() removes expired in-memory sessions."""

    def _store_expired_session(self, key: str) -> None:
        """Inject an expired session directly into the in-memory store."""
        with ss._mem_lock:
            ss._mem_sessions[key] = {
                "api_key_hash": "x",
                "principal": "test",
                "role": "engineer",
                "expires_at": 1.0,  # long past
                "created_at": 0.0,
                "client_ip": _IP_A,
            }

    def _store_live_session(self, key: str) -> None:
        """Inject a still-valid session (expires far in the future)."""
        with ss._mem_lock:
            ss._mem_sessions[key] = {
                "api_key_hash": "x",
                "principal": "test",
                "role": "engineer",
                "expires_at": 1e12,  # far future
                "created_at": 0.0,
                "client_ip": _IP_A,
            }

    def test_expired_session_removed(self):
        self._store_expired_session("expired-key-1")
        removed = session_store.cleanup_expired()
        assert removed == 1
        assert session_store.get("expired-key-1") is None

    def test_live_session_kept(self):
        self._store_live_session("live-key-1")
        removed = session_store.cleanup_expired()
        assert removed == 0
        assert session_store.get("live-key-1") is not None

    def test_mixed_sessions_only_expired_removed(self):
        self._store_expired_session("expired-key-2")
        self._store_live_session("live-key-2")
        removed = session_store.cleanup_expired()
        assert removed == 1
        assert session_store.get("expired-key-2") is None
        assert session_store.get("live-key-2") is not None
