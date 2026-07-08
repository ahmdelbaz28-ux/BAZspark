#!/usr/bin/env bash
#
# verify_vercel_webhook.sh — Verify Vercel GitHub webhook status
#
# This script checks the current state of the Vercel deployment setup:
#   1. Whether the GitHub webhook is registered (via GitHub API)
#   2. Whether recent Vercel deployments succeeded (via Vercel API)
#   3. Whether the trigger-vercel.yml workflow is still needed
#
# Usage:
#   export VERCEL_DEPLOY_TOKEN="your_vercel_token"
#   export GITHUB_TOKEN="your_github_token_with_repo_scope"
#   bash /home/z/my-project/scripts/verify_vercel_webhook.sh
#
# Token sources:
#   - VERCEL_DEPLOY_TOKEN: https://vercel.com/account/tokens (create with
#     full access or scoped to the revit project)
#   - GITHUB_TOKEN: https://github.com/settings/tokens (create with
#     'repo' scope to read webhook config)
#
# What this script checks:
#   Step 1: GitHub webhooks for the repo — is Vercel's webhook registered?
#   Step 2: Recent Vercel deployments — are they succeeding?
#   Step 3: trigger-vercel.yml workflow runs — is it still firing?
#   Step 4: Verdict + recommended action

set -euo pipefail

REPO="ahmdelbaz28-ux/revit"
PROJECT_ID="prj_Y6Qr828DXS83tWF1LntFakyofMrf"
TEAM_ID="team_eeEYqzXI8zkrTo62cUOTMVmS"
LOG_DIR="/home/z/my-project/work"
TIMESTAMP=$(date +%Y%mDD_%H%M%S)
LOG_FILE="${LOG_DIR}/vercel_verify_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

# ── Validate tokens ──
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
VERCEL_TOKEN="${VERCEL_DEPLOY_TOKEN:-${VERCEL_TOKEN:-}}"

if [ -z "$GITHUB_TOKEN" ] && [ -z "$VERCEL_TOKEN" ]; then
    echo "❌ ERROR: Both GITHUB_TOKEN and VERCEL_DEPLOY_TOKEN are unset."
    echo ""
    echo "This script needs at least one of:"
    echo "  GITHUB_TOKEN        — to check if the Vercel webhook is registered"
    echo "  VERCEL_DEPLOY_TOKEN — to check recent deployment status"
    echo ""
    echo "Token sources:"
    echo "  GITHUB_TOKEN:        https://github.com/settings/tokens (scope: repo)"
    echo "  VERCEL_DEPLOY_TOKEN: https://vercel.com/account/tokens"
    echo ""
    echo "Usage:"
    echo "  export GITHUB_TOKEN=\"...\""
    echo "  export VERCEL_DEPLOY_TOKEN=\"...\""
    echo "  bash $0"
    exit 1
fi

