"""Phase 10 — ETAP Live Integration E2E & Security Tests.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 10 & PHASE10_DELIVERY_CONTRACT.md (Stream S2):
- Live ETAP electrical studies (Load Flow IEEE 399, Short Circuit IEC 60909).
- SSRF Defense validation and fail-closed security.
- 100% Real Adapter Evidence Coverage — zero unverified empty successes.
- Zero SIMULATED text/behavior across all delivery interfaces.
"""

from __future__ import annotations

import pytest

from backend.core.capability_registry import default_capability_registry
from backend.core.etap_live_contracts import (
    CAP_ETAP_LIVE_CALCULATE_LOAD_FLOW,
    CAP_ETAP_LIVE_CALCULATE_SHORT_CIRCUIT,
    CAP_ETAP_LIVE_SYNC_PROJECT,
    CAP_ETAP_LIVE_TEST_CONNECTION,
)
from backend.database import get_db
from backend.integrations.etap_live_adapter import (
    MAX_READLINE_BYTES,
    EtapLiveAdapter,
    EtapSecurityViolation,
)
from backend.integrations.etap_schemas import EtapExportRequest, EtapImportRequest
from backend.integrations.etap_service import EtapService


def test_etap_live_capabilities_registered():
    etap_cap_ids = [
        CAP_ETAP_LIVE_TEST_CONNECTION,
        CAP_ETAP_LIVE_SYNC_PROJECT,
        CAP_ETAP_LIVE_CALCULATE_LOAD_FLOW,
        CAP_ETAP_LIVE_CALCULATE_SHORT_CIRCUIT,
    ]
    for cap_id in etap_cap_ids:
        cap = default_capability_registry.get(cap_id)
        assert cap is not None, f"Capability '{cap_id}' must be registered"
        assert cap.contract is not None
        assert cap.category == "etap"
        assert cap.contract.risk in ("LOW", "HIGH", "ENGINEERING_MUTATION")


def test_etap_live_test_connection_e2e():
    cap = default_capability_registry.get(CAP_ETAP_LIVE_TEST_CONNECTION)
    assert cap is not None and cap.handler is not None

    result = cap.handler({"host": "93.184.216.34", "port": 18888})
    assert result["success"] is True
    assert "latency_ms" in result
    assert "server_version" in result
    assert "simulated" not in str(result["server_version"]).lower()
    assert "evidence" in result
    assert "audit_hash" in result


def test_etap_live_load_flow_study_e2e_evidence():
    cap = default_capability_registry.get(CAP_ETAP_LIVE_CALCULATE_LOAD_FLOW)
    assert cap is not None and cap.handler is not None

    payload = {
        "buses": [
            {"id": "BUS-MAIN-13KV", "nominal_kv": 13.8, "p_mw": 2.5, "q_mvar": 1.0},
            {"id": "BUS-EMERG-480V", "nominal_kv": 0.48, "p_mw": 0.45, "q_mvar": 0.15},
            {"id": "BUS-FIRE-PUMP", "nominal_kv": 0.48, "p_mw": 0.185, "q_mvar": 0.09},
        ],
        "generation_sources": [
            {"id": "UTILITY-GRID-13KV", "mw": 3.5, "mvar": 1.5}
        ],
        "method": "Newton-Raphson",
    }

    result = cap.handler(payload)
    assert result["success"] is True
    assert result["converged"] is True
    assert len(result["bus_results"]) == 3
    assert result["total_generation_mw"] >= result["total_load_mw"]
    assert result["total_losses_mw"] > 0.0
    assert "evidence" in result
    assert result["evidence"]["converged"] is True
    assert "audit_hash" in result


def test_etap_live_short_circuit_study_e2e_evidence():
    cap = default_capability_registry.get(CAP_ETAP_LIVE_CALCULATE_SHORT_CIRCUIT)
    assert cap is not None and cap.handler is not None

    payload = {
        "fault_buses": ["BUS-MAIN-13KV", "BUS-EMERG-480V"],
        "nominal_kv": 13.8,
        "r_ohm": 0.06,
        "x_ohm": 0.58,
    }

    result = cap.handler(payload)
    assert result["success"] is True
    assert result["standard"] == "IEC 60909-0:2016"
    assert len(result["fault_results"]) == 2
    for fr in result["fault_results"]:
        assert fr["initial_symmetrical_current_ka"] > 0.0
        assert fr["peak_current_ka"] >= fr["initial_symmetrical_current_ka"]
        assert fr["short_circuit_power_mva"] > 0.0
        assert fr["xr_ratio"] > 0.0
    assert "evidence" in result
    assert "audit_hash" in result


def test_etap_security_ssrf_and_disallowed_commands():
    # Disallowed command
    adapter = EtapLiveAdapter(host="127.0.0.1", port=18888)
    with pytest.raises(EtapSecurityViolation, match="Disallowed ETAP bridge command"):
        adapter._validate_command_allowed("execute_arbitrary_shell_command")

    # SSRF guard block for malicious host
    bad_adapter = EtapLiveAdapter(host="metadata.google.internal", port=18888)
    with pytest.raises(EtapSecurityViolation, match="SSRF Protection"):
        bad_adapter.test_connection_live()


def test_etap_service_zero_simulated_in_runtime():
    db = get_db()
    with db._transaction() as cur:
        cur.execute(
            "INSERT OR IGNORE INTO projects (id, name, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("test_proj_01", "Test Phase 10 Project", "active", "2026-08-31T00:00:00Z", "2026-08-31T00:00:00Z"),
        )
    service = EtapService(db)

    # 1. list_etap_projects returns live format
    projs = service.list_etap_projects("test_proj_01")
    assert isinstance(projs, list)
    assert len(projs) > 0
    for p in projs:
        assert "simulated" not in str(p).lower()

    # 2. export_to_etap returns real evidence
    export_req = EtapExportRequest(project_id="test_proj_01", format="csv", include_loads=True, include_sources=True)
    exp_res = service.export_to_etap("test_proj_01", export_req)
    assert exp_res["records_exported"] > 0
    assert "evidence" in exp_res
    assert "simulated" not in str(exp_res).lower()

    # 3. import_from_etap returns live bridge message and evidence
    import_req = EtapImportRequest(project_id="test_proj_01", etap_project_id="etap-proj-live-001")
    imp_res = service.import_from_etap("test_proj_01", import_req)
    assert imp_res["records_imported"] > 0
    assert "evidence" in imp_res
    assert "simulated" not in str(imp_res).lower()
