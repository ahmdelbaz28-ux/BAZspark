"""
FACP IMMUTABLE DATA SHEET STORAGE — thin wrapper around shared module.

Contains accurate, verified product datasheet values for selection.
"""

from fireai.core.panel_selection import MASTER_PANEL_DATABASE

NOTIFIER_PANELS = [p for p in MASTER_PANEL_DATABASE if p.manufacturer == "NOTIFIER"]
SIEMENS_PANELS = [p for p in MASTER_PANEL_DATABASE if p.manufacturer == "SIEMENS"]
SIMPLEX_PANELS = [p for p in MASTER_PANEL_DATABASE if p.manufacturer == "SIMPLEX"]
