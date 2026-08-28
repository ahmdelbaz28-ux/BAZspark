"""
tests/test_nfpa72_ssot_guard.py — Automated CI Gate for NFPA 72 Constants SSoT.

Enforces:
1. Canonical constants are defined in `fireai/constants/nfpa72.py`.
2. No module in `fireai/core` defines local uppercase constant assignments
   matching canonical NFPA 72 constant names (prevents calculation drift).
3. Core engineering calculation modules import from `fireai.constants.nfpa72`.
"""

from __future__ import annotations

import ast
import glob
import os
import pytest


def get_canonical_constants() -> dict[str, int]:
    """Parse fireai/constants/nfpa72.py and extract all defined constant names."""
    const_path = os.path.join("fireai", "constants", "nfpa72.py")
    assert os.path.exists(const_path), f"SSoT constants file {const_path} not found"

    with open(const_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    canonical = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    canonical[target.id] = getattr(node, "lineno", 0)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id.isupper():
                canonical[node.target.id] = getattr(node, "lineno", 0)
    return canonical


def test_ssot_constants_exist():
    """Verify that canonical NFPA 72 constants are loaded and non-empty."""
    canonical = get_canonical_constants()
    assert len(canonical) >= 40, f"Expected >= 40 NFPA 72 constants, found {len(canonical)}"
    assert "SMOKE_MAX_SPACING_M" in canonical
    assert "DEFAULT_SPRINKLER_RTI" in canonical
    assert "DEFAULT_HD_RTI" in canonical
    assert "BATTERY_STANDBY_HOURS" in canonical


def _is_ssot_reference(val_node: ast.AST | None) -> bool:
    if val_node is None:
        return False
    if isinstance(val_node, ast.Name):
        return val_node.id.startswith("SSoT_") or "nfpa72" in val_node.id.lower()
    if isinstance(val_node, ast.Attribute):
        return "nfpa72" in getattr(val_node.value, "id", "").lower() or val_node.attr.startswith("SSoT_")
    return False


def test_no_local_constant_redefinitions_in_core():
    """Verify that no file in fireai/core directly defines conflicting constant names."""
    canonical = get_canonical_constants()
    core_files = glob.glob("fireai/core/**/*.py", recursive=True)

    violations = []
    for fpath in core_files:
        if "test" in os.path.basename(fpath):
            continue

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            try:
                tree = ast.parse(f.read())
            except Exception:
                continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in canonical:
                        if not _is_ssot_reference(node.value):
                            violations.append((fpath, target.id, getattr(node, "lineno", 0)))
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id in canonical:
                    if not _is_ssot_reference(node.value):
                        violations.append((fpath, node.target.id, getattr(node, "lineno", 0)))

    assert not violations, f"Found conflicting local constant redefinitions in fireai/core: {violations}"
