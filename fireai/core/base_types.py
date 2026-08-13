"""Shared foundational types — Result, Point3D, and enums for all QOMN modules."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")
E = TypeVar("E")


class Result[T, E]:
    __slots__ = ("_error", "_ok", "_value")

    def __init__(self, value: T | None = None, error: E | None = None, *, ok: bool | None = None):
        if ok is not None:
            self._ok = ok
        elif error is not None:
            self._ok = False
        else:
            self._ok = True

        if value is not None and error is not None:
            raise ValueError(
                f"Result cannot hold both value and error. "
                f"Got value={value!r} and error={error!r}."
            )
        if value is None and error is None and ok is None:
            raise ValueError(
                "Result must hold either a value or an error, not neither. "
                "Use Result(value=x) for success or Result(error=e) for failure."
            )
        self._value = value
        self._error = error

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        return cls(value=value, error=None, ok=True)

    @classmethod
    def err(cls, error: E) -> Result[T, E]:
        return cls(value=None, error=error, ok=False)

    @classmethod
    def success(cls, value: T) -> Result[T, E]:
        return cls.ok(value)

    @classmethod
    def failure(cls, error: E) -> Result[T, E]:
        return cls.err(error)

    def is_ok(self) -> bool:
        return self._ok

    def is_err(self) -> bool:
        return not self._ok

    @property
    def is_success(self) -> bool:
        return self._ok

    @property
    def is_failure(self) -> bool:
        return not self._ok

    @property
    def value(self) -> T:
        if not self._ok:
            raise AttributeError(
                "Attempted to access .value on an error Result. "
                "Always check is_ok() before accessing .value."
            )
        if self._value is None:
            raise AttributeError(
                "Attempted to access .value on a success Result with None value."
            )
        return self._value

    @property
    def error(self) -> E:
        if self._ok:
            raise AttributeError(
                "Attempted to access .error on a success Result. "
                "Always check is_err() before accessing .error."
            )
        if self._error is None:
            raise AttributeError(
                "Attempted to access .error on a failure Result with None error."
            )
        return self._error

    def unwrap(self) -> T:
        if self._error is not None:
            raise ValueError(f"Panic: Attempted to unwrap failure Result: {self._error}")
        if self._value is None:
            raise ValueError("Panic: Attempted to unwrap None value from success Result")
        return self._value

    def unwrap_or(self, default: T) -> T:
        if self._error is not None:
            return default
        return self._value if self._value is not None else default

    def __repr__(self) -> str:
        if self._ok:
            return f"Result.ok({self._value!r})"
        return f"Result.err({self._error!r})"


class DeviceType(StrEnum):
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


class ConduitType(StrEnum):
    EMT = "EMT"
    RMC = "RMC"
    FMC = "FMC"
    UPVC_SCH40 = "UPVC_SCH40"
    UPVC_SCH80 = "UPVC_SCH80"
    RGD = "RGD"


class FittingType(StrEnum):
    ELBOW_90 = "ELBOW_90"
    ELBOW_45 = "ELBOW_45"
    COUPLING = "COUPLING"
    TEE = "TEE"
    PULL_BOX = "PULL_BOX"


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def __post_init__(self) -> None:
        for name, val in (("x", self.x), ("y", self.y), ("z", self.z)):
            if not math.isfinite(val):
                raise ValueError(
                    f"Point3D.{name} must be finite (got {val}). "
                    "Non-finite coordinates indicate data corruption."
                )
        object.__setattr__(self, "x", round(float(self.x), 4))
        object.__setattr__(self, "y", round(float(self.y), 4))
        object.__setattr__(self, "z", round(float(self.z), 4))

    def distance_to(self, other: Point3D) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def manhattan_to(self, other: Point3D) -> float:
        return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_dict(self) -> dict[str, float]:
        return {"X": self.x, "Y": self.y, "Z": self.z}

    def __repr__(self) -> str:
        return f"Point3D(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f})"


__all__ = [
    "ConduitType",
    "DeviceType",
    "E",
    "FittingType",
    "Point3D",
    "Result",
    "T",
]
