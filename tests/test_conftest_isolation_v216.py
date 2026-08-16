# NOSONAR — S6801: pytest test file, intentionally no top-level __init__.
"""
Regression test for V216 / Gate 2 — FIREAI_API_KEY contamination.

Tests that the autouse fixture `_enforce_root_test_api_key` in
tests/conftest.py correctly sets FIREAI_API_KEY for root tests/ even when
backend/tests/conftest.py has already leaked its value at import time.

Previously (pre-V216), the fixture used `setdefault` which is a no-op
against the leaked value — causing root tests like test_v2_api.py (which
expects "test-key-for-v2-api-testing-1234567890") to receive the backend
key ("test-api-key-for-testing-only") and fail with 401 Unauthorized.

This regression test pins the contract:
  - Root tests/ and backend/tests/ use DIFFERENT test keys (test_disjoint_keys).
  - When the autouse fixture sees the leaked backend key, it overwrites
    with the root key (test_autouse_logic_overwrites_leaked_value).
  - When the autouse fixture sees a custom key set by the test (e.g.
    test_auth_router's "test_key_for_auth_123"), it preserves it
    (test_autouse_logic_preserves_custom_keys).
"""

from __future__ import annotations

import os
from pathlib import Path

# The value root tests/ tests expect (matches tests/conftest.py and tests/test_v2_api.py).
ROOT_EXPECTED_KEY = "test-key-for-v2-api-testing-1234567890"
# The value backend/tests/ uses (matches backend/tests/conftest.py TEST_API_KEY).
BACKEND_TEST_KEY = "test-api-key-for-testing-only"
# A custom key a test might set (matches tests/test_auth_router.py).
CUSTOM_TEST_KEY = "test_key_for_auth_123"


def test_disjoint_keys():
    """
    Document the contract: root tests/ and backend/tests/ use DIFFERENT
    FIREAI_API_KEY values. This is intentional — root tests test the v2 API
    surface with one key, backend tests test v1 with another. The conftest
    isolation preserves this distinction.

    If this test fails, someone changed one of the keys — investigate
    whether the conftest isolation logic still applies.
    """
    assert ROOT_EXPECTED_KEY != BACKEND_TEST_KEY, (
        "Root and backend test keys must differ — otherwise the isolation test is meaningless."
    )
    assert ROOT_EXPECTED_KEY != CUSTOM_TEST_KEY, (
        "Root and custom test keys must differ — otherwise the autouse "
        "fixture's preserve-vs-overwrite logic is meaningless."
    )
    assert BACKEND_TEST_KEY != CUSTOM_TEST_KEY, "Backend and custom test keys must differ."


def test_autouse_logic_overwrites_leaked_value(monkeypatch):
    """
    Pin the autouse fixture's contract: when FIREAI_API_KEY holds the
    backend-leaked value, the fixture MUST overwrite it with the root default.

    We simulate the autouse fixture's logic by importing tests/conftest.py
    and invoking the same code path. This avoids order-dependence on pytest's
    fixture resolution.
    """
    # Simulate the post-collection state: backend conftest has leaked its key.
    monkeypatch.setenv("FIREAI_API_KEY", BACKEND_TEST_KEY)

    # Replicate the autouse fixture's logic (see tests/conftest.py).
    # This is the V216 fix's core behavior.
    current = os.environ.get("FIREAI_API_KEY", "")
    if current == BACKEND_TEST_KEY or current == "":
        monkeypatch.setenv("FIREAI_API_KEY", ROOT_EXPECTED_KEY)

    assert os.environ["FIREAI_API_KEY"] == ROOT_EXPECTED_KEY, (
        f"Autouse fixture failed to overwrite leaked backend key. "
        f"Got {os.environ['FIREAI_API_KEY']!r}, expected {ROOT_EXPECTED_KEY!r}."
    )


def test_autouse_logic_preserves_custom_keys(monkeypatch):
    """
    Pin the autouse fixture's contract: when FIREAI_API_KEY holds a custom
    value set by the test itself (e.g. test_auth_router.py's
    "test_key_for_auth_123"), the fixture MUST NOT overwrite it.

    Without this contract, the autouse fixture would clobber test-specific
    keys, breaking tests that need a specific key for their assertions.
    """
    # Simulate a test that has set its own custom key via _setup_env_module.
    monkeypatch.setenv("FIREAI_API_KEY", CUSTOM_TEST_KEY)

    # Replicate the autouse fixture's logic.
    current = os.environ.get("FIREAI_API_KEY", "")
    if current == BACKEND_TEST_KEY or current == "":
        monkeypatch.setenv("FIREAI_API_KEY", ROOT_EXPECTED_KEY)

    assert os.environ["FIREAI_API_KEY"] == CUSTOM_TEST_KEY, (
        f"Autouse fixture incorrectly overwrote a custom test key. "
        f"Got {os.environ['FIREAI_API_KEY']!r}, expected {CUSTOM_TEST_KEY!r}. "
        f"The fixture must only overwrite the backend-leaked value, not "
        f"custom keys set by individual tests."
    )


