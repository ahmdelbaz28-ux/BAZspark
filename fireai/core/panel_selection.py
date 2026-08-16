"""Shared FACP panel selection logic — single source of truth for facp_system and qomn_fire."""

import hashlib
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

STANDBY_MA_PER_DEVICE = 0.8
ALARM_MA_PER_DEVICE = 5.0


@dataclass(frozen=True)
class FireAlarmPanel:
    model: str
    manufacturer: str
    points_capacity: int
    nac_capacity: int
    supports_networking: bool
    supports_voice: bool
    supports_releasing: bool
    max_slc_loops: int
    listings: list[str]
    standby_current_amps: float
    alarm_current_amps: float
    power_supply_watts: int


@dataclass(frozen=True)
class ProjectRequirements:
    device_count: int
    nac_circuit_count: int
    building_size_m2: float
    building_floors: int
    requires_network: bool
    requires_voice: bool
    requires_releasing: bool
    jurisdiction: str
    preferred_manufacturer: str | None = None
    min_temperature_c: float = 20.0


@dataclass(frozen=True)
class PanelRecommendation:
    recommended_model: str
    manufacturer: str
    capacity_utilization: float
    nac_utilization: float
    battery_size_ah: float
    battery_derating_details: dict
    power_supply_watts: int
    listings: list[str]
    code_compliance: list[str]
    warnings: list[str]
    alternatives: list[str]
    signature_hash: str


MASTER_PANEL_DATABASE: list[FireAlarmPanel] = [
    FireAlarmPanel(
        model="NFS-320",
        manufacturer="NOTIFIER",
        points_capacity=250,
        nac_capacity=2,
        supports_networking=False,
        supports_voice=False,
        supports_releasing=False,
        max_slc_loops=1,
        listings=["UL", "ULC"],
        standby_current_amps=0.200,
        alarm_current_amps=0.350,
        power_supply_watts=144,
    ),
    FireAlarmPanel(
        model="NFS-640",
        manufacturer="NOTIFIER",
        points_capacity=640,
        nac_capacity=4,
        supports_networking=True,
        supports_voice=True,
        supports_releasing=False,
        max_slc_loops=4,
        listings=["UL", "ULC"],
        standby_current_amps=0.250,
        alarm_current_amps=0.450,
        power_supply_watts=144,
    ),
    FireAlarmPanel(
        model="NFS2-3030",
        manufacturer="NOTIFIER",
        points_capacity=3180,
        nac_capacity=10,
        supports_networking=True,
        supports_voice=True,
        supports_releasing=True,
        max_slc_loops=10,
        listings=["UL", "ULC", "FM"],
        standby_current_amps=0.350,
        alarm_current_amps=0.650,
        power_supply_watts=288,
    ),
    FireAlarmPanel(
        model="FC901",
        manufacturer="SIEMENS",
        points_capacity=50,
        nac_capacity=2,
        supports_networking=False,
        supports_voice=False,
        supports_releasing=False,
        max_slc_loops=1,
        listings=["UL", "FM", "FDNY"],
        standby_current_amps=0.120,
        alarm_current_amps=0.250,
        power_supply_watts=170,
    ),
    FireAlarmPanel(
        model="FC922",
        manufacturer="SIEMENS",
        points_capacity=252,
        nac_capacity=4,
        supports_networking=True,
        supports_voice=True,
        supports_releasing=False,
        max_slc_loops=2,
        listings=["UL", "FM", "FDNY"],
        standby_current_amps=0.180,
        alarm_current_amps=0.350,
        power_supply_watts=170,
    ),
    FireAlarmPanel(
        model="FC924",
        manufacturer="SIEMENS",
        points_capacity=504,
        nac_capacity=6,
        supports_networking=True,
        supports_voice=True,
        supports_releasing=True,
        max_slc_loops=4,
        listings=["UL", "FM", "FDNY"],
        standby_current_amps=0.220,
        alarm_current_amps=0.450,
        power_supply_watts=300,
    ),
    FireAlarmPanel(
        model="4100ES",
        manufacturer="SIMPLEX",
        points_capacity=3000,
        nac_capacity=10,
        supports_networking=True,
        supports_voice=True,
        supports_releasing=True,
        max_slc_loops=10,
        listings=["UL", "FM", "FDNY"],
        standby_current_amps=0.450,
        alarm_current_amps=0.850,
        power_supply_watts=360,
    ),
]


