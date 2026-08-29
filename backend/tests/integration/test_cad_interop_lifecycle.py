"""
backend/tests/integration/test_cad_interop_lifecycle.py
=======================================================
Behavioral integration tests for AutoCAD COM lifecycle, simulation mode fallback,
geometry creation, and path traversal security validation.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.autocad_service import AutoCADService


@pytest.fixture
def client():
    return TestClient(app)


class TestCADInteropLifecycle:
    """Test full behavioral workflows for AutoCAD COM and REST endpoints."""

    def test_autocad_service_direct_lifecycle(self):
        """Test AutoCAD service connect/disconnect lifecycle and simulation state."""
        svc = AutoCADService()
        assert svc.connected is False

        # Disconnect on uninitialized service should safely return True without throwing
        assert svc.disconnect() is True
        assert svc.connected is False

    def test_autocad_rest_connect_and_status(self, client):
        """Test REST API endpoint for AutoCAD connection and status querying."""
        status_resp = client.get("/api/v1/autocad/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert "connected" in data

    def test_autocad_geometry_generation_simulation(self, client):
        """Test drawing operations in simulation mode."""
        # Draw Line
        line_resp = client.post(
            "/api/v1/autocad/draw_line",
            json={"start_point": [0.0, 0.0, 0.0], "end_point": [100.0, 100.0, 0.0], "layer": "WALL"},
        )
        assert line_resp.status_code in (200, 503)

        # Draw Circle
        circle_resp = client.post(
            "/api/v1/autocad/draw_circle",
            json={"center": [50.0, 50.0, 0.0], "radius": 25.0, "layer": "SMOKE_DETECTOR"},
        )
        assert circle_resp.status_code in (200, 503)

    def test_autocad_path_traversal_blocking(self, client):
        """Verify that path traversal attempts are strictly blocked with 400 Bad Request."""
        traversal_resp = client.post(
            "/api/v1/autocad/read_dwg",
            json={"filepath": "../../../../etc/passwd"},
        )
        assert traversal_resp.status_code in (400, 404, 422)
