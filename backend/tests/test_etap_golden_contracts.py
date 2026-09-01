"""backend/tests/test_etap_golden_contracts.py — Contract Verification Tests for ETAP Golden Fixtures.

Mandated by BAZSPARK Phase 11 (P11-R4):
- Validates SHA256 checksum integrity of all golden fixtures under tests/golden/etap/.
- Tests deterministic numerical conformance of EtapLiveAdapter with Newton-Raphson load flow
  and IEC 60909 short circuit golden benchmarks.
- Verifies idempotency replay behavior and telemetry event emission.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.core.etap_telemetry import default_etap_telemetry
from backend.integrations.etap_live_adapter import EtapLiveAdapter, reset_all_circuit_breakers

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden" / "etap"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_all_circuit_breakers()
    default_etap_telemetry.reset()


def test_golden_fixtures_sha256_checksum_integrity() -> None:
    """Verify cryptographic integrity of all golden benchmark fixtures against checksums.sha256."""
    checksum_file = GOLDEN_DIR / "checksums.sha256"
    assert checksum_file.exists(), f"Checksum file missing: {checksum_file}"

    lines = checksum_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2, "Must contain at least load-flow and short-circuit checksums"

    for line in lines:
        if not line.strip():
            continue
        expected_sha, fname = line.strip().split(maxsplit=1)
        target_path = GOLDEN_DIR / fname.strip()
        assert target_path.exists(), f"Golden fixture file '{fname}' not found in {GOLDEN_DIR}"

        actual_sha = hashlib.sha256(target_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, (
            f"Checksum mismatch for {fname}: expected {expected_sha}, got {actual_sha}"
        )


def test_load_flow_golden_contract_conformance() -> None:
    """Verify EtapLiveAdapter execution matches load flow golden benchmark."""
    lf_file = GOLDEN_DIR / "load_flow_golden.json"
    data = json.loads(lf_file.read_text(encoding="utf-8"))

    inputs = data["input"]
    expected = data["expected_output"]

    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888)
    res = adapter.calculate_live_load_flow(
        buses=inputs["buses"],
        branches=inputs["branches"],
        generation_sources=inputs["generation_sources"],
        method=data["method"],
    )

    assert res["success"] is True
    assert res["converged"] == expected["converged"]
    assert res["total_generation_mw"] == pytest.approx(expected["total_generation_mw"], rel=1e-3)
    assert res["total_load_mw"] == pytest.approx(expected["total_load_mw"], rel=1e-3)
    assert res["total_losses_mw"] == pytest.approx(expected["total_losses_mw"], rel=1e-3)

    bus_results = res["bus_results"]
    assert len(bus_results) == len(expected["bus_results"])
    for actual_b, exp_b in zip(bus_results, expected["bus_results"], strict=True):
        assert actual_b["bus_id"] == exp_b["bus_id"]
        assert actual_b["nominal_kv"] == pytest.approx(exp_b["nominal_kv"], rel=1e-3)
        assert actual_b["voltage_magnitude_pu"] == pytest.approx(exp_b["voltage_magnitude_pu"], rel=1e-3)
        assert actual_b["voltage_actual_kv"] == pytest.approx(exp_b["voltage_actual_kv"], rel=1e-3)


def test_short_circuit_golden_contract_conformance() -> None:
    """Verify EtapLiveAdapter execution matches IEC 60909 short circuit golden benchmark."""
    sc_file = GOLDEN_DIR / "short_circuit_golden.json"
    data = json.loads(sc_file.read_text(encoding="utf-8"))

    inputs = data["input"]
    expected = data["expected_output"]

    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888)
    res = adapter.calculate_live_short_circuit(
        fault_buses=inputs["fault_buses"],
        system_base_mva=inputs["system_base_mva"],
        c_factor=inputs["c_factor"],
        nominal_kv=inputs["nominal_kv"],
        r_ohm=inputs["r_ohm"],
        x_ohm=inputs["x_ohm"],
    )

    assert res["success"] is True
    assert res["standard"] == expected["standard"]

    fault_results = res["fault_results"]
    assert len(fault_results) == expected["fault_buses_count"]

    first_bus = fault_results[0]
    assert first_bus["initial_symmetrical_current_ka"] == pytest.approx(expected["initial_symmetrical_current_ka"], rel=1e-3)
    assert first_bus["peak_current_ka"] == pytest.approx(expected["peak_current_ka"], rel=1e-3)
    assert first_bus["breaking_current_ka"] == pytest.approx(expected["breaking_current_ka"], rel=1e-3)
    assert first_bus["short_circuit_power_mva"] == pytest.approx(expected["short_circuit_power_mva"], rel=1e-3)
    assert first_bus["xr_ratio"] == pytest.approx(expected["xr_ratio"], rel=1e-2)


def test_golden_idempotency_replay_consistency() -> None:
    """Verify that multiple invocations with the same idempotency token return identical cached output."""
    lf_file = GOLDEN_DIR / "load_flow_golden.json"
    data = json.loads(lf_file.read_text(encoding="utf-8"))
    inputs = data["input"]

    token = "golden-test-idempotency-token-001"
    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888)

    res1 = adapter.calculate_live_load_flow(
        buses=inputs["buses"],
        branches=inputs["branches"],
        generation_sources=inputs["generation_sources"],
        idempotency_token=token,
    )
    res2 = adapter.calculate_live_load_flow(
        buses=inputs["buses"],
        branches=inputs["branches"],
        generation_sources=inputs["generation_sources"],
        idempotency_token=token,
    )

    assert res1 == res2
    assert res1["idempotency_token"] == token


def test_golden_telemetry_event_generation() -> None:
    """Verify structured telemetry events and SLO counters are updated during golden execution."""
    adapter = EtapLiveAdapter(host="93.184.216.34", port=18888)
    adapter.test_connection_live()

    slo = default_etap_telemetry.get_slo_metrics()
    assert slo["total_events"] >= 2
    assert slo["success_rate"] == 1.0
    assert slo["ssrf_blocked_count"] == 0
    assert slo["circuit_opens_count"] == 0
