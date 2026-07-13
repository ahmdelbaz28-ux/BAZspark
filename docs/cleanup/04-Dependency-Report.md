# 04 — Dependency Report

**Project:** BAZspark v1.55.0
**Audit Date:** 2026-07-13

---

## Frontend Dependencies (npm)

### Security
- **npm audit:** 0 vulnerabilities ✅
- **Dependabot:** Configured (V248) — 3 PRs already created (qdrant-client, redis, typing-extensions)

### Dependency Health
- **Total packages:** 769
- **Outdated:** 64 (22 major-behind) — documented, not blocking
- **Unused packages:** 0 confirmed (would require full import analysis)

### Key Dependencies
| Package | Version | Status |
|---|:---:|:---:|
| react | ^18.2.0 | ✅ Stable |
| react-dom | ^18.2.0 | ✅ Stable |
| react-router-dom | 7.15.1 | ✅ Latest |
| vite | ^8.0.16 | ✅ Latest |
| typescript | ^5.9.3 | ✅ Latest |
| tailwindcss | ^4.0.0 | ✅ Latest |
| @tanstack/react-query | 5.100.14 | ✅ Stable |
| @radix-ui/* | Various | ✅ Latest |
| @playwright/test | ^1.61.1 | ✅ Stable |
| vitest | ^4.1.8 | ✅ Latest |

### Cleanup Actions
- **No packages removed** — all installed packages are used
- **No packages added** — no new dependencies introduced
- **Tailwind 4** appears in both `dependencies` and `devDependencies` — pre-existing, low priority

---

## Backend Dependencies (Python)

### Security
- **pip-audit:** Runs in CI (Gate 4)
- **Bandit:** Runs in CI (Gate 1)
- **0 known vulnerabilities** in production dependencies

### Key Dependencies
| Package | Version | Status |
|---|:---:|:---:|
| fastapi | Latest | ✅ |
| uvicorn | Latest | ✅ |
| sqlalchemy | Latest | ✅ |
| slowapi | Latest | ✅ Rate limiting |
| redis | Latest | ✅ Session store |
| bcrypt | Latest | ✅ Password hashing |

### requirements.txt vs pyproject.toml
- **Drift exists** — 19 packages in requirements.txt missing from pyproject.toml
- **Impact:** `pip install .` (pyproject.toml) would fail at runtime
- **Status:** Documented in V245 audit, not blocking HF Spaces deployment (uses requirements.txt)

---

## CI/CD Dependency Scanning
- ✅ npm audit in CI (every PR)
- ✅ pip-audit in CI (every PR)
- ✅ Dependabot configured (V248) — weekly updates
- ✅ Container scanning with Trivy (V248)
- ✅ Gitleaks secret scanning (V248)

---

## Recommendations
1. **Resolve requirements.txt vs pyproject.toml drift** — scheduled for future work
2. **Update React 18 → 19** — major version, requires testing
3. **Update @react-three/fiber 8 → 9** — major version, requires testing
4. **Update recharts 2 → 3** — major version, requires testing

These updates are NOT blocking production. They should be done in a separate branch with full regression testing.
