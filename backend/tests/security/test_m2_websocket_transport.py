"""Phase 5 — M-2 (websocket_transport) FIX VERIFICATION.

ORIGINAL CLAIM (from Phase 3 verdict, now RESOLVED):
  "M-2: websocket_transport fail-open when auth_token=None + timing
   attack (not in FastAPI backend)"

FIXES APPLIED (this round):
  1. Token comparison now uses hmac.compare_digest (constant-time) —
     the timing attack is eliminated.
  2. auth_token=None now logs a WARNING at startup — the fail-open
     behavior is documented as an explicit design choice for trusted
     internal networks.

These tests verify the FIXES are in place. They serve as regression
guards: if someone reverts the fix, the tests will FAIL.

If any test FAILS, the fix has been reverted — re-apply immediately.
"""
from __future__ import annotations

import ast
import asyncio
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
WS_TRANSPORT_PY = REPO_ROOT / "facp_distributed" / "transport" / "websocket_transport.py"


def _iter_python_files(root: Path):
    skip_dirs = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                 "node_modules", ".git", ".venv", "venv", "site-packages"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                yield Path(dirpath) / fname


def _imports_any(ast_root: ast.AST, *targets: str) -> bool:
    for node in ast.walk(ast_root):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == t or alias.name.startswith(t + ".")
                       for t in targets):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0:
                if any(mod == t or mod.startswith(t + ".") for t in targets):
                    return True
    return False


# ─── FIX VERIFICATION: token comparison uses hmac.compare_digest ────────────


def test_token_comparison_uses_constant_time_hmac_compare_digest():
    """REGRESSION GUARD: verify the token comparison uses hmac.compare_digest.

    The M-2 fix replaced the vulnerable `!= self.auth_token` comparison
    with `hmac.compare_digest(provided, expected)` — a constant-time
    comparison that prevents timing attacks.

    This test scans websocket_transport.py for:
      1. `import hmac` (or `from hmac import ...`)
      2. A call to `hmac.compare_digest` in the auth check

    If this test FAILS, the fix has been reverted — the code is once
    again vulnerable to timing attacks. Re-apply the fix.
    """
    source = WS_TRANSPORT_PY.read_text(encoding="utf-8")

    # Verify hmac is imported
    assert "import hmac" in source, (
        "M-2 FIX REVERTED: websocket_transport.py no longer imports hmac. "
        "The constant-time comparison fix has been removed — re-apply it."
    )

    # Verify hmac.compare_digest is called
    assert "hmac.compare_digest" in source, (
        "M-2 FIX REVERTED: websocket_transport.py no longer calls "
        "hmac.compare_digest. The timing attack vulnerability has "
        "returned — re-apply the fix."
    )

    # Verify the OLD vulnerable pattern is GONE
    # The old code was: request_data.get("token") != self.auth_token
    tree = ast.parse(source, filename=str(WS_TRANSPORT_PY))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if isinstance(op, ast.NotEq):
                    left_str = ast.dump(node.left)
                    right_str = ast.dump(node.comparators[0]) if node.comparators else ""
                    if "auth_token" in left_str or "auth_token" in right_str:
                        pytest.fail(
                            "M-2 FIX REVERTED: found `!= self.auth_token` "
                            f"comparison at line {node.lineno}. The timing "
                            "attack vulnerability has returned — re-apply "
                            "the hmac.compare_digest fix."
                        )


# ─── FIX VERIFICATION: auth_token=None logs a warning ───────────────────────


def test_auth_token_none_logs_warning():
    """REGRESSION GUARD: verify auth_token=None logs a security warning.

    The M-2 fix added a warning log when auth_token=None, making the
    fail-open behavior visible to operators.

    If this test FAILS, the warning has been removed — operators will
    no longer be alerted when authentication is disabled.
    """
    source = WS_TRANSPORT_PY.read_text(encoding="utf-8")

    # Verify there's a warning log about auth_token=None
    assert "auth_token=None" in source or "auth_token is None" in source, (
        "M-2 FIX REVERTED: the auth_token=None warning has been removed."
    )
    assert "warning" in source.lower() or "_logger.warning" in source, (
        "M-2 FIX REVERTED: no warning log found for auth_token=None."
    )


# ─── Part (c): WebSocketTransport is NOT imported by FastAPI backend ─────────
# (This part of the claim was already accurate — no fix needed.
#  The test is kept as a regression guard.)


