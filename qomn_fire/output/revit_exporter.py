"""QOMN-FIRE BIM EXCHANGE SCHEMA EXPORTER

DOMAIN SCOPE (Phase 5 dedup):
  This exporter is specific to the qomn_fire domain — it exports devices,
  conduit runs, and FACP panel recommendations to Revit-compatible JSON.
  It is NOT a duplicate of the other revit_exporter modules:
    - qomn_fire/output/revit_exporter.py     → QOMN-FIRE device/conduit/FACP JSON export
    - marine/integration/revit_exporter.py    → Marine detector family/placement generation
    - fireai/core/revit_exporter.py            → Cable routing IFC/Revit schedule/report export
  Each serves a distinct domain. Do NOT merge.
"""

import json

from qomn_fire.core.types import ConduitRun, Device, PanelRecommendation


def export_to_revit_json(devices: list[Device], runs: list[ConduitRun], facp: PanelRecommendation) -> str:
    schema = {
        "SchemaVersion": "1.0",
        "Project": "QOMN-FIRE INTEGRATED EXPORT ENGINE",
        "SelectedFACP": {
            "Model": facp.recommended_model,
            "Manufacturer": facp.manufacturer,
            "RequiredBatteryAh": facp.battery_size_ah,
            "PointsUtilization": facp.capacity_utilization,
            "Signature": facp.signature_hash
        },
        "Devices": [],
        "ConduitRuns": []
    }

    for d in devices:
        schema["Devices"].append({
            "Id": d.id,
            "type": d.device_type.value,
            "Location": d.location.to_dict(),
            "ElevationFt": d.elevation_ft,
            "Circuit": d.circuit,
            "Zone": d.zone,
            "Hash": d.compute_hash()
        })

    for r in runs:
        schema["ConduitRuns"].append({
            "Id": r.id,
            "ConduitType": r.conduit_type.value,
            "TradeSize": r.trade_size,
            "TotalLengthFt": r.total_length_ft,
            "BendCount": r.bend_count,
            "BendDegrees": r.bend_degrees,
            "Path": [p.to_dict() for p in r.points],
            "Hash": r.compute_hash()
        })

    return json.dumps(schema, indent=2, sort_keys=True)
