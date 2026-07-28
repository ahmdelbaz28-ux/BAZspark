"""
QOMN-FIRE UNIFIED ERROR FRAMEWORK
Extended with parsing and file validation error types for the input pipeline.

Safety-Critical: Each error type maps to a specific physical failure mode.
Missing an error means a corrupted file passes silently = wrong building model = people die.
"""

from fireai.core.base_types import Result

# Re-export shared Result for qomn_fire code
__all__ = [
    "BaseEngineeringError",
    "ConduitFillError",
    "ConversionError",
    "CorruptionError",
    "FACPSelectionError",
    "FileValidationError",
    "FormatError",
    "GeometryError",
    "HatchPlacementError",
    "NECViolationError",
    "PhysicalConstraintError",
    "Result",
    "UnitError",
    "VersionError",
]


class BaseEngineeringError(Exception):
    """
    Base class for all QOMN-FIRE engineering errors.
    """

    def __init__(self, message: str, code_ref: str, remedy: str):
        super().__init__(message)
        self.message = message
        self.code_ref = code_ref
        self.remedy = remedy

    def __repr__(self) -> str:
        return f"[{self.code_ref}] Error: {self.message} (Remedy: {self.remedy})"

    def __str__(self) -> str:
        return f"[{self.code_ref}] {self.message}"


class ConduitFillError(BaseEngineeringError):
    pass


class NECViolationError(BaseEngineeringError):
    pass


class HatchPlacementError(BaseEngineeringError):
    pass


class PhysicalConstraintError(BaseEngineeringError):
    pass


class FACPSelectionError(BaseEngineeringError):
    pass


class FileValidationError(BaseEngineeringError):
    """File does not meet structural requirements (existence, size, permissions)."""
    pass


class FormatError(BaseEngineeringError):
    """File format cannot be identified — magic bytes don't match any known specification."""
    pass


class VersionError(BaseEngineeringError):
    """File version is unsupported or incompatible with the parser."""
    pass


class CorruptionError(BaseEngineeringError):
    """File is structurally corrupted — missing mandatory sections or markers."""
    pass


class ConversionError(BaseEngineeringError):
    """DWG->DXF or RVT->IFC conversion failed — external tool error."""
    pass


class GeometryError(BaseEngineeringError):
    """Building geometry is physically impossible (zero-area rooms, unclosed boundaries)."""
    pass


class UnitError(BaseEngineeringError):
    """File uses wrong unit system (mm/inches instead of meters) — coordinates exceed limits."""
    pass
