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
