"""Shared NFPA 170 device type enumeration for all parsers."""

from enum import Enum


class DeviceType(str, Enum):
    """NFPA 170 device classification symbols used across all parsers."""
    SMOKE_DETECTOR = "SMOKE_DETECTOR"
    HEAT_DETECTOR = "HEAT_DETECTOR"
    MANUAL_PULL_STATION = "MANUAL_PULL_STATION"
    HORN_STROBE = "HORN_STROBE"
    STROBE = "STROBE"
    HORN = "HORN"
    SPEAKER = "SPEAKER"
    FLOW_SWITCH = "FLOW_SWITCH"
    TAMPER_SWITCH = "TAMPER_SWITCH"
    BELL = "BELL"
    DUCT_DETECTOR = "DUCT_DETECTOR"
    CO_DETECTOR = "CO_DETECTOR"
    SPRINKLER = "SPRINKLER"
