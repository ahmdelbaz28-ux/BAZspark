"""
fireai/facade.py — Clean Facade Entry Points for the FireAI System.

Provides 3-5 deep module facades that compose the 130+ internal modules
into small, discoverable interfaces. The facades are the recommended entry
points for new code; existing direct imports continue to work.

Facades:
    Engine — engineering calculations (NFPA 72 spacing, battery, voltage drop)
    Placement — room/floor/building detector placement analysis
    Audit — safety audit, compliance checks, evidence package
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fireai.core.results import (
    BatteryCapacityResult,
    HeatSpacingResult,
    SmokeSpacingResult,
    VoltageDropResult,
)

if TYPE_CHECKING:
    from fireai.core.qomn_kernel import QOMNKernel
    from fireai.core.safety_assurance import SafetyTier
    from fireai.core.safety_audit_engine import AuditResult


class Engine:
    _kernel: QOMNKernel
    """
    Engineering calculation facade.

    Wraps QOMNKernel computation methods — smoke/heat detector spacing,
    battery capacity, voltage drop — with typed results and integrated
    safety validation.

    Usage:
        engine = Engine()
        spacing = engine.smoke_spacing(ceiling_height_m=3.0)
        battery = engine.battery_capacity(standby_a=1.0, alarm_a=2.0)
        vdrop = engine.voltage_drop(current_a=1.0, length_m=100.0, awg="14")
    """

    def __init__(self) -> None:
        from fireai.core.qomn_kernel import QOMNKernel

        self._kernel = QOMNKernel()

    def smoke_spacing(self, ceiling_height_m: float) -> SmokeSpacingResult:
        """Compute smoke detector spacing per NFPA 72-2022 §17.7.3.2.3."""
        return self._kernel.smoke_detector_spacing(ceiling_height_m)

    def heat_spacing(
        self, ceiling_height_m: float, area_per_detector_m2: float
    ) -> HeatSpacingResult:
        """Compute heat detector spacing per NFPA 72-2022 §17.6.3.1."""
        return self._kernel.heat_detector_spacing(ceiling_height_m, area_per_detector_m2)

    def battery_capacity(
        self,
        standby_load_a: float,
        alarm_load_a: float,
        **kwargs: Any,
    ) -> BatteryCapacityResult:
        """Compute battery capacity per NFPA 72-2022 §10.6.7.2.1."""
        return self._kernel.battery_capacity(standby_load_a, alarm_load_a, **kwargs)

    def voltage_drop(
        self,
        current_a: float,
        length_m: float,
        awg_gauge: str,
        supply_voltage_v: float = 24.0,
        max_drop_pct: float = 10.0,
    ) -> VoltageDropResult:
        """Compute voltage drop per NEC Chapter 9 Table 8."""
        return self._kernel.voltage_drop(
            current_a, length_m, awg_gauge, supply_voltage_v, max_drop_pct
        )

    @property
    def audit_log(self) -> dict[str, Any]:
        """Export the full audit log for AHJ review."""
        return self._kernel.get_audit_log()

    @property
    def audit_integrity(self) -> bool:
        """Verify audit log hash chain is intact."""
        return self._kernel.verify_audit_integrity()


class Placement:
    """
    Detector placement analysis facade.

    Orchestrates room/floor/building-level detector placement with
    coverage verification and proof certificate generation.

    Usage:
        placement = Placement()
        floor_result = placement.analyze_floor(rooms, ceiling_height=3.0)
    """

    def __init__(self) -> None:
        self._floor_analyser: Any = None
        self._building_engine: Any = None

    def _lazy_floor_analyser(self) -> Any:
        if self._floor_analyser is None:
            from fireai.core.floor_analyser import FloorAnalyser

            self._floor_analyser = FloorAnalyser
        return self._floor_analyser

    def _lazy_building_engine(self) -> Any:
        if self._building_engine is None:
            from fireai.core.building_engine import BuildingEngine

            self._building_engine = BuildingEngine
        return self._building_engine

    def analyze_floor(
        self,
        rooms: list[Any],
        ceiling_height: float = 3.0,
        **kwargs: Any,
    ) -> Any:
        """Run floor-level detector placement analysis."""
        Analyser = self._lazy_floor_analyser()
        analyser = Analyser() if callable(Analyser) else Analyser
        return analyser.analyze_floor(rooms, ceiling_height=ceiling_height, **kwargs)

    def analyze_building(self, floors: list[Any], **kwargs: Any) -> Any:
        """Run building-level analysis across multiple floors."""
        Engine_cls = self._lazy_building_engine()
        engine = Engine_cls() if callable(Engine_cls) else Engine_cls
        return engine.analyze(floors, **kwargs)


class Safety:
    """
    Safety and compliance facade.

    Wraps safety tier classification, audit engine, and compliance
    verification into a single entry point.

    Usage:
        safety = Safety()
        tier = safety.classify(...)
        audit = safety.audit_engine(...)
    """

    @staticmethod
    def classify_safety_tier(
        coverage_pct: float,
        proof_valid: bool = False,
        fallback_used: bool = False,
    ) -> SafetyTier:
        """Classify design safety tier per engineering policy."""
        from fireai.core.safety_assurance import classify_safety_tier as _classify

        return _classify(coverage_pct, proof_valid, fallback_used)

    @staticmethod
    def requires_fpe_review(tier: SafetyTier) -> bool:
        """Check if a safety tier requires FPE review."""
        from fireai.core.safety_assurance import tier_requires_fpe_review

        return tier_requires_fpe_review(tier)

    @staticmethod
    def can_submit(tier: SafetyTier) -> bool:
        """Check if a safety tier can be submitted to AHJ."""
        from fireai.core.safety_assurance import tier_can_submit

        return tier_can_submit(tier)

    @staticmethod
    def audit_report(
        design: Any,
        **kwargs: Any,
    ) -> AuditResult:
        """Run full safety audit on a design."""
        from fireai.core.safety_audit_engine import SafetyAuditEngine

        engine = SafetyAuditEngine()
        return engine.run_audit(audit_input=design, **kwargs)
