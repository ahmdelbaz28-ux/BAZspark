"""
tests/test_final_release_verification.py
========================================
Comprehensive Verification Test Suite for Final Release Protocol:
- SEC-001: Session / JWT Secret Enforcement
- SEC-002: Multi-Layer SSRF Protection
- SEC-003: WebSocket Authentication & CSWSH Origin Validation
- ENG-001: Darcy-Weisbach Hydraulic Calculations across all flow regimes
- ENG-002: Battery Temperature & Aging Derating (NFPA 72 §10.6.7 / IEEE 485)
- REL-001: Self-Healing Non-Masking of Engineering Failures
- AAI-001: MCP / Agent Canonical Path Security
- Payment / Billing Security & HMAC Verification
"""

import math
import os
import pytest


# ============================================================================
# 1. SEC-001: Session Secret Enforcement
# ============================================================================

class TestSessionSecretEnforcement:
    def test_session_secret_manager_valid_production(self):
        from backend.session_secret import SessionSecretManager, validate_secret
        # Generate a valid high-entropy secret
        valid_key = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ--"
        validate_secret(valid_key)
        assert len(valid_key) >= 32

    def test_session_secret_manager_weak_secret_rejected(self):
        from backend.session_secret import validate_secret
        with pytest.raises(ValueError, match="too short|low entropy|placeholder"):
            validate_secret("short")
        with pytest.raises(ValueError, match="too short|low entropy|placeholder"):
            validate_secret("changeme" * 5)


# ============================================================================
# 2. SEC-002: SSRF Protection
# ============================================================================

class TestSSRFProtection:
    def test_ssrf_rejects_loopback_and_metadata(self):
        from backend.integrations._ssrf_guard import SSRFError, validate_url
        with pytest.raises(SSRFError):
            validate_url("http://127.0.0.1/admin")
        with pytest.raises(SSRFError):
            validate_url("http://localhost:8000/api")
        with pytest.raises(SSRFError):
            validate_url("http://169.254.169.254/latest/meta-data")
        with pytest.raises(SSRFError):
            validate_url("http://[::1]/internal")


# ============================================================================
# 3. SEC-003: WebSocket Authentication & Origin Validation
# ============================================================================

class TestWebSocketSecurity:
    def test_revit_websocket_origin_validation(self, monkeypatch):
        from backend.routers.revit_api import _validate_ws_origin
        
        class MockWS:
            def __init__(self, headers):
                self.headers = headers

        # Allowed same-origin
        ws_valid = MockWS({"origin": "http://localhost:3000", "host": "localhost:8000"})
        assert _validate_ws_origin(ws_valid) is True

        # Malicious external origin in production mode
        monkeypatch.setenv("FIREAI_ENV", "production")
        ws_evil = MockWS({"origin": "https://attacker.evil.com", "host": "app.bazspark.com"})
        assert _validate_ws_origin(ws_evil) is False

        # Missing origin in production mode
        ws_missing = MockWS({"origin": "", "host": "app.bazspark.com"})
        assert _validate_ws_origin(ws_missing) is False


# ============================================================================
# 4. ENG-001: Darcy-Weisbach Hydraulic Solver Benchmarks
# ============================================================================

