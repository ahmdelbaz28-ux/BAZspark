# NOSONAR
"""
FACP DETERMINISTIC SELECTION ALGORITHM — thin wrapper around shared module.

Applies strict engineering multipliers, filters, and scoring logic.
"""

import logging
from typing import List, Optional, Tuple

from fireai.core.panel_selection import (
    FireAlarmPanel,
    MASTER_PANEL_DATABASE,
    PanelRecommendation,
    ProjectRequirements,
    SelectionEngine,
    STANDBY_MA_PER_DEVICE as _STANDBY_MA,
    ALARM_MA_PER_DEVICE as _ALARM_MA,
)

logger = logging.getLogger(__name__)

STANDBY_MA_PER_DEVICE = _STANDBY_MA
ALARM_MA_PER_DEVICE = _ALARM_MA

__all__ = [
    "FireAlarmPanel",
    "MASTER_PANEL_DATABASE",
    "PanelRecommendation",
    "ProjectRequirements",
    "SelectionEngine",
]
