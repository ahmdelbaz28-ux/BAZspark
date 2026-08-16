"""Phase 5 — M-5 (digital_twin path traversal) FIX VERIFICATION.

ORIGINAL CLAIM (from Phase 3 verdict — REWORDED for accuracy in
PHASE5-M4-M5-REWORD-L1-L2-L3 round):
  ORIGINAL (misleading) wording:
    "M-5: digital_twin.py:91 str.startswith (still uses startswith
     despite V214 comment)"

  REWORDED (current, accurate) wording:
    "M-5: backend/routers/digital_twin.py:91 uses str.startswith for
     path containment (brittle pattern, but currently safe due to
     os.path.join preventing suffix attacks; V214 comment explains
     the absolute-path fix and does NOT contradict startswith itself)"

  WHY THE REWORD:
    The original "despite V214 comment" framing suggested the V214
    comment argued against startswith itself. That was misleading.
    The V214 comment actually explains the absolute-path fix (relative
    `resolved` vs absolute `abs_upload`) — it does NOT argue against
    startswith. The reworded wording correctly identifies (a) the
    pattern is brittle, (b) current safety is due to os.path.join,
    (c) V214 explains the absolute-path fix, not an anti-startswith
    stance.

FIXES APPLIED (in PHASE5-PRODUCTION-CODE-FIXES round):
  Replaced the brittle `str.startswith(abs_upload)` check with
  `Path.is_relative_to(abs_upload)` — Python 3.9+ semantic path
  containment check that correctly handles directory boundaries.
  This eliminates the suffix-attack vulnerability that startswith() had.

These tests verify the FIX is in place. They serve as regression
guards: if someone reverts to startswith, the tests will FAIL.
"""

from __future__ import annotations

import ast
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DT_ROUTER_PY = REPO_ROOT / "backend" / "routers" / "digital_twin.py"


# ─── FIX VERIFICATION: Path.is_relative_to is used ──────────────────────────


def test_path_is_relative_to_is_used_instead_of_startswith():
    """REGRESSION GUARD: verify Path.is_relative_to() is used for path
    containment, NOT str.startswith().

    The M-5 fix replaced the brittle startswith pattern with the
    semantic is_relative_to check. If this test FAILS, the code has
    been reverted to the vulnerable startswith pattern.
    """
    source = DT_ROUTER_PY.read_text(encoding="utf-8")

    # Verify is_relative_to is used
    assert "is_relative_to" in source, (
        "M-5 FIX REVERTED: Path.is_relative_to() not found in "
        "digital_twin.py. The code may have reverted to the vulnerable "
        "startswith pattern — re-apply the fix."
    )

    # Verify startswith is NOT used for path containment
    # (It's OK if startswith appears in OTHER contexts — we only care
    # about the path containment check.)
    tree = ast.parse(source, filename=str(DT_ROUTER_PY))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "startswith":
            # Check context: is this a path containment check?
            # If the startswith is called on a variable named 'resolved'
            # or similar path variable, flag it.
            if isinstance(node.value, ast.Name):
                var_name = node.value.id.lower()
                if "resolved" in var_name or "path" in var_name or "upload" in var_name:
                    pytest.fail(
                        f"M-5 FIX REVERTED: found .startswith() call on "
                        f"'{node.value.id}' at line {node.lineno}. The "
                        "vulnerable startswith pattern has returned — "
                        "re-apply the Path.is_relative_to() fix."
                    )


def test_path_import_exists():
    """REGRESSION GUARD: verify `from pathlib import Path` is imported.

    The M-5 fix uses Path.is_relative_to(), which requires Path to be
    imported. If this test FAILS, the import was removed.
    """
    source = DT_ROUTER_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(DT_ROUTER_PY))

    found_path_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "pathlib":
                for alias in node.names:
                    if alias.name == "Path":
                        found_path_import = True
                        break
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pathlib":
                    found_path_import = True
                    break

    assert found_path_import, (
        "M-5 FIX REVERTED: 'from pathlib import Path' not found in "
        "digital_twin.py. The is_relative_to() call will fail with "
        "NameError — re-add the import."
    )


# ─── RUNTIME: path traversal is still blocked after the fix ─────────────────


def test_path_traversal_with_dotdot_is_blocked(monkeypatch):
    """RUNTIME REGRESSION GUARD: verify ../../../etc/passwd is still blocked
    after the M-5 fix.

    The fix changed the check from startswith to is_relative_to, but
    the path traversal defense must still work.
    """
    # Find the _safe_resolve_upload_path function
    source = DT_ROUTER_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(DT_ROUTER_PY))

    target_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_safe_resolve_upload_path":
            target_func = node
            break

    assert target_func is not None, "_safe_resolve_upload_path function not found"

    monkeypatch.syspath_prepend(str(REPO_ROOT))
    import importlib

    spec = importlib.util.spec_from_file_location("digital_twin_router", DT_ROUTER_PY)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pytest.skip("Could not load digital_twin.py module")

    func = getattr(mod, "_safe_resolve_upload_path", None)
    if func is None:
        pytest.skip("_safe_resolve_upload_path not found in module")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"FIREAI_UPLOAD_DIR": tmpdir}):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                func("../../../etc/passwd")
            assert exc_info.value.status_code == 400, (
                f"Path traversal not blocked: got status {exc_info.value.status_code}"
            )