echo "══════════════════════════════════════════════════════════════════"
echo "Vercel Webhook Verification — $REPO"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "══════════════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Check GitHub webhooks ──
echo "─── Step 1: GitHub Webhooks ───"
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Checking webhooks for $REPO..."
    WEBHOOKS_RESPONSE=$(curl -sS -w "\n%{http_code}" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO/hooks" 2>&1 || echo "CURL_FAILED")

    HTTP_CODE=$(echo "$WEBHOOKS_RESPONSE" | tail -1)
    BODY=$(echo "$WEBHOOKS_RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ]; then
        HOOK_COUNT=$(echo "$BODY" | jq 'length' 2>/dev/null || echo "?")
        echo "  Found $HOOK_COUNT webhook(s) registered on the repo"

        if [ "$HOOK_COUNT" != "0" ] && [ "$HOOK_COUNT" != "?" ]; then
            echo ""
            echo "  Webhook details:"
            echo "$BODY" | jq -r '.[] | "    - URL: \(.config.url // "unknown")\n      Name: \(.name // "unknown")\n      Events: \(.events | join(", "))\n      Active: \(.active)\n      Last response code: \(.last_response.code // "none")"' 2>/dev/null || echo "    (could not parse webhook details)"

            # Check if any webhook points to vercel.com
            VERCEL_HOOK=$(echo "$BODY" | jq -r '.[] | select(.config.url | test("vercel")) | .config.url' 2>/dev/null || echo "")
            if [ -n "$VERCEL_HOOK" ]; then
                echo ""
                echo "  ✅ Vercel webhook FOUND: $VERCEL_HOOK"
                echo "  → The GitHub→Vercel integration appears to be REGISTERED."
                echo "  → Proceed to Step 2 to verify it's actually delivering."
            else
                echo ""
                echo "  ⚠️  No Vercel webhook found in the registered hooks."
                echo "  → The GitHub→Vercel integration is NOT connected."
                echo "  → Follow OPS_RUNBOOK.md Task 1 to reconnect it."
            fi
        else
            echo "  ⚠️  No webhooks registered on the repo."
            echo "  → The GitHub→Vercel integration is NOT connected."
            echo "  → Follow OPS_RUNBOOK.md Task 1 to reconnect it."
        fi
    else
        echo "  ❌ Failed to fetch webhooks (HTTP $HTTP_CODE)"
        echo "  → Check that GITHUB_TOKEN has 'repo' scope"
    fi
else
    echo "  ⏭️  GITHUB_TOKEN not set — skipping webhook check"
fi

echo ""

# ── Step 2: Check recent Vercel deployments ──
echo "─── Step 2: Recent Vercel Deployments ───"
if [ -n "$VERCEL_TOKEN" ]; then
    echo "Fetching recent deployments from Vercel API..."
    DEPLOY_RESPONSE=$(curl -sS -w "\n%{http_code}" \
        -H "Authorization: Bearer $VERCEL_TOKEN" \
        "https://api.vercel.com/v6/deployments?projectId=$PROJECT_ID&teamId=$TEAM_ID&limit=5" 2>&1 || echo "CURL_FAILED")

    HTTP_CODE=$(echo "$DEPLOY_RESPONSE" | tail -1)
    BODY=$(echo "$DEPLOY_RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ]; then
        DEPLOY_COUNT=$(echo "$BODY" | jq '.deployments | length' 2>/dev/null || echo "?")
        echo "  Found $DEPLOY_COUNT recent deployment(s)"

        if [ "$DEPLOY_COUNT" != "0" ] && [ "$DEPLOY_COUNT" != "?" ]; then
            echo ""
            echo "  Recent deployments:"
            echo "$BODY" | jq -r '.deployments[] | "    - \(.createdAt // "unknown"): state=\(.state // "unknown"), target=\(.target // "unknown"), url=\(.url // "unknown")"' 2>/dev/null || echo "    (could not parse deployment details)"

            # Check if any recent deployment was triggered by the webhook (not by the workflow)
            echo ""
            echo "  Deployment triggers (check 'meta' field for source):"
            echo "$BODY" | jq -r '.deployments[] | "    - \(.createdAt): meta=\(.meta | to_entries | map(\"\(.key)=\(.value)\") | join(\", \"))"' 2>/dev/null | head -10 || echo "    (could not parse meta)"
        fi
    else
        echo "  ❌ Failed to fetch deployments (HTTP $HTTP_CODE)"
        echo "  → Check that VERCEL_DEPLOY_TOKEN is valid"
        echo "  → Body: $BODY"
    fi
else
    echo "  ⏭️  VERCEL_DEPLOY_TOKEN not set — skipping deployment check"
fi

echo ""

# ── Step 3: Check trigger-vercel.yml workflow runs ──
echo "─── Step 3: trigger-vercel.yml Workflow Runs ───"
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Checking recent runs of 'Trigger Vercel Deploy' workflow..."
    WORKFLOW_RESPONSE=$(curl -sS -w "\n%{http_code}" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO/actions/workflows/trigger-vercel.yml/runs?per_page=5" 2>&1 || echo "CURL_FAILED")

    HTTP_CODE=$(echo "$WORKFLOW_RESPONSE" | tail -1)
    BODY=$(echo "$WORKFLOW_RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ]; then
        RUN_COUNT=$(echo "$BODY" | jq '.workflow_runs | length' 2>/dev/null || echo "?")
        echo "  Found $RUN_COUNT recent run(s) of trigger-vercel.yml"

        if [ "$RUN_COUNT" != "0" ] && [ "$RUN_COUNT" != "?" ]; then
            echo ""
            echo "  Recent runs:"
            echo "$BODY" | jq -r '.workflow_runs[] | "    - \(.created_at): status=\(.status), conclusion=\(.conclusion // "in-progress"), event=\(.event)"' 2>/dev/null | head -10 || echo "    (could not parse run details)"
        fi
    else
        echo "  ⚠️  Could not fetch workflow runs (HTTP $HTTP_CODE)"
    fi
else
    echo "  ⏭️  GITHUB_TOKEN not set — skipping workflow check"
fi

echo ""

# ── Step 4: Verdict ──
echo "─── Step 4: Verdict & Recommended Action ───"
echo ""
echo "Based on the checks above:"
echo ""
echo "  Scenario A — Vercel webhook NOT registered (Step 1 shows no Vercel hook):"
echo "    → The trigger-vercel.yml workflow is STILL NEEDED as the primary trigger"
echo "    → Follow OPS_RUNBOOK.md Task 1 Steps 1-2 to reconnect the integration"
echo "    → After webhook works, downgrade trigger-vercel.yml to workflow_dispatch only"
echo ""
echo "  Scenario B — Vercel webhook registered AND deployments succeeding:"
echo "    → The webhook is the primary trigger; trigger-vercel.yml is now redundant"
echo "    → Downgrade trigger-vercel.yml: change 'on: push: ...' to 'on: workflow_dispatch:'"
echo "    → This saves Vercel free-plan quota (100 deploys/day)"
echo ""
echo "  Scenario C — Vercel webhook registered but deployments FAILING:"
echo "    → Check OPS_RUNBOOK.md Task 1 Troubleshooting table"
echo "    → Common causes: project ID mismatch, branch filter mismatch, framework misconfig"
echo ""
echo "  Scenario D — Neither token available:"
echo "    → This script cannot verify anything automatically"
echo "    → Manual check: go to https://vercel.com/dashboard and look for recent deploys"
echo "    → Manual check: go to https://github.com/$REPO/settings/hooks for webhooks"
echo ""
echo "📝 Full log: $LOG_FILE"
echo ""

# Save full output to log
{
    echo "Vercel Webhook Verification Log"
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Repo: $REPO"
    echo ""
    echo "=== Step 1: GitHub Webhooks ==="
    echo "$WEBHOOKS_RESPONSE" 2>/dev/null || echo "(skipped)"
    echo ""
    echo "=== Step 2: Vercel Deployments ==="
    echo "$DEPLOY_RESPONSE" 2>/dev/null || echo "(skipped)"
    echo ""
    echo "=== Step 3: Workflow Runs ==="
    echo "$WORKFLOW_RESPONSE" 2>/dev/null || echo "(skipped)"
} > "$LOG_FILE" 2>/dev/null || true

exit 0
