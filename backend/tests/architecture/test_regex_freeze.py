"""backend/tests/architecture/test_regex_freeze.py — AST Architecture Test for Regex Planner Freezing.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 & Principle 11:
The legacy regex fallback planner is FROZEN.
Adding ANY new capability to the regex fallback planner path is strictly forbidden and causes CI failure.
"""

from __future__ import annotations

import ast
import os
import pytest
from backend.core.workflow_planner import FROZEN_REGEX_CAPABILITIES

WORKFLOW_PLANNER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "core", "workflow_planner.py")
)

# Canonical 10 frozen capabilities present in the legacy planner
EXACT_FROZEN_CAPABILITY_SET = frozenset(
    {
        "import.inspect_file",
        "import.plan_import",
        "import.execute_import",
        "export.plan_export",
        "export.execute_export",
        "spatial.place_devices",
        "compliance.verify_detector_spacing",
        "electrical.calculate_voltage_drop",
        "electrical.calculate_battery",
        "hydraulics.solve_darcy_weisbach",
    }
)


def test_frozen_regex_capability_set_exact_match() -> None:
    """Verify that FROZEN_REGEX_CAPABILITIES matches the exact historical 10 capabilities."""
    assert FROZEN_REGEX_CAPABILITIES == EXACT_FROZEN_CAPABILITY_SET, (
        f"Regex Freeze Violation: FROZEN_REGEX_CAPABILITIES has been modified.\n"
        f"Expected: {sorted(EXACT_FROZEN_CAPABILITY_SET)}\n"
        f"Actual: {sorted(FROZEN_REGEX_CAPABILITIES)}"
    )


def test_regex_fallback_planner_no_additional_capability_references() -> None:
    """AST Test: RegexFallbackPlanner must not reference any new capability outside the frozen set."""
    assert os.path.exists(WORKFLOW_PLANNER_PATH)

    with open(WORKFLOW_PLANNER_PATH, encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=WORKFLOW_PLANNER_PATH)

    # Find RegexFallbackPlanner class node
    regex_class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RegexFallbackPlanner":
            regex_class_node = node
            break

    assert regex_class_node is not None, "RegexFallbackPlanner class not found in workflow_planner.py"

    # Verify all capability string literals in RegexFallbackPlanner belong to FROZEN_REGEX_CAPABILITIES
    for subnode in ast.walk(regex_class_node):
        if isinstance(subnode, ast.Constant) and isinstance(subnode.value, str):
            val = subnode.value.strip()
            if "." in val and (val.startswith("spatial.") or val.startswith("compliance.") or val.startswith("electrical.") or val.startswith("hydraulics.") or val.startswith("import.") or val.startswith("export.")):
                assert val in EXACT_FROZEN_CAPABILITY_SET, (
                    f"Freeze Violation: Capability '{val}' added to RegexFallbackPlanner!"
                )
