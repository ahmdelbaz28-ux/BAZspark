"""Phase 10 — Architecture & Invariant Compliance Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 10 & PHASE10_DELIVERY_CONTRACT.md:
- Invariant 1: Zero SIMULATED text/behavior in etap_service.py delivery path (Principle 6).
- Invariant 2: VALID_EXECUTION_CHANNELS strictly contains 'desktop_agent'.
- Invariant 3: Generic planner AST structural purity (no hardcoded domain branches).
- Invariant 4: 100% contract explicitness for all Phase 10 capabilities.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backend.core.capability_registry import (
    VALID_CATEGORIES,
    VALID_EXECUTION_CHANNELS,
    default_capability_registry,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ETAP_SERVICE_PATH = REPO_ROOT / "backend" / "integrations" / "etap_service.py"
GENERIC_PLANNER_PATH = REPO_ROOT / "backend" / "core" / "generic_planner.py"


def test_etap_service_zero_simulated_invariant():
    """Verify forensic zero-simulated invariant in backend/integrations/etap_service.py."""
    assert ETAP_SERVICE_PATH.exists(), f"Missing file: {ETAP_SERVICE_PATH}"
    source_code = ETAP_SERVICE_PATH.read_text(encoding="utf-8").lower()

    # Invariant: zero instances of the word 'simulated'
    assert "simulated" not in source_code, (
        "Forensic Invariant Violated: 'simulated' keyword found in backend/integrations/etap_service.py"
    )


def test_execution_channels_contain_desktop_agent():
    """Verify VALID_EXECUTION_CHANNELS includes 'desktop_agent'."""
    assert "desktop_agent" in VALID_EXECUTION_CHANNELS
    assert "cad" in VALID_CATEGORIES
    assert "etap" in VALID_CATEGORIES


def test_generic_planner_ast_purity():
    """Verify AST purity of generic_planner.py — no hardcoded domain branching."""
    assert GENERIC_PLANNER_PATH.exists()
    tree = ast.parse(GENERIC_PLANNER_PATH.read_text(encoding="utf-8"))

    # Scan for any forbidden hardcoded capability or domain branching in planner class
    class PlannerASTVisitor(ast.NodeVisitor):
        def __init__(self):
            self.hardcoded_domain_ifs = []

        def visit_If(self, node: ast.If):
            # Check if condition checks capability_id or domain hardcoded strings
            test_dump = ast.dump(node.test)
            if "cad.revit" in test_dump or "etap.live" in test_dump:
                self.hardcoded_domain_ifs.append(node.lineno)
            self.generic_visit(node)

    visitor = PlannerASTVisitor()
    visitor.visit(tree)
    assert not visitor.hardcoded_domain_ifs, (
        f"Hardcoded domain branches found in generic_planner.py at lines: {visitor.hardcoded_domain_ifs}"
    )


def test_all_phase10_capabilities_explicit_contracts():
    """Verify all Phase 10 registered capabilities have explicit, validated contracts."""
    phase10_caps = [
        "cad.revit_create_wall",
        "cad.revit_get_elements",
        "cad.autocad_draw_line",
        "cad.execute_desktop_command",
        "etap.live_test_connection",
        "etap.live_sync_project",
        "etap.live_calculate_load_flow",
        "etap.live_calculate_short_circuit",
    ]
    for cap_id in phase10_caps:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None, f"Missing Phase 10 capability: {cap_id}"
        assert cap.contract_explicit is True
        assert cap.contract is not None
        assert cap.contract.schema_version == "1.0"
        assert cap.contract.audit.get("enabled") is True


def test_exactly_one_command_registry_json_in_repo():
    """Verify single source of truth: exactly ONE command_registry.json exists in the repository (V-R1)."""
    found_files = list(REPO_ROOT.rglob("command_registry.json"))
    valid_files = [
        f
        for f in found_files
        if not any(part.startswith(".") or part in {"venv", "node_modules", "dist", "build", "egg-info"} for part in f.parts)
    ]
    assert len(valid_files) == 1, (
        f"Forensic Architecture Invariant Violated (V-R1): Expected exactly 1 command_registry.json in tree, found {len(valid_files)}: {valid_files}"
    )
    expected_rel_path = Path("backend") / "core" / "command_registry.json"
    actual_rel_path = valid_files[0].relative_to(REPO_ROOT)
    assert actual_rel_path == expected_rel_path, (
        f"Single source of truth must be at {expected_rel_path}, found at {actual_rel_path}"
    )

