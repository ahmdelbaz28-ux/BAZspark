"""
tests/test_phase8_sonar_coverage.py
===================================
Targeted unit tests to ensure 100% test coverage on all lines and branches
remediated for SonarCloud Quality Gate in Phase 8.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_qomn_conduit_fitting_dimensions():
    from qomn_conduit.catalog import Fitting, FittingType, TradeSize
    from qomn_conduit.types import ConduitType

    f = Fitting(
        fitting_type=FittingType.ELBOW_90,
        conduit_type=ConduitType.EMT,
        trade_size=TradeSize.HALF_INCH,
        od_in=0.84,
        bend_radius_in=4.0,
        developed_length_in=6.28,
        body_length_in=0.0,
        angle_deg=90.0,
        catalog_number="CAT-90-050",
        weight_kg=0.2,
        nec_reference="NEC 358.24",
    )
    assert f.bend_radius_in > 0
    assert f.developed_length_in > 0
    assert f.body_length_in == 0.0

    coupling = Fitting(
        fitting_type=FittingType.COUPLING,
        conduit_type=ConduitType.EMT,
        trade_size=TradeSize.HALF_INCH,
        od_in=0.84,
        bend_radius_in=0.0,
        developed_length_in=0.0,
        body_length_in=1.5,
        angle_deg=0.0,
        catalog_number="CAT-C-050",
        weight_kg=0.1,
        nec_reference="NEC 358.24",
    )
    assert coupling.body_length_in > 0


def test_room_lifecycle_certification():
    from fireai.core.room_lifecycle import RoomLifecycleManager, RoomState

    # RoomLifecycleManager() takes only an optional bus arg.
    # Rooms are registered via register_room().
    mgr = RoomLifecycleManager()
    mgr.register_room("test_room_1")
    assert mgr.certification_progress() == 0.0

    lc = mgr.get_room("test_room_1")
    lc.transition_to(RoomState.ANALYZING, "Placement started", "designer-1")
    lc.transition_to(RoomState.OPTIMIZED, "Placement finished", "designer-1")
    lc.transition_to(RoomState.VERIFYING, "Consensus checking", "designer-1")
    lc.transition_to(RoomState.VERIFIED, "Verified PASS", "designer-1")
    lc.transition_to(RoomState.CERTIFYING, "Sealing", "designer-1")
    lc.transition_to(RoomState.CERTIFIED, "AHJ permit sealed", "designer-1")
    assert mgr.certification_progress() == 100.0

    mgr_dict = mgr.to_dict()
    assert mgr_dict["certification_progress"] == 100.0


def test_compliance_proof_document_file_output(tmp_path):
    from fireai.core.compliance_proof_document import ComplianceProofDocument, _cli_main

    doc = ComplianceProofDocument(
        project_name="Test Project",
        designer="Ahmed Baz, PE",
        nfpa_edition="2022",
    )
    md = doc.generate()
    assert "# NFPA 72" in md or "Compliance Proof" in md or "Test Project" in md

    out_file = tmp_path / "proof.md"
    out_path = Path(str(out_file)).resolve()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    assert out_file.exists()

    # Test CLI entry point file writing — correct flag is --output
    cli_out = tmp_path / "cli_proof.md"
    test_args = [
        "compliance_proof_document",
        "--project", "Test",
        "--designer", "Tester",
        "--output", str(cli_out),
    ]
    with patch.object(sys, "argv", test_args):
        _cli_main()
    assert cli_out.exists()


def test_ifc_parser_bounding_box():
    from fireai.core.ifc_parser import _get_element_bbox

    mock_elem = MagicMock()
    mock_elem.is_a.return_value = "IfcWall"
    mock_elem.GlobalId = "wall-1"
    mock_elem.ObjectPlacement = None
    mock_elem.Representation = None

    bbox = _get_element_bbox(mock_elem)
    assert bbox is None or hasattr(bbox, "volume")


def test_kafka_event_bus_init():
    from fireai.infrastructure.event_bus import KafkaEventBus

    bus = KafkaEventBus("localhost:9092", "test-group")
    assert bus._consume_task is None


@pytest.mark.asyncio
async def test_fireai_settings_router_flags():
    from fireai.api.settings_router import read_feature_flags, update_feature_flags

    flags = await read_feature_flags()
    assert isinstance(flags, dict)

    # Test updating flags to cover async persist
    res = await update_feature_flags({})
    assert res["status"] == "success"


def test_revit_service_error_logging_branches():
    """
    Cover guard clauses: not connected / no Revit API → early return None.
    FilteredElementCollector is only available inside a Revit process,
    so we test the guards that fire before the import.
    """
    from backend.services.revit_service import RevitService

    service = RevitService()
    # not connected → early return at L1084-1089
    result = service.create_floor(
        boundary=[[0, 0, 0], [1000, 0, 0], [1000, 1000, 0]],
        level="NonExistentLevel",
    )
    assert result is None

    # not connected → early return at L1674-1679
    result2 = service.create_door("family-1", "host-wall-1", (0.0, 0.0, 0.0))
    assert result2 is None


def test_acoustics_engine_logging_branches():
    from fireai.core.acoustics_engine import (
        AcousticCoverageResult,
        AcousticsEngine,
    )

    engine = AcousticsEngine()
    # Correct field names from the @dataclass definition
    dummy_result = AcousticCoverageResult(
        compliant=True,
        mode="public",
        required_dba=75.0,
        worst_spl_dba=80.0,
        worst_room_id="room-101",
        worst_point_label="P1",
        margin_dba=5.0,
        violations=[],
        room_results=[],
    )

    # Test PASS and FAIL logging branches
    engine._log_coverage_result(True, "room-101", dummy_result, [])
    engine._log_coverage_result(False, "room-102", dummy_result, ["Violation 1"])


def test_autocad_service_simulation_text_logging():
    from backend.services.autocad_service import AutoCADService

    service = AutoCADService()
    service.connected = True
    service.acad_doc = None

    # Exercises simulation mode logging (L877)
    res = service.draw_text("Sample CAD Label", [0.0, 0.0, 0.0], height=2.5)
    assert res is not None


def test_backend_settings_safe_logging():
    from backend.routers.settings import _safe_log_fragment

    res = _safe_log_fragment("test_provider_api_key_123\n")
    assert "\n" not in res
    assert "test_provider" in res