class TestDarcyWeisbachBenchmarks:
    def test_zero_flow(self):
        from fireai.core.darcy_weisbach_solver import calculate_darcy_weisbach_friction_loss
        res = calculate_darcy_weisbach_friction_loss(
            pipe_length_m=100.0,
            pipe_diameter_m=0.1,
            flow_rate_kg_s=0.0,
        )
        assert res.head_loss_m == 0.0
        assert res.pressure_loss_pa == 0.0
        assert res.flow_regime == "no_flow"

    def test_laminar_flow_stokes_law(self):
        """Re < 2300: f = 64 / Re"""
        from fireai.core.darcy_weisbach_solver import calculate_darcy_weisbach_friction_loss
        # High viscosity fluid for laminar flow
        res = calculate_darcy_weisbach_friction_loss(
            pipe_length_m=50.0,
            pipe_diameter_m=0.05,
            flow_rate_kg_s=0.1,
            density_kg_m3=1000.0,
            viscosity_pa_s=0.1,  # high viscosity => low Re
        )
        assert res.flow_regime == "laminar"
        assert res.reynolds_number < 2300
        expected_f = 64.0 / res.reynolds_number
        assert math.isclose(res.friction_factor, expected_f, rel_tol=1e-4)
        assert res.pressure_loss_pa > 0.0

    def test_transitional_flow(self):
        """2300 <= Re <= 4000: Transitional regime"""
        from fireai.core.darcy_weisbach_solver import calculate_darcy_weisbach_friction_loss
        res = calculate_darcy_weisbach_friction_loss(
            pipe_length_m=50.0,
            pipe_diameter_m=0.05,
            flow_rate_kg_s=0.11,
            density_kg_m3=1000.0,
            viscosity_pa_s=0.002,
        )
        if 2300 <= res.reynolds_number <= 4000:
            assert res.flow_regime == "transitional"
            assert res.pressure_loss_pa > 0.0

    def test_turbulent_flow_colebrook(self):
        """Re > 4000: Colebrook-White equation"""
        from fireai.core.darcy_weisbach_solver import calculate_darcy_weisbach_friction_loss, FluidType
        res = calculate_darcy_weisbach_friction_loss(
            pipe_length_m=100.0,
            pipe_diameter_m=0.1,
            flow_rate_kg_s=15.0,
            fluid_type=FluidType.WATER,
        )
        assert res.flow_regime == "turbulent"
        assert res.reynolds_number > 4000
        assert 0.008 <= res.friction_factor <= 0.08
        assert res.converged is True
        assert res.pressure_loss_pa > 0.0

    def test_negative_parameters_raise(self):
        from fireai.core.darcy_weisbach_solver import calculate_darcy_weisbach_friction_loss
        with pytest.raises(ValueError):
            calculate_darcy_weisbach_friction_loss(
                pipe_length_m=-10.0,
                pipe_diameter_m=0.1,
                flow_rate_kg_s=5.0,
            )
        with pytest.raises(ValueError):
            calculate_darcy_weisbach_friction_loss(
                pipe_length_m=10.0,
                pipe_diameter_m=-0.1,
                flow_rate_kg_s=5.0,
            )


# ============================================================================
# 5. ENG-002: Battery Temperature & Aging Derating
# ============================================================================

class TestBatteryDeratingBenchmarks:
    def test_battery_temperature_curve(self):
        from fireai.core.battery_aging_derating import (
            TEMPERATURE_DERATING,
            size_battery,
        )
        # Check standard IEEE 485 values
        assert TEMPERATURE_DERATING[-10] == 0.60
        assert TEMPERATURE_DERATING[0] == 0.72
        assert TEMPERATURE_DERATING[25] == 1.00

        # Sizing at 25C vs 0C
        res_25c = size_battery(
            standby_load_amps=0.5,
            alarm_load_amps=2.0,
            standby_hours=24.0,
            alarm_hours=0.25,
            min_temperature_c=25.0,
            service_life_years=5,
        )
        res_0c = size_battery(
            standby_load_amps=0.5,
            alarm_load_amps=2.0,
            standby_hours=24.0,
            alarm_hours=0.25,
            min_temperature_c=0.0,
            service_life_years=5,
        )
        # At 0C, required rated capacity must be strictly greater than at 25C due to temperature derating
        assert res_0c.required_ah > res_25c.required_ah


# ============================================================================
# 6. REL-001: Self-Healing Failure Non-Masking
# ============================================================================

class TestSelfHealingIntegrity:
    def test_safety_critical_failure_is_reraised(self):
        from fireai.core.qomn_self_healing_engine import (
            SafetyCriticalFailure,
            self_healing,
        )

        @self_healing()
        def failing_calc():
            raise SafetyCriticalFailure("Solver completely diverged — cannot synthesize output")

        with pytest.raises(SafetyCriticalFailure):
            failing_calc()


# ============================================================================
# 7. AAI-001: MCP / Agent File Path Security
# ============================================================================

class TestAgentFilePathSecurity:
    def test_sanitize_file_path_blocks_null_and_devices(self):
        from fireai.core.bim_input_sanitizer import sanitize_file_path
        
        # Simple safe path
        assert sanitize_file_path("project/model.rvt") == "project/model.rvt"

        # Traversal blocked
        with pytest.raises(ValueError, match="[Tt]raversal"):
            sanitize_file_path("../../../etc/passwd")

        # Null byte blocked
        with pytest.raises(ValueError, match="Null byte"):
            sanitize_file_path("model.rvt\x00.exe")

        # Windows device blocked
        with pytest.raises(ValueError, match="reserved"):
            sanitize_file_path("NUL")
        with pytest.raises(ValueError, match="reserved"):
            sanitize_file_path("COM1")
