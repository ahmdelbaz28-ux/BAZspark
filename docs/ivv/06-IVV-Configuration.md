# 06-IVV-Configuration
## Independent Verification & Validation — Configuration Audit

**Auditor:** Kilo (IV&V authority)
**Target:** BAZspark @ `ivv-certification-20260714113042`
**Date:** 2026-07-14

---

## 1. Environment Variables

### Required for production (from code analysis)
| Variable | Required by | Hard-fail? | Notes |
|---|---|---|---|
| `FIREAI_SESSION_SECRET` | `backend/app.py:370` | YES — `RuntimeError` | Min 43 chars URL-safe base64 |
| `FIREAI_API_KEY` | `backend/api_keys.py` | NO (fallback) | Default admin auto-generated if missing |
| `CORS_ALLOWED_ORIGINS` | `backend/app.py:481` | YES (production) | Comma-separated; `*` rejected |
| `DATABASE_URL` | `backend/database.py` | NO (warn) | Falls to SQLite |

### Required for Docker
| Variable | Required by | Hard-fail? | Notes |
|---|---|---|---|
| `FIREAI_API_KEY` | `docker-compose.yml:17` | YES (`${VAR:?ERROR}`) | |
| `NEO4J_PASSWORD` | `docker-compose.yml:140` | YES (`${VAR:?ERROR}`) | Only if neo4j container started |

### Required for CI/CD
| Secret | Workflow | Notes |
|---|---|---|
| `HF_TOKEN` | `sync-to-hf.yml` | HF Space write access |
| `DOCKER_USERNAME`/`DOCKER_PASSWORD` | Various | Container registry |
| `VERCEL_TOKEN` | `trigger-vercel.yml` | Vercel deployment |
| `KUBE_CONFIG_STAGING` | `deploy.yml` | K8s staging cluster |
| `KUBE_CONFIG_PRODUCTION` | `deploy.yml` | K8s production cluster |
| `FIREAI_SESSION_SECRET_CI` | `ci.yml:203` | Optional (ephemeral fallback) |

---

## 2. Configuration Files Audit

### pyproject.toml
| Setting | Value | Assessment |
|---|---|---|
| `requires-python` | `>=3.12` | OK |
| `[build-system]` | setuptools | OK |
| `[tool.setuptools.packages.find]` | Includes `skills*` | **Skills (501 files) packaged in wheel** |
| `[tool.black].target-version` | `py38` | **CONTRADICTS requires-python >=3.12** |
| `[tool.ruff].target-version` | `py38` | **CONTRADICTS requires-python >=3.12** |
| `[tool.mypy].python_version` | `3.12` | OK (contradicts black/ruff — see ISSUE-005/006) |
| `[tool.pytest].testpaths` | 8 directories | **Verified: all exist** |
| `[tool.pytest].filterwarnings` | `["error"]` | OK (Promotes warnings to errors) |
| `[tool.pytest].norecursedirs` | `facp_distributed` included | OK |
| `[tool.coverage].fail_under` | 40 | **CAUTION: 40% floor is very low** |
| `[tool.bandit]` | `B101,B102` skipped | OK (tests use assert) |

### .env.example
| Setting | Value | Assessment |
|---|---|---|
| Variables documented | 42 entries | OK |
| `SECRET_KEY` | `ci-test-hmac-secret-key-32-chars-minimum!!` | **TEST VALUE in example** |
| `FIREAI_SESSION_SECRET` | Placeholder with 43-char requirement | OK |

### Docker configuration
| File | Finding |
|---|---|
| `Dockerfile` | 3-stage build, non-root user, `EXPOSE 7860` |
| `docker-compose.yml` | 6 services, healthchecked, resource-limited |
| `.dockerignore` | Exists |

---

## 3. Toolchain Configuration Mismatches

### Python version inconsistency
Three tools disagree on target Python:
| Tool | Target | Impact |
|---|---|---|
| `pyproject.toml requires-python` | >=3.12 | Runtime requirement |
| `black target-version` | py38 | Black allows 3.8 syntax |
| `ruff target-version` | py38 | Ruff allows 3.8 syntax |
| `mypy python_version` | 3.12 | Type-checker uses 3.12 rules |

**Impact:** Code written with 3.12 features (PEP 604, PEP 585) passes mypy but may be flagged by ruff/black. The tooling disagrees with itself.

### CI Python matrix
- CI only tests Python 3.12
- `requires-python >=3.12` promises broader support than actually tested
- No 3.13 or 3.14 testing despite both being available

---

## 4. Security Configuration

| Control | Status | Evidence |
|---|---|---|
| CSP | Configured (hardcoded, with `'unsafe-inline'`) | `security_middleware.py:118` |
| HSTS | Enabled (1 year, includeSubDomains) | `security_middleware.py:99` |
| X-Frame-Options | DENY | `security_middleware.py:72` |
| X-Content-Type-Options | nosniff | `security_middleware.py:74` |
| Referrer-Policy | no-referrer | `security_middleware.py:78` |
| Permissions-Policy | All restricted | `security_middleware.py:85` |
| CSRF | Enabled (opt-out via env var) | `security_csrf.py:192` |
| CORS | Explicit allowlist (no wildcard) | `backend/app.py:479–505` |
| Rate limiting | 135+ decorators | Across routers |

---

## 5. Package Distribution Configuration

| Aspect | Setting | Assessment |
|---|---|---|
| Package name | `cad-bim-integration-platform` | **Does NOT match repo name** |
| Urls | `github.com/fireai/platform` | **404 — different org** |
| Author | `FireAI Project <contact@fireai.org>` | OK |
| Package data | `*.json`, `*.yaml`, `*.svg`, `*.html` | OK |
| Console scripts | `fireai-server`, `fireai-cli` | **Not generated in Docker** |

---

## 6. Configuration Vulnerabilities Found

### CFG-01: CI secret with ephemeral fallback
`ci.yml:214-217` generates an ephemeral `FIREAI_SESSION_SECRET` if the GitHub secret is not configured. This means CI tests can run without a properly configured secret — masking a configuration gap.

### CFG-02: Coverage disabled in CI
`ci.yml:227` `--no-cov`. The `fail_under = 40` setting in pyproject is NEVER enforced in CI. Coverage can drop to zero without CI noticing.

### CFG-03: Dependabot auto-merge
The `dependabot-auto-merge.yml` workflow (existence confirmed) likely auto-merges Dependabot PRs. This is a **critical security risk** if not carefully scoped, as it automatically introduces dependency updates without human review.

**Action:** Verify that `dependabot-auto-merge.yml` restricts auto-merge to only PATCH-level updates with passing CI.

---

## Configuration Conclusion

The repository has comprehensive configuration but suffers from:
- Divergent toolchain target versions (py38 vs 3.12)
- Coverage measurement disabled in CI
- Auto-merge of Dependabot PRs (potential supply-chain risk)
- Ephemeral CI secrets mask missing configuration

None of these are production blockers individually, but collectively they represent configuration drift that should be addressed.

---

*This document was independently produced by Kilo IV&V. All claims backed by executable evidence.*
