"""backend/tests/architecture/test_planner_purity.py — AST Architecture Test for Generic Planner Purity.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 & Gate 5/6:
Enforces that the Generic Planner (generic_planner.py) contains ZERO capability-specific
hardcoded branches or hardcoded capability ID literals.
Capability resolution must occur dynamically through the CapabilityRegistry.
"""

from __future__ import annotations

import ast
import os
import pytest

GENERIC_PLANNER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "core", "generic_planner.py")
)

# Prohibited capability strings that must NEVER be hardcoded inside generic_planner.py
FORBIDDEN_CAPABILITY_LITERALS = frozenset(
    {
        "spatial.place_devices",
        "spatial.verify_detector_spacing",
        "electrical.calculate_voltage_drop",
        "electrical.calculate_battery",
        "hydraulics.solve_darcy_weisbach",
        "import.inspect_file",
        "import.plan_import",
        "import.execute_import",
        "export.plan_export",
        "export.execute_export",
    }
)


def test_generic_planner_ast_purity_no_hardcoded_capability_literals() -> None:
    """AST Test: generic_planner.py must not contain any hardcoded capability ID literals."""
    assert os.path.exists(GENERIC_PLANNER_PATH), f"File not found: {GENERIC_PLANNER_PATH}"

    with open(GENERIC_PLANNER_PATH, encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=GENERIC_PLANNER_PATH)

    found_violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value.strip()
            if val in FORBIDDEN_CAPABILITY_LITERALS:
                found_violations.append(f"Line {node.lineno}: Hardcoded capability literal '{val}'")

    assert not found_violations, (
        f"Planner Purity Violation in generic_planner.py:\n" + "\n".join(found_violations)
    )


def test_generic_planner_ast_purity_no_capability_specific_if_branches() -> None:
    """AST Test: generic_planner.py must not branch on hardcoded capability keyword strings."""
    with open(GENERIC_PLANNER_PATH, encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=GENERIC_PLANNER_PATH)

    # Walk all Compare and If nodes to ensure no `if "spatial" in prompt` or similar hardcoded branch expressions
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Check the test condition of the if-statement
            cond_str = ast.unparse(node.test)
            for keyword in ["is_spatial", "is_electrical", "is_hydraulic", "is_battery"]:
                if keyword in cond_str:
                    violations.append(f"Line {node.lineno}: Capability-specific branch flag '{keyword}' in '{cond_str}'")

    assert not violations, (
        f"Planner Purity Violation: Capability-specific branching detected in generic_planner.py:\n"
        + "\n".join(violations)
    )
