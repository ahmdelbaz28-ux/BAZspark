"""
QOMN-FIRE UNIFIED ERROR FRAMEWORK
Extended with parsing and file validation error types for the input pipeline.

Safety-Critical: Each error type maps to a specific physical failure mode.
Missing an error means a corrupted file passes silently = wrong building model = people die.
"""

from typing import Generic, TypeVar, Optional, Union

T = TypeVar('T')
E = TypeVar('E')

class Result(Generic[T, E]):
    def __init__(self, value: Optional[T] = None, error: Optional[E] = None):
        self._value = value
        self._error = error

    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def is_failure(self) -> bool:
        return self._error is not None

    def unwrap(self) -> T:
        if self._error is not None:
            raise ValueError(f"Panic: Attempted to unwrap failure Result: {self._error}")
        return self._value

    def error(self) -> E:
        if self._error is None:
            raise ValueError("Panic: Attempted to fetch error of successful Result")
        return self._error

class BaseEngineeringError:
    def __init__(self, message: str, code_ref: str, remedy: str):
        self.message = message
        self.code_ref = code_ref
        self.remedy = remedy

    def __repr__(self) -> str:
        return f"[{self.code_ref}] Error: {self.message} (Remedy: {self.remedy})"

class ConduitFillError(BaseEngineeringError): pass
class NECViolationError(BaseEngineeringError): pass
class HatchPlacementError(BaseEngineeringError): pass
class PhysicalConstraintError(BaseEngineeringError): pass
class FACPSelectionError(BaseEngineeringError): pass

# ── Input Parsing Pipeline Error Types ──
# These errors prevent corrupted BIM files from producing wrong fire protection designs.

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
    """DWG→DXF or RVT→IFC conversion failed — external tool error."""
    pass

class GeometryError(BaseEngineeringError):
    """Building geometry is physically impossible (zero-area rooms, unclosed boundaries)."""
    pass

class UnitError(BaseEngineeringError):
    """File uses wrong unit system (mm/inches instead of meters) — coordinates exceed limits."""
    pass
