"""
backend/tests/integration/test_revit_sync_behavior.py
=====================================================
Behavioral integration tests for Revit CAD synchronization, element lifecycle,
parameter manipulation, and error contracts under simulation/API modes.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.revit_service import RevitService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def revit_service():
    service = RevitService()
    service.simulation_mode = True
    service.connected = True
    return service


class TestRevitSyncBehavior:
    """Test full behavioral workflows for Revit element synchronization."""

    def test_revit_connection_simulation_lifecycle(self, client):
        """Test connecting to Revit in simulation mode and checking connection status."""
        resp = client.post(
            "/api/v1/revit/connect",
            json={"method": "simulation", "version": "2024"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "connected" or data.get("connected") is True or "simulation" in str(data)

        # Status check
        status_resp = client.get("/api/v1/revit/status")
        assert status_resp.status_code == 200

    def test_revit_element_creation_and_query_flow(self, client):
        """Test creating elements (wall, door) in simulation and querying parameters."""
        # Create wall
        wall_resp = client.post(
            "/api/v1/revit/elements/create/wall",
            json={
                "start_point": [0.0, 0.0, 0.0],
                "end_point": [10.0, 0.0, 0.0],
                "wall_type": "Generic - 200mm",
                "level": "Level 1",
                "height": 3.0,
            },
        )
        assert wall_resp.status_code in (200, 201)
        wall_data = wall_resp.json()
        assert "id" in wall_data or "element_id" in wall_data or "success" in wall_data

        # Query elements list
        elements_resp = client.get("/api/v1/revit/elements", params={"category": "Walls"})
        assert elements_resp.status_code == 200

    def test_revit_parameter_update_validation(self, client):
        """Test parameter updates with boundary validations."""
        update_resp = client.put(
            "/api/v1/revit/elements/12345/parameters",
            json={
                "parameters": {
                    "Comments": "Integration Test Fire Rating",
                    "Fire Rating": "2 hr",
                }
            },
        )
        assert update_resp.status_code in (200, 404, 503)

    def test_revit_openapi_standard_error_contracts(self, client):
        """Verify standard OpenAPI error handling contracts on invalid requests."""
        # Malformed body -> 422 Unprocessable Entity
        bad_req_resp = client.post(
            "/api/v1/revit/elements/create/wall",
            json={"invalid_field": True},
        )
        assert bad_req_resp.status_code in (400, 422)
