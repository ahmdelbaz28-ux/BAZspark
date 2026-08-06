# FireAI System Architecture

**Architected by Eng. Ahmed Elbaz**

The FireAI platform implements a safety-critical architecture for fire protection engineering. The system enforces deterministic calculation algorithms, code compliance, and immutable auditability.

---

## 1. Multi-Tier Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    L1 - Interface Layer                         │
│  AutoCAD Plugin  │  Revit Bridge  │  Web SPA  │  API Gateway   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    L2 - Orchestration Layer                     │
│  Workflow Engine │ Event Bus │ Agent Dispatcher │ Context Store │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    L3 - Engine Layer                            │
│  NFPA 72 Solver  │ Hydraulic Solver │ Spatial Engine │ Audit Trail │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    L4 - Data Layer                              │
│  PostgreSQL / Supabase │ WAL SQLite │ Redis Cache │ Qdrant Vector│
└─────────────────────────────────────────────────────────────────┘
```

The L1 Interface Layer accepts requests from web clients, AutoCAD scripts, and Revit plugins. Requests undergo origin validation and RBAC checks at the API Gateway.

The L2 Orchestration Layer coordinates multi-step workflows across asynchronous worker tasks. It dispatches event notifications while maintaining session context.

The L3 Engine Layer executes deterministic engineering algorithms for spatial coverage and voltage drop. It enforces strict physical bounds without heuristic approximations.

The L4 Data Layer persists building models, calculation ledgers, and audit logs. Structured data stores in PostgreSQL while vector embeddings persist in Qdrant.

---

## 2. Single Source of Truth (SSoT)

All NFPA 72-2022 engineering constants centralize in `fireai/constants/nfpa72.py`. Secondary modules import from this canonical module to prevent calculation drift.

```
                  ┌───────────────────────────────┐
                  │  fireai/constants/nfpa72.py   │
                  └───────────────┬───────────────┘
                                  │ Imports
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  qomn_kernel.py   │   │  nfpa72_calc.py   │   │  dispatcher.py    │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

Modules must not redefine engineering constants or physical thresholds locally. Centralization guarantees identical calculation results across the API and CLI.

---

## 3. Safety & Verification Architecture

The engine implements a five-layer QOMN-FIRE validation model. Each layer verifies specific physical invariants before passing execution to the next stage.

- Layer 0: Input sanitization and coordinate bound verification
- Layer 1: Deterministic spatial geometry and obstruction analysis
- Layer 2: Electrical circuit voltage drop and battery sizing
- Layer 3: Code compliance verification against NFPA 72 and IBC
- Layer 4: HMAC-SHA256 signed SHA-256 hash-chain audit log generation (tamper-evident; RFC 3161 TSA optional for legal timestamping)

```
Input Data ──► L0 Sanitization ──► L1 Geometry ──► L2 Electrical ──► L3 Code ──► L4 Audit
```

If an evaluation step fails validation, the system halts execution immediately. It logs the exact failure cause and returns a conservative fallback state.

---

## 4. Security & Defense in Depth

The application applies a four-tier defense model across all entry points. Security controls operate continuously from network ingress to data storage.

1. Network Ingress: Akamai/Cloudflare headers, IP filtering, and rate limits
2. Application Layer: Strict Pydantic schemas and CORS origin enforcement
3. Data Layer: Role-based access control and encrypted connection pools
4. Storage Layer: HMAC signed ledgers and isolated execution environments

```
Traffic ──► Ingress Guard ──► App Validation ──► RBAC Engine ──► Encrypted Storage
```

Fail-Fast secret validation inspects environment tokens during app initialization. Startup terminates instantly if default signing keys are detected in production.

---

## 5. Storage & Database Resilience

PostgreSQL functions as the primary store for structured building topologies. WAL-mode SQLite acts as an isolated local fallback during offline execution.

```
PostgreSQL / Supabase ◄──► PgBouncer Pool ◄──► SQLAlchemy / psycopg2
       ▲
       └──► Local Fallback: WAL SQLite (fireai_universal.db)
```

PostgreSQL connection pools incorporate pre-ping health checks and auto-retry logic. This design maintains zero-downtime connection handling with PgBouncer.

Redis caches transient spatial queries and session tokens. Qdrant manages high-dimensional vector embeddings for GraphRAG knowledge queries.

---

## 6. Deployment & Infrastructure

The application runs in containerized environments managed by Kubernetes or Docker Compose. Container images compile through multi-stage Dockerfiles.

```
Docker Image ──► GHCR Registry ──► Helm Chart ──► Kubernetes Pods ──► Ingress Proxy
```

Production helm charts deploy isolated pods with automated liveness probes. Scaling rules maintain service availability under heavy calculation loads.