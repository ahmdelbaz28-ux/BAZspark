"""Phase 5 — Strict verification of the L-2 (qomn_kernel.py stale comment) claim.

CLAIM UNDER TEST (from worklog.md, Phase 3 verdict, LOW ISSUES section):
  Original wording (HISTORICAL):
    "L-2: qomn_kernel.py stale comment defending old 0.0 behavior"
  Current wording (after L-2 FIX round):
    "L-2: qomn_kernel.py stale comment defending old 0.0 behavior — RESOLVED.
     The comment block at lines 1061-1085 was updated to say '72 Ah'
     (matching the actual `safe_minimum=72.0` in battery_capacity) and
     a NOTE was added explaining the historical 0 Ah → 72 Ah change.
     The stale '0 Ah' wording is gone."

WHAT WE VERIFY (post-fix regression guards):
  1. The file exists at the expected path.
  2. The comment block NOW says "72 Ah" (the fix).
  3. The comment STILL contains defensive language ("intentional",
     "do NOT change the default behaviour", etc.) — the FIX preserved
     the design rationale, only updated the value.
  4. The actual code STILL uses 72.0 Ah (regression guard — if the
     code is reverted to 0 Ah, the comment would be accurate again
     and the staleness would be gone, but the safety regression
     would be critical).
  5. The comment AND the code are in the same file.
  6. The comment block is still substantial (≥5 lines).
  7. The OLD "0 Ah" wording is GONE from the active comment block
     (post-fix guard — if someone re-adds "0 Ah" to the comment,
     this test FAILS).
  8. The L-2 claim text in worklog.md reflects the RESOLVED state.
  9. The comment EXPLAINS the historical 0→72 change (the FIX
     requires a NOTE explaining why the value changed).

NON-VACUOUSNESS:
  Each test below is proven to fail when its assertion is violated.
  Verified by /home/z/my-project/scripts/verify_l1_l2_l3_post_fix_nonvacuous.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
QOMN_KERNEL_PY = REPO_ROOT / "fireai" / "core" / "qomn_kernel.py"


# ─── L-2 part (a): file exists ──────────────────────────────────────────────


def test_l2_qomn_kernel_file_exists():
    """REGRESSION GUARD: qomn_kernel.py must exist at the expected path."""
    assert QOMN_KERNEL_PY.exists(), (
        f"qomn_kernel.py not found at {QOMN_KERNEL_PY}. The L-2 claim "
        "references this file — if it has been moved, update the claim "
        "and the test path."
    )


def _get_c01_comment_block(source: str) -> str:
    """Extract the C-01 FIX comment block from qomn_kernel.py.

    The block structure is:
      # ═══...═══       <- start delimiter
      # C-01 FIX (Engineering Review): QOMNCalculationError  <- header
      # ═══...═══       <- inner delimiter (after header)
      # The engineering review flagged...
      # ... (body)
      # ═══...═══       <- end delimiter

    Returns the block text (from start delimiter to end delimiter,
    inclusive) or empty string if not found.
    """
    lines = source.split('\n')
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r'C-01\s+FIX.*QOMNCalculationError', line):
            header_idx = i
            break
    if header_idx is None:
        return ""

    # Walk backward to find the start delimiter (the `# ═══...` line
    # directly above the header).
    start_idx = header_idx
    while start_idx > 0 and re.match(r'^#\s*═{5,}', lines[start_idx - 1]):
        # Found the start delimiter
        start_idx -= 1
        break  # only walk one line back to the delimiter

    # If the line above the header is NOT a delimiter, the block starts
    # at the header line itself.
    if start_idx == header_idx:
        start_idx = header_idx

    # Walk forward to find the END delimiter. The block has an inner
    # delimiter right after the header (line header_idx+1 if it's a
    # `# ═══...` line). The END delimiter is the LAST `# ═══...` line
    # before a non-comment line.
    end_idx = header_idx
    for i in range(header_idx + 1, len(lines)):
        if re.match(r'^#\s*═{5,}', lines[i]):
            end_idx = i  # tentative end — keep going in case there are more
        elif lines[i].lstrip().startswith('#'):
            # Comment line (but not a delimiter) — body continues
            continue
        else:
            # Non-comment line — block has ended
            break

    return '\n'.join(lines[start_idx:end_idx + 1])


# ─── L-2 part (b): the comment NOW says "72 Ah" (post-fix) ──────────────────


def test_l2_comment_now_says_72_ah():
    """REGRESSION GUARD (post-fix): the C-01 FIX comment block must NOW
    mention "72 Ah" (the actual fallback value), not "0 Ah".

    This is the SUBSTANCE of the L-2 FIX: the comment was updated to
    match the code. If someone reverts the comment to "0 Ah", this
    test FAILS.
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")
    comment_block = _get_c01_comment_block(source)
    assert comment_block, (
        "Could not find the C-01 FIX comment block. The block is "
        "delimited by `# ═══...═══` lines and starts with "
        "`# C-01 FIX (Engineering Review): QOMNCalculationError`. "
        "If the comment structure has changed, update this test."
    )

    # The comment must mention 72 Ah (the actual code value).
    has_72_ah = bool(re.search(r'72\s*Ah', comment_block))
    assert has_72_ah, (
        "The C-01 FIX comment block does not mention '72 Ah'. The L-2 "
        "fix requires the comment to match the actual code (which uses "
        "safe_minimum=72.0). RESTORE the L-2 fix."
    )


