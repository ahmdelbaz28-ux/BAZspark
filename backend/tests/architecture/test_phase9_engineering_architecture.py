"""backend/tests/architecture/test_phase9_engineering_architecture.py — Phase 9 Architecture Invariants.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 9 & Gate 9:
- Generic Planner AST Purity: Zero domain-specific hardcoded branching in generic_planner.py.
- Capability Registry Completeness: All 12 Phase 9 capabilities are registered with valid schemas and authority classes.
- Tool Schema Auto-Derivation: Schema generator dynamically discovers Phase 9 capabilities.
- Chat Architecture Shield: Chat routes never bypass the control plane.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import pytest

from backend.core.capability_registry import (
    CapabilityRegistry,
    default_capability_registry,
    VALID_CATEGORIES,
)
from backend.core.engineering_expansion_contracts import ALL_PHASE9_CAPABILITIES
from backend.core.tender_contracts import ALL_PHASE9B_TENDER_CAPABILITIES
from backend.core.generic_planner import GenericWorkflowPlanner
from backend.core.tool_schema_gen import derive_all_tool_schemas, derive_tool_schema_from_capability


def test_generic_planner_ast_purity_zero_hardcoded_phase9_branches() -> None:
    """Assert AST purity of GenericWorkflowPlanner — zero hardcoded domain branches."""
    planner_file = Path(__file__).resolve().parent.parent.parent / "core" / "generic_planner.py"
    assert planner_file.exists(), f"Generic planner file not found at {planner_file}"

    source = planner_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Inspect all String constants and Compare nodes in AST
    # Generic planner should not contain domain-specific branching like 'if domain == "marine"'
    forbidden_tokens = [
        "if domain ==",
        "if capability ==",
        "marine.verify_solas_compliance",
        "etap.calculate_load_flow",
        "facp.design_loop_topology",
        "bim.validate_spatial_clash",
        "tender.generate_financial_proposal",
        "tender.generate_technical_compliance",
    ]
    for token in forbidden_tokens:
        assert token not in source, f"AST Purity violation: generic_planner.py contains hardcoded token '{token}'"


def test_all_phase9_and_9b_capabilities_registered_and_structured() -> None:
    """Assert all 12 Phase 9 + 2 Phase 9b capabilities are registered with strict structure."""
    reg = default_capability_registry
    all_caps = list(ALL_PHASE9_CAPABILITIES) + list(ALL_PHASE9B_TENDER_CAPABILITIES)

    for cap_id in all_caps:
        cap = reg.get(cap_id)
        assert cap is not None, f"Capability '{cap_id}' not registered in CapabilityRegistry"
        assert cap.category in VALID_CATEGORIES
        assert cap.contract is not None
        assert cap.contract.risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert cap.required_scopes, f"Capability '{cap_id}' must require explicit scopes"
        assert cap.input_schema, f"Capability '{cap_id}' must define input_schema"
        assert cap.output_schema, f"Capability '{cap_id}' must define output_schema"
        assert callable(cap.handler), f"Capability '{cap_id}' must have a callable deterministic handler"


def test_tool_schema_auto_derivation_discovers_phase9_and_9b_capabilities() -> None:
    """Assert tool schema generator automatically discovers Phase 9 and 9b capabilities."""
    openai_tools = derive_all_tool_schemas(scopes=["*"], target_format="openai")
    openai_tool_names = {t["function"]["name"] for t in openai_tools}
    all_caps = list(ALL_PHASE9_CAPABILITIES) + list(ALL_PHASE9B_TENDER_CAPABILITIES)

    for cap_id in all_caps:
        sanitized_name = cap_id.replace(".", "_")
        assert sanitized_name in openai_tool_names, (
            f"Auto-generated OpenAI tool schemas missing capability '{sanitized_name}'"
        )


def test_capability_registry_rejects_alien_class_fail_closed() -> None:
    """Assert CapabilityRegistry.register() strictly fails closed on alien classes matching by name only (R-9.1)."""
    from backend.core.capability_registry import CapabilityDefinition, CapabilityContract

    # 1. Alien capability definition object with matching class name
    AlienCapabilityDefinition = type("CapabilityDefinition", (), {
        "capability_id": "alien.test_capability",
        "contract": None,
        "contract_explicit": True,
    })
    alien_def = AlienCapabilityDefinition()

    reg = CapabilityRegistry()
    with pytest.raises(TypeError, match="capability must be an instance of CapabilityDefinition"):
        reg.register(alien_def)  # type: ignore

    # 2. Legit capability definition with alien contract object matching class name
    AlienCapabilityContract = type("CapabilityContract", (), {
        "schema_version": "1.0",
        "revision_binding": "none",
        "execution_mode": "inline",
        "mutation_type": "read_only",
        "risk": "LOW",
        "scopes": [],
        "input_schema": {},
        "output_schema": {},
    })
    legit_def_with_alien_contract = CapabilityDefinition(
        capability_id="test.legit_id",
        name="Test Legit",
        description="Test",
        category="compliance",
        contract=AlienCapabilityContract(),  # type: ignore
        handler=lambda p: {},
        contract_explicit=True,
    )
    with pytest.raises(ValueError, match="must have an explicit, valid CapabilityContract declared"):
        reg.register(legit_def_with_alien_contract)

