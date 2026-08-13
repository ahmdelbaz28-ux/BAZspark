# System Architecture

## Overview

BAZSpark is a safety-critical fire alarm engineering platform. The architecture prioritizes reliability, accuracy, and auditability for life-safety calculations.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
├─────────────────────────────────────────────────────────────┤
│  React 18 SPA          │  Electron Desktop   │  REST API    │
│  • TypeScript 5.9      │  • Windows           │  • FastAPI   │
│  • Vite 8              │  • macOS             │  • WebSocket │
│  • Tailwind CSS 4      │  • Linux             │  • 188 ends  │
│  • Three.js (3D)       │                      │              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Service Layer                             │
├─────────────────────────────────────────────────────────────┤
│  Authentication     │  RBAC              │  Rate Limiting   │
│  HMAC-SHA256        │  5 roles           │  SlowAPI         │
│  HttpOnly Cookies   │  Permission-based  │  Brute-force     │
├─────────────────────────────────────────────────────────────┤
│  Workflow Engine    │  Digital Twin      │  Audit Trail     │
│  LangGraph          │  CAD ↔ BIM         │  Merkle Tree     │
│  Multi-agent        │  Bidirectional     │  Immutable       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Core Engine Layer                          │
├─────────────────────────────────────────────────────────────┤
│  NFPA 72 Engine     │  Spatial Analysis  │  Compliance Gate │
│  • Detector spacing │  • Voronoi         │  • NFPA 72       │
│  • Coverage         │  • MIP solver      │  • NEC           │
│  • NAC design       │  • Shapely/GEOS    │  • IBC           │
│  • Voltage drop     │  • Coverage map    │  • SOLAS         │
│  • Battery sizing   │                    │                  │
├─────────────────────────────────────────────────────────────┤
│  Acoustics Engine   │  QOMN Conduit      │  FACP Selector   │
│  • dB calculations  │  • Cable routing   │  • Panel sizing  │
│  • NHA spacing      │  • Fill analysis   │  • Circuit calc  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Data Layer                                │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL         │  Redis             │  Qdrant          │
│  (Supabase)         │  Cache + sessions  │  Vector DB (RAG) │
│  Primary DB         │                    │                  │
├─────────────────────────────────────────────────────────────┤
│  Neo4j              │  SQLite            │  File Storage    │
│  Graph DB           │  Development       │  CAD/BIM files   │
│  Network topology   │  Local dev         │  Reports         │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### NFPA 72 Engine (`fireai/core/`)

The deterministic engineering kernel implements NFPA 72-2022 calculations:

- **Detector Placement**: Smoke detectors use flat 9.1m spacing (§17.7.3.2.3). Heat detectors use 6.1m spacing (§17.6.3.1).
- **Coverage Analysis**: Spatial analysis using Shapely/GEOS with Voronoi diagrams and MIP solvers.
- **Compliance Verification**: Automated checks against NFPA 72, NEC, IBC, and local codes.
- **NAC Design**: Notification appliance circuit calculations with voltage drop and battery sizing.

Key files:
- `fireai/core/qomn_kernel.py` — Deterministic calculation kernel
- `fireai/core/nfpa72_engine.py` — Main NFPA 72 compliance engine
- `fireai/core/nfpa72_models.py` — Data models and constants
- `fireai/core/voltage_drop.py` — Voltage drop calculator
- `fireai/constants/nfpa72.py` — Canonical NFPA 72-2022 constants (Single Source of Truth)
- `fireai/constants/nec.py` — NEC 2023 Chapter 9 constants

### Digital Twin

Bidirectional conversion between AutoCAD and Revit formats:

- **Input**: DWG, DXF, IFC, Revit JSON
- **Output**: DWG, DXF, IFC, Revit elements
- **Process**: Parse → Normalize → Transform → Validate → Export

Key files:
- `qomn_fire/` — Standalone QOMN-FIRE engine
- `parsers/` — Multi-format file parsers (DXF, IFC, PDF, Excel, Image)
- `revit_addin/` — Revit add-in (C#/.NET)

### Audit Trail

Immutable, cryptographically signed record of all engineering decisions:

- **HMAC-SHA256**: Each calculation produces a signed hash
- **Merkle Tree**: Tamper-evident chain of all project changes
- **PE Review**: Designed for Professional Engineer review and sign-off

Key file: `fireai/core/audit_trail.py`

### Marine Module

Fire safety design for ships per international standards:

- **SOLAS** Chapter II-2 (IMO)
- **IEC 60092-502/504** (Electrical installations on ships)
- **ISO 15370** (Thermal alarms)
- **NFPA 302** (Small craft)
- **Lloyd's Register** rules

Key directory: `marine/`

### Distributed FACP

Three-layer agent communication protocol for fire alarm control panels:

```
L1 External Clients → L2 Orchestrator → L3 Engine Workers
     (Gateway)         (Cluster)          (Cluster)
```

Key directory: `facp_distributed/`

## Security Architecture

### Authentication

- API key-based authentication
- HttpOnly cookies with HMAC-SHA256 signing
- Session management with secure tokens

### Authorization (RBAC)

Five roles with permission-based access:

| Role | Capabilities |
|---|---|
| `admin` | Full system access |
| `engineer` | Create/edit/delete projects, run calculations |
| `reviewer` | Read-only access, approve/reject changes |
| `viewer` | Read-only access to projects and reports |
| `api` | Programmatic access with limited scope |

### Defense in Depth

- **Network**: TLS 1.3, CSP/HSTS headers
- **Application**: Input validation, SQL injection prevention
- **Data**: Encryption at rest, integrity verification
- **Audit**: Comprehensive logging, tamper-evident records

## Data Flow

### Calculation Request

```
Client → API → Auth → RBAC → Engine → Validation → Audit → Response
                                       ↓
                                  NFPA 72 Check
                                  Coverage Analysis
                                  Compliance Gate
```

### Digital Twin Conversion

```
Upload → Parse (DWG/DXF/IFC) → Normalize → Transform → Validate → Export
                                    ↓
                              Geometry Engine
                              (Shapely/GEOS)
                                    ↓
                              Compliance Check
                                    ↓
                              Audit Trail
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│  Load Balancer (Cloudflare / Akamai)                │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  Kubernetes Cluster                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ API Pod(s)  │ │ Worker Pod  │ │ Redis Pod   │   │
│  │ (FastAPI)   │ │ (Celery)    │ │ (Cache)     │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  Databases                                          │
│  PostgreSQL (Supabase) │ Qdrant │ Neo4j │ Redis    │
└─────────────────────────────────────────────────────┘
```

## Development vs Production

| Aspect | Development | Production |
|---|---|---|
| Database | SQLite | PostgreSQL |
| Auth | Relaxed (dev keys) | Strict (HMAC + RBAC) |
| Caching | None | Redis |
| Vector DB | None | Qdrant |
| Graph DB | None | Neo4j |
| Logging | Console | Prometheus + Grafana |
| Tracing | None | Loki + Tempo |

## Key Design Decisions

1. **Deterministic Calculations**: All NFPA 72 calculations use deterministic algorithms, not heuristics. This ensures reproducible results for PE review.

2. **Immutable Audit Trail**: Every engineering decision is recorded with a cryptographic hash. This is non-negotiable for a life-safety system.

3. **Fail-Safe Defaults**: When in doubt, the system defaults to the most conservative (safest) interpretation of the code.

4. **Separation of Concerns**: The core engine is independent of the web layer. It can be used as a library, CLI, or API.

5. **Single Source of Truth**: All NFPA 72 / NEC constants are defined in `fireai/constants/` and referenced everywhere else. No hardcoded values in calculation code.
