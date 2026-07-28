"""Pytest fixtures for SSRF security tests.

Ensures each test starts with clean DNS cache/lock state, so tests don't
pollute each other. Also isolates backend.app (but NOT backend.integrations)
from sys.modules to prevent cross-test pollution of the FastAPI app cache.
"""
import sys

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


# Modules to evict after each security test to prevent backend.app caching
# from polluting other test modules. We deliberately EXCLUDE:
#   - backend.integrations._ssrf_guard  (has daemon threads that reference
#     module-level state; evicting it causes test_dns_rebinding_attack_is_defeated
#     to fail when run after test_hostname_resolving_to_loopback_is_rejected)
#   - backend.integrations             (parent of _ssrf_guard, same reason)
#   - backend.services.workflow_service (uses langgraph ForwardRef type hints
#     with `from __future__ import annotations`; evicting it causes NameError
#     on re-import because ForwardRef resolution happens before the module's
#     namespace is fully populated)
#   - backend.routers.*                (same ForwardRef issue with Pydantic)
#
# We ONLY evict backend.app itself. The backend.app module caches
# FIREAI_API_KEY at import time via config, which is the root cause of the
# auth test pollution. Evicting just backend.app forces a re-import of the
# app (which re-reads env vars) without breaking any submodule's type hints.
_EVICT_PATTERNS = (
    "backend.app",
)


@pytest.fixture(autouse=True)
def _evict_backend_app_after_security_tests():
    """Evict backend.app (but NOT _ssrf_guard) from sys.modules after each test.

    SECURITY TEST ISOLATION CONTRACT:
    ---------------------------------
    test_marshal_loads_not_http_reachable.py imports `from backend.app import app`
    inside the test function. Without eviction, this caches `backend.app` in
    sys.modules with FIREAI_API_KEY captured at import time. When a later test
    in tests/test_auth_router.py sets a DIFFERENT FIREAI_API_KEY, the cached
    app is reused — so the new API key is silently ignored.

    This fixture evicts backend.app and related modules AFTER each security
    test, so the next test module that imports backend.app gets a FRESH import.

    IMPORTANT: We do NOT evict backend.integrations._ssrf_guard because it has
    daemon threads (started by _resolve_host_with_timeout) that reference
    module-level state (_DNS_CACHE, _DNS_THREAD_COUNT). Evicting _ssrf_guard
    while a daemon thread is in-flight causes the thread to cache its result
    in the OLD module's _DNS_CACHE, but the NEW module (re-imported after
    eviction) has a fresh _DNS_CACHE. This causes test_dns_rebinding_attack_is_defeated
    to fail when run after test_hostname_resolving_to_loopback_is_rejected
    (which starts a real DNS query daemon thread that may still be running).
    """
    yield
    for key in list(sys.modules.keys()):
        if any(key == pat.rstrip(".") or key.startswith(pat) for pat in _EVICT_PATTERNS):
            sys.modules.pop(key, None)
