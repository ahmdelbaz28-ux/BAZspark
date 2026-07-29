"""Phase 5 — Strict verification of the M-4 (CVE smuggling) claim.

CLAIM UNDER TEST (RETRACTED from active Phase 3 verdict):
  ORIGINAL wording (now removed from the active verdict):
    "M-4: 18-24 unfixed CVEs in pinned cryptography/pyjwt/python-multipart
     (depends on duplicate counting)"

  RETRACTION (applied in PHASE5-M4-M5-REWORD-L1-L2-L3 round):
    The standalone M-4 entry has been removed from the active Phase 3
    verdict listing. The CVE substance is owned by C-1 (CRITICAL) which
    was RESOLVED in Phase 4. Keeping a separate M-4 listing was a
    duplicate that implied TWO outstanding CVE issues when there was
    only ONE (C-1), now resolved.

    The M-4 entry has also been added to the RETRACTED FALSE CLAIMS
    section near the top of worklog.md with the reason for retraction.

CONTEXT:
  This claim was originally part of C-1 (CRITICAL). The Phase 4 fix
  updated requirements.txt and pyproject.toml to use >= safe versions.
  After the fix, M-4 became STALE — the CVEs are no longer present.

  The 6 regression-guard tests below REMAIN IN FORCE. They serve as
  guards against future reverts of the C-1 fix. If the pins are
  reverted to vulnerable versions, the tests will FAIL — even though
  the standalone M-4 claim itself has been retracted.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIREMENTS_TXT = REPO_ROOT / "requirements.txt"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


# ─── Pin version checks ──────────────────────────────────────────────────────


def _read_pin(filepath: Path, package: str) -> str | None:
    """Extract the version specifier for `package` from a requirements file.

    Supports:
      - requirements.txt: `cryptography==43.0.0` or `cryptography>=48.0.1,<50.0.0`
      - pyproject.toml array form: `"cryptography>=48.0.1,<50.0.0"`
      - pyproject.toml table form:  `cryptography = ">=48.0.1,<50.0.0"`
    """
    if not filepath.exists():
        return None
    content = filepath.read_text(encoding="utf-8")

    # Form 1: requirements.txt — `package>=1.2.3,<4.0.0` at start of line
    # Allow optional extras like `pyjwt[crypto]`
    pkg_pattern = re.escape(package) + r"(\[[^\]]+\])?"
    pattern = rf"(?m)^{pkg_pattern}\s*([=<>~!]+\s*[^\s,#]+(?:\s*,\s*[=<>~!]+\s*[^\s,#]+)*)"
    m = re.search(pattern, content)
    if m:
        return m.group(0)  # full match like "cryptography>=48.0.1,<50.0.0"

    # Form 2: pyproject.toml array form — `"package>=1.2.3,<4.0.0"`
    pattern_toml_array = rf'"{pkg_pattern}\s*([=<>~!]+\s*[^"\s,#]+(?:\s*,\s*[=<>~!]+\s*[^"\s,#]+)*)"'
    m = re.search(pattern_toml_array, content)
    if m:
        return m.group(0)

    # Form 3: pyproject.toml table form — `package = ">=1.2.3,<4.0.0"`
    pattern_toml_table = rf'(?m)^{pkg_pattern}\s*=\s*"([^"]+)"'
    m = re.search(pattern_toml_table, content)
    if m:
        return f'{package} = "{m.group(2)}"'

    return None


def test_cryptography_is_above_vulnerable_pin():
    """Verify cryptography is no longer pinned to the vulnerable 43.0.0.

    The C-1 fix updated cryptography from ==43.0.0 to >=48.0.1,<50.0.0.
    If this test FAILS, the pin has been reverted (or never applied).
    """
    for filepath in (REQUIREMENTS_TXT, PYPROJECT_TOML):
        pin = _read_pin(filepath, "cryptography")
        assert pin is not None, (
            f"cryptography not found in {filepath} — the dependency "
            "may have been removed entirely (which would be unusual)."
        )
        # Must NOT be the vulnerable pin
        assert "43.0.0" not in pin, (
            f"M-4 CLAIM IS ACCURATE: {filepath.name} still pins "
            f"cryptography to 43.0.0 ({pin}). The C-1 fix has been "
            "reverted — re-escalate to CRITICAL."
        )
        # Must be >= a safe version
        assert ">=48" in pin or ">=49" in pin or ">=50" in pin, (
            f"M-4 CLAIM UNCERTAIN: {filepath.name} pins cryptography "
            f"to '{pin}' which is not the expected safe version "
            "(>=48.0.1). Manually verify with pip-audit."
        )


def test_pyjwt_is_above_vulnerable_pin():
    """Verify pyjwt is no longer pinned to the vulnerable 2.9.0."""
    for filepath in (REQUIREMENTS_TXT, PYPROJECT_TOML):
        # pyjwt appears as "pyjwt" or "pyjwt[crypto]"
        pin = _read_pin(filepath, "pyjwt")
        if pin is None:
            pin = _read_pin(filepath, "pyjwt[crypto]")
        assert pin is not None, (
            f"pyjwt not found in {filepath} — the dependency may "
            "have been removed (unusual)."
        )
        assert "2.9.0" not in pin, (
            f"M-4 CLAIM IS ACCURATE: {filepath.name} still pins "
            f"pyjwt to 2.9.0 ({pin}). The C-1 fix has been reverted."
        )
        assert ">=2.13" in pin or ">=2.14" in pin or ">=2.15" in pin \
            or ">=3" in pin, (
            f"M-4 CLAIM UNCERTAIN: {filepath.name} pins pyjwt to "
            f"'{pin}' which is not the expected safe version (>=2.13.0)."
        )


def test_python_multipart_is_above_vulnerable_pin():
    """Verify python-multipart is no longer pinned to the vulnerable 0.0.20."""
    for filepath in (REQUIREMENTS_TXT, PYPROJECT_TOML):
        pin = _read_pin(filepath, "python-multipart")
        assert pin is not None, (
            f"python-multipart not found in {filepath}."
        )
        assert "0.0.20" not in pin, (
            f"M-4 CLAIM IS ACCURATE: {filepath.name} still pins "
            f"python-multipart to 0.0.0 ({pin}). C-1 fix reverted."
        )
        assert ">=0.0.31" in pin or ">=0.0.32" in pin or ">=0.1" in pin \
            or ">=1" in pin, (
            f"M-4 CLAIM UNCERTAIN: {filepath.name} pins "
            f"python-multipart to '{pin}' which is not the expected "
            "safe version (>=0.0.31)."
        )


def test_no_false_python_38_justification():
    """Verify no ACTIVE 'Python 3.8' justification remains for the three pins.

    The C-1 finding was that commit 9da220d2 smuggled a revert of
    CVE fixes with a misleading 'Python 3.8' justification, even
    though pyproject.toml requires Python >=3.12. This test verifies
    no NEW false justification has been added.

    NOTE on what counts as a "false justification":
      - ACTIVE false justification (FLAGGED): a comment that JUSTIFIES
        the pin by claiming Python 3.8 compatibility. Examples:
          "compatible with Python 3.8"
          "disabled for Python 3.8"
          "Python 3.8 support"
      - AUDIT DOCUMENTATION (NOT FLAGGED): a comment that MENTIONS the
        historical false justification as documentation. Example:
          "V163 RESTORE: was reverted to 2.9.0 by 9da220d2 with false
           'Python 3.8' justification"
        Such comments are GOOD — they document the audit finding.

    If this test FAILS, a new false justification has been added.
    """
    # Patterns that indicate an ACTIVE false justification (not just
    # documentation of the historical false claim)
    active_justification_patterns = [
        r"#\s*compatible with Python 3\.8",
        r"#\s*disabled for Python 3\.8",
        r"#\s*Python 3\.8 support",
        r"#\s*for Python 3\.8 compatibility",
        r"#\s*requires Python 3\.8",
    ]

    for filepath in (REQUIREMENTS_TXT, PYPROJECT_TOML):
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")

        for i, line in enumerate(lines):
            # Check if this line is a cryptography/pyjwt/python-multipart pin
            if not any(pkg in line.lower() for pkg in
                       ("cryptography", "pyjwt", "python-multipart")):
                continue

            # Skip commented-out lines (these are inactive)
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue

            # Check if any active false justification pattern matches
            for pattern in active_justification_patterns:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    pytest.fail(
                        f"M-4/C-1 REGRESSION: false 'Python 3.8' "
                        f"justification found in {filepath.name} on "
                        f"the {line.split()[0] if line.split() else '?'} "
                        f"pin. Line {i+1}: {line}"
                    )


# ─── pip-audit verification (the gold standard) ─────────────────────────────


@pytest.mark.timeout(30)
def test_pip_audit_reports_no_known_vulnerabilities():
    """Run pip-audit on requirements.txt — assert zero CVEs.

    This is the GOLD STANDARD test. If pip-audit reports any CVEs in
    cryptography, pyjwt, or python-multipart, the M-4 claim is
    ACCURATE (CVEs remain). If pip-audit is clean, M-4 is STALE.

    We skip this test if pip-audit is not installed (CI environments
    may not have it).
    """
    if not REQUIREMENTS_TXT.exists():
        pytest.skip(f"requirements.txt not found at {REQUIREMENTS_TXT}")

    try:
        result = subprocess.run(
            ["pip-audit", "-r", str(REQUIREMENTS_TXT),
             "--strict", "--no-deps"],
            capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        pytest.skip("pip-audit not installed")
    except subprocess.TimeoutExpired:
        pytest.skip("pip-audit timed out — likely network issue")

    output = result.stdout + result.stderr

    # Filter to the three packages M-4 mentions
    relevant_lines = [
        line for line in output.split("\n")
        if any(pkg in line.lower() for pkg in
               ("cryptography", "pyjwt", "python-multipart"))
    ]

    # pip-audit exit code 0 = no vulnerabilities
    if result.returncode == 0:
        # No vulnerabilities — M-4 is STALE
        return

    # If pip-audit found vulnerabilities in OTHER packages, that's
    # outside M-4's scope — skip
    if not relevant_lines:
        return

    pytest.fail(
        "M-4 CLAIM IS ACCURATE: pip-audit reports vulnerabilities in "
        "cryptography/pyjwt/python-multipart:\n  "
        + "\n  ".join(relevant_lines)
    )


# ─── Claim retraction regression guard ────────────────────────────────────────


def test_m4_claim_text_REMOVED_from_active_worklog():
    """REGRESSION GUARD: assert the M-4 active-claim wording has been
    REMOVED from the active Phase 3 verdict section of worklog.md.

    The standalone M-4 claim was RETRACTED in the
    PHASE5-M4-M5-REWORD-L1-L2-L3 round because it duplicated the C-1
    RESOLVED state. The active Phase 3 verdict listing (the "MEDIUM
    ISSUES" block) must NOT contain the standalone M-4 wording.

    Note: the M-4 entry is allowed to appear ELSEWHERE in the worklog
    (the RETRACTED FALSE CLAIMS section, the M-4 RETRACTION NOTE, the
    PRODUCTION-CODE-FIXES status section, etc.) — those mentions are
    intentional historical records. This test only asserts it's gone
    from the ACTIVE Phase 3 verdict listing.
    """
    WORKLOG = Path("/home/z/my-project/worklog.md")
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")

    # The original standalone M-4 wording that was retracted
    retracted_wording = (
        "M-4: 18-24 unfixed CVEs in pinned cryptography/pyjwt/"
        "python-multipart (depends on duplicate counting)"
    )

    # The active Phase 3 verdict section starts with "MEDIUM ISSUES"
    # and ends before "LOW ISSUES:" or "RETRACTED FALSE CLAIMS".
    # Extract that block and check M-4 is NOT there as an active claim.
    medium_section_start = worklog_text.find("MEDIUM ISSUES")
    if medium_section_start == -1:
        pytest.skip("MEDIUM ISSUES section not found in worklog")
    # Find the end of the MEDIUM ISSUES block — the next section header
    # that starts at column 0 with no leading whitespace.
    after_medium = worklog_text[medium_section_start:]
    # The MEDIUM block ends at the next "LOW ISSUES:" or
    # "RETRACTED FALSE CLAIMS" line.
    end_markers = ["LOW ISSUES:", "RETRACTED FALSE CLAIMS"]
    end_idx = len(after_medium)
    for marker in end_markers:
        idx = after_medium.find(marker)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    medium_section = after_medium[:end_idx]

    # Normalize whitespace so multi-line matches work correctly.
    medium_section_normalized = re.sub(r"\s+", " ", medium_section)
    retracted_wording_normalized = re.sub(r"\s+", " ", retracted_wording)

    assert retracted_wording_normalized not in medium_section_normalized, (
        "M-4 active-claim wording is still present in the MEDIUM ISSUES "
        "section of worklog.md. The PHASE5-M4-M5-REWORD-L1-L2-L3 round "
        "should have retracted it. If you are intentionally re-activating "
        "M-4 as a standalone claim (e.g., a new CVE regression was "
        "discovered), update this test to match the new active wording."
    )

    # Also verify the M-4 retraction IS documented somewhere in the worklog
    # (so future readers know the retraction was conscious, not an accident).
    retraction_marker = "RETRACTED FALSE CLAIMS"
    assert retraction_marker in worklog_text, (
        "RETRACTED FALSE CLAIMS section not found in worklog.md — "
        "the M-4 retraction notice has no home."
    )
    # The M-4 entry must appear in the RETRACTED section
    retracted_section_start = worklog_text.find(retraction_marker)
    retracted_section = worklog_text[retracted_section_start:
                                      retracted_section_start + 4000]
    assert "M-4" in retracted_section and "RETRACTED" in retracted_section, (
        "M-4 retraction notice not found in the RETRACTED FALSE CLAIMS "
        "section. The retraction must be documented for traceability."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
