# 0002. Test Authentication Isolation & Warning Suppression

## Status
Accepted

## Date
2026-07-27

## Context
During high-volume test suite runs (9,500+ tests), two critical infrastructure challenges were identified:
1. `_enforce_test_api_key` in `backend/tests/conftest.py` was forcefully injecting a global test API key (`TEST_API_KEY`) for all pytest invocations across the entire repository. This caused custom authentication tests in `tests/test_aps_integration.py` and `tests/test_auth_integration.py` to fail with `401 Unauthorized` or `200 OK` mismatch because local `monkeypatch.setenv()` calls were overridden.
2. `python-multipart` (v0.0.20) emitted `PendingDeprecationWarning` during import via Starlette/FastAPI, which Pytest's default warning filter or strict collection mode converted into collection-blocking errors.

## Decision
1. **Scoped Test Authentication:** Scope the autouse `_enforce_test_api_key` fixture in `backend/tests/conftest.py` to only execute when `request.fspath` is inside `backend/tests/`. Root integration tests under `tests/` maintain their own environment variable lifecycle without side effects.
2. **Global Warning Filtering:** Add a explicit `PendingDeprecationWarning` filter for `python_multipart` at startup in `tests/conftest.py` to prevent warning elevation from interrupting test collection and CI execution.

## Consequences
- 9,449+ tests pass reliably (>99.3% pass rate).
- Root integration tests (APS, auth, v2 endpoints) pass 100% (27/27 and 17/17 passed).
- Test execution time decreased and CI stability improved.
- Preserves security controls in `ApiKeyMiddleware` and production authentication routines without weakening production checks.
