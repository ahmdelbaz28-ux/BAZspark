# 04 — Configuration Consistency

**Project:** BAZspark v1.55.0
**Audit Date:** 2026-07-13

---

## Configuration Consistency Matrix

### Environment Variables

| Variable | .env.example | docker-compose | render.yaml | K8s ConfigMap | K8s Secret | Code | Consistent? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| FIREAI_ENV | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| FIREAI_API_KEY | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| FIREAI_SESSION_SECRET | ✅ | ✅ | ✅ (V243) | — | ✅ (V248) | ✅ | ✅ |
| CORS_ALLOWED_ORIGINS | ✅ | ✅ | ✅ (V243) | ✅ (V248) | — | ✅ | ✅ |
| DATABASE_URL | ✅ | ✅ | — | — | ✅ (V248) | ✅ | ✅ |
| REDIS_URL | ✅ (V254) | ✅ (V254) | — | — | ✅ (V248) | ✅ | ✅ |
| FIREAI_CSRF_DISABLED | ✅ (V254) | — | — | — | — | ✅ | ✅ |

### Port Consistency

| Config | Port | Consistent? |
|---|:---:|:---:|
| Dockerfile EXPOSE | 7860 | ✅ |
| Dockerfile CMD | 7860 | ✅ |
| docker-compose ports | 7860 (V248) | ✅ |
| docker-compose healthcheck | 7860 (V248) | ✅ |
| HF Spaces | 7860 | ✅ |
| render.yaml health check | /api/health | ✅ |

### Cookie Configuration

| Property | Value | Consistent? |
|---|---|:---:|
| Cookie name | `fireai_session` | ✅ (backend only — frontend can't read HttpOnly) |
| HttpOnly | true | ✅ |
| Secure | true (production) | ✅ |
| SameSite | Strict | ✅ |
| Max-Age | 86400 (24h) | ✅ |

### CSRF Configuration

| Property | Value | Consistent? |
|---|---|:---:|
| Token endpoint | `/api/v1/auth/csrf-token` | ✅ |
| Header name | `X-CSRF-Token` | ✅ (frontend + backend) |
| Cookie name | `__Host-fireai-csrf` | ✅ |
| Middleware registered | ✅ (V254 fix) | ✅ |
| Exempt methods | GET, HEAD, OPTIONS | ✅ |

### Database Path Consistency (V254 Fix)

| Config | Before V254 | After V254 |
|---|---|---|
| DATABASE_URL default | `sqlite:///./db/digital_twin.db` (relative) | `sqlite:////app/data/digital_twin.db` (absolute) |
| DIGITAL_TWIN_DB_PATH default | Absolute path (different) | Same as DATABASE_URL |
| Volume mount | `/app/data` | `/app/data` (both paths now inside) |

### FIREAI_ENV Default Consistency

| File | Default | V246 Fix |
|---|---|:---:|
| app.py | "production" | ✅ |
| config.py | "production" | ✅ |
| security_csrf.py | "production" | ✅ |
| session_secret.py | "production" | ✅ |
| auth.py | "production" | ✅ |
| All others | "production" | ✅ |

**All 7 sites now default to "production" (fail-safe).** ✅

---

## V254 Configuration Fixes

1. ✅ Added REDIS_URL to docker-compose fireai service
2. ✅ Unified DATABASE_URL and DIGITAL_TWIN_DB_PATH to /app/data/
3. ✅ Added 17 missing env vars to .env.example
4. ✅ Called Config.validate_config() at startup
5. ✅ Registered CSRF middleware (was defined but never called)

**Configuration Consistency: VERIFIED** ✅
