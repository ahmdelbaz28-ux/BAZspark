"""backend/tests/kernel/test_phase9_engineering_kernels.py — Phase 9 Kernel Verification Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 9 & Gate 9:
- Kernel tests against standard reference values for all 6 domains:
  1. Marine (SOLAS Chapter II-2, IMO MSC/Circ.848, FSS Code)
  2. FACP (NFPA 72 §10.6, §12.3, EN 54)
  3. ETAP (IEEE 399, IEEE 141, IEC 60909) [Deterministic REST kernels]
  4. Digital Twin (Multi-sensor telemetry & dynamic risk evaluation)
  5. Copilot (Intent translation & code synthesis)
  6. BIM & Simulation (IFC 4.3 AABB clash detection & NFPA 92 two-zone smoke model)
- Exact numerical validation against statutory formulas and standard tables.
"""

import math

from backend.core.engineering_expansion_contracts import (
    handle_bim_validate_clash,
    handle_copilot_synthesize_recommendations,
    handle_copilot_translate_intent,
    handle_digital_twin_evaluate_risk,
    handle_digital_twin_synchronize,
    handle_etap_calculate_load_flow,
    handle_etap_calculate_short_circuit,
    handle_facp_design_loop,
    handle_facp_verify_panel,
    handle_marine_calculate_suppression,
    handle_marine_verify_solas,
    handle_simulation_smoke_flow,
)

# ═══════════════════════════════════════════════════════════════════════════
# 1. MARINE KERNEL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestMarineKernel:
    def test_solas_machinery_space_a60_compliant(self):
        result = handle_marine_verify_solas({
            "compartment_type": "machinery_space_category_a",
            "bulkhead_class": "A-60",
            "deck_area_m2": 200.0,
            "height_m": 5.0,
        })
        assert result["compliant"] is True
        assert result["required_boundary_class"] == "A-60"
        assert result["fixed_extinguishing_mandated"] is True
        assert result["volume_m3"] == 1000.0
        assert "SOLAS II-2/Reg. 9" in result["applicable_solas_regulations"]
        assert len(result["audit_reference"]) == 64

    def test_solas_machinery_space_b15_rejected(self):
        result = handle_marine_verify_solas({
            "compartment_type": "machinery_space_category_a",
            "bulkhead_class": "B-15",
            "deck_area_m2": 100.0,
            "height_m": 4.0,
        })
        assert result["compliant"] is False
        assert any("does not meet A-60 requirement" in f for f in result["findings"])

    def test_co2_suppression_calculation_solas_reference(self):
        # 500 m3 gross volume, 40% gross rule for machinery spaces: 200 m3 gas
        # 200 / 0.56 = 357.14 kg CO2 -> 8 cylinders of 45 kg
        result = handle_marine_calculate_suppression({
            "agent_type": "CO2",
            "protected_volume_m3": 500.0,
            "net_gross_ratio": 0.85,
            "temperature_c": 20.0,
        })
        assert result["required_mass_kg"] == 357.14
        assert result["cylinder_count"] == 8
        assert result["cylinder_capacity_kg"] == 45.0
        assert result["flooding_time_seconds"] == 120.0
        assert "FSS Code" in result["standard_reference"]

    def test_novec_1230_suppression_calculation_iso14520(self):
        # 100 m3 gross, net ratio 0.85 -> net volume 85 m3
        # s at 20C = 0.07188 -> W = (85 / 0.07188) * (5.6 / 94.4) ≈ 70.15 kg
        result = handle_marine_calculate_suppression({
            "agent_type": "NOVEC_1230",
            "protected_volume_m3": 100.0,
            "net_gross_ratio": 0.85,
            "design_concentration_pct": 5.6,
            "temperature_c": 20.0,
        })
        assert 69.0 <= result["required_mass_kg"] <= 71.0
        assert result["cylinder_count"] == 1
        assert result["flooding_time_seconds"] == 10.0


