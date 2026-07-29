# 03 — Dependency Graph

**Project:** BAZspark v1.55.0
**Audit Date:** 2026-07-13

---

## Dependency Graph

```
                    ┌─────────────┐
                    │   Frontend   │
                    │  (React 18)  │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │   Backend    │
                    │  (FastAPI)   │
                    └──┬──┬──┬──┬──┘
           ┌───────────┘  │  │  └───────────┐
           │              │  │              │
    ┌──────▼──────┐ ┌─────▼──▼──┐ ┌────────▼────────┐
    │  Database   │ │   Redis   │ │  External APIs  │
    │ SQLite/PG   │ │ Sessions  │ │ LLM, Langfuse   │
    └─────────────┘ │ RateLimit │ │ Sentry, Supabase│
                    └───────────┘ └─────────────────┘
    ┌─────────────┐ ┌───────────┐
    │   Qdrant    │ │   Neo4j   │
    │  (Vectors)  │ │  (Graph)  │
    └─────────────┘ └───────────┘
```

## Dependency Analysis

### Clean Layering ✅
- Frontend → Backend API (one direction, no back-imports)
- Backend routers → Backend services (one direction)
- Backend services → Database/Redis/External (one direction)
- **No services→routers back-imports** (verified by grep)

### No Circular Dependencies ✅
- Verified: no module imports from a module that imports it
- Routers import from services, services import from database/utils
- No router imports from another router

### Shared Mutable State (Documented) ⚠️
| State | Location | Risk | Mitigation |
|---|---|---|---|
| Session store | session_store.py | Per-worker if no Redis | V254: REDIS_URL wired |
| Rate limiter | limiter.py | Per-worker if no Redis | V248: Redis storage_uri |
| API key cache | api_keys.py | Revoked keys work up to TTL | Acceptable (5min TTL) |
| Failed attempts | session_store.py | Per-worker if no Redis | V254: REDIS_URL wired |

### Single Points of Failure
| Component | SPOF? | Mitigation |
|---|:---:|---|
| Database | Yes | Volume mount + backup strategy |
| Redis | No | In-memory fallback (V244) |
| Backend | No | HF Spaces auto-restart |
| Frontend | No | Vercel CDN + HF Spaces |

### Hidden Dependencies (V254 Found & Fixed)
1. ✅ CSRF middleware was defined but never called (hidden: frontend expected CSRF, backend didn't enforce)
2. ✅ REDIS_URL not passed to container (hidden: session store assumed Redis was available)
3. ✅ DATABASE_URL path diverged from DIGITAL_TWIN_DB_PATH (hidden: data written outside volume)
4. ✅ Config.validate_config() never called (hidden: invalid config silently accepted)

### External Dependencies
| Dependency | Required? | Fallback? |
|---|:---:|:---:|
| Redis | No (recommended) | In-memory (dev only) |
| Qdrant | No (AI features) | Features disabled |
| Neo4j | No (topology) | Features disabled |
| Supabase | No (REST data) | Direct DB queries |
| LLM (Zenmux) | No (AI copilot) | Error toast |
| Langfuse | No (observability) | No tracing |
| Sentry | No (error tracking) | console.error |

**All external dependencies have graceful fallbacks.** ✅
