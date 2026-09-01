"""backend/tests/architecture/test_phase11_architecture.py — Phase 11 Architectural Invariant Guards.

Mandated by BAZSPARK Phase 11 (P11-R5):
- Architectural Guard A: AST verification that EtapLiveAdapter cannot bypass resolve_to_safe_ip.
- Architectural Guard B: Verification that EtapLiveAdapter and EtapService contain ZERO fallback to mock.
- Architectural Guard C: Extended simulated = 0 invariant covering all Phase 10 & 11 ETAP code paths.
- Architectural Guard D: Verification of resilience contracts versioning and schema integrity.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
INTEGRATIONS_DIR = BACKEND_DIR / "integrations"
CORE_DIR = BACKEND_DIR / "core"


def test_guard_adapter_mandatory_ssrf_resolution_ast() -> None:
    """Guard A: AST check proving EtapLiveAdapter public methods enforce _resolve_and_validate_target."""
    adapter_file = INTEGRATIONS_DIR / "etap_live_adapter.py"
    assert adapter_file.exists(), f"Missing file: {adapter_file}"

    tree = ast.parse(adapter_file.read_text(encoding="utf-8"))

    adapter_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "EtapLiveAdapter":
            adapter_class = node
            break

    assert adapter_class is not None, "EtapLiveAdapter class not found in AST"

    # Methods that perform network/target operations
    target_methods = [
        "test_connection_live",
        "list_projects_live",
        "export_project_live",
        "import_project_live",
        "calculate_live_load_flow",
        "calculate_live_short_circuit",
    ]

    for method_name in target_methods:
        method_node = None
        for item in adapter_class.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                method_node = item
                break

        assert method_node is not None, f"Method {method_name} missing from EtapLiveAdapter"

        # Check that method calls _resolve_and_validate_target
        calls = [
            n.func.attr
            for n in ast.walk(method_node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        ]
        assert "_resolve_and_validate_target" in calls, (
            f"Method '{method_name}' does not call '_resolve_and_validate_target' — SSRF bypass risk!"
        )


def test_guard_zero_mock_fallback_fail_closed() -> None:
    """Guard B: Verify that EtapLiveAdapter never catches exceptions to silently return mock data."""
    adapter_file = INTEGRATIONS_DIR / "etap_live_adapter.py"
    content = adapter_file.read_text(encoding="utf-8").lower()

    # Prohibited patterns indicating silent fallback to mock
    assert "return mock" not in content
    assert "mock_mode" not in content
    assert "simulated_result" not in content
    assert "fallback_to_simulated" not in content


def test_guard_simulated_zero_invariant_universal() -> None:
    """Guard C: Verify simulated = 0 invariant across all ETAP integration and resilience modules."""
    files_to_check = [
        INTEGRATIONS_DIR / "etap_live_adapter.py",
        INTEGRATIONS_DIR / "etap_service.py",
        CORE_DIR / "etap_live_contracts.py",
        CORE_DIR / "etap_resilience_contracts.py",
        CORE_DIR / "etap_telemetry.py",
    ]

    for fpath in files_to_check:
        assert fpath.exists(), f"Required file missing: {fpath}"
        lines = fpath.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            line_clean = line.strip()
            # Comments explaining the invariant are allowed; code assigning or returning simulated is strictly forbidden
            if line_clean.startswith("#") or line_clean.startswith('"""') or line_clean.startswith("*"):
                continue
            if '"simulated": true' in line_clean.lower() or "'simulated': true" in line_clean.lower():
                pytest.fail(f"Found active simulated payload in {fpath.name}:{idx} -> {line_clean}")
            if "simulated = true" in line_clean.lower():
                pytest.fail(f"Found active simulated variable in {fpath.name}:{idx} -> {line_clean}")


def test_guard_resilience_schemas_versioning() -> None:
    """Guard D: Verify that all resilience schemas define explicit versioning."""
    from backend.core.etap_resilience_contracts import (
        RESILIENCE_CONTRACT_VERSION,
        BackpressurePolicy,
        CircuitBreakerPolicy,
        RetryPolicy,
    )

    assert RESILIENCE_CONTRACT_VERSION == "1.0"
    assert RetryPolicy().schema_version == "1.0"
    assert CircuitBreakerPolicy().schema_version == "1.0"
    assert BackpressurePolicy().schema_version == "1.0"
