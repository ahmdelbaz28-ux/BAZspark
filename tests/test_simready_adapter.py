"""
tests/test_simready_adapter.py — NVIDIA SimReady Adapter Unit Tests
=====================================================================

Tests for SimReadyAdapter and CAD-to-SimReady digital twin conversion pipeline.
"""

import tempfile
from pathlib import Path

from backend.services.digital_twin_service import DigitalTwinService
from backend.services.simready_adapter import (
    SimReadyAdapter,
    SimReadyPipelineConfig,
)


class TestSimReadyAdapter:
    """Test suite for SimReadyAdapter."""

    def test_detect_source_format(self):
        """Test file extension detection."""
        adapter = SimReadyAdapter()
        assert adapter.detect_source_format("model.dwg") == "dwg"
        assert adapter.detect_source_format("building.ifc") == "ifc"
        assert adapter.detect_source_format("robot.urdf") == "urdf"
        assert adapter.detect_source_format("scene.usda") == "usd"
        assert adapter.detect_source_format("package.usdz") == "usdz"
        assert adapter.detect_source_format("unknown.xyz") == "unknown"

    def test_pipeline_nonexistent_source(self):
        """Test pipeline behavior when source file does not exist."""
        adapter = SimReadyAdapter()
        result = adapter.run_pipeline("non_existent_file.dwg")
        assert not result.success
        assert "does not exist" in result.errors[0]

    def test_pipeline_with_mock_dwg(self):
        """Test pipeline run with a sample DWG file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_dwg = Path(tmp_dir) / "sample_fire_alarm.dwg"
            sample_dwg.write_text("MOCK DWG HEADER DATA")

            output_root = Path(tmp_dir) / "output_simready"
            adapter = SimReadyAdapter()
            cfg = SimReadyPipelineConfig(
                simready_profile="Prop-Robotics-Neutral",
                property_assignment_intent="run",
                output_root=str(output_root),
            )
            result = adapter.run_pipeline(str(sample_dwg), cfg)

            assert result.success
            assert result.source_format == "dwg"
            assert result.simready_profile == "Prop-Robotics-Neutral"
            assert result.output_usd_path is not None
            assert result.conformed_usd_path is not None
            assert Path(result.conformed_usd_path).exists()
            assert result.deliverable_root is not None
            assert Path(result.deliverable_root).exists()

    def test_digital_twin_service_simready_integration(self):
        """Test DigitalTwinService.convert_cad_to_simready method integration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_ifc = Path(tmp_dir) / "building.ifc"
            sample_ifc.write_text("MOCK IFC DATA")

            service = DigitalTwinService()
            output_root = Path(tmp_dir) / "ifc_simready"
            res = service.convert_cad_to_simready(
                source_asset=str(sample_ifc),
                profile="Prop-Robotics-Neutral",
                property_assignment="run",
                output_root=str(output_root),
            )

            assert res["success"] is True
            assert res["source_format"] == "ifc"
            assert res["simready_profile"] == "Prop-Robotics-Neutral"
            assert res["output_usd_path"] is not None
            assert res["conformed_usd_path"] is not None
            assert res["deliverable_root"] is not None
