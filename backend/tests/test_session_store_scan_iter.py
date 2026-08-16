"""
test_session_store_scan_iter.py — C-09 regression tests.

Verifies that the session store never calls Redis KEYS (which blocks the
server on large key sets) — only SCAN-based iteration — in the three
production-reachable bulk operations.
"""

from __future__ import annotations

import pytest

import backend.session_store as ss
from backend.session_store import session_store


class _FakeRedis:
    """Minimal fake with scan_iter/delete; keys() raises to prove it's unused."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self.deleted: list[str] = []
        self.scan_calls = 0

    def scan_iter(self, match: str, count: int = 100):  # noqa: A002 — matches redis-py
        self.scan_calls += 1
        for k in self._keys:
            if k.startswith(match.rstrip("*")):
                yield k

    def delete(self, *keys: str) -> int:
        self.deleted.extend(keys)
        return len(keys)

    def keys(self, pattern: str):  # pragma: no cover - must never be reached
        raise AssertionError(f"redis.keys({pattern!r}) must not be called (C-09)")


@pytest.fixture(autouse=True)
def _inject_fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    ss._redis_checked = False
    ss._redis_available = False
    ss._redis_client = None


def _set_fake(keys: list[str]) -> _FakeRedis:
    fake = _FakeRedis(keys)
    ss._redis_checked = True
    ss._redis_available = True
    ss._redis_client = fake
    return fake


class TestScanIterOnly:
    def test_clear_all_sessions_uses_scan_not_keys(self):
        fake = _set_fake(["bazspark:session:a", "bazspark:session:b", "other:key"])
        session_store.clear_all_sessions()
        assert fake.scan_calls >= 1
        assert sorted(fake.deleted) == ["bazspark:session:a", "bazspark:session:b"]
        assert "other:key" not in fake.deleted

    def test_clear_all_failed_attempts_uses_scan_not_keys(self):
        fake = _set_fake(["bazspark:failed:1.2.3.4", "bazspark:session:a"])
        session_store.clear_all_failed_attempts()
        assert fake.scan_calls >= 1
        assert fake.deleted == ["bazspark:failed:1.2.3.4"]

    def test_get_session_count_uses_scan_not_keys(self):
        fake = _set_fake(["bazspark:session:a", "bazspark:session:b", "bazspark:session:c"])
        assert session_store.get_session_count() == 3
        assert fake.scan_calls >= 1
