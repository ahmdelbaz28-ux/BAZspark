"""Phase 10 — External CAD Control E2E Integration Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 10 & PHASE10_DELIVERY_CONTRACT.md (Stream S1):
- E2E flow: ControlRequest / capability invocation → validation against command_registry → evidence generation.
- Desktop agent execution channel conformance.
- Real element ID creation and project revision synchronization.
- Fail-closed rejection of disallowed actions.
"""

from __future__ import annotations

import pytest

from backend.core.capability_registry import default_capability_registry
from backend.core.cad_control_contracts import (
    CAP_CAD_AUTOCAD_DRAW_LINE,
    CAP_CAD_EXECUTE_DESKTOP_COMMAND,
    CAP_CAD_REVIT_CREATE_WALL,
    CAP_CAD_REVIT_GET_ELEMENTS,
)


def test_cad_capabilities_registered_with_desktop_agent_channel():
    cad_cap_ids = [
        CAP_CAD_REVIT_CREATE_WALL,
        CAP_CAD_REVIT_GET_ELEMENTS,
        CAP_CAD_AUTOCAD_DRAW_LINE,
        CAP_CAD_EXECUTE_DESKTOP_COMMAND,
    ]
    for cap_id in cad_cap_ids:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None, f"Capability '{cap_id}' must be registered in default_capability_registry"
        assert cap.contract is not None
        assert cap.contract.execution_channel == "desktop_agent"
        assert cap.category == "cad"
        assert cap.contract.risk in ("HIGH", "LOW")
        assert cap.contract.mutation_type in ("state_mutation", "read_only")


def test_revit_create_wall_e2e_evidence_and_revision():
    cap = default_capability_registry.get(CAP_CAD_REVIT_CREATE_WALL)
    assert cap is not None and cap.handler is not None

    payload = {
        "start_point": [0, 0, 0],
        "end_point": [6000, 0, 0],
        "height": 3200.0,
        "wall_type": "Exterior - Brick on CMU",
        "level": "Level 1",
        "project_id": "test_cad_project_01",
    }

    result = cap.handler(payload)
    assert result["success"] is True
    assert result["status"] == "created"
    assert "element_id" in result
    assert result["element_id"].startswith("REVIT-WALL-")
    assert "evidence" in result
    evidence = result["evidence"]
    assert evidence["wall_type"] == "Exterior - Brick on CMU"
    assert evidence["length_mm"] == 6000.0
    assert evidence["service"] == "revit"
    assert evidence["action"] == "create_wall"
    assert "audit_hash" in result
    assert len(result["audit_hash"]) == 64


def test_revit_get_elements_e2e():
    cap = default_capability_registry.get(CAP_CAD_REVIT_GET_ELEMENTS)
    assert cap is not None and cap.handler is not None

    payload = {"category": "Doors", "limit": 50}
    result = cap.handler(payload)
    assert result["success"] is True
    assert result["count"] > 0
    assert isinstance(result["elements"], list)
    assert "evidence" in result
    assert "audit_hash" in result


def test_autocad_draw_line_e2e_evidence():
    cap = default_capability_registry.get(CAP_CAD_AUTOCAD_DRAW_LINE)
    assert cap is not None and cap.handler is not None

    payload = {
        "start_point": [10.0, 20.0],
        "end_point": [110.0, 20.0],
        "layer": "A-WALL",
        "color": 1,
        "project_id": "test_acad_project_01",
    }

    result = cap.handler(payload)
    assert result["success"] is True
    assert result["status"] == "drawn"
    assert result["handle"].startswith("ACAD-LINE-")
    assert result["entity_type"] == "LINE"
    assert result["evidence"]["layer"] == "A-WALL"
    assert "audit_hash" in result


def test_generic_desktop_command_dispatch_and_fail_closed():
    cap = default_capability_registry.get(CAP_CAD_EXECUTE_DESKTOP_COMMAND)
    assert cap is not None and cap.handler is not None

    # Valid command
    valid_payload = {
        "service": "revit",
        "command": "create_floor",
        "params": {"boundary_points": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]},
        "project_id": "test_cad_project_02",
    }
    res = cap.handler(valid_payload)
    assert res["success"] is True
    assert "audit_hash" in res

    # Disallowed command (fail-closed)
    invalid_payload = {
        "service": "revit",
        "command": "malicious_unregistered_action",
        "params": {},
    }
    with pytest.raises(ValueError, match="is not allowed"):
        cap.handler(invalid_payload)
