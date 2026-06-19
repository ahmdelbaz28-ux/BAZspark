# Repo Cleanup Plan — 2026-06-19

**Branch:** `repo-cleanup-ci-config`
**Goal:** Fix the broken CI/CD pipeline, harden the auto-merge workflow, and document everything that needs manual operator action — **without touching any production code**.

## What was wrong (the diagnosis)

A full audit on 2026-06-19 against `main` (commit `c1d7fb42`) revealed:

### CI/CD pipeline was green-on-red
The `CI/CD Pipeline` workflow (`.github/workflows/ci.yml`) had **5 instances of `|| true`** that swallowed every meaningful failure:
- `pytest ... -x || true` — test failures ignored
- `pytest tests/property_based/ ... || true` — property tests ignored
- `pip-audit ... || true` — dependency vulnerabilities ignored
- `npm audit --audit-level=high || true` — frontend vulnerabilities ignored
- The final `success` job used `if: always()` and printed "✅ All Gates Passed" even when every gate failed.

Plus `--cov-fail-under=5` — 5% coverage floor is effectively no floor.

Result: GitHub showed a green check on the most recent `main` push, but Gate 1 (Static Analysis) and Gate 4 (Frontend Build) were both **red**. The success job's green check was misleading.

### Dependabot auto-merge was unsafe
`.github/workflows/dependabot-auto-merge.yml` had a critical logic bug:
```js
} else if (statuses.length === 0) {
  // No status checks configured - proceed
  core.setOutput('ready', 'true');
  return;
}
```
This means: **if no CI checks had run yet, the workflow would auto-merge the PR anyway.** Combined with branch protection being OFF (see below), any dependabot PR could silently land on `main` without a single test running. This is the textbook supply-chain attack path.

### No branch protection on `main`
`curl /branches/main/protection` returned `Branch not protected`. Anyone with push access could push directly to `main` without a PR. The `dependabot-auto-merge.yml` workflow's bug was made 10× worse by this.

### Dependabot config was missing
`.github/dependabot.yml` did not exist. Dependabot was running with defaults, producing 20+ open vulnerability alerts (in `cryptography`, `python-multipart`, `lxml`, `vite`, `undici`, `tar`, `js-yaml`) and 50+ closed PRs that were mostly not merged because the auto-merge path was broken.

### Repo settings were wide open
- `delete_branch_on_merge = false` → dead branches accumulate (8 active branches, 5 with stale PRs)
- `allow_auto_merge = false` → the auto-merge workflow's `gh pr merge --auto` cannot work even after we fix it
- `visibility = public` → **the repo is on the public internet**. With leaked PATs and 20 open vulnerability alerts, this is high-risk.
- `secret_scanning` disabled → leaked tokens are not detected automatically
- `has_wiki = false` ✓, `has_pages = false` ✓, `has_discussions = false` ✓ (these are fine)

### Stale branches and PRs
8 remote branches, 5 open PRs (some from 2026-06-17, 3+ days stale):
- `autocad-enhancement-v2` → PR #58 (18 commits ahead, 21 behind — badly diverged)
- `cleanup-dead-code` → PR #59 (1 commit ahead — small)
- `feature/input-normalization` → PR #61 (3 commits ahead — recent)
- `feature/production-infrastructure` → PR #57 (5 commits ahead, 24 behind — badly diverged)
- `marine-v2-improvements` → PR #60? (1 commit ahead — recent)
- `v130-security-review` → no PR? (10 commits ahead)
- `ponytail-phase-2-cleanup` → no PR yet (this is my work)

---

## What this branch fixes (no production code touched)

### 1. `.github/workflows/ci.yml` — hardened
- Removed all 4 `|| true` from gate steps. Failures now fail CI.
- Raised `--cov-fail-under` from 5 → 25 (current actual is ~39%, so this is a real floor).
- Changed the `success` job from `if: always()` to `if: success()`. A red gate now produces a *skipped* success job — visually obvious in the GitHub UI, no longer misleading.
- Added explanatory `ponytail:` comments at every changed site.

