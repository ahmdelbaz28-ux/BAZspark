"""backend/tests/architecture/test_phase8_workspace_governance_architecture.py — Architecture Gate for Phase 8.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 8 & Gate 8:
- 1. All 9 Workspace & Governance contracts are registered with explicit CapabilityContract.
- 2. Authority classes strictly conform to the 4 canonical plan classes:
     (CANONICAL_COMMAND, SYSTEM_INFRASTRUCTURE, EXTERNAL_TRANSACTION, LEGACY_EXCEPTION).
- 3. Tool schemas auto-derived via tool_schema_gen (zero manual duplicate tool definitions).
- 4. Generic Planner purity preserved (Principle 4: zero hardcoded capability branching).
- 5. ControlRequest unification & zero parallel execution bypasses.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import pytest

from backend.core.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.control_request import ControlRequest
from backend.core.tool_schema_gen import (
    derive_all_tool_schemas,
    derive_tool_schema_from_capability,
    validate_tool_schema_conformance,
)
from backend.core.workspace_governance_contracts import (
    ALL_PHASE8_CAPABILITIES,
    CAPABILITY_AUTHORITY_MAP,
    CAP_GOVERNANCE_ARTIFACT,
    CAP_GOVERNANCE_AUDIT,
    CAP_GOVERNANCE_INSPECT,
    CAP_GOVERNANCE_REPORT,
    CAP_GOVERNANCE_REVIEW,
    CAP_GOVERNANCE_VALIDATE,
    CAP_WORKSPACE_MODEL,
    CAP_WORKSPACE_PROJECT,
    CAP_WORKSPACE_REVISION,
)

CORE_DIR = Path(__file__).resolve().parent.parent.parent / "core"
GENERIC_PLANNER_PATH = CORE_DIR / "generic_planner.py"


def test_phase8_nine_contracts_registered_with_explicit_contracts() -> None:
    """Verify all 9 Workspace and Governance capabilities are registered in CapabilityRegistry."""
    registered = default_capability_registry.discover_authorized(scopes=["*"])
    registered_ids = {c["capability_id"] for c in registered}

    for cap_id in ALL_PHASE8_CAPABILITIES:
        assert cap_id in registered_ids, f"Phase 8 capability '{cap_id}' not found in registered capabilities"

        cap_def = default_capability_registry.get(cap_id)
        assert cap_def is not None
        assert cap_def.contract is not None, f"Capability '{cap_id}' missing explicit contract"
        assert cap_def.contract_explicit is True
        assert cap_def.contract.schema_version == "1.0"
        assert isinstance(cap_def.contract.input_schema, dict)
        assert isinstance(cap_def.contract.output_schema, dict)
        assert len(cap_def.contract.input_schema.get("properties", {})) > 0


def test_phase8_authority_classes_conform_to_four_plan_classes() -> None:
    """Verify authority classes for all 9 capabilities belong strictly to the 4 canonical plan classes."""
    valid_classes = {
        "CANONICAL_COMMAND",
        "SYSTEM_INFRASTRUCTURE",
        "EXTERNAL_TRANSACTION",
        "LEGACY_EXCEPTION",
    }
    for cap_id in ALL_PHASE8_CAPABILITIES:
        auth_class = CAPABILITY_AUTHORITY_MAP.get(cap_id)
        assert auth_class in valid_classes, (
            f"Capability '{cap_id}' has invalid authority class '{auth_class}'. "
            f"Must be one of {valid_classes}"
        )


def test_phase8_tool_schemas_auto_derived_and_conforming() -> None:
    """Verify tool schemas for all 9 capabilities are auto-derived via tool_schema_gen with 100% conformance."""
    for cap_id in ALL_PHASE8_CAPABILITIES:
        cap_def = default_capability_registry.get(cap_id)
        assert cap_def is not None

        # Derive OpenAI function schema
        openai_schema = derive_tool_schema_from_capability(cap_def, target_format="openai")
        assert openai_schema["type"] == "function"
        fn = openai_schema["function"]
        assert fn["name"] == cap_id.replace(".", "_").replace("-", "_")
        assert len(fn["description"]) > 0
        assert isinstance(fn["parameters"], dict)
        assert validate_tool_schema_conformance(openai_schema, cap_def) is True

        # Derive Anthropic schema
        anthropic_schema = derive_tool_schema_from_capability(cap_def, target_format="anthropic")
        assert anthropic_schema["name"] == cap_id.replace(".", "_").replace("-", "_")
        assert isinstance(anthropic_schema["input_schema"], dict)


def test_phase8_zero_hardcoded_capability_branching_in_generic_planner() -> None:
    """AST Test: generic_planner.py contains ZERO hardcoded branching on Phase 8 capability IDs."""
    assert GENERIC_PLANNER_PATH.exists()
    source = GENERIC_PLANNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(GENERIC_PLANNER_PATH))

    forbidden_literals = set(ALL_PHASE8_CAPABILITIES)

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value.strip()
            if val in forbidden_literals:
                violations.append(f"Line {node.lineno}: Hardcoded Phase 8 capability literal '{val}'")

    assert not violations, (
        f"Planner Purity Violation in generic_planner.py:\n" + "\n".join(violations)
    )


def test_phase8_capabilities_bound_to_audit_events() -> None:
    """Verify every Phase 8 capability definition declares an audit event configuration."""
    for cap_id in ALL_PHASE8_CAPABILITIES:
        cap_def = default_capability_registry.get(cap_id)
        assert cap_def is not None
        contract = cap_def.contract
        assert contract is not None
        assert isinstance(contract.audit, dict)
        assert contract.audit.get("enabled") is True
        assert "event_type" in contract.audit
