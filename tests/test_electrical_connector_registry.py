"""Path C: electrical connector contract + registry tests."""

from __future__ import annotations

import pytest

from engineering_copilot.connectors.base import (
    ConnectorUnavailableError,
    ElectricalConnector,
    get_connector,
    list_connectors,
    register_connector,
)
from engineering_copilot.connectors.etap_connector import ETAPConnector, NotConnectedError


def test_etap_registered_in_connector_registry():
    assert "etap" in list_connectors()
    connector = get_connector("etap")
    assert isinstance(connector, ETAPConnector)
    assert isinstance(connector, ElectricalConnector)


def test_unknown_connector_rejected():
    with pytest.raises(KeyError):
        get_connector("does_not_exist")


def test_connect_fails_honestly_without_runtime():
    """Contract rule 1: no simulated sessions when ETAP runtime is absent."""
    connector = get_connector("etap")
    assert connector.connect("dummy.eto") is False
    assert connector.is_connected is False


def test_reads_require_live_session():
    """No fabricated sample rows may leak out without a connection."""
    connector = get_connector("etap")
    for reader in (
        connector.read_project,
        connector.read_buses,
        connector.read_transformers,
        connector.read_cables,
        connector.read_breakers,
        connector.read_loads,
    ):
        with pytest.raises(NotConnectedError):
            reader()


def test_run_study_never_fabricates_results():
    """Contract rule 3: real solver output or an honest failure."""
    connector = get_connector("etap")
    with pytest.raises((NotConnectedError, ConnectorUnavailableError)):
        connector.run_study("LoadFlow")


def test_custom_connector_registration():
    @register_connector("_test_vendor")
    class _TestVendor(ElectricalConnector):
        def connect(self, project_path=None):
            return True

        def disconnect(self):
            return True

        @property
        def is_connected(self):
            return True

        def read_project(self):
            return {}

        def read_buses(self):
            return []

        def read_transformers(self):
            return []

        def read_cables(self):
            return []

        def read_breakers(self):
            return []

        def read_loads(self):
            return []

        def supported_studies(self):
            return []

        def run_study(self, study_type):
            return {}

    try:
        assert "_test_vendor" in list_connectors()
        instance = get_connector("_test_vendor")
        assert instance.provider_name == "_test_vendor"
        assert instance.connect() is True
    finally:
        from engineering_copilot.connectors import base as base_module

        base_module._REGISTRY.pop("_test_vendor", None)
