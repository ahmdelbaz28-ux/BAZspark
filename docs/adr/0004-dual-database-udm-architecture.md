# 0004 — Dual-Database UDM Architecture

## Status
Accepted

## Date
2026-07-27

## Context

BAZSpark requires two distinct data-access patterns:

1. **CRUD operations** — Creating, reading, updating, and deleting
   projects, devices, and connections. These are transactional,
   relationship-heavy, and benefit from a relational model with
   foreign keys and joins.

2. **Spatial analysis** — Detecting overlapping device coverage zones,
   verifying spacing compliance, and performing conflict detection.
   These are read-heavy, geometry-intensive queries that benefit from
   spatial indexing.

A single database forces a trade-off: either the CRUD operations
suffer from spatial-index overhead, or the spatial queries lack
efficient indexing. Additionally, coupling conflict detection to the
primary write path means a spatial-query failure could block
project creation.

The UDM (Universal Data Model) was introduced as **System B** — a
secondary, synchronized data store dedicated to spatial queries and
conflict detection. The primary database (**System A**) handles all
CRUD operations.

## Decision

Maintain a dual-database architecture with one-way synchronization:

```
System A (Primary)          System B (UDM)
PostgreSQL/SQLite CRUD  ──→  SQLite with spatial indexing
       │                           │
       │ sync_device_to_udm()      │ conflict detection
       │ sync_project_to_udm()     │ coverage analysis
       │ sync_connection_to_udm()  │ spacing verification
       │                           │
       └──── project_bridge.py ────┘
```

### Design Constraints

1. **One-way sync only** — Data flows from System A → System B via
   `backend/project_bridge.py`. System B is never written to directly
   by API consumers.

2. **Fire-and-forget sync** — `sync_device_to_udm()` and related
   functions must never raise exceptions. Sync failures are logged
   but do not block the primary CRUD operation. The system tolerates
   temporary UDM inconsistency.

3. **Pluggable backend** — System B defaults to SQLite but the
   `db_service.py` interface supports PostGIS-capable backends without
   affecting System A.

4. **Spatial queries are read-only** — Conflict detection and coverage
   analysis read from System B. They never write back to System A.

## Alternatives Considered

### PostGIS on the primary database
- Pros: Single database; no sync overhead; native spatial queries
- Cons: Requires PostGIS extension (not available on all hosting);
  spatial-index overhead degrades CRUD performance; couples conflict
  detection to the primary write path
- Rejected: The separation of concerns is valuable; spatial query
  failures should not block project creation

### In-memory spatial index (Redis + custom geometry)
- Pros: Fast spatial queries; no additional database
- Cons: Redis geo-commands lack the precision needed for detector
  coverage analysis (sub-metre accuracy); data must be rebuilt on
  restart; adds operational complexity
- Rejected: Insufficient precision for life-safety calculations

### Single database with read replicas
- Pros: Standard scaling pattern; no sync logic needed
- Cons: Read replicas don't solve the spatial-index problem; adds
  replication lag; over-engineered for the current team size
- Rejected: Does not address the core problem (spatial vs. CRUD
  access patterns)

## Consequences

- **Sync failures are non-blocking.** If the UDM is temporarily
  unavailable, CRUD operations continue. The trade-off is that spatial
  queries may return stale data. This is acceptable because conflict
  detection is a review-time activity, not a real-time constraint.

- **Dual-database adds operational complexity.** Two databases must
  be backed up, monitored, and migrated. The `alembic/` directory
  handles System A migrations; System B migrations are manual
  (SQLite schema is simple).

- **The `project_bridge.py` module is critical infrastructure.**
  It must be thoroughly tested (352+ lines, 15+ test cases) and
  kept free of business logic. It is a sync layer, not a service.

- **Future: PostGIS.** When the project scales to multi-tenant SaaS,
  System B should migrate to PostGIS for concurrent spatial queries.
  The pluggable backend design makes this a configuration change, not
  a rewrite.
