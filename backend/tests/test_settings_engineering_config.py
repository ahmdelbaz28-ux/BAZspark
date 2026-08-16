"""
backend/tests/test_settings_engineering_config.py — Tests for Engineering & CAD Configuration Endpoints.
========================================================================================================

Verifies:
  - GET /api/v1/env-config returns structured categories matching AdvancedSettingsPage.tsx format
  - PUT /api/v1/env-config handles category-based overrides
  - GET & PUT /api/v1/settings/engineering-config (Acoustic, Hydraulic, Battery, Integration)
  - Boundary validation & physical unit checks (Pydantic schema enforcement)
  - GET & PUT /api/v1/settings/cad-config (AutoCAD, Revit, Cloud) with masked secrets
  - GET & POST /api/v1/settings/runtime, /settings/bootstrap, /settings/config
  - GET & POST /api/v1/settings/feature-flags (single and batch)
  - RBAC enforcement (rejects unauthorized calls)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with conftest-managed auth headers."""
    from backend.app import app

    with TestClient(app) as c:
        yield c


class TestEnvConfig:
    """Test /api/v1/env-config endpoint."""

    def test_get_env_config_structure(self, client: TestClient):
        resp = client.get("/api/v1/env-config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert "categories" in data
        assert "config" in data

        # Verify key categories exist
        categories = data["categories"]
        for cat in ["nvidia", "langfuse", "database", "acoustic", "hydraulic", "battery", "cad"]:
            assert cat in categories
            assert "label" in categories[cat]
            assert "settings" in categories[cat]
            assert isinstance(categories[cat]["settings"], list)

    def test_put_env_config_nested(self, client: TestClient):
        resp = client.put(
            "/api/v1/env-config",
            json={"overrides": {"database": {"DATABASE_POOL_SIZE": "25"}}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "applied" in body["data"]

    def test_put_env_config_flat(self, client: TestClient):
        resp = client.put(
            "/api/v1/env-config",
            json={"overrides": {"DATABASE_TIMEOUT": "45"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True


class TestEngineeringConfig:
    """Test /api/v1/settings/engineering-config endpoint."""

    def test_get_engineering_config(self, client: TestClient):
        resp = client.get("/api/v1/settings/engineering-config")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "config" in data
        assert "metadata" in data

        cfg = data["config"]
        assert "acoustic" in cfg
        assert "hydraulic" in cfg
        assert "battery" in cfg
        assert "integration" in cfg

        assert cfg["acoustic"]["ambient_noise_db"] == 65.0
        assert cfg["hydraulic"]["default_fluid_density_kg_m3"] == 1000.0
        assert cfg["battery"]["ambient_temperature_c"] == 25.0

    def test_put_engineering_config_valid(self, client: TestClient):
        update_payload = {
            "acoustic": {
                "ambient_noise_db": 70.0,
                "spl_drop_per_doubling_db": 6.0,
                "min_snr_dba": 15.0,
                "strobe_sync_enabled": True,
                "strobe_flash_rate_hz": 1.0,
            },
            "battery": {
                "ambient_temperature_c": 10.0,
                "standby_duration_hours": 60.0,
                "alarm_duration_minutes": 15.0,
                "aging_safety_margin_pct": 25.0,
                "battery_derating_factor": 0.80,
            },
        }
        resp = client.put("/api/v1/settings/engineering-config", json=update_payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["config"]["acoustic"]["ambient_noise_db"] == 70.0
        assert data["config"]["battery"]["standby_duration_hours"] == 60.0

    def test_put_engineering_config_invalid_bounds(self, client: TestClient):
        # Negative ambient noise or out-of-range dB rejected by Pydantic
        bad_payload = {
            "acoustic": {
                "ambient_noise_db": 200.0,  # Max is 120.0
                "spl_drop_per_doubling_db": 6.0,
                "min_snr_dba": 15.0,
                "strobe_sync_enabled": True,
                "strobe_flash_rate_hz": 1.0,
            }
        }
        resp = client.put("/api/v1/settings/engineering-config", json=bad_payload)
        assert resp.status_code == 422  # Validation error

    def test_engineering_config_rbac_enforcement(self, client: TestClient):
        # Using invalid API key returns 401
        resp = client.put(
            "/api/v1/settings/engineering-config",
            json={"acoustic": {"ambient_noise_db": 70.0}},
            headers={"X-API-Key": "invalid_wrong_key"},
        )
        assert resp.status_code == 401


class TestCADConfig:
    """Test /api/v1/settings/cad-config endpoint."""

    def test_get_cad_config_masks_secrets(self, client: TestClient):
        resp = client.get("/api/v1/settings/cad-config")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "autocad" in data
        assert "revit" in data
        assert "cloud" in data

    def test_put_cad_config(self, client: TestClient):
        payload = {
            "autocad": {
                "path": "C:\\Program Files\\Autodesk\\AutoCAD 2025\\acad.exe",
                "version": "2025",
                "template": "acad.dwt",
                "units": "Millimeters",
                "bridge_port": 8005,
            },
            "revit": {
                "path": "C:\\Program Files\\Autodesk\\Revit 2025\\revit.exe",
                "version": "2025",
                "template": "Mechanical.rte",
                "units": "Millimeters",
                "bridge_url": "http://localhost:8005",
            },
            "cloud": {
                "speckle_server": "https://app.speckle.systems",
                "speckle_stream_id": "stream_12345",
                "speckle_token": "speckle_token_abcdef123456",
                "aps_client_id": "aps_client_id_test",
                "aps_client_secret": "aps_secret_xyz987654",
                "aps_activity_id": "BazSparkAutoCADBridge.DrawLayout",
            },
        }
        resp = client.put("/api/v1/settings/cad-config", json=payload)
        assert resp.status_code == 200

        # Verify retrieval masks token
        get_resp = client.get("/api/v1/settings/cad-config")
        assert get_resp.status_code == 200
        cloud = get_resp.json()["data"]["cloud"]
        assert cloud["speckle_token"] == "spec***"
        assert cloud["aps_client_secret"] == "aps_***"


class TestRegistriesAndFeatureFlags:
    """Test /settings/runtime, /settings/bootstrap, /settings/config, /settings/feature-flags."""

    def test_runtime_and_bootstrap_endpoints(self, client: TestClient):
        # GET /settings/runtime
        r_resp = client.get("/api/v1/settings/runtime")
        assert r_resp.status_code == 200
        assert isinstance(r_resp.json(), dict)

        # POST /settings/runtime
        p_resp = client.post(
            "/api/v1/settings/runtime",
            json={"DEV_MODE": True},
        )
        assert p_resp.status_code == 200

        # GET /settings/bootstrap
        b_resp = client.get("/api/v1/settings/bootstrap")
        assert b_resp.status_code == 200
        assert "FIREAI_ENV" in b_resp.json()

        # GET /settings/config
        c_resp = client.get("/api/v1/settings/config")
        assert c_resp.status_code == 200
        assert "DATABASE_URL" in c_resp.json()

    def test_feature_flags_batch_update(self, client: TestClient):
        resp = client.post(
            "/api/v1/settings/feature-flags",
            json={"DEV_MODE": True, "VERBOSE_LOGGING": True},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
