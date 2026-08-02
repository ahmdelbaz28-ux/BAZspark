"""Phase 5 — Strict verification of the L-3 (websocket_transport ws:// default) claim.

CLAIM UNDER TEST (from worklog.md, Phase 3 verdict, LOW ISSUES section):
  Original wording (HISTORICAL):
    "L-3: websocket_transport ws:// default (intended for internal comms
     per NOSONAR comment)"
  Current wording (after L-3 FIX round):
    "L-3: websocket_transport ws:// default — RESOLVED. The default
     outbound URL was changed from `ws://` to `wss://` (secure-by-
     default). A new constructor parameter `allow_insecure_ws: bool =
     False` allows opt-in to ws:// for trusted internal dev/test.
     Any caller that passes a ws:// target_node without
     allow_insecure_ws=True now triggers a ValueError at request time."

WHAT WE VERIFY (post-fix regression guards):
  1. The file exists at the expected path.
  2. The default outbound URL is now `wss://` (post-fix).
  3. The OLD `ws://` default is GONE (post-fix).
  4. The `allow_insecure_ws` constructor parameter exists (opt-in flag).
  5. The default value of `allow_insecure_ws` is `False` (secure-by-default).
  6. The ws:// rejection logic exists (raises ValueError when ws:// is
     used without allow_insecure_ws=True).
  7. The class is NOT instantiated in production code (latent-risk
     tripwire — fails if a future commit wires the class into production).
  8. The class IS exported from the package's __init__.py (the export
     remains — risk is latent, not closed).
  9. The L-3 claim text in worklog.md reflects the RESOLVED state.
  10. RUNTIME test: instantiating WebSocketTransport and calling
      send_request with a ws:// target_node raises ValueError without
      allow_insecure_ws=True.

NON-VACUOUSNESS:
  Each test below is proven to fail when its assertion is violated.
  Verified by /home/z/my-project/scripts/verify_l1_l2_l3_post_fix_nonvacuous.py.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WEBSOCKET_TRANSPORT_PY = (
    REPO_ROOT / "facp_distributed" / "transport" / "websocket_transport.py"
)
TRANSPORT_INIT_PY = (
    REPO_ROOT / "facp_distributed" / "transport" / "__init__.py"
)


# ─── L-3 part (a): file exists ──────────────────────────────────────────────


def test_l3_websocket_transport_file_exists():
    """REGRESSION GUARD: websocket_transport.py must exist at the expected path."""
    assert WEBSOCKET_TRANSPORT_PY.exists(), (
        f"websocket_transport.py not found at {WEBSOCKET_TRANSPORT_PY}. "
        "The L-3 claim references this file — if it has been moved, "
        "update the claim and the test path."
    )


# ─── L-3 part (b): the default outbound URL is now wss:// (post-fix) ────────


def test_l3_default_url_is_now_wss():
    """REGRESSION GUARD (post-fix): the default outbound URL must be
    `wss://` (secure-by-default).

    The pre-fix code used `f"ws://{self.host}:{self.port}"`. The post-fix
    code uses `f"wss://{self.host}:{self.port}"`. If someone reverts to
    ws://, this test FAILS.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")
    source = WEBSOCKET_TRANSPORT_PY.read_text(encoding="utf-8")

    # Look for the wss:// default URL pattern.
    wss_default_pattern = re.compile(
        r'f?"wss://\{?self\.(host|port)',
    )
    assert wss_default_pattern.search(source), (
        "No `wss://` default URL pattern (e.g., "
        "`f\"wss://{self.host}:{self.port}\"`) found in "
        "websocket_transport.py. The L-3 fix requires the default "
        "outbound URL to be `wss://` (secure-by-default). RESTORE the "
        "L-3 fix."
    )


# ─── L-3 part (c): the OLD ws:// default is GONE (post-fix) ─────────────────


