"""backend/tests/test_contract_conformance.py — Gate 1 Conformance Test Suite.

Verifies:
1. All 11 registered default capabilities conform to CapabilityContract.
2. Canonical mutation classification (canonical_project_state vs none).
3. Fail-closed registration enforcement in CapabilityRegistry.register().
4. CapabilityContract field integrity and discovery filtering.
"""

from __future__ import annotations

import pytest
from typing import Any

from backend.core.capability_registry import (
    CAP_COMPLIANCE_VERIFY_SPACING,
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_EXPORT_EXECUTE_EXPORT,
    CAP_EXPORT_PLAN_EXPORT,
    CAP_EXPORT_VALIDATE_ARTIFACT,
    CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    CAP_IMPORT_EXECUTE_IMPORT,
    CAP_IMPORT_INSPECT_FILE,
    CAP_IMPORT_PLAN_IMPORT,
    CAP_SPATIAL_PLACE_DEVICES,
    CapabilityContract,
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)

CANONICAL_11_CAPABILITIES = [
    CAP_SPATIAL_PLACE_DEVICES,
    CAP_COMPLIANCE_VERIFY_SPACING,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    CAP_IMPORT_INSPECT_FILE,
    CAP_IMPORT_PLAN_IMPORT,
    CAP_IMPORT_EXECUTE_IMPORT,
    CAP_EXPORT_PLAN_EXPORT,
    CAP_EXPORT_EXECUTE_EXPORT,
    CAP_EXPORT_VALIDATE_ARTIFACT,
]


def test_all_11_capabilities_registered_with_valid_contracts() -> None:
    """Gate 1: Verify all 11 default capabilities exist and possess a valid CapabilityContract."""
    for cap_id in CANONICAL_11_CAPABILITIES:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None, f"Capability '{cap_id}' must be registered in default registry"
        assert cap.contract is not None, f"Capability '{cap_id}' must have a contract"
        assert isinstance(
            cap.contract, CapabilityContract
        ), f"Capability '{cap_id}' contract must be an instance of CapabilityContract"
        assert cap.contract.revision_binding in (
            "canonical_project_state",
            "none",
        ), f"Capability '{cap_id}' has invalid revision_binding: {cap.contract.revision_binding}"
        assert cap.contract.execution_mode in (
            "inline",
            "background_run",
        ), f"Capability '{cap_id}' has invalid execution_mode: {cap.contract.execution_mode}"
        assert isinstance(cap.contract.input_schema, dict), f"'{cap_id}' input_schema must be dict"
        assert isinstance(cap.contract.output_schema, dict), f"'{cap_id}' output_schema must be dict"
        assert isinstance(cap.contract.scopes, list), f"'{cap_id}' scopes must be a list"
        assert len(cap.contract.scopes) > 0, f"'{cap_id}' must declare at least one scope"
        assert cap.contract.execution_channel in (
            "sync",
            "async",
            "websocket",
            "worker",
            "inline",
        )
        assert cap.contract.risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "ENGINEERING_MUTATION")
        assert cap.contract.mutation_type in ("read_only", "idempotent_write", "state_mutation", "none")


def test_canonical_mutation_binding_classification() -> None:
    """Gate 1: Verify classification of canonical mutations vs read/calc capabilities."""
    # State-mutating capabilities that write to canonical project state
    import_exec = default_capability_registry.get(CAP_IMPORT_EXECUTE_IMPORT)
    assert import_exec is not None and import_exec.contract is not None
    assert import_exec.contract.revision_binding == "canonical_project_state"
    assert import_exec.contract.mutation_type == "state_mutation"

    export_exec = default_capability_registry.get(CAP_EXPORT_EXECUTE_EXPORT)
    assert export_exec is not None and export_exec.contract is not None
    assert export_exec.contract.revision_binding == "canonical_project_state"
    assert export_exec.contract.mutation_type == "state_mutation"

    # Deterministic calculations & verifications (binding = none)
    calc_caps = [
        CAP_SPATIAL_PLACE_DEVICES,
        CAP_COMPLIANCE_VERIFY_SPACING,
        CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
        CAP_ELECTRICAL_CALCULATE_BATTERY,
        CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    ]
    for cap_id in calc_caps:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None and cap.contract is not None
        assert cap.contract.revision_binding == "none"
        assert cap.contract.execution_mode == "inline"
        assert cap.contract.mutation_type == "read_only"

    # Inspection, planning, validation (binding = none)
    read_caps = [
        CAP_IMPORT_INSPECT_FILE,
        CAP_IMPORT_PLAN_IMPORT,
        CAP_EXPORT_PLAN_EXPORT,
        CAP_EXPORT_VALIDATE_ARTIFACT,
    ]
    for cap_id in read_caps:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None and cap.contract is not None
        assert cap.contract.revision_binding == "none"
        assert cap.contract.mutation_type == "read_only"


