# ═══════════════════════════════════════════════════════════════════════════
# BAZSPARK CI/CD Policy — Root Cause Analysis, GitHub Actions & Safe Integration
# ═══════════════════════════════════════════════════════════════════════════
**Version:** 1.0
**Status:** **MANDATORY** — All contributors must follow this policy.
**Effective Date:** 2026-07-29
**Owner:** Engineering Team (Eng. Ahmed Elbaz)

---

## Purpose

This policy establishes mandatory rules for the CI/CD pipeline, root-cause
analysis, GitHub Actions validation, and safe code integration. The primary
objective is to maintain a **permanently healthy, reproducible, secure, and
deterministic CI/CD pipeline**.

**No code change is considered complete unless the entire pipeline succeeds.**

---

## Table of Contents

1. [Rule 1 — Root Cause First](#rule-1--root-cause-first)
2. [Rule 2 — CI/CD Ownership](#rule-2--cicd-ownership)
3. [Rule 3 — GitHub Actions Validation](#rule-3--github-actions-validation)
4. [Rule 4 — Safe Push](#rule-4--safe-push)
5. [Rule 5 — Safe Merge](#rule-5--safe-merge)
6. [Rule 6 — Failure Investigation](#rule-6--failure-investigation)
7. [Rule 7 — Regression Prevention](#rule-7--regression-prevention)
8. [Rule 8 — Git Safety](#rule-8--git-safety)
9. [Rule 9 — Dependency Safety](#rule-9--dependency-safety)
10. [Rule 10 — Secure Deployment](#rule-10--secure-deployment)
11. [Rule 11 — No Assumptions](#rule-11--no-assumptions)
12. [Rule 12 — Completion Criteria](#rule-12--completion-criteria)
13. [Existing CI/CD Infrastructure](#existing-cicd-infrastructure)
14. [Workflow Reference](#workflow-reference)
15. [Enforcement](#enforcement)

---

## Rule 1 — Root Cause First

> **Never apply quick fixes.**

Before modifying any file you **MUST**:

1. **Identify** the exact failure.
2. **Locate** the first failing step.
3. **Trace** the dependency chain.
4. **Identify** the real root cause.
5. **Explain** why the failure occurred.
6. **Explain** why your fix permanently resolves it.

**Do NOT fix symptoms. Fix only the actual cause.**

### Application in This Project

Every CI failure must be traced to the first meaningful error, not the last
visible symptom. For example, if a test suite fails:

```
❌ Symptom:    Gate 2 (Test Suite) reports 15 test failures
✅ Root Cause: Router import error because of missing optional dependency
✅ Fix:        Add missing dep to pyproject.toml or fix the import guard
```

---

## Rule 2 — CI/CD Ownership

> **Treat every CI/CD failure as a production incident.**

Mandatory inspection includes:

| Category | Items |
|----------|-------|
| **Pipeline** | GitHub Actions, Build, Test, Lint, Type Checking |
| **Artifacts** | Packaging, Artifacts, Release Pipeline, Deployment |
| **Infrastructure** | Docker, Cache, Matrix Jobs |
| **Configuration** | Environment Variables, Secrets, Permissions |
| **Governance** | Branch Protection, Required Status Checks |

**Nothing may be ignored.** Every failure must be investigated and resolved
before proceeding.

---

## Rule 3 — GitHub Actions Validation

> **Before changing any workflow, validate ALL of the following:**

- [ ] Workflow syntax (YAML validity)
- [ ] Reusable workflows and composite actions
- [ ] Action versions (pinned to SHA, not `@main`/`@v1`)
- [ ] Deprecated actions
- [ ] Cache keys (correct prefix, path, and key generation)
- [ ] Matrix strategy (include/exclude correctness)
- [ ] Concurrency groups (prevent duplicate runs)
- [ ] Permissions (least-privilege)
- [ ] Secrets usage (`${{ secrets.NAME }}` — never hardcoded)
- [ ] Timeout values (reasonable limits)
- [ ] Artifact upload/download (paths, retention)
- [ ] Conditional execution (`if:` expressions)
- [ ] Branch filters and path filters

**Never introduce breaking workflow changes.**

---

## Rule 4 — Safe Push

> **Never push directly without verification.**

Required sequence (every time, no exceptions):

```
Analyze
  ↓
Fix
  ↓
Run local validation (pre-commit hooks)
  ↓
Run tests (pytest)
  ↓
Run lint (ruff)
  ↓
Run type checking (mypy)
  ↓
Verify GitHub Actions configuration
  ↓
Review diff
  ↓
Commit (use conventional commit message)
  ↓
Push to feature branch
```

Only push when **every mandatory validation passes**.

### Local Validation Commands

```bash
# Pre-commit hooks (fastest feedback)
pre-commit run --all-files

# Python lint
ruff check backend/ fireai/ core/ parsers/ qomn_conduit/ qomn_fire/

# Python type check
mypy backend/ fireai/ core/ parsers/ --ignore-missing-imports

# Python tests (fast subset)
python -m pytest tests/ backend/tests/ -x --tb=short -q

# Frontend
cd frontend && npm run typecheck && npm run lint && npm run build
```

---

## Rule 5 — Safe Merge

> **Never merge code automatically.**

Before merge, verify ALL of the following:

- [ ] Pipeline is green (all CI gates pass)
- [ ] Required status checks pass
- [ ] No merge conflicts
- [ ] No skipped required jobs
- [ ] No unresolved review comments
- [ ] No failing security checks (gitleaks, bandit, pip-audit)
- [ ] No failing dependency checks
- [ ] PR has at least one approval (safety-critical changes need 2+)

**Reject any merge violating these rules.**

---

## Rule 6 — Failure Investigation

> **When CI fails, produce a complete report.**

Report structure (mandatory):

| Field | Description |
|-------|-------------|
| **Failure Stage** | Which gate/job/step failed? |
| **First Error** | The earliest error in the log (not the last) |
| **Root Cause** | The underlying reason (not a symptom) |
| **Files Involved** | All files related to the failure |
| **Impact** | What is affected (safety, features, performance)? |
| **Permanent Fix** | How the fix permanently resolves the root cause |
| **Regression Risk** | What could this fix break? |
| **Validation Performed** | How was the fix verified? |

> **Never provide only the last error. Locate the first meaningful failure.**

---

## Rule 7 — Regression Prevention

Every fix must be evaluated for:

- Breaking existing features
- Pipeline stability
- Backward compatibility
- Deployment safety
- Dependency compatibility
- Cross-platform compatibility (Linux, Windows, macOS)
- Performance impact
- Security impact

**If risk exists: explain it before making changes.**

---

## Rule 8 — Git Safety

> **Never perform these operations unless explicitly authorized:**

- ❌ **Force Push** (`git push --force` / `git push --force-with-lease`)
- ❌ **History Rewrite** (`git rebase`, `git commit --amend` on shared branches)
- ❌ **Deleting Branches** (remote branches without confirmation)
- ❌ **Deleting Tags**
- ❌ **Deleting Workflows**
- ❌ **Changing Protected Branch Rules**

**Exception:** Force push to your **own feature branch** is allowed only if:
1. You are the sole contributor on that branch
2. The branch has no open PR
3. You notify the team

---

## Rule 9 — Dependency Safety

> **Never blindly update dependencies.**

Before upgrading ANY dependency:

- [ ] Read the release notes and changelog
- [ ] Identify breaking changes
- [ ] Verify compatibility with current codebase
- [ ] Run full regression test suite
- [ ] Run dependency audit (`pip-audit`, `npm audit`)
- [ ] Check for known CVEs in the new version

**Reject unnecessary upgrades.** Only upgrade when there is a clear benefit
(bug fix, security patch, required feature).

---

## Rule 10 — Secure Deployment

> **Deployment must verify all of the following before proceeding:**

- [ ] Secrets are present (not empty)
- [ ] Environment variables are correctly set
- [ ] Permissions are appropriate (least privilege)
- [ ] Tokens are valid and not expired
- [ ] OIDC configuration is correct
- [ ] Artifact integrity is verified (checksums, signatures)
- [ ] Container images are scanned for vulnerabilities
- [ ] Image tags are consistent with source version
- [ ] Rollback capability is available and tested
- [ ] Version consistency across all deployed components

**Deployment must stop if any verification fails.**

---

## Rule 11 — No Assumptions

> **Never assume — always verify.**

| ❌ Wrong Assumption | ✅ Correct Verification |
|---------------------|------------------------|
| "The secret exists" | `if [ -z "$SECRET" ]; then exit 1; fi` |
| "The runner has Docker" | `which docker || exit 1` |
| "The branch is main" | `if [ "${{ github.ref }}" != "refs/heads/main" ]; then ...` |
| "Python 3.12 is installed" | `python --version | grep "3.12"` |
| "The dependency exists" | `pip show <package> || pip install <package>` |
| "Network is available" | `curl -sf https://pypi.org > /dev/null || exit 1` |

---

## Rule 12 — Completion Criteria

> **A task is COMPLETE only when ALL of these pass:**

| # | Criteria | Status |
|---|----------|--------|
| 1 | Root cause identified and fixed | ✓ / ❌ |
| 2 | Local validation passed (pre-commit) | ✓ / ❌ |
| 3 | Tests passed (pytest) | ✓ / ❌ |
| 4 | Lint passed (ruff) | ✓ / ❌ |
| 5 | Type checking passed (mypy) | ✓ / ❌ |
| 6 | GitHub Actions validated | ✓ / ❌ |
| 7 | CI pipeline green | ✓ / ❌ |
| 8 | Deployment verified | ✓ / ❌ |
| 9 | No regression introduced | ✓ / ❌ |
| 10 | Report generated (if failure investigation) | ✓ / ❌ |

**If any item fails, the task is NOT complete.**

---

## Existing CI/CD Infrastructure

This project already implements a comprehensive CI/CD pipeline consisting of
**15 GitHub Actions workflows**, **pre-commit hooks**, and **security scanning**
tools. The following table maps the existing infrastructure to this policy.

[//]: # "Workflow inventory — add/remove workflows as the project evolves"

| # | Workflow File | Purpose | Related Rules |
|---|---------------|---------|---------------|
| 1 | `ci.yml` | 7-gate CI pipeline (static analysis, tests, frontend, Docker, bundle) | R2, R4, R6 |
| 2 | `deploy.yml` | Staging + Production deployment via Helm/Kubernetes | R2, R6, R10 |
| 3 | `secret-scan.yml` | Gitleaks secret scanning on every push/PR | R2, R3 |
| 4 | `sonarcloud.yml` | SonarCloud code quality analysis | R2, R3 |
| 5 | `ci-build-gate.yml` | Pre-merge frontend build + typecheck gate | R2, R4, R5 |
| 6 | `ai-code-review.yml` | AI-powered code review | R1, R5 |
| 7 | `bundle-size.yml` | Frontend bundle size regression tracking | R2, R7 |
| 8 | `container-scan.yml` | Container image vulnerability scanning | R2, R10 |
| 9 | `dependabot-auto-merge.yml` | Automated safe merging of dependency updates | R3, R5, R9 |
| 10 | `modernization-showcase.yml` | Tech modernization demonstration | R2 |
| 11 | `regulatory-data-guard.yml` | Safety-critical regulatory data change protection | R1, R2 |
| 12 | `rollback.yml` | Rollback procedure — two strategies: Helm revision rollback or image tag re-deploy. Includes secret validation, rollout verification, smoke test, and audit report. | R8, R10, R11, R12 |
| 13 | `sync-to-hf.yml` | Hugging Face Spaces synchronization | R2, R3 |
| 14 | `trigger-vercel.yml` | Vercel deployment trigger | R2, R10 |
| 15 | `vercel-preview.yml` | Vercel preview deployment | R2, R4, R10 |

### Pre-Commit Hooks

The project uses `pre-commit` with 8 stages that enforce this policy locally:

| Stage | Tool | Policy Rule |
|-------|------|-------------|
| 1 — Formatting | ruff-format | R4 (local validation) |
| 2 — Linting | ruff | R4 |
| 3 — Type Checking | mypy | R4 |
| 4 — Security Scan | bandit | R4, R11 |
| 5 — Fast Tests | pytest | R4 |
| 6 — Property Tests | pytest (property-based) | R4, R7 |
| 7 — Dependency Audit | pip-audit | R9 |
| 8 — Secret Scanning | gitleaks + detect-secrets | R4, R11 |

---

## Workflow Reference

### How to Use This Policy

1. **Before coding:** Read this policy. Understand the 12 rules.
2. **During coding:** Follow Rule 4 (Safe Push) sequence.
3. **After coding:** Run Rule 12 (Completion Criteria) checklist.
4. **On CI failure:** Follow Rule 6 (Failure Investigation) and produce a report.
5. **Before merging:** Follow Rule 5 (Safe Merge) checklist.
6. **Before deploying:** Follow Rule 10 (Secure Deployment) checklist.

### Failure Investigation Template

When CI fails, use this template (copy into the PR or issue):

```
## Failure Investigation Report

**Failure Stage:** Gate X — [Job Name]
**First Error:** [Paste the first error from CI logs]
**Root Cause:** [Explain the underlying reason]
**Files Involved:**
  - [path/to/file.py] — [reason]
  - [path/to/file2.py] — [reason]
**Impact:** [What is affected? Safety-critical?]
**Permanent Fix:** [How does the fix resolve the root cause forever?]
**Regression Risk:** [What could this break?]
**Validation Performed:**
  - [ ] Local pre-commit passed
  - [ ] Tests pass
  - [ ] Lint passes
  - [ ] Type check passes
  - [ ] CI pipeline re-run passes
```

---

## Enforcement

### Automated Enforcement

| Rule | Enforced By | Location |
|------|-------------|----------|
| R4 (Safe Push) | pre-commit hooks | `.pre-commit-config.yaml` |
| R5 (Safe Merge) | Branch protection rules | GitHub Settings |
| R9 (Dependency Safety) | pip-audit + npm audit | `ci.yml` Gate 5 |
| R10 (Secure Deployment) | Secret validation step | `deploy.yml` |
| R11 (No Assumptions) | gitleaks + detect-secrets | `secret-scan.yml`, pre-commit |

### Manual Enforcement

- **Code Reviews:** Every PR must be reviewed. Safety-critical changes need 2+.
- **First Failure Rule:** The first CI failure in any PR must have a
  documented root cause before the fix is merged.
- **Escalation:** Repeated violations are escalated to the Engineering Lead.

### Violation Consequences

| Severity | Consequence |
|----------|-------------|
| **Minor** (forgot pre-commit, fixed immediately) | Written note to contributor |
| **Moderate** (skipped local validation, caused CI failure) | PR blocked until investigation report filed |
| **Major** (force push to shared branch, caused data loss) | Access revocation + incident review |
| **Critical** (bypassed security checks, exposed secrets) | Immediate revocation + mandatory retraining |

---

## References

- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — Contribution guidelines
- [`DEVELOPMENT.md`](./DEVELOPMENT.md) — Development standards
- [`POLICY.md`](./POLICY.md) — Security policy
- [`SECURITY.md`](./SECURITY.md) — Security practices
- [`AGENTS.md`](./AGENTS.md) — Agent skill configuration
- [`.pre-commit-config.yaml`](./.pre-commit-config.yaml) — Pre-commit hooks
- [`.github/workflows/`](./.github/workflows/) — All CI/CD workflows
- [`.gitleaks.toml`](./.gitleaks.toml) — Secret scanning configuration

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-29 | Eng. Ahmed Elbaz | Initial policy — 12 rules for CI/CD, root cause analysis, and safe integration |

---

*This policy is effective immediately and supersedes any prior informal CI/CD
practices. All contributors must acknowledge and comply.*