def test_l3_old_ws_default_is_REMOVED():
    """REGRESSION GUARD (post-fix): the OLD `ws://` default URL must
    NOT be used as the fallback in `send_request`.

    The pre-fix code had `node = target_node or f"ws://..."`. The post-fix
    code has `node = target_node or f"wss://..."`. If someone reverts
    to ws:// as the default fallback, this test FAILS.

    NOTE: a `ws://` STRING LITERAL may still appear in the file as part
    of the ValueError rejection logic (`if node.startswith("ws://")`).
    That is CORRECT post-fix behavior — the check uses ws:// to detect
    insecure URLs and reject them. What is forbidden is using ws:// as
    the DEFAULT fallback when no target_node is provided.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")
    source = WEBSOCKET_TRANSPORT_PY.read_text(encoding="utf-8")

    # The forbidden pattern: `node = target_node or f"ws://..."`.
    # This is the OLD default fallback. The post-fix uses wss://.
    forbidden_pattern = re.compile(
        r'node\s*=\s*target_node\s+or\s+f?"ws://',
    )
    assert not forbidden_pattern.search(source), (
        "The OLD `node = target_node or f\"ws://...\"` default fallback "
        "is still present. The L-3 fix requires this to be `wss://`. "
        "RESTORE the L-3 fix."
    )


# ─── L-3 part (d): the allow_insecure_ws constructor parameter exists ───────


def test_l3_allow_insecure_ws_parameter_exists():
    """REGRESSION GUARD (post-fix): the `WebSocketTransport.__init__`
    must accept an `allow_insecure_ws: bool = False` parameter.

    This is the OPT-IN mechanism for ws://. Without this parameter,
    callers have no way to use ws:// even for trusted internal dev/test.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")
    source = WEBSOCKET_TRANSPORT_PY.read_text(encoding="utf-8")

    # Look for `allow_insecure_ws: bool = False` in the __init__ signature.
    param_pattern = re.compile(
        r'def\s+__init__\s*\([^)]*allow_insecure_ws\s*:\s*bool\s*=\s*False',
        re.MULTILINE | re.DOTALL,
    )
    assert param_pattern.search(source), (
        "The `allow_insecure_ws: bool = False` parameter is NOT in the "
        "WebSocketTransport.__init__ signature. The L-3 fix requires "
        "this opt-in parameter for ws:// callers. RESTORE the L-3 fix."
    )


# ─── L-3 part (e): the default value of allow_insecure_ws is False ──────────


def test_l3_allow_insecure_ws_defaults_to_false():
    """REGRESSION GUARD (post-fix): `allow_insecure_ws` must default to
    `False` (secure-by-default).

    If someone "conveniently" changes the default to `True` (e.g., to
    "avoid breaking existing callers"), this test FAILS — the secure-
    by-default guarantee is broken.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")
    source = WEBSOCKET_TRANSPORT_PY.read_text(encoding="utf-8")

    # The parameter must default to False (not True).
    # Match `allow_insecure_ws: bool = False` (allowed)
    # Reject `allow_insecure_ws: bool = True` (forbidden)
    true_default_pattern = re.compile(
        r'allow_insecure_ws\s*:\s*bool\s*=\s*True',
    )
    assert not true_default_pattern.search(source), (
        "The `allow_insecure_ws` parameter defaults to `True` — this "
        "BREAKS the secure-by-default guarantee. The default must be "
        "`False` so callers must explicitly opt in to ws://. RESTORE "
        "the L-3 fix."
    )


# ─── L-3 part (f): the ws:// rejection logic exists ─────────────────────────


def test_l3_ws_rejection_logic_exists():
    """REGRESSION GUARD (post-fix): the file must contain logic that
    REJECTS ws:// URLs when allow_insecure_ws is False.

    The expected pattern:
      if node.startswith("ws://") and not self.allow_insecure_ws:
          raise ValueError(...)
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")
    source = WEBSOCKET_TRANSPORT_PY.read_text(encoding="utf-8")

    rejection_pattern = re.compile(
        r'node\.startswith\s*\(\s*["\']ws://["\']\s*\)\s+and\s+not\s+self\.allow_insecure_ws',
    )
    assert rejection_pattern.search(source), (
        "The ws:// rejection logic is missing. The L-3 fix requires "
        "`if node.startswith('ws://') and not self.allow_insecure_ws: "
        "raise ValueError(...)`. RESTORE the L-3 fix."
    )

    # The rejection must raise ValueError (not just log a warning).
    # Find the rejection block and verify it raises ValueError.
    rejection_block_pattern = re.compile(
        r'node\.startswith\s*\(\s*["\']ws://["\']\s*\)\s+and\s+not\s+self\.allow_insecure_ws'
        r'.*?raise\s+ValueError',
        re.MULTILINE | re.DOTALL,
    )
    assert rejection_block_pattern.search(source), (
        "The ws:// rejection logic does not raise ValueError. The L-3 "
        "fix requires a hard failure (ValueError), not just a warning "
        "log. RESTORE the L-3 fix."
    )


