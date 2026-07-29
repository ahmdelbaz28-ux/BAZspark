"""Phase 4 — Failing test for C-1 (CVE smuggling regression).

This test FAILS now (proving the bug exists).
After the fix (bump 3 packages back to security-fixed versions), it PASSES.

Evidence chain:
- requirements.txt:41  pyjwt[crypto]==2.9.0
- requirements.txt:43  cryptography==43.0.0
- requirements.txt:22  python-multipart==0.0.20
- pyproject.toml:45    cryptography==43.0.0
- pyproject.toml:44    pyjwt[crypto]==2.9.0
- pyproject.toml:42    python-multipart==0.0.20
- pyproject.toml:12    requires-python = ">=3.12"
- commit 9da220d2     reverted security bumps with false "Python 3.8" justification

Per pip-audit (run 2026-07-28):
  cryptography 43.0.0     -> 5 unique CVEs (latest fix: 48.0.1)
  pyjwt 2.9.0             -> 7 unique CVEs (latest fix: 2.13.0)
  python-multipart 0.0.20 -> 6 unique CVEs (latest fix: 0.0.31)
"""
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIREMENTS_TXT = REPO_ROOT / "requirements.txt"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def _extract_min_version(text: str, package: str) -> Optional[str]:
    """Extract the minimum required version of a package from text.

    Handles both requirements.txt and pyproject.toml formats, and both
    strict pins (==) and range pins (>=X.Y.Z,<A.B.C):
        cryptography==43.0.0
        cryptography>=48.0.1,<50.0.0
        "cryptography==43.0.0",  # comment
        "cryptography>=48.0.1,<50.0.0",
        pyjwt[crypto]==2.9.0
        pyjwt[crypto]>=2.13.0,<3.0.0
    """
    # Match the >= operator (preferred for ranges) or == operator (strict pins)
    # Capture the FIRST version specifier found.
    pattern = (
        rf"(?:^|\W){re.escape(package)}"
        rf"(?:\[[^\]]+\])?"        # optional extras like [crypto]
        rf"(?:>=(?P<min_ver>[0-9]+(?:\.[0-9]+)*)"   # >= min version
        rf"|==(?P<eq_ver>[0-9]+(?:\.[0-9]+)*))"     # OR == strict pin
    )
    for line in text.splitlines():
        m = re.search(pattern, line)
        if m:
            return m.group("min_ver") or m.group("eq_ver")
    return None


# Backward-compatible alias
_extract_version = _extract_min_version


def _version_tuple(v: str) -> Tuple[int, ...]:

    return tuple(int(p) for p in v.split("."))


def test_cryptography_is_above_vulnerable_pin():
    """cryptography must be > 43.0.0 (24 CVEs fixed in 48.0.1)."""
    text = REQUIREMENTS_TXT.read_text()
    version = _extract_version(text, "cryptography")
    assert version is not None, "cryptography not found in requirements.txt"
    assert _version_tuple(version) > (43, 0, 0), (
        f"cryptography is pinned to {version} which has 5 known CVEs. "
        f"Per pip-audit, minimum safe version is 48.0.1. "
        f"Commit 9da220d2 reverted this pin with false 'Python 3.8' justification "
        f"while pyproject.toml declares requires-python >= 3.12."
    )


def test_pyjwt_is_above_vulnerable_pin():
    """pyjwt must be > 2.9.0 (7 CVEs fixed in 2.13.0)."""
    text = REQUIREMENTS_TXT.read_text()
    version = _extract_version(text, "pyjwt")
    assert version is not None, "pyjwt not found in requirements.txt"
    assert _version_tuple(version) > (2, 9, 0), (
        f"pyjwt is pinned to {version} which has 7 known CVEs. "
        f"Per pip-audit, minimum safe version is 2.13.0. "
        f"Commit 9da220d2 reverted this pin with false 'Python 3.8' justification."
    )


def test_python_multipart_is_above_vulnerable_pin():
    """python-multipart must be > 0.0.20 (6 CVEs fixed in 0.0.31)."""
    text = REQUIREMENTS_TXT.read_text()
    version = _extract_version(text, "python-multipart")
    assert version is not None, "python-multipart not found in requirements.txt"
    assert _version_tuple(version) > (0, 0, 20), (
        f"python-multipart is pinned to {version} which has 6 known CVEs. "
        f"Per pip-audit, minimum safe version is 0.0.31. "
        f"Commit 9da220d2 reverted this pin with false 'Python 3.8' justification."
    )


def test_pyproject_cryptography_is_above_vulnerable_pin():
    text = PYPROJECT_TOML.read_text()
    version = _extract_version(text, "cryptography")
    assert version is not None, "cryptography not found in pyproject.toml"
    assert _version_tuple(version) > (43, 0, 0), (
        f"pyproject.toml pins cryptography to {version} (vulnerable). "
        f"Commit 9da220d2 falsely commented 'V163: fix 5 HIGH CVEs with compatible version for Python 3.8' "
        f"while requires-python = '>=3.12'."
    )


def test_pyproject_pyjwt_is_above_vulnerable_pin():
    text = PYPROJECT_TOML.read_text()
    version = _extract_version(text, "pyjwt")
    assert version is not None, "pyjwt not found in pyproject.toml"
    assert _version_tuple(version) > (2, 9, 0), (
        f"pyproject.toml pins pyjwt to {version} (vulnerable)."
    )


def test_pyproject_python_multipart_is_above_vulnerable_pin():
    text = PYPROJECT_TOML.read_text()
    version = _extract_version(text, "python-multipart")
    assert version is not None, "python-multipart not found in pyproject.toml"
    assert _version_tuple(version) > (0, 0, 20), (
        f"pyproject.toml pins python-multipart to {version} (vulnerable)."
    )


def test_no_false_python_38_justification():
    """The 'Python 3.8' justification in pyproject.toml is FALSE because
    requires-python = '>=3.12'. No security downgrade should reference Python 3.8."""
    text = PYPROJECT_TOML.read_text()
    # If requires-python is >=3.12, no line should mention "Python 3.8" as a downgrade reason
    if 'requires-python = ">=3.12"' in text:
        offending_lines = [
            line for line in text.splitlines()
            if "Python 3.8" in line and ("compat" in line.lower() or "disabled" in line.lower())
        ]
        assert not offending_lines, (
            f"pyproject.toml declares requires-python = '>=3.12' but contains "
            f"{len(offending_lines)} line(s) justifying downgrades with 'Python 3.8'. "
            f"This is the smuggling pattern from commit 9da220d2. "
            f"Offending lines: {offending_lines[:3]}"
        )


if __name__ == "__main__":
    # Run as standalone to see which tests fail
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