# ═══════════════════════════════════════════════════════════════════════════
# 2. FACP KERNEL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestFACPKernel:
    def test_panel_capacity_and_battery_sizing_nfpa72(self):
        loops = [
            {"loop_number": 1, "device_count": 80, "standby_current_ma": 160.0, "alarm_current_ma": 450.0, "wire_length_m": 200.0},
            {"loop_number": 2, "device_count": 95, "standby_current_ma": 190.0, "alarm_current_ma": 500.0, "wire_length_m": 250.0},
        ]
        result = handle_facp_verify_panel({
            "panel_model": "FACP-ADVANCED",
            "loops": loops,
            "standby_hours": 24.0,
            "alarm_minutes": 5.0,
            "derating_factor": 1.25,
        })
        assert result["total_devices"] == 175
        assert result["loop_count"] == 2
        assert result["compliant"] is True
        # Battery Ah must be positive and select a standard size >= required
        assert result["required_battery_ah"] > 0
        assert result["recommended_standard_battery_ah"] >= result["required_battery_ah"]
        assert len(result["audit_reference"]) == 64

    def test_panel_capacity_overload_detected(self):
        loops = [
            {"loop_number": 1, "device_count": 300, "standby_current_ma": 500.0, "alarm_current_ma": 2500.0, "wire_length_m": 600.0},
        ]
        result = handle_facp_verify_panel({
            "panel_model": "FACP-STANDARD",
            "loops": loops,
            "max_devices_per_loop": 250,
        })
        assert result["compliant"] is False
        assert result["loop_evaluations"][0]["status"] == "OVERLOAD"

    def test_loop_design_isolator_placement_class_a(self):
        devices = [
            {"device_id": f"DEV-{i:03d}", "type": "SMOKE_DETECTOR", "zone": f"Z-{(i // 15) + 1}", "x": i * 4.0, "y": 8.0}
            for i in range(1, 46)
        ]
        result = handle_facp_design_loop({
            "devices": devices,
            "max_devices_between_isolators": 20,
            "loop_style": "Class_A",
        })
        assert result["total_devices"] == 45
        assert result["injected_isolator_count"] >= 3
        assert result["segment_count"] >= 3
        assert result["estimated_cable_length_m"] > 0
        assert "NFPA 72" in result["nfpa_compliance_clause"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. ETAP DETERMINISTIC REST KERNEL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestETAPKernel:
    def test_load_flow_convergence_and_power_balance(self):
        result = handle_etap_calculate_load_flow({
            "base_mva": 100.0,
            "buses": [
                {"bus_id": "BUS-1", "base_kv": 13.8, "bus_type": "SWING", "generation_mw": 0.0, "generation_mvar": 0.0, "load_mw": 0.0, "load_mvar": 0.0},
                {"bus_id": "BUS-2", "base_kv": 13.8, "bus_type": "PQ", "generation_mw": 0.0, "generation_mvar": 0.0, "load_mw": 20.0, "load_mvar": 10.0},
                {"bus_id": "BUS-3", "base_kv": 13.8, "bus_type": "PQ", "generation_mw": 0.0, "generation_mvar": 0.0, "load_mw": 15.0, "load_mvar": 7.5},
            ],
            "branches": [
                {"from_bus": "BUS-1", "to_bus": "BUS-2", "r_pu": 0.015, "x_pu": 0.06, "rating_mva": 50.0},
                {"from_bus": "BUS-2", "to_bus": "BUS-3", "r_pu": 0.010, "x_pu": 0.04, "rating_mva": 30.0},
            ],
            "max_iterations": 30,
            "tolerance": 1e-4,
        })
        assert result["converged"] is True
        assert result["iterations"] <= 30
        assert len(result["bus_results"]) == 3
        # Power balance: Total Generation = Total Load + Total Losses
        assert math.isclose(result["total_generation_mw"], result["total_load_mw"] + result["total_loss_mw"], rel_tol=1e-2)
        # All bus voltages should be within reasonable bounds (0.90 to 1.10 pu)
        for b in result["bus_results"]:
            assert 0.90 <= b["voltage_pu"] <= 1.10

    def test_short_circuit_iec60909_numerical_precision(self):
        # 13.8 kV, R=0.08 ohm, X=0.65 ohm, c=1.10
        # Zth = sqrt(0.08^2 + 0.65^2) ≈ 0.6549 ohm
        # Ik'' = (1.10 * 13.8) / (sqrt(3) * 0.6549) ≈ 13.383 kA
        # X/R = 8.125 -> kappa ≈ 1.697 -> ip ≈ 32.13 kA
        result = handle_etap_calculate_short_circuit({
            "fault_bus": "BUS-2",
            "nominal_kv": 13.8,
            "fault_type": "3_PHASE",
            "thevenin_r_ohm": 0.08,
            "thevenin_x_ohm": 0.65,
            "voltage_factor_c": 1.10,
        })
        assert 13.3 <= result["ik_initial_symmetrical_ka"] <= 13.5
        assert 31.0 <= result["ip_peak_current_ka"] <= 33.0
        assert result["xr_ratio"] == 8.12
        assert result["thevenin_impedance_ohm"] == 0.6549
        assert "IEC 60909" in result["standard_reference"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. DIGITAL TWIN KERNEL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestDigitalTwinKernel:
    def test_telemetry_synchronization_and_anomaly_detection(self):
        records = [
            {"sensor_id": "TEMP-01", "metric": "temperature_c", "value": 24.0, "unit": "C", "zone_id": "Z1"},
            {"sensor_id": "TEMP-02", "metric": "temperature_c", "value": 68.5, "unit": "C", "zone_id": "Z2"},  # Anomaly
            {"sensor_id": "SMK-01", "metric": "smoke_obscuration_pct", "value": 3.2, "unit": "%/m", "zone_id": "Z2"},  # Anomaly
        ]
        result = handle_digital_twin_synchronize({
            "project_id": "twin-proj-01",
            "telemetry_records": records,
            "expected_revision": 5,
        })
        assert result["processed_records_count"] == 3
        assert result["anomaly_count"] == 2
        assert result["revision"] == 6
        assert result["status"] == "SYNCHRONIZED"

    def test_dynamic_risk_evaluation_composite_score(self):
        zones = [
            {"zone_id": "Z-ATRIUM", "occupancy": "ASSEMBLY", "current_temp_c": 22.0, "smoke_obscuration_pct": 0.1, "co_ppm": 2.0, "sprinkler_active": False},
            {"zone_id": "Z-PLANT", "occupancy": "STORAGE", "current_temp_c": 55.0, "smoke_obscuration_pct": 2.8, "co_ppm": 45.0, "sprinkler_active": False},
        ]
        result = handle_digital_twin_evaluate_risk({
            "project_id": "twin-proj-01",
            "zones": zones,
        })
        assert result["overall_risk_level"] in ("ELEVATED", "CRITICAL")
        assert len(result["zone_evaluations"]) == 2
        assert result["maximum_risk_score"] > 50.0


# ═══════════════════════════════════════════════════════════════════════════
# 5. COPILOT KERNEL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestCopilotKernel:
    def test_intent_translation_arabic_voltage_drop(self):
        result = handle_copilot_translate_intent({
            "natural_language_intent": "احسب هبوط الجهد على الدائرة nac-01 بطول 60م وسلك 12 AWG",
        })
        assert result["detected_domain"] == "electrical"
        assert result["recommended_capability"] == "electrical.calculate_voltage_drop"
        assert result["confidence_score"] >= 0.90

    def test_intent_translation_marine_solas(self):
        result = handle_copilot_translate_intent({
            "natural_language_intent": "verify marine SOLAS compartment fire compliance in machinery space",
        })
        assert result["detected_domain"] == "marine"
        assert result["recommended_capability"] == "marine.verify_solas_compliance"

    def test_design_recommendations_synthesis(self):
        result = handle_copilot_synthesize_recommendations({
            "system_type": "FIRE_ALARM",
            "building_parameters": {
                "occupancy_class": "BUSINESS",
                "floors": 6,
                "area_m2": 8000.0,
            },
        })
        assert len(result["mandatory_requirements"]) >= 3
        # Large multi-story building triggers voice evacuation enhancement recommendation
        assert any("Voice Evacuation" in e["item"] for e in result["recommended_enhancements"])
        assert "NFPA 72-2022" in result["applicable_codes"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. BIM & SIMULATION KERNEL TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestBIMAndSimulationKernel:
    def test_bim_aabb_spatial_clash_detection(self):
        fa_elements = [
            {"id": "CONDUIT-1", "type": "CONDUIT", "bbox": {"min_x": 5.0, "min_y": 5.0, "min_z": 3.0, "max_x": 15.0, "max_y": 5.2, "max_z": 3.2}},
            {"id": "SMOKE-1", "type": "DETECTOR", "bbox": {"min_x": 20.0, "min_y": 20.0, "min_z": 3.0, "max_x": 20.2, "max_y": 20.2, "max_z": 3.15}},
        ]
        obstacles = [
            {"id": "DUCT-1", "category": "MEP_DUCT", "bbox": {"min_x": 8.0, "min_y": 4.8, "min_z": 2.9, "max_x": 12.0, "max_y": 6.0, "max_z": 3.5}},
        ]
        result = handle_bim_validate_clash({
            "fire_alarm_elements": fa_elements,
            "obstacle_elements": obstacles,
            "clearance_tolerance_m": 0.10,
        })
        assert result["total_inspections"] == 2
        assert result["clash_count"] == 1
        assert result["clearance_compliant"] is False
        assert result["clashes"][0]["element_a_id"] == "CONDUIT-1"
        assert result["clashes"][0]["element_b_id"] == "DUCT-1"

    def test_simulation_smoke_flow_nfpa92_two_zone(self):
        result = handle_simulation_smoke_flow({
            "room_length_m": 20.0,
            "room_width_m": 15.0,
            "ceiling_height_m": 6.0,
            "fire_hrr_kw": 1000.0,
            "simulation_duration_s": 300.0,
            "ambient_temp_c": 20.0,
        })
        assert result["critical_time_to_untenable_s"] > 0
        assert len(result["time_progression"]) == 7
        # Smoke layer must descend over time
        first_layer_h = result["time_progression"][0]["smoke_layer_height_m"]
        last_layer_h = result["time_progression"][-1]["smoke_layer_height_m"]
        assert last_layer_h < first_layer_h
        assert result["tenability_status"] in ("TENABLY_SAFE", "MARGINAL", "UNTENABLE")
        assert "NFPA 92" in result["standard_reference"]