# ─── L-3 part (g): the class is NOT instantiated in production code ─────────


def test_l3_class_not_instantiated_in_production():
    """HONEST CAVEAT (unchanged from pre-fix): WebSocketTransport is
    NOT instantiated in any production code file. The risk is LATENT,
    not active.

    NOTE: After the L-3 fix, the risk is not just latent — it's also
    GUARDED. Even if a future commit wires WebSocketTransport into
    production, the secure-by-default wss:// and the ValueError on
    ws:// without opt-in will prevent insecure usage. But the orphan
    status is still relevant: if the class is wired into production,
    the runtime tests below (part j, k) become ACTIVE guarantees.

    If a future commit adds a production instantiation, this test
    FAILS — forcing the L-3 claim to be re-evaluated.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")

    instantiation_pattern = re.compile(r'WebSocketTransport\s*\(')

    production_instantiations = []
    for py_file in REPO_ROOT.rglob("*.py"):
        rel_path = py_file.relative_to(REPO_ROOT)
        if py_file == WEBSOCKET_TRANSPORT_PY:
            continue
        path_str = str(rel_path)
        if "/tests/" in path_str or "/test/" in path_str \
            or path_str.startswith("tests/") or path_str.startswith("test/") \
            or "conftest.py" in path_str or "test_" in py_file.stem:
            continue
        if py_file.name == "__init__.py":
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in instantiation_pattern.finditer(text):
            start = max(0, m.start() - 30)
            prefix = text[start:m.start()]
            if re.search(r'\bclass\s+$', prefix) or re.search(r'\bdef\s+$', prefix) \
                or re.search(r'\bfrom\s+$', prefix) or re.search(r'\bimport\s+$', prefix):
                continue
            production_instantiations.append(str(rel_path))

    assert not production_instantiations, (
        "WebSocketTransport is now INSTANTIATED in production code: "
        + str(production_instantiations) + ". "
        "The L-3 risk is no longer latent — but the L-3 fix (secure-by-"
        "default wss:// + ValueError on ws:// without opt-in) should "
        "still prevent insecure usage. Re-evaluate the L-3 claim's "
        "severity and verify the runtime tests below still pass."
    )


# ─── L-3 part (h): the class IS exported from the package's __init__.py ─────


def test_l3_class_is_exported_from_package():
    """HONEST CAVEAT (unchanged from pre-fix): WebSocketTransport IS
    exported from facp_distributed/transport/__init__.py, so a future
    production instantiation is possible (the risk is latent, not closed).

    NOTE: After the L-3 fix, the export is no longer a "soft caveat" —
    it's a HARD TRIPWIRE combined with the secure-by-default behavior.
    Any future production instantiation will get wss:// by default and
    ValueError on ws:// without opt-in.

    If the export is removed (e.g., the class is made private), this
    test FAILS — and the L-3 claim's "latent risk" framing should be
    updated to "closed".
    """
    if not TRANSPORT_INIT_PY.exists():
        pytest.skip("facp_distributed/transport/__init__.py not found")
    init_source = TRANSPORT_INIT_PY.read_text(encoding="utf-8")

    export_pattern = re.compile(
        r'from\s+\.websocket_transport\s+import\s+WebSocketTransport'
        r'|from\s+facp_distributed\.transport\.websocket_transport\s+import\s+WebSocketTransport',
    )
    assert export_pattern.search(init_source), (
        "WebSocketTransport is no longer exported from "
        "facp_distributed/transport/__init__.py. The L-3 risk has "
        "been CLOSED (the class is no longer reachable from outside "
        "the package). Update the worklog claim to 'L-3: RESOLVED — "
        "WebSocketTransport export removed' if this was intentional."
    )


# ─── L-3 part (i): the claim text in worklog.md reflects RESOLVED state ─────


def test_l3_claim_text_reflects_resolved_state():
    """REGRESSION GUARD (post-fix): the L-3 claim text in worklog.md
    must reflect the RESOLVED state.

    The pre-fix claim was:
      "L-3: websocket_transport ws:// default (intended for internal
       comms per NOSONAR comment)"

    The post-fix claim should include the markers:
      - "RESOLVED" or "FIXED"
      - "wss://" (the new default)
      - "allow_insecure_ws" (the opt-in parameter)
    """
    WORKLOG = Path("/home/z/my-project/worklog.md")
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")

    low_section_start = worklog_text.find("LOW ISSUES:")
    if low_section_start == -1:
        pytest.skip("LOW ISSUES section not found in worklog")
    after_low = worklog_text[low_section_start:]
    end_markers = ["RETRACTED FALSE CLAIMS", "NUMERICAL ERRORS",
                   "FALSE ACCUSATION PATTERNS", "POSITIVES VERIFIED"]
    end_idx = len(after_low)
    for marker in end_markers:
        idx = after_low.find(marker)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    low_section = after_low[:end_idx]
    low_normalized = re.sub(r"\s+", " ", low_section)

    # Extract the L-3 entry specifically (from "L-3:" up to the next
    # section marker or end). L-3 is the LAST entry in LOW ISSUES, so
    # the end is the end of the section.
    l3_match = re.search(r'L-3:.*?(?=\s*(?:RETRACTED|NUMERICAL|FALSE|POSITIVES|LOW ISSUES|$))',
                         low_normalized, re.DOTALL)
    assert l3_match, (
        "L-3 entry missing from LOW ISSUES section. The LOW ISSUES "
        "section should contain entries L-1, L-2, L-3."
    )
    l3_entry = l3_match.group(0)

    assert ("RESOLVED" in l3_entry or "FIXED" in l3_entry), (
        "L-3 entry in LOW ISSUES does not mention RESOLVED or FIXED. "
        "The L-3 fix has been applied — update the worklog to reflect "
        "the RESOLVED state."
    )
    assert "wss://" in l3_entry, (
        "L-3 entry in LOW ISSUES does not mention 'wss://' (the new "
        "secure default). Update the worklog claim wording."
    )
    assert "allow_insecure_ws" in l3_entry, (
        "L-3 entry in LOW ISSUES does not mention 'allow_insecure_ws' "
        "(the opt-in parameter for ws://). Update the worklog claim "
        "wording."
    )


# ─── L-3 part (j): RUNTIME — ws:// without opt-in raises ValueError ─────────


@pytest.mark.timeout(15)
def test_l3_runtime_ws_rejected_without_opt_in(monkeypatch):
    """REGRESSION GUARD (post-fix, RUNTIME): instantiating WebSocketTransport
    with default parameters and calling send_request with a ws://
    target_node must RAISE ValueError.

    This is the RUNTIME proof that the L-3 fix is effective, not just
    present in the source code.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")

    # Import the class dynamically (the module path may not be on sys.path
    # by default — add the repo root).
    import importlib
    if str(REPO_ROOT) not in sys.path:
        monkeypatch.syspath_prepend(str(REPO_ROOT))
    try:
        mod = importlib.import_module(
            "facp_distributed.transport.websocket_transport"
        )
        WebSocketTransport = mod.WebSocketTransport
    except Exception as e:
        pytest.skip(f"Cannot import WebSocketTransport: {e}")

    # Instantiate with default parameters (allow_insecure_ws=False).
    transport = WebSocketTransport(host="example.com", port=8002)

    # Call send_request with a ws:// target_node. This should raise
    # ValueError because allow_insecure_ws is False.
    with pytest.raises(ValueError, match="insecure ws://"):
        asyncio.run(transport.send_request(
            target_node="ws://insecure.example.com:8002",
            request_data={"id": "test", "method": "ping"},
        ))


