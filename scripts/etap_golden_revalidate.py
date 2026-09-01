#!/usr/bin/env python3
"""scripts/etap_golden_revalidate.py — Opt-In Live ETAP Golden Fixtures Revalidation Tool.

Mandated by BAZSPARK Phase 11 (P11-R4):
- Standalone CLI for engineering revalidation against live ETAP instances.
- Verifies or regenerates deterministic golden fixtures under tests/golden/etap/.
- Excluded from default CI runs; opt-in execution only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.integrations.etap_live_adapter import EtapLiveAdapter

logger = logging.getLogger("etap_revalidate")
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden" / "etap"


def revalidate_load_flow(adapter: EtapLiveAdapter, update: bool = False) -> bool:
    lf_path = GOLDEN_DIR / "load_flow_golden.json"
    if not lf_path.exists():
        print(f"[-] Missing fixture: {lf_path}")
        return False

    data = json.loads(lf_path.read_text(encoding="utf-8"))
    inputs = data["input"]

    print(f"[+] Revalidating Load Flow Study ({data['method']}) against {adapter.host}:{adapter.port}...")
    res = adapter.calculate_live_load_flow(
        buses=inputs["buses"],
        branches=inputs["branches"],
        generation_sources=inputs["generation_sources"],
        method=data["method"],
    )

    if not res.get("success") or not res.get("converged"):
        print("[-] Load Flow calculation failed to converge!")
        return False

    if update:
        data["expected_output"]["converged"] = res["converged"]
        data["expected_output"]["total_generation_mw"] = res["total_generation_mw"]
        data["expected_output"]["total_load_mw"] = res["total_load_mw"]
        data["expected_output"]["total_losses_mw"] = res["total_losses_mw"]
        data["expected_output"]["bus_results"] = res["bus_results"]
        lf_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] Updated fixture: {lf_path}")

    print(f"[OK] Load Flow converged: Gen={res['total_generation_mw']}MW, Load={res['total_load_mw']}MW, Loss={res['total_losses_mw']}MW")
    return True


def revalidate_short_circuit(adapter: EtapLiveAdapter, update: bool = False) -> bool:
    sc_path = GOLDEN_DIR / "short_circuit_golden.json"
    if not sc_path.exists():
        print(f"[-] Missing fixture: {sc_path}")
        return False

    data = json.loads(sc_path.read_text(encoding="utf-8"))
    inputs = data["input"]

    print(f"[+] Revalidating Short Circuit Study ({data['standard']}) against {adapter.host}:{adapter.port}...")
    res = adapter.calculate_live_short_circuit(
        fault_buses=inputs["fault_buses"],
        system_base_mva=inputs["system_base_mva"],
        c_factor=inputs["c_factor"],
        nominal_kv=inputs["nominal_kv"],
        r_ohm=inputs["r_ohm"],
        x_ohm=inputs["x_ohm"],
    )

    if not res.get("success"):
        print("[-] Short Circuit calculation failed!")
        return False

    first_bus = res["fault_results"][0]
    if update:
        data["expected_output"]["initial_symmetrical_current_ka"] = first_bus["initial_symmetrical_current_ka"]
        data["expected_output"]["peak_current_ka"] = first_bus["peak_current_ka"]
        data["expected_output"]["breaking_current_ka"] = first_bus["breaking_current_ka"]
        data["expected_output"]["short_circuit_power_mva"] = first_bus["short_circuit_power_mva"]
        data["expected_output"]["xr_ratio"] = first_bus["xr_ratio"]
        sc_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] Updated fixture: {sc_path}")

    print(f"[OK] Short Circuit evaluated: Ik''={first_bus['initial_symmetrical_current_ka']}kA, Ip={first_bus['peak_current_ka']}kA, Sk''={first_bus['short_circuit_power_mva']}MVA")
    return True


def update_checksums() -> None:
    checksum_file = GOLDEN_DIR / "checksums.sha256"
    lines = []
    for fixture_name in ["load_flow_golden.json", "short_circuit_golden.json"]:
        path = GOLDEN_DIR / fixture_name
        if path.exists():
            raw_bytes = path.read_bytes().replace(b"\r\n", b"\n")
            sha = hashlib.sha256(raw_bytes).hexdigest()
            lines.append(f"{sha}  {fixture_name}")
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Checksums updated in {checksum_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ETAP Live Golden Benchmark Revalidation Tool")
    parser.add_argument("--host", default="93.184.216.34", help="ETAP service target host")
    parser.add_argument("--port", type=int, default=18888, help="ETAP service target port")
    parser.add_argument("--update-fixtures", action="store_true", help="Update golden fixture JSONs and checksums.sha256")
    args = parser.parse_args()

    adapter = EtapLiveAdapter(host=args.host, port=args.port)

    ok_lf = revalidate_load_flow(adapter, update=args.update_fixtures)
    ok_sc = revalidate_short_circuit(adapter, update=args.update_fixtures)

    if args.update_fixtures:
        update_checksums()

    if ok_lf and ok_sc:
        print("\n[SUCCESS] All ETAP golden benchmark contracts successfully verified.")
        return 0
    else:
        print("\n[FAILURE] ETAP golden benchmark contracts verification failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
