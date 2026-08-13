"""
fireai/bridges/building_model_provider.py — ABC Contract for BIM Providers.

Defines ``BuildingModelProvider``, an ABC that canonicalises the contract
already described by the ``BIMProvider`` Protocol in ``bim_provider.py``.
New bridge adapters should inherit from this ABC; existing ones are
updated to inherit from it while remaining Protocol-conformant.

Methods
-------
- extract_rooms(source, **kwargs) -> list[BIMRoom]
- read_devices(source, **kwargs) -> list[dict]
- write_devices(devices, target, **kwargs) -> int
- health_check() -> dict

Safety invariants (mirrored from BIMProvider Protocol):
  1. ``extract_rooms()`` MUST set ``BIMRoom.source`` for audit traceability.
  2. ``extract_rooms()`` MUST return ``[]`` (not raise) for empty input.
  3. ``write_devices()`` is OPTIONAL — raise ``NotImplementedError`` if unsupported.
  4. All methods MUST be deterministic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fireai.bridges.bim_provider import BIMProviderCapability

from fireai.bridges.revit_bim_sync import BIMRoom

logger = logging.getLogger(__name__)


class BuildingModelProvider(ABC):
    """
    ABC for BIM/Building-Model providers.

    Every bridge adapter that talks to a BIM source (Revit, IFC, APS,
    Bentley, AutoCAD) should inherit from this ABC.  The ABC enforces
    the contract at instantiation time (``TypeError`` if a method is
    missing) AND provides a shared base for runtime ``isinstance``
    checks that the structural ``BIMProvider`` Protocol cannot offer
    for class-level checks.
    """

    # -- Metadata -------------------------------------------------------

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable identifier (e.g. ``'local_revit'``)."""

    @property
    @abstractmethod
    def capabilities(self) -> tuple[BIMProviderCapability, ...]:
        """Capability flags declared by this provider."""

    # -- Core contract --------------------------------------------------

    @abstractmethod
    def extract_rooms(
        self,
        source: str | None = None,
        **kwargs: Any,
    ) -> list[BIMRoom]:
        """
        Extract rooms from the BIM source.

        Args:
            source: Optional path/URL/identifier.  ``None`` = default source.
            **kwargs: Provider-specific options.

        Returns:
            List of ``BIMRoom``.  Empty list if no rooms (never raises
            for *no data* — only for genuine errors).
        """

    @abstractmethod
    def read_devices(
        self,
        source: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Read existing fire-alarm devices from the BIM source.

        Returns:
            List of device dicts with at minimum:
            ``device_id``, ``room_id``, ``x``, ``y``, ``z``, ``type``.
        """

    @abstractmethod
    def write_devices(
        self,
        devices: list[dict[str, Any]],
        target: str | None = None,
        **kwargs: Any,
    ) -> int:
        """
        Write devices back to the BIM source.

        Raises ``NotImplementedError`` if the provider lacks write
        capability (callers MUST check ``capabilities`` first).
        """

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """
        Verify provider is operational.

        Returns a dict with keys:
            - ``healthy``: bool
            - ``latency_ms``: float
            - ``details``: str
            - ``error``: str | None
        """

    # -- Shared helpers -------------------------------------------------

    @staticmethod
    def _make_healthy(details: str) -> dict[str, Any]:
        return {"healthy": True, "latency_ms": 0.0, "details": details, "error": None}

    @staticmethod
    def _make_unhealthy(details: str, error: str) -> dict[str, Any]:
        return {"healthy": False, "latency_ms": 0.0, "details": details, "error": error}
