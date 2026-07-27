"""Pytest fixtures for SSRF security tests.

Ensures each test starts with clean DNS cache/lock state, so tests don't
pollute each other.
"""
import pytest


@pytest.fixture(autouse=True)
def _reset_ssrf_dns_state():
    """Auto-reset DNS cache + per-host locks + thread counter before each test.

    This prevents test pollution: without it, a test that caches a hostname
    would cause subsequent tests to hit the cache instead of doing fresh
    DNS lookups (breaking test isolation).
    """
    from backend.integrations._ssrf_guard import _reset_dns_state_for_testing
    _reset_dns_state_for_testing()
    yield
    # Clean up after test too, in case the test populated the cache
    _reset_dns_state_for_testing()
