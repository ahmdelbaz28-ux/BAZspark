# Electrical Tool Integrations (Path C)

All electrical-analysis tool integrations plug into the platform through one
explicit contract: `engineering_copilot/connectors/base.py::ElectricalConnector`.

## Contract rules

1. **Honest connections** — `connect()` must fail (`return False`) when the
   vendor runtime is unavailable. Simulated sessions are forbidden.
2. **Verbatim reads** — read methods return live vendor data only. Fabricated
   sample rows are forbidden.
3. **Real studies only** — `run_study()` returns real solver output or raises
   `ConnectorUnavailableError`. Fake "completed" statuses are forbidden.
4. **Registry** — concrete connectors register via
   `@register_connector("<name>")` so tooling can enumerate providers without
   importing vendor assemblies.

## Adding a new provider (e.g. SKM, DIALux, DIgSILENT)

```python
# engineering_copilot/connectors/skm_connector.py
from engineering_copilot.connectors.base import (
    ElectricalConnector,
    register_connector,
)

@register_connector("skm")
class SKMConnector(ElectricalConnector):
    def connect(self, project_path=None) -> bool: ...
    def disconnect(self) -> bool: ...
    @property
    def is_connected(self) -> bool: ...
    def read_project(self) -> dict: ...
    def read_buses(self): ...
    def read_transformers(self): ...
    def read_cables(self): ...
    def read_breakers(self): ...
    def read_loads(self): ...
    def supported_studies(self): ...
    def run_study(self, study_type): ...
```

Consumers resolve providers by name:

```python
from engineering_copilot.connectors.base import get_connector

connector = get_connector("etap")           # or "skm", "dialux", ...
connector.connect(project_path="plant.eto")
buses = connector.read_buses()
```

## Current registry

| Provider  | Status |
|-----------|--------|
| `etap`    | Contract implemented; COM bridge pending — connects only inside the ETAP runtime |

## Enforcement

`tests/test_electrical_connector_registry.py` fails the build when a
connector simulates sessions/studies or when the registry loses its
providers.
