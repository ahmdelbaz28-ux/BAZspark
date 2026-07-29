# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
QOMN-FIRE FACP SELECTION ENGINE — thin wrapper around shared module.

Reference Standard: NFPA 72 (2022) §10.6.7, UL 864 10th Edition.

Wraps the shared SelectionEngine to return Result[PanelRecommendation, FACPSelectionError].
"""

from typing import Any, Dict, Tuple

from fireai.core.panel_selection import (
    FireAlarmPanel,
)
from fireai.core.panel_selection import (
    PanelRecommendation as _PanelRec,
)
from fireai.core.panel_selection import (
    ProjectRequirements as _ProjReq,
)
from fireai.core.panel_selection import (
    SelectionEngine as _SelectionEngine,
)
from qomn_fire.core.errors import FACPSelectionError, Result


class PanelRecommendation(_PanelRec):
    ...


class ProjectRequirements(_ProjReq):
    ...


class SelectionEngine(_SelectionEngine):
    @classmethod
    def select_panel(cls, req: ProjectRequirements) -> Result[PanelRecommendation, FACPSelectionError]:
        try:
            rec = super().select_panel(req)
            return Result(value=rec)
        except ValueError as e:
            return Result(error=FACPSelectionError(
                message=str(e),
                code_ref="UL 864 / NFPA 72",
                remedy="Reduce required device loads or transition to a multi-node networked panel architecture."
            ))

    @classmethod
    def compute_battery_ah(
        cls,
        device_count: int,
        nac_circuit_count: int,
        panel: FireAlarmPanel,
        requires_voice: bool,
        min_temperature_c: float = 20.0,
    ) -> Tuple[float, Dict[str, Any]]:
        return super().compute_battery_ah(
            device_count, nac_circuit_count, panel, requires_voice, min_temperature_c
        )
