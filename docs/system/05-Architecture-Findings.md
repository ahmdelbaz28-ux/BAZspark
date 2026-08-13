# 05 — Architecture Findings

**Project:** BAZspark v1.55.0
**Audit Date:** 2026-07-13

---

## Architecture Strengths

### Clean Layering ✅
```
Frontend (React) → API (FastAPI routers) → Services → Database
                                          → External services
```
- No back-imports (services don't import from routers)
- No circular dependencies
- Clear separation of concerns

### Security Architecture ✅
- Defense in depth: Auth → RBAC → CSRF → Rate limiting → Input validation
- HttpOnly cookies (XSS can't steal sessions)
- HMAC-SHA256 session signing (tamper-proof)
- bcrypt API key hashing (timing-attack resistant)
- Parameterized SQL (injection-proof)
- Path traversal protection on uploads

### Resilience Architecture ✅
- PageErrorBoundary (page-level error isolation, V250)
- ErrorRecovery (app-level error boundary)
- ChunkLoadError auto-reload (V250)
- Redis session store with in-memory fallback (V244)
- WebSocket auto-reconnect (5 attempts with backoff)
- Config validation at startup (V254)

### Observability Architecture ✅
- Sentry (frontend + backend error tracking)
- Langfuse (LLM call tracing)
- Python logging (structured, no secret leakage)
- Health endpoint (/api/health)
- Audit logging (admin actions with user + timestamp)

---

## Architecture Findings (V254)

### CRITICAL (Fixed)
1. **CSRF middleware not registered** — the most dangerous finding. The CSRF middleware was fully implemented (CSRFMiddleware class, Double Submit Cookie pattern, `__Host-` prefix) but the registration function was never called. This means the entire CSRF defense was non-existent in production. Fixed by calling `_register_csrf_middleware()` at startup.

2. **Session store isolation** — without REDIS_URL wired to the container, each uvicorn worker had its own session dict. Login succeeds on worker A, next request hits worker B → 401. Fixed by wiring REDIS_URL in docker-compose.

3. **Database path divergence** — DATABASE_URL and DIGITAL_TWIN_DB_PATH defaulted to different paths. Data written via one API was invisible to the other. Fixed by unifying both to /app/data/digital_twin.db.

### HIGH (Documented)
1. **4 frontend API clients** — api.ts, fullApi.ts, miningApi.ts, digitalTwinApi.ts. Only api.ts applies deepCamelToSnake transformation. This is a known inconsistency but doesn't cause runtime errors because the backend's CamelModel accepts both camelCase and snake_case (populate_by_name=True).

2. **Two .env.example files** — root `.env.example` (backend) and `frontend/.env.example` (frontend). This is intentional (different scopes) but could confuse. Documented.

### MEDIUM (Documented)
1. **Config.validate_config() was never called** — fixed in V254 by calling it in lifespan startup. Issues are logged as warnings (non-blocking).

2. **17 env vars missing from .env.example** — fixed in V254 by adding all missing vars with documentation.

---

## Architectural Consistency

| Principle | Status | Evidence |
|---|:---:|---|
| Single Responsibility | ✅ | Each module has one job |
| No circular dependencies | ✅ | Verified by grep |
| Clean layering | ✅ | Frontend → API → Services → DB |
| Fail-safe defaults | ✅ | All FIREAI_ENV → "production" (V246) |
| Defense in depth | ✅ | Auth + RBAC + CSRF + Rate limit |
| Graceful degradation | ✅ | Redis/Qdrant/Neo4j all optional |
| Observable | ✅ | Sentry + Langfuse + logging |
| Recoverable | ✅ | Error boundaries + auto-reload |

**Architecture: SOUND** ✅