### 2. `.github/workflows/dependabot-auto-merge.yml` — rewritten for safety
- The "no statuses = proceed" bug is fixed: the new workflow **requires at least one CI check to have completed** before auto-merging.
- Major-version bumps are now blocked from auto-merge ( Dependabot title parsing detects `from N.x to N+1.x`).
- Only PATCH and MINOR bumps can auto-merge. Major bumps need human review.
- `gh pr merge --admin` → `gh pr merge --squash --auto` (the `--admin` flag was wrong; `--auto` requires the repo's `allow_auto_merge` setting, which the operator must enable — see §3 below).

### 3. `.github/dependabot.yml` — new
- Scopes dependabot to 4 ecosystems actually in use: pip, npm, github-actions, docker.
- Groups minor + patch bumps together (one weekly PR per ecosystem, not 20).
- Major bumps stay separate (so the auto-merge workflow can refuse them).
- Schedules: weekly Monday 07:00 Africa/Cairo (matches operator timezone).
- Pins `three` / `@react-three/fiber` / `@react-three/drei` to current major (0.16x series has broken the 3D viewer twice in 2026).
- `open-pull-requests-limit: 5` per ecosystem (was unbounded).

---

## What the operator MUST do manually (cannot be done via PR)

### §1 — Revoke the leaked GitHub tokens (URGENT, do this FIRST)

Two PATs are visible in this chat history and in the git remote URL:
1. [REDACTED-PAT]` (already revoked — push failed with 403)
2. [REDACTED-PAT] (still active — used for the pushes above)

**Action:**
1. Go to https://github.com/settings/tokens
2. Revoke [REDACTED-PAT] immediately.
3. Generate a new fine-grained PAT scoped only to this repo, with `Contents: write` + `Pull requests: write` + `Workflows: write` permissions.
4. Store the new token in a password manager (1Password, Bitwarden) — never paste it in a chat again.

### §2 — Enable secret scanning (5 minutes)

The repo has **20 open dependabot alerts** but secret scanning is **disabled** — meaning if you paste a token in any file, GitHub will not alert you.

**Action:**
1. Settings → Code security → Secret scanning → **Enable**.
2. Also enable "Push protection" (blocks tokens from being pushed in the first place).
3. Also enable "Validity checks" (flags tokens that are still active).

### §3 — Enable branch protection on `main` (10 minutes)

This is the single most important change. Without it, all the CI fixes in this PR are theater — anyone can push directly to `main`.

**Action:**
1. Settings → Branches → Add branch protection rule → Branch name pattern: `main`.
2. Tick:
   - ☑ Require a pull request before merging (require 1 approval)
   - ☑ Require status checks to pass (select: `Gate 1 — Static Analysis`, `Gate 2 — Test Suite`, `Gate 4 — Frontend Build`, `Gate 5 — Dependency Audit`). Do NOT select `Gate 6 — Docker Build` as required (it's slow and can be a separate release gate).
   - ☑ Require branches to be up to date before merging
   - ☑ Require conversation resolution before merging
   - ☑ Require linear history (forces squash or rebase merges — no merge commits)
   - ☑ Do not allow bypassing the above settings (even for admins)
3. Save.

After this, the `dependabot-auto-merge.yml` workflow will actually work — `gh pr merge --auto` requires the branch protection rules to satisfy before it merges.

### §4 — Fix repo settings (5 minutes)

**Action:**
1. Settings → General:
   - ☑ Auto-delete head branches (after PR merge)
2. Settings → General → Pull Requests:
   - ☑ Allow auto-merge (this is what makes `gh pr merge --auto` work)
3. Settings → Actions → General → Workflow permissions:
   - ☑ Allow GitHub Actions to create and approve pull requests (required for dependabot auto-merge workflow)

### §5 — Triage the 5 open PRs (15 minutes)

Look at each PR and decide: merge / rebase / close. Recommended actions:

| PR | Branch | Status | Recommended action |
|---|---|---|---|
| #61 | `feature/input-normalization` | 3 ahead, 3 behind — recent | Rebase on main, run CI, merge if green |
| #60 | `v130-security-review` (note: PR #60 title says "V130 Security Review v2 — 8 commits") | 10 ahead, 7 behind | **Review carefully** — 8 commits include 2 CRITICAL + 3 HIGH security fixes. This is the highest-priority PR. |
| #59 | `cleanup-dead-code` | 1 ahead, 21 behind | Rebase on main, run CI, merge if green |
| #58 | `autocad-enhancement-v2` | 18 ahead, 21 behind | Badly diverged. Close + recreate from current main, or cherry-pick the relevant commits. |
| #57 | `feature/production-infrastructure` | 5 ahead, 24 behind | Badly diverged. Close + recreate from current main. |

For each closed-without-merge branch, delete the remote branch:
```bash
git push origin --delete <branch-name>
```

### §6 — Delete stale local branches (after PR triage)

After §5, clean up local refs:
```bash
git fetch --prune
git branch -d <local-branch-names>
```

### §7 — Address the 20 open dependabot alerts

After §2 (secret scanning enabled) and §3 (branch protection on), the dependabot alerts become actionable:

1. Go to https://github.com/ahmdelbaz28-ux/revit/security/dependabot
2. For each alert: either click "Dependabot creates a PR" or "Dismiss alert" with a reason.
3. For HIGH/CRITICAL alerts in `cryptography`, `python-multipart`, `lxml`: prioritize. These have known exploits.
4. The new `.github/dependabot.yml` will prevent future alert accumulation by opening grouped PRs weekly.

### §8 — Consider making the repo private

The repo is currently `public`. With the leaked PATs, the 20 open vulnerabilities, and the safety-critical nature of the code (fire-protection engineering), public visibility is high-risk.

**Action:** Settings → General → Danger Zone → Change visibility → Private.

If the repo must stay public for portfolio reasons, at least enable secret scanning + push protection (§2) before doing anything else.

---

## What was NOT changed (deferred — needs operator decision)

- **No production code touched.** Zero `.py`, `.ts`, `.tsx`, `.cs` files modified. Only `.github/workflows/*.yml`, `.github/dependabot.yml` (new), and this doc.
- **No existing branches deleted.** Branch deletion is irreversible; the operator should decide which PRs to merge/close first (§5).
- **No `main` history rewritten.** Even though there are 2 commits on `main` from `5cd6b4b5` to `c1d7fb42` that appear to be from a force-push, rewriting history would break every open PR.
- **The `ponytail-phase-2-cleanup` branch is left alone.** It's a separate PR with its own review path.
- **The `regulatory-data-guard.yml` workflow was not modified.** It works correctly as-is.
- **The `modernization-showcase.yml` workflow was not modified.** It's a reporting workflow, not a gate.
- **The `deploy.yml` workflow was not modified.** It is currently failing on main, but the failure is downstream of the CI gate failures we fixed — once CI passes, deploy should pass too. If it still fails after this PR merges, investigate separately.

---

## Verification

After merging this branch, the operator should see:

1. **CI/CD Pipeline runs red on the current `main`** (because Gate 1 Ruff lint + Gate 4 TypeScript check were already failing — they were just hidden by `|| true`). This is the desired behavior: the failures were always there; now they're visible.

2. **To get CI green, the operator needs to fix the actual lint + TypeScript errors.** This is intentional — the CI is now telling the truth. Do not re-add `|| true` to silence it. Fix the root cause instead.

3. **Dependabot PRs will start respecting CI.** Once branch protection is on (§3), no dependabot PR can merge without CI passing.

4. **No new auto-merge will happen** until §3 (branch protection) + §4 (allow_auto_merge) are done. The new workflow is safe-by-default.

---

## Risk assessment

| Change | Risk | Mitigation |
|---|---|---|
| Removed `|| true` from CI gates | Pre-existing failures now visible | Fix the actual lint/TS errors (do NOT re-add `|| true`) |
| Raised `cov-fail-under` 5 → 25 | Build fails if coverage drops below 25% | Current coverage is ~39%, so this is safe; raise further in a future PR |
| Rewrote `dependabot-auto-merge.yml` | Auto-merge will not work until §4 is done | Documented in §4; safe-by-default |
| New `dependabot.yml` | Old ungrouped PRs may close | Dependabot will recreate as grouped PRs |
| No production code touched | Zero risk to runtime behavior | Verified by `git diff main..HEAD --stat` showing only `.github/` and `.md` changes |

---

## How to verify this PR before merging

```bash
# 1. Check that only .github/ files changed
git diff main..repo-cleanup-ci-config --stat

# 2. Sanity-check the CI workflow YAML
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "ci.yml OK"
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/dependabot-auto-merge.yml'))" && echo "dependabot-auto-merge.yml OK"
python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))" && echo "dependabot.yml OK"

# 3. Confirm no .py / .ts / .tsx / .cs files were modified
git diff main..repo-cleanup-ci-config --name-only | grep -E '\.(py|ts|tsx|cs|go|rs|java)$' && echo "FAIL: source files modified" || echo "PASS: no source files modified"
```

---

## Summary

This PR is **defense-in-depth, not a silver bullet**. It closes the most dangerous gaps (CI was lying, auto-merge was unsafe, branch protection was off) but it cannot fix the operator-side items (§1–§8) on its own. Those require manual GitHub UI actions.

Do the §1 token revocation FIRST. Then merge this PR. Then work through §2–§8 in order.
