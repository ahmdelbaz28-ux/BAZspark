# NOSONAR
"""
FACP DETERMINISTIC SELECTION ALGORITHM — thin wrapper around shared module.

Applies strict engineering multipliers, filters, and scoring logic.
"""

import logging

from fireai.core.panel_selection import (
    ALARM_MA_PER_DEVICE as _ALARM_MA,
)
from fireai.core.panel_selection import (
    MASTER_PANEL_DATABASE,
    FireAlarmPanel,
    PanelRecommendation,
    ProjectRequirements,
    SelectionEngine,
)
from fireai.core.panel_selection import (
    STANDBY_MA_PER_DEVICE as _STANDBY_MA,
)

logger = logging.getLogger(__name__)

STANDBY_MA_PER_DEVICE = _STANDBY_MA
ALARM_MA_PER_DEVICE = _ALARM_MA

__all__ = [
    "MASTER_PANEL_DATABASE",
    "FireAlarmPanel",
    "PanelRecommendation",
    "ProjectRequirements",
    "SelectionEngine",
]
