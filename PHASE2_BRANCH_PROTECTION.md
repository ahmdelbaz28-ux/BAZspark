# Phase 2 — Branch Protection on main — Applied & Verified

> Date: 2026-08-03 10:34:22 UTC
> Applied by: BAZSPARK Engineering (via GitHub REST API)

## What Was Done

Branch protection rules were enabled on `main` via the GitHub API
(`PUT /repos/{owner}/{repo}/branches/main/protection`).

## Configuration Applied

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Frontend Build + TypeCheck",
      "Frontend Unit Tests (Vitest)",
      "Backend Tests (pytest) (3.12)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "block_creations": false
}
```

## What Each Rule Does

| Rule | Value | Effect |
|---|---|---|
| **required_status_checks** | 3 contexts | CI must pass before merge |
| **strict** | true | PR branch must be up-to-date with main before merge |
| **required_pull_request_reviews** | 1 approval | At least 1 human reviewer must approve |
| **dismiss_stale_reviews** | true | New commits dismiss old approvals |
| **enforce_admins** | true | Even repo admins cannot bypass rules |
| **allow_force_pushes** | false | `git push --force` to main is blocked |
| **allow_deletions** | false | main branch cannot be deleted |

## Verification — Direct Push Test

Attempted a direct `git push origin main` after creating a test commit.
The push was **REJECTED** by GitHub:

```
remote: error: GH006: Protected branch update failed for refs/heads/main.
remote: - Changes must be made through a pull request.
remote: - 3 of 3 required status checks are expected.
To https://github.com/ahmdelbaz28-ux/BAZspark.git
 ! [remote rejected]   main -> main (protected branch hook declined)
```

The local test commit was then reset (`git reset --hard origin/main`)
so the working tree is back to the clean state.

## Required Status Checks — Proven to Run on PRs

The 3 required contexts come from the `ci-build-gate.yml` workflow which
triggers on both `pull_request` and `push` to main (when `frontend/**`
or `backend/**` files change).

Verified from the last CI Build Gate run on main HEAD (SHA `98e70c8c`):

| Job Name | Status | Conclusion |
|---|---|---|
| Frontend Build + TypeCheck | completed | success |
| Frontend Unit Tests (Vitest) | completed | success |
| Backend Tests (pytest) (3.12) | completed | success |

Run URL: https://github.com/ahmdelbaz28-ux/BAZspark/actions/runs/30804809030

## Implications for Future PRs

From now on, every PR to main must:

1. **Be up-to-date with main** — if main moves forward, the PR branch
   must be rebased/merged before merging.
2. **Pass all 3 CI checks** — typecheck, build, frontend tests, and
   backend tests must all succeed.
3. **Receive 1 approving review** — a human reviewer must approve.
4. **Cannot be force-pushed** — once created, the PR branch history
   is preserved.

If a PR only changes documentation (no `frontend/**` or `backend/**`
files), the CI Build Gate workflow will NOT run. In that case, the
required status checks will be "expected" but never "completed",
which means the PR **cannot be merged** until at least one
`frontend/**` or `backend/**` file is changed.

⚠️ **KNOWN LIMITATION**: PRs that only change docs/scripts will be
blocked by the required status checks. If this becomes a problem,
we can either:
  (a) Remove the paths filter from ci-build-gate.yml (runs on all PRs)
  (b) Change `strict` to false and remove specific contexts
  (c) Use GitHub's "required status checks" admin override

For now, all PRs in the cleanup plan touch frontend files, so this
is not an issue.

## Rollback

To disable branch protection:
```bash
curl -X DELETE \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/ahmdelbaz28-ux/BAZspark/branches/main/protection"
```

## Definition of Done

- [x] Branch protection enabled via GitHub API
- [x] 3 required status checks configured (all from ci-build-gate.yml)
- [x] 1 approving review required
- [x] enforce_admins = true
- [x] allow_force_pushes = false
- [x] allow_deletions = false
- [x] Direct push to main tested and REJECTED
- [x] Local test commit reset to clean state
