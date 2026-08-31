"""Phase 10 — Command Registry Unit & Contract Tests.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 10 & PHASE10_DELIVERY_CONTRACT.md (Stream S1):
- Fail-closed validation for desktop agent commands.
- Parameter schema validation and normalization.
- Rejection of unregistered commands and services.
"""

from __future__ import annotations

import pytest

from backend.core import command_registry


def test_command_registry_loads_successfully():
    registry = command_registry.load_registry(force_reload=True)
    assert isinstance(registry, dict)
    assert registry.get("version") == 1
    assert "services" in registry
    assert "revit" in registry["services"]
    assert "autocad" in registry["services"]


def test_get_service_names():
    services = command_registry.get_service_names()
    assert "revit" in services
    assert "autocad" in services


def test_revit_allowed_commands():
    assert command_registry.is_allowed("revit", "create_wall")
    assert command_registry.is_allowed("revit", "get_elements")
    assert command_registry.is_allowed("revit", "list_elements")  # Alias
    assert command_registry.is_allowed("revit", "place_family_instance")
    assert not command_registry.is_allowed("revit", "unregistered_dangerous_action")


def test_autocad_allowed_commands():
    assert command_registry.is_allowed("autocad", "draw_line")
    assert command_registry.is_allowed("autocad", "draw_circle")
    assert command_registry.is_allowed("autocad", "insert_block")
    assert not command_registry.is_allowed("autocad", "drop_database")


def test_validate_params_success_and_failure():
    # Valid revit create_wall params
    err = command_registry.validate_params(
        "revit", "create_wall", {"start_point": [0, 0, 0], "end_point": [5000, 0, 0]}
    )
    assert err is None

    # Missing required end_point
    err_missing = command_registry.validate_params(
        "revit", "create_wall", {"start_point": [0, 0, 0]}
    )
    assert err_missing is not None
    assert "Missing required params" in err_missing
    assert "end_point" in err_missing

    # Unknown command fail-closed
    err_unknown = command_registry.validate_params("revit", "nonexistent_cmd", {})
    assert err_unknown is not None
    assert "Unknown revit command" in err_unknown


def test_param_normalization_revit():
    raw_params = {
        "start_point": [100, 200],
        "end_point": [500, 600],
        "height": 3500.0,
        "wall_type": "Curtain Wall",
    }
    normalized = command_registry.normalize_params("revit", "create_wall", raw_params)
    assert normalized["x1"] == 100.0
    assert normalized["y1"] == 200.0
    assert normalized["x2"] == 500.0
    assert normalized["y2"] == 600.0
    assert normalized["height"] == 3500.0
    assert normalized["wall_type"] == "Curtain Wall"


def test_expand_update_parameters():
    params = {
        "element_id": "WALL-1234",
        "parameters": {"Unconnected Height": 4000.0, "Comments": "Fire Rated"},
    }
    action, calls = command_registry.expand_update_parameters(params)
    assert action == "set_parameter"
    assert len(calls) == 2
    assert {"element_id": "WALL-1234", "id": "WALL-1234", "name": "Unconnected Height", "value": 4000.0} in calls