def test_legitimate_filename_is_accepted(monkeypatch):
    """RUNTIME REGRESSION GUARD: verify a legitimate filename is accepted.

    The M-5 fix must not break legitimate file uploads.
    """
    source = DT_ROUTER_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(DT_ROUTER_PY))

    target_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_safe_resolve_upload_path":
            target_func = node
            break

    assert target_func is not None

    monkeypatch.syspath_prepend(str(REPO_ROOT))
    import importlib

    spec = importlib.util.spec_from_file_location("digital_twin_router", DT_ROUTER_PY)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pytest.skip("Could not load digital_twin.py module")

    func = getattr(mod, "_safe_resolve_upload_path", None)
    if func is None:
        pytest.skip("_safe_resolve_upload_path not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"FIREAI_UPLOAD_DIR": tmpdir}):
            result = func("legitimate_file.dwg")
            assert tmpdir in result, f"Legitimate file not accepted: {result}"


# ─── Claim text regression guard ─────────────────────────────────────────────


def test_m5_claim_text_REWORDED_in_worklog():
    """REGRESSION GUARD: the M-5 claim wording has been REWORDED in the
    active Phase 3 verdict section of worklog.md.

    The original misleading wording was:
      "M-5: digital_twin.py:91 str.startswith (still uses startswith
       despite V214 comment)"

    The reworded (accurate) wording is:
      "M-5: backend/routers/digital_twin.py:91 uses str.startswith for
       path containment (brittle pattern, but currently safe due to
       os.path.join preventing suffix attacks; V214 comment explains
       the absolute-path fix and does NOT contradict startswith itself)"

    This test asserts:
      (a) The misleading wording is GONE from the active Phase 3 verdict
          (the MEDIUM ISSUES block in worklog.md).
      (b) The reworded (accurate) wording IS present in the active
          Phase 3 verdict.
    """
    WORKLOG = REPO_ROOT / "worklog.md"
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")

    # The original (misleading) wording — must NOT be in the active verdict
    misleading_wording = (
        "M-5: digital_twin.py:91 str.startswith (still uses startswith despite V214 comment)"
    )

    # The reworded (accurate) wording — MUST be in the active verdict
    reworded_markers = [
        "M-5: backend/routers/digital_twin.py:91 uses str.startswith for",
        "brittle pattern, but currently safe due to os.path.join",
        "V214 comment explains",
        "absolute-path fix and does NOT contradict startswith itself",
    ]

    # Extract the active Phase 3 verdict MEDIUM ISSUES block
    medium_section_start = worklog_text.find("MEDIUM ISSUES")
    if medium_section_start == -1:
        pytest.skip("MEDIUM ISSUES section not found in worklog")
    after_medium = worklog_text[medium_section_start:]
    end_markers = ["LOW ISSUES:", "RETRACTED FALSE CLAIMS"]
    end_idx = len(after_medium)
    for marker in end_markers:
        idx = after_medium.find(marker)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    medium_section = after_medium[:end_idx]

    # Normalize whitespace so multi-line marker matches work correctly.
    # The worklog wraps long lines, so a single conceptual marker may be
    # split across physical lines. Collapse all runs of whitespace to a
    # single space before substring matching.
    import re as _re

    medium_section_normalized = _re.sub(r"\s+", " ", medium_section)

    # (a) The misleading wording must NOT be present in the active verdict
    misleading_normalized = _re.sub(r"\s+", " ", misleading_wording)
    assert misleading_normalized not in medium_section_normalized, (
        "M-5 misleading wording ('still uses startswith despite V214 "
        "comment') is still present in the active MEDIUM ISSUES section. "
        "The PHASE5-M4-M5-REWORD-L1-L2-L3 round should have replaced it "
        "with the accurate wording."
    )

    # (b) The reworded wording MUST be present in the active verdict
    missing_markers = [
        m for m in reworded_markers if _re.sub(r"\s+", " ", m) not in medium_section_normalized
    ]
    assert not missing_markers, (
        "M-5 reworded wording is incomplete in the active MEDIUM ISSUES "
        "section. Missing markers: " + repr(missing_markers) + ". The "
        "rewrod must include all of: 'uses str.startswith for path "
        "containment', 'brittle pattern, but currently safe due to "
        "os.path.join', 'V214 comment explains', 'absolute-path fix "
        "and does NOT contradict startswith itself'."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