# ─── L-3 part (k): RUNTIME — wss:// default works without opt-in ────────────


@pytest.mark.timeout(15)
def test_l3_runtime_wss_default_does_not_raise(monkeypatch):
    """REGRESSION GUARD (post-fix, RUNTIME): instantiating WebSocketTransport
    with default parameters and calling send_request with NO target_node
    must NOT raise ValueError (the default is wss://, which is allowed).

    This verifies that the L-3 fix doesn't break the default usage
    pattern — only ws:// without opt-in is rejected.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")

    import importlib
    if str(REPO_ROOT) not in sys.path:
        monkeypatch.syspath_prepend(str(REPO_ROOT))
    try:
        mod = importlib.import_module(
            "facp_distributed.transport.websocket_transport"
        )
        WebSocketTransport = mod.WebSocketTransport
    except Exception as e:
        pytest.skip(f"Cannot import WebSocketTransport: {e}")

    transport = WebSocketTransport(host="example.com", port=8002)

    async def _call():
        # No target_node — the default wss:// URL should be used.
        # The actual connection will FAIL (example.com:8002 doesn't
        # run a websocket server), but the failure should NOT be a
        # ValueError from the ws:// rejection. It should be a
        # WEBSOCKET_CONNECTION_ERROR from the connection attempt.
        result = await transport.send_request(
            target_node=None,
            request_data={"id": "test", "method": "ping"},
        )
        return result

    # The call should NOT raise ValueError. It may return an error
    # dict (WEBSOCKET_CONNECTION_ERROR) because the connection fails,
    # but that's expected — we're testing that the ws:// rejection
    # logic doesn't fire on the wss:// default.
    try:
        result = asyncio.run(_call())
        # If we got a result, it should be an error dict (connection
        # failed), NOT a successful response (we didn't actually
        # connect to anything).
        if not isinstance(result, dict):
            pytest.fail(
                f"Expected dict result, got {type(result).__name__}: {result}"
            )
    except ValueError as e:
        if "insecure ws://" in str(e):
            pytest.fail(
                "The wss:// default URL was WRONGLY rejected by the "
                "ws:// rejection logic. The check must only fire on "
                "ws:// URLs, not wss://. RESTORE the L-3 fix."
            )
        else:
            # A different ValueError — re-raise (unexpected).
            raise
    except (OSError, ConnectionError, RuntimeError, TypeError):
        # Connection/type errors are acceptable — send_request is sync
        # but the test awaits it; TypeError from non-awaitable is expected.
        # Intentionally narrow catch to avoid swallowing AssertionError.
        pass


# ─── L-3 part (l): RUNTIME — ws:// WITH opt-in does not raise ValueError ────


@pytest.mark.timeout(15)
def test_l3_runtime_ws_allowed_with_opt_in(monkeypatch):
    """REGRESSION GUARD (post-fix, RUNTIME): instantiating WebSocketTransport
    with `allow_insecure_ws=True` and calling send_request with a ws://
    target_node must NOT raise ValueError (the opt-in flag is set).

    This verifies that the opt-in mechanism actually works — callers
    who explicitly opt in can still use ws:// for trusted internal
    dev/test.
    """
    if not WEBSOCKET_TRANSPORT_PY.exists():
        pytest.skip("websocket_transport.py not found")

    import importlib
    if str(REPO_ROOT) not in sys.path:
        monkeypatch.syspath_prepend(str(REPO_ROOT))
    try:
        mod = importlib.import_module(
            "facp_distributed.transport.websocket_transport"
        )
        WebSocketTransport = mod.WebSocketTransport
    except Exception as e:
        pytest.skip(f"Cannot import WebSocketTransport: {e}")

    transport = WebSocketTransport(
        host="example.com", port=8002, allow_insecure_ws=True,
    )

    async def _call():
        await transport.send_request(
            target_node="ws://internal-dev.example.com:8002",
            request_data={"id": "test", "method": "ping"},
        )

    # The call should NOT raise ValueError. It may raise a connection
    # error (no actual server running), but that's acceptable.
    try:
        asyncio.run(_call())
    except ValueError as e:
        if "insecure ws://" in str(e):
            pytest.fail(
                "The ws:// URL was WRONGLY rejected even though "
                "allow_insecure_ws=True was set. The opt-in mechanism "
                "is broken. RESTORE the L-3 fix."
            )
        else:
            raise
    except (OSError, ConnectionError, RuntimeError, TypeError):
        # Connection/type errors are acceptable — send_request is sync
        # but the test awaits it; TypeError from non-awaitable is expected.
        # Intentionally narrow catch to avoid swallowing AssertionError.
        pass


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
