# FireAI Platform Configuration Guide

**Environment & Security Settings Reference**

The FireAI platform uses environment variables for zero-code deployments. All configuration parameters pass through strict validation during application initialization.

---

## 1. Core & Environment Settings

The environment type determines validation rules, logging verbosity, and API documentation visibility across runtime services.

| Variable | Values | Purpose | Default |
|---|---|---|---|
| `FIREAI_ENV` | `development`, `production` | Execution mode | `production` |
| `FIREAI_DATA_DIR` | File path | Persistent storage directory | `/app/data` |
| `FIREAI_LOGS_DIR` | File path | System log directory | `/app/logs` |

Setting `FIREAI_ENV=production` automatically disables anonymous Swagger documentation routes (`/docs`, `/openapi.json`) to prevent API surface exposure.

---

## 2. Secrets & Fail-Fast Authentication

Production mode enforces strict secret validation during startup. If missing or default placeholder keys are detected, startup terminates immediately.

| Variable | Requirement | Purpose |
|---|---|---|
| `FIREAI_SESSION_SECRET` | Min 43 chars (256-bit) | Session token signing secret |
| `JWT_SECRET` | Min 32 chars | JWT token encryption key |
| `FIREAI_API_KEY` | Min 32 chars | Primary API authorization key |
| `FIREAI_EVIDENCE_HMAC_KEY` | 64 hex chars | Merkle tree audit log HMAC key |

Placeholders such as `secret`, `change-me`, or `admin` trigger immediate `RuntimeError` aborts during container boot.

---

## 3. Database Connection Resilience

The primary database layer connects via PostgreSQL with fallback support for SQLite during offline or single-instance executions.

| Variable | Specification | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Primary PostgreSQL connection string |
| `NEON_DATABASE_URL` | Direct IPv4 URI | Automatic IPv4 fallback connection |
| `DIGITAL_TWIN_DB_PATH` | File path | Local WAL-mode SQLite fallback |

PostgreSQL connection pools execute pre-ping health checks before reusing idle connections. This design guarantees resilience when operating behind PgBouncer.

---

## 4. Cache & Memory Services

Redis handles rate-limiting quotas, ephemeral session tokens, and pub/sub events. Qdrant manages vector embeddings for GraphRAG memory queries.

| Variable | Specification | Default |
|---|---|---|
| `REDIS_URL` | `redis://:pass@host:port/0` | In-memory cache endpoint |
| `QDRANT_HOST` | Hostname / IP | Vector memory server |
| `QDRANT_PORT` | Port number | `6333` |

When Redis is unavailable, the rate limiter falls back to an in-memory sliding window algorithm without crashing incoming API requests.

---

## 5. Security Middleware & CORS

Security middleware filters incoming HTTP requests before reaching business routers. Origins must be declared explicitly in production mode.

| Variable | Specification | Enforcement |
|---|---|---|
| `CORS_ORIGINS` | Comma-separated URLs | Wildcard `*` is strictly forbidden |
| `AKAMAI_ENABLED` | `true` / `false` | Validates Akamai EdgeWorker headers |
| `AKAMAI_REQUIRE_ORIGIN_TOKEN` | String token | Blocks direct origin bypass attacks |

Omitting `CORS_ORIGINS` in production mode halts application boot. The system requires explicit domain declaration to prevent data exfiltration.

---

## 6. Performance & Worker Tuning

Worker concurrency and command timeouts balance calculation throughput against memory constraints.

| Variable | Recommended Value | Purpose |
|---|---|---|
| `FIREAI_PROCESSING_TIMEOUT` | `300` | Max seconds for spatial calculations |
| `FIREAI_HTTP_CLIENT_TIMEOUT` | `30` | Adapter HTTP fetch timeout |
| `FIREAI_MEMORY_CACHE_SIZE` | `128` | Maximum cache allocation in MB |

High-concurrency deployments should tune PostgreSQL pool sizes (`minconn=2`, `maxconn=20`) to match downstream database connection limits.