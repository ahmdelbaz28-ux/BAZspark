#!/usr/bin/env python3
"""
remove_file_level_nosonar.py — Safely remove file-level '# NOSONAR' from Python files.

This script replaces the file-level '# NOSONAR' suppression (which silences
ALL SonarQube rules for the entire file) with a documentation comment that
points to NOSONAR_AUDIT.md. Per-line justified suppressions are PRESERVED.

Usage:
    python scripts/remove_file_level_nosonar.py <file1> [file2] [file3] ...

Safety:
    - Only modifies files where line 1 is EXACTLY '# NOSONAR'
    - Preserves all other content (including per-line NOSONAR suppressions)
    - Reports what was changed for audit trail
    - Does NOT modify files that don't match the pattern
"""

from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENT_COMMENT = (
    "# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).\n"
    "# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.\n"
)


def remove_file_level_nosonar(filepath: Path) -> bool:
    """
    Remove file-level '# NOSONAR' from the first line of a Python file.

    Returns True if the file was modified, False if it was already clean
    or didn't match the pattern.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"  SKIP {filepath}: cannot read ({e})")
        return False

    lines = content.split("\n")

    # Check if line 0 (first line) is exactly '# NOSONAR'
    if not lines or lines[0].strip() != "# NOSONAR":
        first = lines[0][:50] if lines else "empty"
        print(f"  SKIP {filepath}: line 1 is not '# NOSONAR' (got: {first!r})")
        return False

    # Replace line 0 with the documentation comment
    # Keep the rest of the file unchanged
    new_lines = [REPLACEMENT_COMMENT.rstrip("\n")] + lines[1:]
    new_content = "\n".join(new_lines)

    # Ensure file ends with newline
    if not new_content.endswith("\n"):
        new_content += "\n"

    filepath.write_text(new_content, encoding="utf-8")
    print(f"  DONE {filepath}")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: remove_file_level_nosonar.py <file1> [file2] ...", file=sys.stderr)
        return 1

    files = [Path(f) for f in sys.argv[1:]]
    modified = 0
    skipped = 0

    print(f"Processing {len(files)} file(s)...")
    for f in files:
        if not f.exists():
            print(f"  SKIP {f}: does not exist")
            skipped += 1
            continue
        if remove_file_level_nosonar(f):
            modified += 1
        else:
            skipped += 1

    print(f"\nSummary: {modified} modified, {skipped} skipped")
    return 0 if modified > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