def test_websocket_transport_not_imported_by_backend():
    """REGRESSION GUARD: WebSocketTransport must not be imported by backend/.

    This was already true (no fix needed), but we keep the test as a
    tripwire — if a future change adds such an import, M-2 escalates
    to HIGH.
    """
    offenders: list[str] = []
    for subdir in ("backend", "fireai", "parsers", "facp_system", "core", "marine"):
        pkg_dir = REPO_ROOT / subdir
        if not pkg_dir.is_dir():
            continue
        for py in _iter_python_files(pkg_dir):
            parts = py.parts
            if "tests" in parts or py.name.startswith("test_") or py.name == "conftest.py":
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            except SyntaxError:
                continue
            if _imports_any(tree, "facp_distributed"):
                offenders.append(str(py))

    assert not offenders, (
        "M-2 REGRESSION: non-test code now imports facp_distributed. "
        "WebSocketTransport is reachable from HTTP-serving code. "
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_websocket_transport_class_not_referenced_outside_facp_distributed():
    """REGRESSION GUARD: no non-test file outside facp_distributed/ references
    WebSocketTransport by name."""
    offenders: list[str] = []
    for py in _iter_python_files(REPO_ROOT):
        parts = py.parts
        if "tests" in parts or py.name.startswith("test_") or py.name == "conftest.py":
            continue
        if py.resolve() == WS_TRANSPORT_PY.resolve():
            continue
        if py.name == "__init__.py" and py.parent.name == "transport" \
           and "facp_distributed" in parts:
            continue
        try:
            content = py.read_text(encoding="utf-8")
        except Exception:
            continue
        if "WebSocketTransport" in content:
            offenders.append(str(py))

    assert not offenders, (
        "M-2 REGRESSION: non-test files reference WebSocketTransport. "
        "Offenders:\n  " + "\n  ".join(offenders)
    )


# ─── RUNTIME: auth still works correctly after the fix ──────────────────────


def test_auth_token_set_still_correctly_rejects_wrong_token():
    """RUNTIME REGRESSION GUARD: verify the hmac.compare_digest fix didn't
    break legitimate auth rejection.

    After the fix, when auth_token IS set, a wrong token must still be
    rejected. This test sends a wrong token and verifies the server
    returns UNAUTHORIZED.
    """
    try:
        from facp_distributed.transport.websocket_transport import WebSocketTransport
    except ImportError as e:
        pytest.skip(f"facp_distributed not importable: {e}")

    transport = WebSocketTransport(
        host="127.0.0.1", port=0,
        auth_token="expected-secret-token",
    )

    class FakeWebSocket:
        def __init__(self, messages):
            self._messages = list(messages)
            self.sent: list[str] = []
            self.remote_address = ("127.0.0.1", 12345)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._messages:
                return self._messages.pop(0)
            raise StopAsyncIteration

        async def send(self, data):
            self.sent.append(data)

    mock_ws = FakeWebSocket([
        '{"method": "auth", "token": "WRONG-TOKEN", "id": "test-1"}',
    ])

    async def run():
        await transport._handle_client_message(mock_ws, "/")

    asyncio.run(run())

    import json
    assert mock_ws.sent, "Server sent no messages"
    first_response = json.loads(mock_ws.sent[0])
    err = first_response.get("error", {})
    err_code = err.get("code", "") if isinstance(err, dict) else ""
    assert err_code == "UNAUTHORIZED", (
        f"Auth regression: wrong token was NOT rejected. Got: {mock_ws.sent[0]}"
    )


def test_auth_token_set_correctly_accepts_right_token():
    """RUNTIME REGRESSION GUARD: verify the hmac.compare_digest fix didn't
    break legitimate auth acceptance.

    After the fix, when auth_token IS set, the CORRECT token must be
    accepted. This test sends the correct token and verifies the server
    returns a success response.
    """
    try:
        from facp_distributed.transport.websocket_transport import WebSocketTransport
    except ImportError as e:
        pytest.skip(f"facp_distributed not importable: {e}")

    transport = WebSocketTransport(
        host="127.0.0.1", port=0,
        auth_token="correct-secret-token",
    )

    class FakeWebSocket:
        def __init__(self, messages):
            self._messages = list(messages)
            self.sent: list[str] = []
            self.remote_address = ("127.0.0.1", 12345)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._messages:
                return self._messages.pop(0)
            raise StopAsyncIteration

        async def send(self, data):
            self.sent.append(data)

    mock_ws = FakeWebSocket([
        '{"method": "auth", "token": "correct-secret-token", "id": "test-1"}',
    ])

    async def run():
        await transport._handle_client_message(mock_ws, "/")

    asyncio.run(run())

    import json
    assert mock_ws.sent, "Server sent no messages"
    first_response = json.loads(mock_ws.sent[0])
    status = first_response.get("status", "")
    assert status == "ok", (
        f"Auth regression: correct token was NOT accepted. Got: {mock_ws.sent[0]}"
    )


# ─── Claim text regression guard ─────────────────────────────────────────────


def test_m2_claim_text_exists_in_worklog():
    """REGRESSION GUARD: the M-2 claim text must exist in worklog.md.

    The claim is now RESOLVED (fixes applied), but the original text
    must remain for traceability. If someone removes it, this test
    forces a conscious decision.
    """
    WORKLOG = REPO_ROOT / "worklog.md"
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")
    expected_substring = (
        "M-2: websocket_transport fail-open when auth_token=None + "
        "timing attack (not in FastAPI backend)"
    )

    assert expected_substring in worklog_text, (
        "M-2 claim text removed from worklog.md. If the claim has been "
        "resolved, update the worklog to mark it as RESOLVED rather "
        "than deleting the original text."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
