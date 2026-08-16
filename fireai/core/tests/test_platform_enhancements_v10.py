"""
test_platform_enhancements_v10.py — Verification unit tests for 10 platform enhancements.
"""

from engineering_copilot.ai_agent.ai_agent import LocalCodeRAGRetriever
from fireai.core.acoustic_calculator import generate_acoustic_heatmap_matrix
from fireai.core.ahj_submittal_package import AHJSubmittalGenerator
from fireai.core.digital_twin import DigitalTwin
from fireai.core.digital_twin_sync import DigitalTwinSync
from fireai.core.hydraulic_solver import solve_hydraulics_from_revit
from fireai.core.pdf_report import generate_civil_defense_submittal_pdf
from fireai.core.smoke_simulation_state import AutoMeshBoundaryGenerator
from marine.output import MarineClassificationReportGenerator


def test_task1_auto_mesh_generator():
    gen = AutoMeshBoundaryGenerator(default_cell_size_m=0.1)
    doors = [{"x1": 0.0, "x2": 1.0, "y1": 0.0, "y2": 0.0, "z1": 0.0, "z2": 2.1}]
    res = gen.generate_fds_script("R-101", width_m=10.0, depth_m=8.0, height_m=3.0, doors=doors)
    assert "mesh_grid" in res
    assert res["mesh_grid"]["total_cells"] > 0
    assert "&MESH" in res["fds_script"]
    assert "&OBST" in res["fds_script"]
    assert "&VENT" in res["fds_script"]


def test_task2_acoustic_heatmap_matrix():
    speakers = [{"x": 5.0, "y": 5.0, "z": 3.0, "source_dba": 90.0}]
    res = generate_acoustic_heatmap_matrix(width_m=10.0, depth_m=10.0, speakers=speakers)
    assert res["rows"] > 0
    assert res["cols"] > 0
    assert len(res["spl_matrix"]) == res["rows"]
    assert len(res["sti_matrix"]) == res["rows"]
    assert res["max_spl_dba"] > res["min_spl_dba"]


def test_task3_ahj_submittal_package_electrical_integration():
    gen = AHJSubmittalGenerator()
    pkg = gen.assemble(project_name="Test Tower", project_address="Cairo")
    sec_names = [s.title for s in pkg.sections]
    assert "Voltage Drop Calculations" in sec_names
    assert "Battery Calculations" in sec_names
    vd_sec = next(s for s in pkg.sections if s.title == "Voltage Drop Calculations")
    bat_sec = next(s for s in pkg.sections if s.title == "Battery Calculations")
    assert "VOLTAGE DROP CALCULATIONS" in vd_sec.content
    assert "BATTERY CALCULATIONS" in bat_sec.content


def test_task5_hydraulic_revit_solver():
    revit_elements = [
        {
            "id": "PIPE-001",
            "category": "Pipes",
            "parameters": {"length_ft": 50.0, "diameter_in": 2.067, "flow_gpm": 120.0},
        }
    ]
    res = solve_hydraulics_from_revit(revit_elements, source_pressure_psi=60.0)
    assert res["total_pipes_evaluated"] == 1
    assert res["total_friction_loss_psi"] > 0
    assert res["residual_pressure_psi"] < 60.0


def test_task6_local_code_rag():
    retriever = LocalCodeRAGRetriever()
    res = retriever.retrieve_code_clause("كود الحريق المصري الدخان", jurisdiction="egyptian")
    assert res["results_count"] > 0
    assert len(res["matched_clauses"]) > 0


def test_task7_marine_classification_reports():
    dnv = MarineClassificationReportGenerator.generate_dnv_compliance_report(
        "MV Baz", "IMO 9876543"
    )
    lr = MarineClassificationReportGenerator.generate_lloyds_register_report(
        "SS Spark", "IMO 1234567"
    )
    assert dnv["society"] == "DNV GL"
    assert dnv["is_approved"] is True
    assert lr["society"] == "Lloyd's Register (LR)"
    assert lr["is_approved"] is True


def test_task8_digital_twin_mqtt_bacnet():
    twin = DigitalTwin(building_id="B-TEST")
    sync = DigitalTwinSync(twin=twin)
    mqtt_res = sync.handle_mqtt_telemetry(
        "facp/B-TEST/detector/D-999/telemetry", {"detector_id": "D-999", "status": "OK"}
    )
    bacnet_res = sync.handle_bacnet_ip_event("BI-101", 1)
    assert mqtt_res["protocol"] == "MQTT"
    assert bacnet_res["protocol"] == "BACnet/IP"


def test_task10_civil_defense_pdf():
    class DummyReport:
        building_id = "B-001"

    path = generate_civil_defense_submittal_pdf(
        DummyReport(), "/tmp/test_report.txt", language="bilingual"
    )
    assert path.endswith("_civil_defense.txt") or path.endswith(".txt")
