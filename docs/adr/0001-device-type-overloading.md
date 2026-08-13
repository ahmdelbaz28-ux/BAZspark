# 0001 — Device Type Overloading

The term "Device" is used for three distinct domain concepts across the
codebase. This is an accepted trade-off to avoid a massive cross-cutting
rename; future work should disambiguate when the refactoring cost is
justified.

## Context

The BAZSpark/FireAI codebase uses "Device" in three different ways:

1. **Frontend canvas (`DeviceType`)** — Electrical power system components
   (GENERATOR, BATTERY, LOAD, PANEL) with `defaultLoad` in Amperes.
   Source: `frontend/src/store/simpleStore.ts`

2. **Backend database (`backend/db_models.py::Device`)** — Fire alarm field
   devices (detectors, pull stations, notification appliances) with NFPA 72
   compliance attributes (spacing, coverage, candela rating).

3. **Backend UDM CRUD (`backend/schemas.py::DeviceCreate`/`DeviceResponse`)** —
   Generic device entity in the Universal Data Model, synced for conflict
   detection.

## Decision

Keep all three named "Device" for now. The disambiguation is documented in
`CONTEXT.md` (Section D — Core Entities) with a "rule of thumb" for which
meaning applies in which context.

## Considered Options

- **Rename frontend `DeviceType` → `PowerComponent`** — More precise but
  would require renaming across 20+ frontend files (components, services,
  translations, help topics).

- **Rename backend `Device` → `FireAlarmDevice`** — More precise but would
  require renaming across 30+ backend files (models, routers, services,
  tests, database migrations).

- **Keep as-is with glossary** — Zero code churn, the glossary provides
  the disambiguation. The cost is that new developers must learn the
  context-dependent meanings.

The rename options would each take 2-3 developer-days and touch 150+
files with risk of merge conflicts. The glossary approach was chosen to
unblock the current work. A future PR should plan the rename as a
dedicated refactoring effort, ideally batched with a major version
boundary.

## Consequences

- New contributors must check the glossary when encountering "Device".
- Code searches for "Device" return results from all three contexts,
  requiring manual filtering.
- The risk of a bug caused by confusing the two meanings is low because
  the frontend/backend boundary naturally isolates them (frontend "Device"
  is TypeScript, backend "Device" is Python — they never cross the wire
  as the same serializable type).
- When the refactoring is done, the three types should be named:
  1. `PowerComponent` (frontend canvas)
  2. `FireAlarmDevice` (backend models)
  3. `UdmDevice` (backend schemas)
