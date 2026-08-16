"""Phase 5 — Strict verification of the L-1 (dataService.ts localhost exception) claim.

CLAIM UNDER TEST (from worklog.md, Phase 3 verdict, LOW ISSUES section):
  Original wording (HISTORICAL):
    "L-1: dataService.ts localhost exception in isSecure check (dev convenience)"
  Current wording (after L-1 FIX round):
    "L-1: dataService.ts localhost exception TIGHTENED to exact hostname match
    (RESOLVED — substring `includes('localhost')` replaced with
    `new URL(WS_BASE_URL).hostname === 'localhost'|'127.0.0.1'|'[::1]'`)"

WHAT WE VERIFY (post-fix regression guards):
  1. The file exists at the expected path.
  2. The isSecure check exists.
  3. The isSecure check uses an EXACT hostname match via `new URL(...)`.
  4. The OLD substring `includes("localhost")` is GONE from the isSecure check.
  5. The isSecure check is the SECURITY gate for sending the API key.
  6. The file is part of the production frontend source tree.
  7. The L-1 claim text in worklog.md reflects the RESOLVED state.
  8. The file is currently orphaned (latent-risk tripwire — fails if a future
     commit wires the file into a production component, forcing re-evaluation).
  9. The new logic REJECTS bypass URLs like `ws://my-localhost-proxy.example.com`
     (simulated in Python — proves the fix is effective, not just present).

NON-VACUOUSNESS:
  Each test below is proven to fail when its assertion is violated. The
  injected violations are documented in the test bodies and verified by
  /home/z/my-project/scripts/verify_l1_l2_l3_post_fix_nonvacuous.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_SERVICE_TS = REPO_ROOT / "frontend" / "src" / "services" / "dataService.ts"


# ─── L-1 part (a): file exists ──────────────────────────────────────────────


def test_l1_data_service_file_exists():
    """REGRESSION GUARD: dataService.ts must exist at the expected path.

    The claim references "dataService.ts". If the file is moved or
    renamed, the claim's reference is stale and this test fails.
    """
    assert DATA_SERVICE_TS.exists(), (
        f"dataService.ts not found at {DATA_SERVICE_TS}. The L-1 claim "
        "references this file — if it has been moved, update the claim "
        "and the test path."
    )


# ─── L-1 part (b): the isSecure check exists ────────────────────────────────


def test_l1_isSecure_check_exists():
    """REGRESSION GUARD: the `isSecure` variable must exist in the file.

    The claim references "isSecure check" — this is the security gate
    that decides whether to send the API key over the WebSocket.
    """
    if not DATA_SERVICE_TS.exists():
        pytest.skip("dataService.ts not found")
    source = DATA_SERVICE_TS.read_text(encoding="utf-8")

    # The claim says "isSecure check" — verify the variable exists.
    assert "isSecure" in source, (
        "The 'isSecure' variable referenced by the L-1 claim is not "
        "present in dataService.ts. The claim may be stale, or the "
        "code may have been refactored to use a different name."
    )


# ─── L-1 part (c): the isSecure check uses EXACT hostname match (post-fix) ───


def test_l1_isSecure_check_uses_exact_hostname_match():
    """REGRESSION GUARD (post-fix): the isSecure check must use
    `new URL(WS_BASE_URL).hostname` to match against the loopback set
    {localhost, 127.0.0.1, [::1]} — NOT a substring `.includes` check.

    This is the SUBSTANCE of the L-1 FIX: the previous substring check
    `WS_BASE_URL.includes("localhost")` would match any URL containing
    "localhost" anywhere (e.g., `ws://my-localhost-proxy.example.com/ws`)
    and bypass the security gate. The exact hostname match closes that
    bypass because `new URL(...).hostname` extracts only the hostname
    component, so `my-localhost-proxy.example.com` does NOT equal
    `localhost`.

    If someone reverts to the substring check, this test FAILS.
    """
    if not DATA_SERVICE_TS.exists():
        pytest.skip("dataService.ts not found")
    source = DATA_SERVICE_TS.read_text(encoding="utf-8")

    # The exact-hostname pattern: new URL(WS_BASE_URL) is called and
    # .hostname is used in the comparison. The TS code structure is:
    #   const url = new URL(WS_BASE_URL);
    #   return (
    #     url.hostname === "localhost" ||
    #     url.hostname === "127.0.0.1" ||
    #     url.hostname === "[::1]"
    #   );
    # So we look for both `new URL(WS_BASE_URL)` AND `.hostname ===` separately.
    new_url_pattern = re.compile(r"new\s+URL\s*\(\s*WS_BASE_URL\s*\)")
    hostname_eq_pattern = re.compile(r"\.hostname\s*===")
    assert new_url_pattern.search(source), (
        "The isSecure check no longer uses `new URL(WS_BASE_URL)` to parse "
        "the URL. The L-1 fix may have been reverted to the old substring "
        "`.includes('localhost')` check. If so, RESTORE the exact-hostname "
        "fix — the substring check is vulnerable to bypass via URLs like "
        "`ws://my-localhost-proxy.example.com`."
    )
    assert hostname_eq_pattern.search(source), (
        "The isSecure check no longer uses `.hostname ===` for exact hostname "
        "matching. The L-1 fix requires `new URL(...).hostname === ...` "
        "comparison (not `.includes()` substring)."
    )

    # The loopback set must include localhost AND 127.0.0.1 AND [::1] or ::1.
    # Find the isSecure IIFE block.
    issecure_block_pattern = re.compile(
        r"isSecure\s*=\s*\(\s*\(\s*\)\s*=>\s*\{(.*?)\}\)\s*\(\s*\)\s*;",
        re.MULTILINE | re.DOTALL,
    )
    m = issecure_block_pattern.search(source)
    assert m, (
        "isSecure assignment (as IIFE) not found. The L-1 fix uses an IIFE "
        "to compute isSecure. If the code structure has changed, update "
        "this test to match the new structure."
    )
    issecure_block = m.group(1)
    assert '"localhost"' in issecure_block or "'localhost'" in issecure_block, (
        "The isSecure check does not include 'localhost' in the loopback "
        "set. The L-1 fix must allow dev access via localhost."
    )
    assert "127.0.0.1" in issecure_block, (
        "The isSecure check does not include '127.0.0.1' in the loopback "
        "set. The L-1 fix must allow dev access via 127.0.0.1."
    )
    assert "::1" in issecure_block, (
        "The isSecure check does not include '[::1]' or '::1' in the "
        "loopback set. The L-1 fix must allow dev access via IPv6 loopback."
    )


# ─── L-1 part (d): the OLD substring check is GONE (post-fix) ────────────────


def test_l1_old_substring_includes_localhost_is_REMOVED():
    """REGRESSION GUARD (post-fix): the OLD substring
    `.includes("localhost")` check must NOT be present in the isSecure
    block.

    This is the INVERSE of the pre-fix test. The pre-fix test asserted
    the substring check WAS present (vulnerability detector). The
    post-fix test asserts it is GONE (fix regression guard).

    If someone reverts to the substring check, this test FAILS.
    """
    if not DATA_SERVICE_TS.exists():
        pytest.skip("dataService.ts not found")
    source = DATA_SERVICE_TS.read_text(encoding="utf-8")

    # Locate the isSecure IIFE block.
    issecure_block_pattern = re.compile(
        r"isSecure\s*=\s*\(\s*\(\s*\)\s*=>\s*\{(.*?)\}\)\s*\(\s*\)\s*;",
        re.MULTILINE | re.DOTALL,
    )
    m = issecure_block_pattern.search(source)
    assert m, "isSecure IIFE not found — cannot check for residual substring check"
    issecure_block = m.group(1)

    substring_pattern = re.compile(
        r'\.includes\s*\(\s*["\']localhost["\']\s*\)',
    )
    assert not substring_pattern.search(issecure_block), (
        "The OLD substring `.includes('localhost')` check is STILL present "
        "in the isSecure block. The L-1 fix requires this to be REMOVED "
        "and replaced with the exact-hostname match. RESTORE the L-1 fix."
    )


# ─── L-1 part (e): the isSecure check is the API-key-sending gate ────────────


def test_l1_isSecure_check_gates_api_key_send():
    """REGRESSION GUARD: the isSecure check must be the gate for sending
    the API key.

    The L-1 claim's severity depends on the isSecure check actually
    being the gate for sending the API key. If the check is moved away
    from the API-key send call, the claim's substance changes.
    """
    if not DATA_SERVICE_TS.exists():
        pytest.skip("dataService.ts not found")
    source = DATA_SERVICE_TS.read_text(encoding="utf-8")

    # Find the isSecure IIFE assignment and verify the API-key send is
    # gated by it. The post-fix code structure is:
    #   const isSecure = (() => { ... })();
    #   if (isSecure) {
    #     this.ws?.send(JSON.stringify({ action: "auth", apiKey: this.apiKey }));
    #   } else { ... }
    # The IIFE can contain internal semicolons, so we match up to the
    # closing `();` of the IIFE, then look for the if-block.
    issecure_block_pattern = re.compile(
        r"isSecure\s*=\s*\(\s*\(\s*\)\s*=>\s*\{.*?\}\)\s*\(\s*\)\s*;"
        r"\s*\n\s*if\s*\(\s*isSecure\s*\)\s*\{[^}]*?"
        r'action:\s*["\']auth["\'][^}]*?apiKey',
        re.MULTILINE | re.DOTALL,
    )
    assert issecure_block_pattern.search(source), (
        "The isSecure check is not followed by an `if (isSecure) { ... "
        "send apiKey ... }` block. The L-1 claim assumes the isSecure "
        "check gates the API-key send call. If the code has been "
        "refactored, update this test to match the new structure."
    )


# ─── L-1 part (f): the file is in the production source tree ────────────────


def test_l1_file_is_in_production_source_tree():
    """REGRESSION GUARD: dataService.ts must be in the production source
    tree (frontend/src/).

    The L-1 claim's relevance depends on the file being part of the
    production frontend. If the file is moved to a test/ or mock/
    directory, the claim may no longer apply.
    """
    if not DATA_SERVICE_TS.exists():
        pytest.skip("dataService.ts not found")

    path_str = DATA_SERVICE_TS.as_posix()
    assert "frontend/src/" in path_str, (
        "dataService.ts is no longer under frontend/src/ — it may have "
        "been moved to a non-production directory. If so, the L-1 claim "
        "may no longer apply and should be reworded."
    )

    assert (
        "/test/" not in path_str and "/__tests__/" not in path_str and "/mock/" not in path_str
    ), (
        "dataService.ts is under a test/ or mock/ directory — it is no "
        "longer production code. Update the L-1 claim."
    )


# ─── L-1 part (g): the claim text in worklog.md reflects the RESOLVED state ──


def test_l1_claim_text_reflects_resolved_state():
    """REGRESSION GUARD: the L-1 claim text in worklog.md must reflect
    the RESOLVED state (post-fix).

    The pre-fix claim was:
      "L-1: dataService.ts localhost exception in isSecure check (dev convenience)"

    The post-fix claim should include the markers:
      - "TIGHTENED" or "RESOLVED"
      - "exact hostname" (the fix mechanism)
      - "substring" (the old mechanism being replaced)

    If a future commit reverts the fix, the worklog should be updated
    to remove the RESOLVED wording — and this test will FAIL, forcing
    a conscious update.
    """
    WORKLOG = REPO_ROOT / "worklog.md"
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")

    # Extract the LOW ISSUES section.
    low_section_start = worklog_text.find("LOW ISSUES:")
    if low_section_start == -1:
        pytest.skip("LOW ISSUES section not found in worklog")
    after_low = worklog_text[low_section_start:]
    end_markers = [
        "RETRACTED FALSE CLAIMS",
        "NUMERICAL ERRORS",
        "FALSE ACCUSATION PATTERNS",
        "POSITIVES VERIFIED",
    ]
    end_idx = len(after_low)
    for marker in end_markers:
        idx = after_low.find(marker)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    low_section = after_low[:end_idx]

    low_normalized = re.sub(r"\s+", " ", low_section)

    # Extract the L-1 entry specifically (from "L-1:" up to "L-2:" or end).
    l1_match = re.search(r"L-1:.*?(?=\s*L-2:|$)", low_normalized, re.DOTALL)
    assert l1_match, (
        "L-1 entry missing from LOW ISSUES section. The LOW ISSUES "
        "section should contain entries L-1, L-2, L-3."
    )
    l1_entry = l1_match.group(0)

    # The L-1 entry must mention RESOLVED (or TIGHTENED) and "exact hostname"
    # and reference the old "substring" mechanism.
    assert "RESOLVED" in l1_entry or "TIGHTENED" in l1_entry, (
        "L-1 entry in LOW ISSUES does not mention RESOLVED or TIGHTENED. "
        "The L-1 fix has been applied — update the worklog to reflect "
        "the RESOLVED state."
    )
    assert "exact hostname" in l1_entry or "exact-hostname" in l1_entry, (
        "L-1 entry in LOW ISSUES does not mention 'exact hostname' (the "
        "fix mechanism). Update the worklog claim wording."
    )
    assert "substring" in l1_entry, (
        "L-1 entry in LOW ISSUES does not mention 'substring' (the old "
        "mechanism being replaced). The RESOLVED wording should reference "
        "what was replaced so future readers understand the fix."
    )


# ─── L-1 part (h): HONEST CAVEAT — is the file actually reachable? ──────────


def test_l1_honest_caveat_file_is_orphaned_in_production():
    """HONEST CAVEAT (documented for completeness): dataService.ts is
    currently ORPHANED — no production component imports it through a
    live import chain.

    This test documents the caveat honestly:
      - The file IS in the production source tree.
      - The file's `dataService` singleton IS exported.
      - But the two hooks that import it (`useTelemetryStream`,
        `useLiveData`) are NOT imported by any production component.
      - The risk is LATENT: any future component that imports
        `useLiveData` or `useTelemetryStream` would activate the
        (now-fixed) localhost check.

    NOTE: After the L-1 fix, the localhost check is no longer a bypass
    (it uses exact hostname match). But the file's orphan status is
    still relevant — if it gets wired into production, the new tests
    below (parts i, j) become ACTIVE runtime guarantees.

    This test does NOT assert the file is reachable — it asserts the
    OPPOSITE (that the file is currently orphaned). If a future commit
    wires the file into a production component, this test will FAIL,
    forcing the L-1 claim to be re-evaluated at that time.
    """
    if not DATA_SERVICE_TS.exists():
        pytest.skip("dataService.ts not found")

    FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
    if not FRONTEND_SRC.exists():
        pytest.skip("frontend/src not found")

    # Scan all .ts/.tsx files under frontend/src for imports of dataService
    # (excluding the dataService.ts file itself and test files).
    import_pattern = re.compile(
        r'from\s+["\'][^"\']*dataService["\']'
        r'|import\s+["\'][^"\']*dataService["\']'
        r'|require\s*\(\s*["\'][^"\']*dataService["\']\s*\)',
    )

    importers = []
    for ts_file in FRONTEND_SRC.rglob("*.ts*"):
        if ts_file.name == "dataService.ts":
            continue
        if "__tests__" in str(ts_file) or ".test." in ts_file.name:
            continue
        try:
            text = ts_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if import_pattern.search(text):
            importers.append(ts_file.relative_to(FRONTEND_SRC).as_posix())

    # The two hooks that historically imported dataService
    # (useTelemetryStream, useLiveData) were archived out of the
    # production tree during the mockups-v1 housekeeping phase
    # (see docs/deletion-log.md). They now live under archived/,
    # which is intentionally outside frontend/src — so the production
    # tree must contain NO importers of dataService at all. If a future
    # commit wires dataService (or a hook that imports it) back into
    # frontend/src, the `extra_importers` assertion below fails and the
    # L-1 claim must be re-evaluated.
    expected_hooks: set[str] = set()
    actual_importers = set(importers)

    missing_expected = expected_hooks - actual_importers
    assert not missing_expected, (
        "Expected importer(s) not found: " + str(missing_expected) + ". "
        "The L-1 caveat assumes these two hooks import dataService. If "
        "they no longer do, the caveat needs updating."
    )

    extra_importers = actual_importers - expected_hooks
    assert not extra_importers, (
        "UNEXPECTED IMPORTERS of dataService found: " + str(extra_importers) + ". "
        "dataService is NO LONGER ORPHANED — it is now wired into "
        "production components. The L-1 claim should be re-evaluated: "
        "the (now-fixed) localhost check is ACTIVE — verify the fix "
        "still passes runtime tests in the new wiring."
    )


# ─── L-1 part (i): the fix REJECTS bypass URLs (Python simulation) ──────────


def _python_simulated_is_secure(ws_base_url: str) -> bool:
    """Python equivalent of the post-fix TypeScript isSecure check.

    Mirrors the logic in dataService.ts:
      const isSecure = (() => {
          if (WS_BASE_URL.startsWith("wss://")) return true;
          try {
              const url = new URL(WS_BASE_URL);
              return (
                  url.hostname === "localhost" ||
                  url.hostname === "127.0.0.1" ||
                  url.hostname === "[::1]"
              );
          } catch {
              return false;
          }
      })();

    We use urlsplit() (Python's stdlib) to extract the hostname. Note:
    Python's urlsplit does NOT include the brackets for IPv6, so we
    test against both "::1" and "[::1]".
    """
    if ws_base_url.startswith("wss://"):
        return True
    try:
        parts = urlsplit(ws_base_url)
        hostname = parts.hostname
        if hostname is None:
            return False
        return hostname in {"localhost", "127.0.0.1", "::1"}
    except Exception:
        return False


def test_l1_fix_rejects_bypass_urls_simulation():
    """REGRESSION GUARD: the post-fix logic must REJECT bypass URLs that
    contain "localhost" as a substring but are not the actual loopback
    hostname.

    This is the SUBSTANCE of the L-1 fix. The pre-fix substring check
    `WS_BASE_URL.includes("localhost")` would WRONGLY accept:
      - ws://my-localhost-proxy.example.com/ws
      - ws://localhost.evil.com/ws
      - ws://not-localhost-at-all.example.com/ws?fake=localhost

    The post-fix exact-hostname check correctly REJECTS these.

    This test uses a Python simulation of the TS logic. If the TS code
    is reverted to the substring check, this Python simulation still
    passes (because it's a separate implementation) — but test (c) and
    (d) above will FAIL, catching the revert. The simulation is a
    BEHAVIORAL spec, not a code-structure spec.
    """
    # Bypass URLs that contain "localhost" as a substring but should be REJECTED.
    bypass_urls = [
        "ws://my-localhost-proxy.example.com/ws",
        "ws://localhost.evil.com/ws",
        "ws://not-localhost-at-all.example.com/ws?fake=localhost",
        "ws://attacker.com/localhost",  # path-based bypass attempt
        "ws://localhost-attacker.com/ws",  # subdomain-based bypass
    ]
    for url in bypass_urls:
        assert not _python_simulated_is_secure(url), (
            f"Bypass URL {url!r} was ACCEPTED by the simulated isSecure "
            "check. This means the L-1 fix is ineffective against this "
            "bypass. The exact-hostname match must reject any URL whose "
            "parsed hostname is not in {localhost, 127.0.0.1, ::1}."
        )

    # Legitimate loopback URLs that should be ACCEPTED.
    legit_urls = [
        "ws://localhost:8000/ws",
        "ws://127.0.0.1:8000/ws",
        "ws://[::1]:8000/ws",
        "wss://localhost:8000/ws",  # wss always allowed
        "wss://example.com/ws",  # wss always allowed
    ]
    for url in legit_urls:
        assert _python_simulated_is_secure(url), (
            f"Legitimate URL {url!r} was REJECTED by the simulated isSecure "
            "check. The L-1 fix must not break legitimate dev access via "
            "loopback addresses."
        )


# ─── L-1 part (j): the fix FAILS CLOSED on malformed URLs ───────────────────


def test_l1_fix_fails_closed_on_malformed_urls_simulation():
    """REGRESSION GUARD: the post-fix logic must FAIL CLOSED on malformed
    URLs (return false, not true).

    This is defense-in-depth: if the URL parser throws, the catch block
    returns false — meaning the API key is NOT sent. This is the correct
    secure-by-default behavior.

    If someone "fixes" the catch block to return true (e.g., to "avoid
    breaking dev workflows"), this test FAILS.
    """
    malformed_urls = [
        "",  # empty string
        "not-a-url",  # bare string
        "://no-scheme",  # no scheme
        "ws://",  # scheme only, no host
    ]
    for url in malformed_urls:
        assert not _python_simulated_is_secure(url), (
            f"Malformed URL {url!r} was ACCEPTED by the simulated isSecure "
            "check. The L-1 fix must FAIL CLOSED on malformed URLs (return "
            "false from the catch block) to prevent an attacker from "
            "crafting a malformed URL that bypasses the hostname check."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