def test_capability_contract_dataclass_fields() -> None:
    """Verify CapabilityContract dataclass requires revision_binding and allows default execution_mode."""
    # Test valid instantiation with minimum required fields
    contract = CapabilityContract(
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        revision_binding="canonical_project_state",
    )
    assert contract.revision_binding == "canonical_project_state"
    assert contract.execution_mode == "inline"
    assert contract.mutation_type == "read_only"
    assert contract.risk == "LOW"
    assert contract.approval_policy == "auto"
    assert contract.timeout_seconds == 30.0
    assert contract.idempotent is True


def test_capability_registry_register_fail_closed_validation() -> None:
    """Gate 1: CapabilityRegistry.register() must strictly reject invalid or contract-lacking definitions."""
    registry = CapabilityRegistry()

    # 1. Reject non-CapabilityDefinition
    with pytest.raises(TypeError, match="instance of CapabilityDefinition"):
        registry.register("not a capability")  # type: ignore[arg-type]

    # 2. Reject empty capability_id
    contract = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="none",
    )
    with pytest.raises(ValueError, match="capability_id must be a non-empty string"):
        registry.register(
            CapabilityDefinition(
                capability_id="",
                name="Empty ID",
                description="desc",
                category="custom",
                contract=contract,
            )
        )

    # 3. Reject missing contract (contract=None)
    no_contract_def = CapabilityDefinition(
        capability_id="custom.no_contract",
        name="No Contract",
        description="desc",
        category="custom",
    )
    no_contract_def.contract = None
    with pytest.raises(ValueError, match="must have a valid CapabilityContract"):
        registry.register(no_contract_def)

    # 4. Reject invalid revision_binding
    invalid_binding_contract = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="invalid_binding",  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="Invalid revision_binding"):
        registry.register(
            CapabilityDefinition(
                capability_id="custom.invalid_binding",
                name="Invalid Binding",
                description="desc",
                category="custom",
                contract=invalid_binding_contract,
            )
        )

    # 5. Reject invalid execution_mode
    invalid_mode_contract = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="none",
        execution_mode="invalid_mode",  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="Invalid execution_mode"):
        registry.register(
            CapabilityDefinition(
                capability_id="custom.invalid_mode",
                name="Invalid Mode",
                description="desc",
                category="custom",
                contract=invalid_mode_contract,
            )
        )

    # 6. Reject non-dict schemas
    invalid_schema_contract = CapabilityContract(
        input_schema="not a dict",  # type: ignore[arg-type]
        output_schema={},
        revision_binding="none",
    )
    with pytest.raises(ValueError, match="Schemas.*must be dictionaries"):
        registry.register(
            CapabilityDefinition(
                capability_id="custom.invalid_schema",
                name="Invalid Schema",
                description="desc",
                category="custom",
                contract=invalid_schema_contract,
            )
        )

    # 7. Reject non-list scopes
    invalid_scopes_contract = CapabilityContract(
        input_schema={},
        output_schema={},
        revision_binding="none",
        scopes="not a list",  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="Scopes.*must be a list of strings"):
        registry.register(
            CapabilityDefinition(
                capability_id="custom.invalid_scopes",
                name="Invalid Scopes",
                description="desc",
                category="custom",
                contract=invalid_scopes_contract,
            )
        )


def test_capability_discovery_filtering() -> None:
    """Verify CapabilityRegistry.discover() filters by category and required scopes."""
    registry = default_capability_registry

    # Category filter
    electrical = registry.discover(categories=["electrical"])
    assert len(electrical) == 2
    assert all(c.category == "electrical" for c in electrical)

    spatial = registry.discover(categories=["spatial"])
    assert len(spatial) == 1
    assert spatial[0].capability_id == CAP_SPATIAL_PLACE_DEVICES

    # Scope filter
    write_only = registry.discover(scopes=["spatial:write"])
    assert any(c.capability_id == CAP_SPATIAL_PLACE_DEVICES for c in write_only)
    assert not any(c.capability_id == CAP_COMPLIANCE_VERIFY_SPACING for c in write_only)

    read_only = registry.discover(scopes=["compliance:read"])
    assert any(c.capability_id == CAP_COMPLIANCE_VERIFY_SPACING for c in read_only)
    assert not any(c.capability_id == CAP_SPATIAL_PLACE_DEVICES for c in read_only)