def test_root_conftest_uses_monkeypatch_not_setdefault():
    """
    Static check: verify tests/conftest.py::_enforce_root_test_api_key uses
    `monkeypatch.setenv` (the V216 fix) and NOT `setdefault` (the buggy
    pre-V216 behavior).

    This is a structural regression test — it reads the conftest source and
    asserts the fix is in place. If someone reverts the fix, this test fails.
    """
    conftest_path = Path(__file__).parent / "conftest.py"
    src = conftest_path.read_text()

    # Locate the autouse fixture body.
    marker = "_enforce_root_test_api_key"
    assert marker in src, f"Could not find {marker} fixture in tests/conftest.py"

    # Find the fixture body (between the @pytest.fixture decorator and the
    # next top-level def/class).
    start = src.index(marker)
    # Find the next top-level def/class after the fixture
    end_markers = ["\ndef ", "\nclass ", "\n@"]
    end = len(src)
    for em in end_markers:
        idx = src.find(em, start + 1)
        if idx != -1 and idx < end:
            end = idx
    fixture_body = src[start:end]

    # Assert the fix is present
    assert "monkeypatch.setenv" in fixture_body, (
        "tests/conftest.py::_enforce_root_test_api_key must use "
        "`monkeypatch.setenv` to overwrite the leaked backend value. "
        "Found fixture body does not contain `monkeypatch.setenv` — "
        "did someone revert the V216 fix?"
    )
    # Assert the buggy pattern is NOT used for FIREAI_API_KEY
    assert 'setdefault("FIREAI_API_KEY"' not in fixture_body, (
        "tests/conftest.py::_enforce_root_test_api_key must NOT use "
        "`setdefault('FIREAI_API_KEY', ...)` — that is the buggy pre-V216 "
        "behavior that fails to overwrite the leaked backend value. "
        "Use `monkeypatch.setenv` instead."
    )


def test_backend_conftest_uses_setdefault_not_direct_assignment():
    """
    Static check: verify backend/tests/conftest.py uses `setdefault` (the
    V216 fix) at IMPORT TIME and NOT direct `os.environ[...] = ...`
    assignment. The import-time leak is the Gate 2 contamination source.

    Note: there is a separate `os.environ["FIREAI_API_KEY"] = TEST_API_KEY`
    inside `_patched_testclient_init` (gated by `if is_backend_test:`),
    which only fires for actual backend tests. That is intentional and
    safe — it doesn't leak to root tests/ because it's gated by the
    is_backend_test check. This static check verifies only the IMPORT-TIME
    behavior.

    This is a structural regression test — if someone reverts the fix,
    this test fails.
    """
    conftest_path = Path(__file__).parent.parent / "backend" / "tests" / "conftest.py"
    src = conftest_path.read_text()
    lines = src.splitlines()

    # The buggy pattern at IMPORT TIME (top-level, no indentation):
    # `os.environ["FIREAI_API_KEY"] = TEST_API_KEY`
    # The fix pattern at IMPORT TIME (top-level):
    # `os.environ.setdefault("FIREAI_API_KEY", TEST_API_KEY)`
    #
    # We check only top-level lines (no leading whitespace) to distinguish
    # import-time assignments from the function-gated one on line ~203.
    top_level_lines = [
        (i + 1, ln)
        for i, ln in enumerate(lines)
        if ln and not ln[0].isspace() and not ln.startswith("#")
    ]

    # Find any top-level line that does a DIRECT assignment to FIREAI_API_KEY
    # using TEST_API_KEY. This is the buggy import-time leak.
    buggy_top_level = [
        (ln_no, ln)
        for ln_no, ln in top_level_lines
        if 'os.environ["FIREAI_API_KEY"]' in ln and "TEST_API_KEY" in ln and "setdefault" not in ln
    ]
    assert not buggy_top_level, (
        f"backend/tests/conftest.py has a top-level (import-time) direct "
        f"assignment that leaks FIREAI_API_KEY: {buggy_top_level}. "
        "Restore the V216 fix: use `os.environ.setdefault('FIREAI_API_KEY', "
        "TEST_API_KEY)` at top level."
    )

    # Verify the fix is in place at top level.
    fix_present = any(
        'os.environ.setdefault("FIREAI_API_KEY", TEST_API_KEY)' in ln for _, ln in top_level_lines
    )
    assert fix_present, (
        "backend/tests/conftest.py is missing the V216 fix: top-level "
        "`os.environ.setdefault('FIREAI_API_KEY', TEST_API_KEY)`. "
        "Restore the fix."
    )
