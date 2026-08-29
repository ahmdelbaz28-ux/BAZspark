"""Electrical analysis tool connector contract + registry (Path C).

Every electrical-engineering integration (ETAP today; SKM, DIgSILENT,
DIALux, ...) plugs into the platform through one explicit contract so the
service layer never depends on a vendor SDK shape.

Contract rules
--------------
1. ``connect`` must fail honestly when the vendor runtime is unavailable —
   NEVER simulate a successful session.
2. Read methods return vendor data verbatim (no fabricated sample rows).
3. ``run_study`` returns real solver output or raises; simulated results are
   forbidden at this layer.
4. Register concrete connectors via :func:`register_connector` so tooling can
   enumerate providers without importing vendor assemblies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

_REGISTRY: dict[str, type[ElectricalConnector]] = {}


class ConnectorUnavailableError(ConnectionError):
    """Raised when the vendor runtime/application cannot be reached."""


def register_connector(name: str):
    """Class decorator that adds a connector implementation to the registry."""

    def _wrap(cls: type[ElectricalConnector]) -> type[ElectricalConnector]:
        _REGISTRY[name.strip().lower()] = cls
        cls.provider_name = name.strip().lower()  # type: ignore[attr-defined]
        return cls

    return _wrap


def get_connector(name: str, **kwargs: Any) -> ElectricalConnector:
    """Instantiate a registered connector by provider name."""
    key = name.strip().lower()
    if key not in _REGISTRY:
        raise KeyError(f"Unknown electrical connector {name!r}. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[key](**kwargs)


def list_connectors() -> list[str]:
    """Names of all registered electrical connectors."""
    return sorted(_REGISTRY)


class ElectricalConnector(ABC):
    """Uniform interface for electrical analysis tool integrations."""

    #: Set by :func:`register_connector`.
    provider_name: str = ""

    # ── lifecycle ────────────────────────────────────────────────────────
    @abstractmethod
    def connect(self, project_path: str | None = None) -> bool:
        """Attach to a running vendor application / open a project."""

    @abstractmethod
    def disconnect(self) -> bool:
        """Detach from the vendor application."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True only while a live vendor session is bound."""

    # ── model reads ──────────────────────────────────────────────────────
    @abstractmethod
    def read_project(self) -> dict[str, Any]:
        """Read the full project model from the connected tool."""

    @abstractmethod
    def read_buses(self) -> list[dict[str, Any]]:
        """Read distribution buses / nodes."""

    @abstractmethod
    def read_transformers(self) -> list[dict[str, Any]]:
        """Read transformers."""

    @abstractmethod
    def read_cables(self) -> list[dict[str, Any]]:
        """Read cables / feeders."""

    @abstractmethod
    def read_breakers(self) -> list[dict[str, Any]]:
        """Read protective devices."""

    @abstractmethod
    def read_loads(self) -> list[dict[str, Any]]:
        """Read loads."""

    # ── studies ──────────────────────────────────────────────────────────
    @abstractmethod
    def supported_studies(self) -> list[str]:
        """Study identifiers this provider can execute."""

    @abstractmethod
    def run_study(self, study_type: str) -> dict[str, Any]:
        """Execute one study and return the real solver output."""
