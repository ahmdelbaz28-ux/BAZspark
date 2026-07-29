"""Phase 5 — M-6 (AuthContext logout) FIX VERIFICATION.

ORIGINAL CLAIM (from Phase 3 verdict, now RESOLVED):
  "M-6: AuthContext.tsx logout clears only specific localStorage keys"

FIXES APPLIED (this round):
  Extended the logout function to clear ALL app-set localStorage keys:
    - nexus_project_state (was already cleared)
    - cad_settings (was already cleared)
    - digital_twin_settings (NEW — was leaking)
    - fireai_firealarm_detectors (NEW — was leaking)
    - nexus_imported_dxf (NEW — was leaking)
    - onboarding-completed (NEW — was leaking)
    - fireai_settings_* (NEW — dynamic keys, now cleared via prefix scan)

  The "dark" (theme) key is intentionally NOT cleared — it's a UI
  preference, not user-specific data.

These tests verify the FIX is in place. They serve as regression
guards: if someone reverts to clearing only specific keys, the tests
will FAIL.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AUTH_CONTEXT_TSX = REPO_ROOT / "frontend" / "src" / "contexts" / "AuthContext.tsx"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


# ─── FIX VERIFICATION: logout clears all app-set keys ───────────────────────


def test_logout_clears_all_app_set_localStorage_keys():
    """REGRESSION GUARD: verify logout clears ALL app-set localStorage keys.

    The M-6 fix extended logout to clear every key that the app sets
    via localStorage.setItem. This test:
      1. Scans frontend/src for all localStorage.setItem("key", ...) calls
      2. Extracts the set of keys
      3. Verifies logout has a localStorage.removeItem("key") for each
         (OR a prefix-based scan for dynamic keys like fireai_settings_*)

    If this test FAILS, some keys are no longer cleared — the leak has
    returned. Re-apply the fix.
    """
    # Step 1: Find all keys set by the frontend
    set_item_pattern = r'localStorage\.setItem\s*\(\s*["\']([^"\']+)["\']'
    keys_set: set[str] = set()

    for ts_file in FRONTEND_SRC.rglob("*.ts*"):
        if "node_modules" in str(ts_file):
            continue
        try:
            content = ts_file.read_text(encoding="utf-8")
        except Exception:
            continue
        keys_set.update(re.findall(set_item_pattern, content))

    # Also handle multi-line setItem calls (key on next line)
    multiline_pattern = r'localStorage\.setItem\s*\(\s*\n\s*["\']([^"\']+)["\']'
    for ts_file in FRONTEND_SRC.rglob("*.ts*"):
        if "node_modules" in str(ts_file):
            continue
        try:
            content = ts_file.read_text(encoding="utf-8")
        except Exception:
            continue
        keys_set.update(re.findall(multiline_pattern, content))

    # Exclude the "dark" key (UI theme preference, intentionally not cleared)
    keys_set.discard("dark")

    # Step 2: Read the logout function from AuthContext.tsx
    auth_source = AUTH_CONTEXT_TSX.read_text(encoding="utf-8")
    logout_pattern = r"const\s+logout\s*=\s*useCallback\s*\(\s*async\s*\(\s*\)\s*=>\s*\{(.+?)\},\s*\[\]\s*\)"
    m = re.search(logout_pattern, auth_source, re.DOTALL)
    assert m, "Could not find logout function in AuthContext.tsx"
    logout_body = m.group(1)

    # Step 3: For each key, verify it's cleared
    # Static keys: localStorage.removeItem("key")
    remove_item_pattern = r'localStorage\.removeItem\s*\(\s*["\']([^"\']+)["\']\s*\)'
    cleared_keys: set[str] = set(re.findall(remove_item_pattern, logout_body))

    # Dynamic keys (fireai_settings_*): handled by prefix scan
    has_prefix_scan = "fireai_settings_" in logout_body and "startsWith" in logout_body

    uncleared_keys: list[str] = []
    for key in keys_set:
        if key in cleared_keys:
            continue
        # Check if this is a dynamic key handled by prefix scan
        if key.startswith("fireai_settings_") and has_prefix_scan:
            continue
        # This key is NOT cleared
        uncleared_keys.append(key)

    assert not uncleared_keys, (
        "M-6 FIX REVERTED: the following localStorage keys are set by "
        "the frontend but NOT cleared by logout:\n  "
        + "\n  ".join(sorted(uncleared_keys))
        + "\nRe-apply the M-6 fix to clear all app-set keys on logout."
    )


def test_logout_does_not_use_localStorage_clear():
    """REGRESSION GUARD: logout must NOT use localStorage.clear().

    localStorage.clear() would remove ALL keys including those set by
    other apps on the same origin. The M-6 fix uses targeted
    removeItem() calls instead.

    If this test FAILS, someone replaced the targeted removals with
    localStorage.clear() — which is overly aggressive.
    """
    source = AUTH_CONTEXT_TSX.read_text(encoding="utf-8")
    assert "localStorage.clear()" not in source, (
        "M-6 REGRESSION: AuthContext.tsx now uses localStorage.clear() "
        "which removes ALL keys including those from other apps. Use "
        "targeted removeItem() calls instead."
    )


# ─── Claim text regression guard ─────────────────────────────────────────────


def test_m6_claim_text_exists_in_worklog():
    """REGRESSION GUARD: the M-6 claim text must exist in worklog.md."""
    WORKLOG = Path("/home/z/my-project/worklog.md")
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")
    expected_substring = (
        "M-6: AuthContext.tsx logout clears only specific localStorage keys"
    )

    assert expected_substring in worklog_text, (
        "M-6 claim text removed from worklog.md."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