# ─── L-2 part (c): the comment STILL defends the conservative fallback ──────


def test_l2_comment_still_defends_conservative_fallback():
    """REGRESSION GUARD (post-fix): the comment must STILL contain
    defensive language explaining why the conservative fallback is
    intentional.

    The L-2 fix only updated the VALUE (0 → 72), not the rationale.
    The design rationale (force manual intervention, conservative
    fallback, legitimate design choice) must be preserved.
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")
    comment_block = _get_c01_comment_block(source)
    assert comment_block, "C-01 FIX comment block not found"

    defensive_patterns = [
        r"intentional",
        r"do\s+NOT\s+change\s+the\s+default\s+behavi[ou]r",
        r"conservative\s+fallback",
        r"force\s+manual\s+intervention",
        r"legitimate\s+design\s+choice",
    ]
    matched = [p for p in defensive_patterns
               if re.search(p, comment_block, re.IGNORECASE)]
    assert matched, (
        "The defensive language has been REMOVED from the C-01 FIX "
        "comment block. The L-2 fix preserved the rationale — only "
        "the value (0 → 72) was updated. RESTORE the defensive language."
    )


# ─── L-2 part (d): the actual code STILL uses 72.0 Ah (regression guard) ────


def test_l2_actual_code_still_uses_72_ah():
    """REGRESSION GUARD (post-fix): the actual battery_capacity fallback
    must STILL use 72.0 Ah.

    This is a regression guard for the SAFETY-CRITICAL value. If someone
    reverts the code back to 0 Ah, the comment would technically become
    "accurate" (no longer stale) — but the safety regression would be
    CRITICAL (0 Ah battery fallback means fire alarms may not work
    during a power outage). This test catches such a revert.
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")

    pattern = re.compile(
        r'@_healing_wrapper\s*\(\s*'
        r'safe_result\s*=\s*\{[^}]*?"required_ah"\s*:\s*'
        r'(\d+(?:\.\d+)?)',
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(source)
    assert m, (
        "Could not find a @_healing_wrapper decorator with a "
        "'required_ah' value. The structure of qomn_kernel.py may "
        "have changed — update this test."
    )
    value = float(m.group(1))
    assert value == 72.0, (
        f"The battery_capacity fallback is now {value} Ah (expected 72.0). "
        "If this was an intentional change, update the comment block to "
        "match. If this was a revert to 0 Ah, this is a CRITICAL SAFETY "
        "REGRESSION — battery fallback must be at least 72 Ah per "
        "NFPA 72-2022 §10.6.7.2.1."
    )


# ─── L-2 part (e): comment and code in same file (unchanged) ─────────────────


def test_l2_comment_and_code_in_same_file():
    """REGRESSION GUARD: the comment AND the contradicting code must
    both be in qomn_kernel.py.

    Post-fix: the comment now matches the code (both say 72 Ah), so
    they no longer contradict. But the test still verifies they're
    in the same file (the L-2 claim's reference to qomn_kernel.py
    remains accurate).
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")

    has_72_ah_comment = bool(re.search(r'72\s*Ah', source))
    has_72_ah_code = bool(re.search(r'"required_ah"\s*:\s*72', source))

    assert has_72_ah_comment, (
        "The '72 Ah' mention is not in qomn_kernel.py — the comment may "
        "have been moved to a different file. Update the L-2 claim."
    )
    assert has_72_ah_code, (
        "The 72.0 Ah fallback is not in qomn_kernel.py — the actual "
        "code may have been moved. Update the L-2 claim."
    )


# ─── L-2 part (f): the comment block is still substantial (≥5 lines) ─────────


def test_l2_comment_block_is_substantial():
    """REGRESSION GUARD: the C-01 FIX comment block must still be a
    SUBSTANTIAL block (≥5 lines), not just a one-line note.

    The L-2 fix EXPANDED the block to add the NOTE about the historical
    0→72 change. If someone "cleans up" the block to a one-liner, the
    rationale is lost.
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")
    comment_block = _get_c01_comment_block(source)
    assert comment_block, "C-01 FIX comment block not found"

    block_lines = [l for l in comment_block.split('\n') if l.strip()]
    assert len(block_lines) >= 5, (
        f"The C-01 FIX comment block is only {len(block_lines)} lines long. "
        "The L-2 audit found a substantial 20-line comment block defending "
        "the conservative fallback. If the block has been reduced to a "
        "one-liner, the rationale is lost — restore the substantial block."
    )


# ─── L-2 part (g): the OLD "0 Ah" wording is GONE from active comment (post-fix) ─


def test_l2_old_zero_ah_wording_is_REMOVED_from_active_comment():
    """REGRESSION GUARD (post-fix): the OLD "0 Ah" wording must NOT be
    in the active C-01 FIX comment block.

    The pre-fix comment said "battery=0 Ah". The post-fix comment says
    "battery=72 Ah". If someone reverts the comment to "0 Ah", this
    test FAILS.

    Note: the comment may MENTION the historical 0 Ah value in the
    NOTE explaining the 0→72 change (e.g., "raised from the historical
    0 Ah to 72 Ah"). Such a MENTION is allowed — what is forbidden is
    the ORIGINAL "battery=0 Ah" framing that describes the CURRENT
    behavior as 0 Ah.
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")
    comment_block = _get_c01_comment_block(source)
    assert comment_block, "C-01 FIX comment block not found"

    # The forbidden pattern: describing the CURRENT fallback as 0 Ah.
    # The expected post-fix wording is "battery=72 Ah" or "72 Ah".
    # A historical mention like "raised from 0 Ah to 72 Ah" is allowed.
    # The pattern looks for "battery=0 Ah" or "battery=0.0 Ah" (the
    # ORIGINAL stale wording).
    forbidden_patterns = [
        r'battery\s*=\s*0(\.0)?\s*Ah',
        r'fallbacks?\s*\(\s*battery\s*=\s*0(\.0)?\s*Ah',
    ]
    for p in forbidden_patterns:
        m = re.search(p, comment_block, re.IGNORECASE)
        assert not m, (
            f"The forbidden pattern {p!r} was found in the C-01 FIX "
            f"comment block: {m.group(0)!r}. The L-2 fix requires the "
            "comment to say '72 Ah' (the actual fallback value), not "
            "'0 Ah'. RESTORE the L-2 fix."
        )


# ─── L-2 part (h): the comment EXPLAINS the historical 0→72 change ──────────


def test_l2_comment_explains_historical_change():
    """REGRESSION GUARD (post-fix): the C-01 FIX comment block must
    include a NOTE explaining the historical 0 Ah → 72 Ah change.

    This is the SUBSTANCE of the L-2 fix beyond just updating the value:
    the comment now DOCUMENTS why the value was changed (so a future
    reader doesn't think "72 Ah" was always the value and gets confused
    by old commit messages or old test snapshots).

    If someone removes the NOTE, this test FAILS.
    """
    if not QOMN_KERNEL_PY.exists():
        pytest.skip("qomn_kernel.py not found")
    source = QOMN_KERNEL_PY.read_text(encoding="utf-8")
    comment_block = _get_c01_comment_block(source)
    assert comment_block, "C-01 FIX comment block not found"

    # The NOTE should mention "historical" or "raised from" or "0 Ah"
    # in the context of explaining the change. We look for any of:
    #   - "historical"
    #   - "raised from" + "0" + "72"
    #   - "0 Ah" + "72 Ah" in close proximity (the NOTE explains the change)
    has_explanation = (
        bool(re.search(r'historical', comment_block, re.IGNORECASE))
        or bool(re.search(r'raised\s+from\s+.*0\s*Ah.*72\s*Ah', comment_block,
                          re.IGNORECASE | re.DOTALL))
        or bool(re.search(r'0\s*Ah.*72\s*Ah|72\s*Ah.*0\s*Ah', comment_block,
                          re.IGNORECASE | re.DOTALL))
    )
    assert has_explanation, (
        "The C-01 FIX comment block does NOT include a NOTE explaining "
        "the historical 0 Ah → 72 Ah change. The L-2 fix requires this "
        "NOTE so future readers understand why the value changed. "
        "RESTORE the NOTE."
    )


# ─── L-2 part (i): the claim text in worklog.md reflects RESOLVED state ─────


def test_l2_claim_text_reflects_resolved_state():
    """REGRESSION GUARD (post-fix): the L-2 claim text in worklog.md
    must reflect the RESOLVED state.

    The pre-fix claim was:
      "L-2: qomn_kernel.py stale comment defending old 0.0 behavior"

    The post-fix claim should include the markers:
      - "RESOLVED" or "FIXED"
      - "72 Ah" (the new value)
      - "0 Ah" (the old value being replaced)
    """
    WORKLOG = REPO_ROOT / "worklog.md"
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

    # Extract the L-2 entry specifically (from "L-2:" up to "L-3:" or end).
    l2_match = re.search(r'L-2:.*?(?=\s*L-3:|$)', low_normalized, re.DOTALL)
    assert l2_match, (
        "L-2 entry missing from LOW ISSUES section. The LOW ISSUES "
        "section should contain entries L-1, L-2, L-3."
    )
    l2_entry = l2_match.group(0)

    assert ("RESOLVED" in l2_entry or "FIXED" in l2_entry), (
        "L-2 entry in LOW ISSUES does not mention RESOLVED or FIXED. "
        "The L-2 fix has been applied — update the worklog to reflect "
        "the RESOLVED state."
    )
    assert "72 Ah" in l2_entry, (
        "L-2 entry in LOW ISSUES does not mention '72 Ah' (the new "
        "value). Update the worklog claim wording."
    )
    assert "0 Ah" in l2_entry, (
        "L-2 entry in LOW ISSUES does not mention '0 Ah' (the old "
        "value being replaced). The RESOLVED wording should reference "
        "both the old and new values so future readers understand "
        "the fix."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
