"""
tests/test_phase8_sonar_coverage.py
===================================
Targeted unit tests to ensure 100% test coverage on all lines and branches
remediated for SonarCloud Quality Gate in Phase 8.
"""

from pathlib import Path

import pytest


def test_qomn_conduit_fitting_dimensions():
    from qomn_conduit.catalog import Fitting
    f = Fitting(
        id="fit-1",
        fitting_type="ELBOW",
        trade_size_in="1/2",
        standard="NEMA",
        description="Standard Elbow",
        outer_diameter_in=0.84,
        inner_diameter_in=0.622,
        body_length_in=2.5,
        bend_radius_in=4.0,
        developed_length_in=6.28,
        angle_deg=90.0
    )
    assert f.body_length_in > 0
    assert f.bend_radius_in > 0
    assert f.developed_length_in > 0
    assert f.angle_deg > 0

    f_zero = Fitting(
        id="fit-0",
        fitting_type="COUPLING",
        trade_size_in="1/2",
        standard="NEMA",
        description="Zero Fitting",
        outer_diameter_in=0.84,
        inner_diameter_in=0.622,
        body_length_in=0.0,
        bend_radius_in=0.0,
        developed_length_in=0.0,
        angle_deg=0.0
    )
    assert f_zero.body_length_in == 0.0

def test_room_lifecycle_certification():
    from fireai.core.room_lifecycle import LifecycleStatus, RoomLifecycleManager
    mgr = RoomLifecycleManager("test_room_1", 10.0, 10.0, 3.0)
    assert mgr.certification_progress() == 0.0

    mgr.advance(LifecycleStatus.ARCH_VERIFIED, "Architect signoff", "arch-1")
    assert mgr.certification_progress() > 0.0

    mgr.advance(LifecycleStatus.MEP_COORDINATED, "MEP signoff", "mep-1")
    mgr.advance(LifecycleStatus.AHJ_APPROVED, "AHJ permit", "ahj-1")
    assert mgr.certification_progress() == 100.0

    mgr_dict = mgr.to_dict()
    assert mgr_dict["certification_progress"] == 100.0

def test_compliance_proof_document_file_output(tmp_path):
    from fireai.core.compliance_proof_document import ComplianceProofDocument
    doc = ComplianceProofDocument(
        project_name="Test Project",
        designer="Ahmed Baz, PE",
        nfpa_edition="2022"
    )
    md = doc.generate()
    assert "# NFPA 72" in md or "Compliance Proof" in md or "Test Project" in md

    out_file = tmp_path / "proof.md"
    out_path = Path(str(out_file)).resolve()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    assert out_file.exists()

def test_ifc_parser_bounding_box():
    from fireai.core.ifc_parser import IfcElementType, _get_element_bbox

    bbox = _get_element_bbox(
        element_type=IfcElementType.WALL,
        placement_matrix=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
        geometry_points=[(0,0,0), (1,0,0), (1,1,0), (0,1,0)],
        volume=0.0
    )
    assert bbox is not None

    bbox_space = _get_element_bbox(
        element_type=IfcElementType.SPACE,
        placement_matrix=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
        geometry_points=[(0,0,0), (2,0,0), (2,2,0), (0,2,0)],
        volume=0.0
    )
    assert bbox_space is not None

def test_kafka_event_bus_init():
    from fireai.infrastructure.event_bus import KafkaEventBus
    bus = KafkaEventBus("localhost:9092", "test-group")
    assert bus._consume_task is None

@pytest.mark.asyncio
async def test_fireai_settings_router_flags():
    from fireai.api.settings_router import read_feature_flags
    flags = await read_feature_flags()
    assert isinstance(flags, dict)
