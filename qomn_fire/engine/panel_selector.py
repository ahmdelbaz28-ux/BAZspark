"""
QOMN-FIRE FACP SELECTION ENGINE
Reference Standard: NFPA 72 (2022) §10.6.10, UL 864 10th Edition.
"""

import hashlib
from typing import List, Optional, Tuple
from qomn_fire.core.types import ProjectRequirements, PanelRecommendation, FireAlarmPanel
from qomn_fire.core.errors import Result, FACPSelectionError
from qomn_fire.engine.panel_database import MASTER_PANEL_DATABASE

class SelectionEngine:
    @staticmethod
    def compute_battery_ah(
        device_count: int,
        nac_circuit_count: int,
        panel: FireAlarmPanel,
        requires_voice: bool
    ) -> float:
        """
        Calculates battery capacity per NFPA 72 §10.6.10.
        - Standby: 24 Hours
        - Alarm: 15 Mins (0.25h) if Voice Evacuation is required; else 5 Mins (0.0833h)
        - Safety Margin: 20%
        """
        standby_load = (device_count * 0.001) + panel.standby_current_amps
        alarm_load = (nac_circuit_count * 2.0) + (device_count * 0.005) + panel.alarm_current_amps
        alarm_duration_h = 0.25 if requires_voice else 0.0833

        raw_capacity = (standby_load * 24.0) + (alarm_load * alarm_duration_h)
        return round(raw_capacity * 1.2, 2)

    @classmethod
    def select_panel(cls, req: ProjectRequirements) -> Result[PanelRecommendation, FACPSelectionError]:
        # Enforce code capacity margins (20% spare capacity per NFPA 72 §10.6.10)
        required_points = req.device_count * 1.2
        # NAC circuits are sized by battery calculation, not blanket margin.
        # The 20% margin applies to address points only (NFPA 72 §10.6.10.2).
        required_nacs = req.nac_circuit_count

        eligible_panels: List[Tuple[FireAlarmPanel, float]] = []

        for p in MASTER_PANEL_DATABASE:
            if p.points_capacity < required_points:
                continue
            if p.nac_capacity < required_nacs:
                continue
            if req.requires_network and not p.supports_networking:
                continue
            if req.requires_voice and not p.supports_voice:
                continue
            if req.jurisdiction == "FDNY" and "FDNY" not in p.listings:
                continue
            if req.jurisdiction == "Canada" and "ULC" not in p.listings:
                continue

            # Multi-criteria scoring
            score = 0.0
            utilization = required_points / p.points_capacity

            if 0.5 <= utilization <= 0.8:
                score += 50.0
            elif 0.3 <= utilization < 0.5:
                score += 20.0
            elif 0.8 < utilization <= 0.95:
                score += 15.0
            else:
                score += 5.0

            if req.preferred_manufacturer and req.preferred_manufacturer.upper() == p.manufacturer.upper():
                score += 100.0

            eligible_panels.append((p, score))

        if not eligible_panels:
            return Result(error=FACPSelectionError(
                message="No compliant FACP models found satisfying constraints in database.",
                code_ref="UL 864 / NFPA 72",
                remedy="Reduce required device loads or transition to a multi-node networked panel architecture."
            ))

        # Deterministic sorting: Right-sizing principle
        # Primary: highest score. Tie-break: smallest capacity (right-sizing),
        # then lowest standby draw, then model name for determinism.
        eligible_panels.sort(
            key=lambda x: (x[1], -x[0].points_capacity, -x[0].standby_current_amps, x[0].model),
            reverse=True
        )

        selected, _ = eligible_panels[0]
        alternatives = tuple([p[0].model for p in eligible_panels[1:4]])

        capacity_util = required_points / selected.points_capacity
        nac_util = required_nacs / selected.nac_capacity

        warnings = []
        if capacity_util > 0.90:
            warnings.append("FACP loading is close to maximum capacity limits.")
        elif capacity_util < 0.30:
            warnings.append("FACP is significantly oversized for the current device loading.")

        battery_size = cls.compute_battery_ah(
            req.device_count,
            req.nac_circuit_count,
            selected,
            req.requires_voice
        )

        # Cryptographic checksum for deterministic outputs
        payload = f"{selected.model}:{selected.manufacturer}:{capacity_util:.4f}:{battery_size:.2f}"
        signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        rec = PanelRecommendation(
            recommended_model=selected.model,
            manufacturer=selected.manufacturer,
            capacity_utilization=round(capacity_util, 4),
            nac_utilization=round(nac_util, 4),
            battery_size_ah=battery_size,
            power_supply_watts=selected.power_supply_watts,
            listings=selected.listings,
            code_compliance=(
                "UL 864 10th Edition",
                "NFPA 72 §10.6.10 Compliance"
            ),
            warnings=tuple(warnings),
            alternatives=alternatives,
            signature_hash=signature
        )
        return Result(value=rec)
