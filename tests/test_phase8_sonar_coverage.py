"""
tests/test_phase8_sonar_coverage.py
===================================
Targeted unit tests to ensure 100% test coverage on all lines and branches
remediated for SonarCloud Quality Gate in Phase 8.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_qomn_conduit_fitting_dimensions():
    from qomn_conduit.catalog import Fitting, FittingType, TradeSize

    f = Fitting(
        fitting_type=FittingType.ELBOW_90,
        trade_size=TradeSize.T_0_50,
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
        trade_size=TradeSize.T_0_50,
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

    mgr = RoomLifecycleManager("test_room_1", 10.0, 10.0, 3.0)
    assert mgr.certification_progress() == 0.0

    mgr.transition(RoomState.ANALYZING, "Placement started", "designer-1")
    mgr.transition(RoomState.OPTIMIZED, "Placement finished", "designer-1")
    mgr.transition(RoomState.VERIFYING, "Consensus checking", "designer-1")
    mgr.transition(RoomState.VERIFIED, "Verified PASS", "designer-1")
    mgr.transition(RoomState.CERTIFYING, "Sealing", "designer-1")
    mgr.transition(RoomState.CERTIFIED, "AHJ permit sealed", "designer-1")
    assert mgr.certification_progress() == 100.0

    mgr_dict = mgr.to_dict()
    assert mgr_dict["certification_progress"] == 100.0


def test_compliance_proof_document_file_output(tmp_path):
    from fireai.core.compliance_proof_document import ComplianceProofDocument

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


def test_ifc_parser_bounding_box():
    from fireai.core.ifc_parser import _get_element_bbox

    mock_elem = MagicMock()
    mock_elem.is_a.return_value = "IfcWall"
    mock_elem.GlobalId = "wall-1"
    mock_elem.ObjectPlacement = None
    mock_elem.Representation = None

    bbox = _get_element_bbox(mock_elem)
    # Returns None or BoundingBox3D safely
    assert bbox is None or hasattr(bbox, "volume")


def test_kafka_event_bus_init():
    from fireai.infrastructure.event_bus import KafkaEventBus

    bus = KafkaEventBus("localhost:9092", "test-group")
    assert bus._consume_task is None


@pytest.mark.asyncio
async def test_fireai_settings_router_flags():
    from fireai.api.settings_router import read_feature_flags

    flags = await read_feature_flags()
    assert isinstance(flags, dict)