class SelectionEngine:
    @staticmethod
    def compute_battery_ah(
        device_count: int,
        nac_circuit_count: int,
        panel: FireAlarmPanel,
        requires_voice: bool,
        min_temperature_c: float = 20.0,
    ) -> tuple[float, dict]:
        standby_load = (device_count * STANDBY_MA_PER_DEVICE / 1000.0) + panel.standby_current_amps
        alarm_load = (
            (nac_circuit_count * 2.0)
            + (device_count * ALARM_MA_PER_DEVICE / 1000.0)
            + panel.alarm_current_amps
        )
        alarm_duration_h = 0.25 if requires_voice else (5.0 / 60.0)

        try:
            from fireai.core.battery_aging_derating import size_battery

            result = size_battery(
                standby_load_amps=standby_load,
                alarm_load_amps=alarm_load,
                standby_hours=24.0,
                alarm_hours=alarm_duration_h,
                min_temperature_c=min_temperature_c,
                service_life_years=5,
                safety_margin_pct=0.0,
            )

            derating_details = {
                "method": "NFPA_72_IEEE_485_1188_full_derating",
                "temperature_derating": result.temperature_derating,
                "aging_derating": result.aging_derating,
                "discharge_rate_correction": result.discharge_rate_correction,
                "combined_safety_factor": round(
                    1.0
                    / max(
                        result.temperature_derating
                        * result.aging_derating
                        * result.discharge_rate_correction,
                        0.01,
                    ),
                    2,
                ),
                "standby_ah": result.standby_ah,
                "alarm_ah": result.alarm_ah,
                "total_load_ah": result.total_load_ah,
                "min_temperature_c": min_temperature_c,
                "nfpa_reference": "NFPA 72-2022 SS10.6.7, IEEE 485, IEEE 1188",
            }

            return round(result.required_ah, 2), derating_details

        except ImportError as exc:
            raise RuntimeError(
                "fireai.core.battery_aging_derating is REQUIRED for life-safety "
                "battery sizing. The previous 'simplified fallback' used a flat "
                "temperature derating (0.85) that under-sized batteries by ~31% "
                "at 0C vs. the real IEEE 485 derating (0.72). Refusing to "
                "operate without the production module. "
                "Original error: " + str(exc)
            ) from exc

    @classmethod
    def select_panel(
        cls, req: ProjectRequirements
    ) -> PanelRecommendation:  # NOSONAR — S3776: panel selection logic must evaluate many criteria
        required_points = req.device_count * 1.2
        required_nacs = req.nac_circuit_count

        eligible_panels: list[tuple[FireAlarmPanel, float]] = []

        for p in MASTER_PANEL_DATABASE:
            if p.points_capacity < required_points:
                continue
            if p.nac_capacity < required_nacs:
                continue
            if req.requires_network and not p.supports_networking:
                continue
            if req.requires_voice and not p.supports_voice:
                continue
            if req.requires_releasing and not p.supports_releasing:
                continue
            if req.jurisdiction == "FDNY" and "FDNY" not in p.listings:
                continue
            if req.jurisdiction == "Canada" and "ULC" not in p.listings:
                continue

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

            if (
                req.preferred_manufacturer
                and req.preferred_manufacturer.upper() == p.manufacturer.upper()
            ):
                score += 100.0

            eligible_panels.append((p, score))

        if not eligible_panels:
            raise ValueError(
                "No compliant panels found in database for the given design requirements."
            )

        eligible_panels.sort(
            key=lambda x: (-x[1], x[0].points_capacity, x[0].standby_current_amps, x[0].model)
        )

        selected_panel, _ = eligible_panels[0]

        alternatives = [p[0].model for p in eligible_panels[1:4]]

        capacity_util = required_points / selected_panel.points_capacity
        nac_util = required_nacs / selected_panel.nac_capacity

        warnings = []
        if capacity_util > 0.90:
            warnings.append("FACP loading exceeds 90% space capacity limit. Consider upsizing.")
        elif capacity_util < 0.30:
            warnings.append("FACP loading is under 30% capacity. Panel is significantly oversized.")

        if nac_util > 0.80:
            warnings.append(
                f"NAC utilization is {nac_util:.0%}. Consider a panel with more NAC circuits "
                f"or plan for NAC extender modules to accommodate future expansion."
            )

        if req.requires_releasing:
            releasing_alternatives = [
                p[0].model for p in eligible_panels[1:] if p[0].supports_releasing
            ]
            if not releasing_alternatives:
                warnings.append(
                    "No alternative releasing-capable panels available. "
                    "Verify selected panel meets all suppression system requirements per NFPA 72 SS21.7."
                )

        battery_size, battery_derating = cls.compute_battery_ah(
            req.device_count,
            req.nac_circuit_count,
            selected_panel,
            req.requires_voice,
            req.min_temperature_c,
        )

        serialized_payload = (
            f"{selected_panel.model}:{selected_panel.manufacturer}:"
            f"{capacity_util:.4f}:{battery_size:.2f}:{battery_derating['method']}"
        )
        signature = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()

        return PanelRecommendation(
            recommended_model=selected_panel.model,
            manufacturer=selected_panel.manufacturer,
            capacity_utilization=round(capacity_util, 4),
            nac_utilization=round(nac_util, 4),
            battery_size_ah=battery_size,
            battery_derating_details=battery_derating,
            power_supply_watts=selected_panel.power_supply_watts,
            listings=selected_panel.listings,
            code_compliance=[
                "UL 864 10th Edition",
                "NFPA 72 SS10.6.7 Compliance",
                f"Sizing margin verified: {1.2:.1f}x multiplier (points only)",
                f"Battery derating: {battery_derating['method']}",
            ],
            warnings=warnings,
            alternatives=alternatives,
            signature_hash=signature,
        )


__all__ = [
    "ALARM_MA_PER_DEVICE",
    "MASTER_PANEL_DATABASE",
    "STANDBY_MA_PER_DEVICE",
    "FireAlarmPanel",
    "PanelRecommendation",
    "ProjectRequirements",
    "SelectionEngine",
]
