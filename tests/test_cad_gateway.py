import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.cad_gateway import CADGateway, CADElement

@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app and log in."""
    os.environ["FIREAI_ENV"] = "development"
    os.environ["FIREAI_API_KEY"] = "test_key_for_cad_gateway_testing"

    with TestClient(app) as c:
        # Log in to get session cookie
        login_resp = c.post(
            "/api/v1/auth/login",
            json={"api_key": "test_key_for_cad_gateway_testing"}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        yield c

class TestCADGatewayEndpoints:
    """Test suite for the unified CAD/BIM Integration Engine endpoints."""

    def test_cad_gateway_singleton(self):
        """Verify that CADGateway is a thread-safe singleton."""
        gateway1 = CADGateway()
        gateway2 = CADGateway()
        assert gateway1 is gateway2

    @patch('backend.services.autocad_service.AutoCADService.connect')
    def test_cad_connect_autocad(self, mock_connect, client):
        """Verify connecting to AutoCAD."""
        # Setup mock connection to succeed and set connected flag
        def side_effect(*args, **kwargs):
            gateway = CADGateway()
            service = gateway.get_service("autocad")
            service.connected = True
            service.simulation_mode = True
            return True
        mock_connect.side_effect = side_effect

        response = client.post(
            "/api/v1/cad/connect",
            json={
                "provider": "autocad",
                "visible": True,
                "force_new": False,
                "method": "simulation"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connected"] is True
        assert data["simulation_mode"] is True

    @patch('backend.services.revit_service.RevitService.connect')
    def test_cad_connect_revit(self, mock_connect, client):
        """Verify connecting to Revit."""
        # Setup mock connection
        def side_effect(*args, **kwargs):
            gateway = CADGateway()
            service = gateway.get_service("revit")
            service._connected = True
            service._simulation_mode = True
            from backend.services.revit_service import ConnectionMethod
            service._connection_method = ConnectionMethod.SIMULATION
            return True
        mock_connect.side_effect = side_effect

        response = client.post(
            "/api/v1/cad/connect",
            json={
                "provider": "revit",
                "method": "simulation"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connected"] is True
        assert data["simulation_mode"] is True

    def test_cad_status(self, client):
        """Verify retrieving connection status."""
        # AutoCAD status
        response = client.get("/api/v1/cad/status?provider=autocad")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "autocad"
        assert data["status"]["connected"] is True

        # Revit status
        response = client.get("/api/v1/cad/status?provider=revit")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "revit"
        assert data["status"]["connected"] is True

    @patch('backend.services.autocad_service.AutoCADService.read_dwg')
    @patch('backend.services.autocad_service.AutoCADService.write_dwg')
    def test_cad_read_drawing_autocad(self, mock_write, mock_read, client):
        """Verify reading drawing elements from AutoCAD DWG/DXF."""
        mock_write.return_value = True
        mock_read.return_value = {
            "success": True,
            "entities": [
                {"handle": "H1", "object_name": "AcDbLine", "layer": "Walls", "color": 1},
                {"handle": "H2", "object_name": "AcDbCircle", "layer": "Devices", "color": 2}
            ],
            "count": 2,
            "source_file": "dummy.dxf"
        }

        # Create a temp DXF file path to validate path security
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            filepath = f.name
        try:
            # Read via endpoint
            response = client.post(
                "/api/v1/cad/read",
                json={
                    "provider": "autocad",
                    "filepath": filepath
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["provider"] == "autocad"
            assert data["element_count"] == 2
            assert data["elements"][0]["id"] == "H1"
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    @patch('backend.services.autocad_service.AutoCADService.draw_line')
    @patch('backend.services.autocad_service.AutoCADService.draw_polyline')
    @patch('backend.services.autocad_service.AutoCADService.draw_circle')
    @patch('backend.services.autocad_service.AutoCADService.draw_text')
    def test_cad_draw_primitives(self, mock_text, mock_circle, mock_polyline, mock_line, client):
        """Verify CAD drawing endpoints."""
        mock_line.return_value = "LINE_HANDLE"
        mock_polyline.return_value = "POLYLINE_HANDLE"
        mock_circle.return_value = "CIRCLE_HANDLE"
        mock_text.return_value = "TEXT_HANDLE"

        # Test draw line
        response = client.post(
            "/api/v1/cad/draw_line",
            json={
                "provider": "autocad",
                "start_point": [0.0, 0.0, 0.0],
                "end_point": [10.0, 10.0, 0.0],
                "layer": "Walls",
                "color": 1
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["handle"] == "LINE_HANDLE"

        # Test draw circle
        response = client.post(
            "/api/v1/cad/draw_circle",
            json={
                "provider": "autocad",
                "center": [5.0, 5.0, 0.0],
                "radius": 2.5,
                "layer": "SmokeDetectors",
                "color": 2
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["handle"] == "CIRCLE_HANDLE"

        # Test draw text
        response = client.post(
            "/api/v1/cad/draw_text",
            json={
                "provider": "autocad",
                "text": "FACP-01",
                "insertion_point": [2.0, 2.0, 0.0],
                "height": 0.5,
                "layer": "Text",
                "color": 3
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["handle"] == "TEXT_HANDLE"
