#!/usr/bin/env bash
#
# run_sonar_scan.sh — Run SonarQube scan against SonarCloud
#
# This script was prepared by the AI agent. It is READY TO RUN — the only
# missing piece is the SONAR_TOKEN, which the user must generate at:
#   https://sonarcloud.io/account/security/
#
# Usage:
#   export SONAR_TOKEN="your_token_here"
#   bash /home/z/my-project/scripts/run_sonar_scan.sh
#
# Or pass the token as an argument:
#   bash /home/z/my-project/scripts/run_sonar_scan.sh "your_token_here"
#
# What this script does:
#   1. Validates SONAR_TOKEN is set
#   2. Runs sonar-scanner against SonarCloud project ahmdelbaz28-ux_revit
#   3. Saves output to /home/z/my-project/work/sonar_scan_YYYYMMDD_HHMMSS.log
#   4. Prints the SonarCloud dashboard URL for reviewing results
#
# Prerequisites:
#   - sonar-scanner installed at /home/z/sonar-scanner/sonar-scanner-5.0.1.3006-linux/
#   - SONAR_TOKEN with "Execute Analysis" scope on ahmdelbaz28-ux_revit project
#   - sonar-project.properties exists in repo root (✅ already present)

set -euo pipefail

REPO_ROOT="/home/z/my-project/work/revit"
SONAR_SCANNER="/home/z/sonar-scanner/sonar-scanner-5.0.1.3006-linux/bin/sonar-scanner"
LOG_DIR="/home/z/my-project/work"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/sonar_scan_${TIMESTAMP}.log"

# ── Step 1: Validate token ──
SONAR_TOKEN="${1:-${SONAR_TOKEN:-}}"
if [ -z "$SONAR_TOKEN" ]; then
    echo "❌ ERROR: SONAR_TOKEN is not set"
    echo ""
    echo "To generate a token:"
    echo "  1. Go to https://sonarcloud.io/account/security/"
    echo "  2. Click 'Generate Token'"
    echo "  3. Name it 'fireai-local-scan'"
    echo "  4. Select scope: 'Execute Analysis'"
    echo "  5. Copy the token"
    echo "  6. Run this script with the token:"
    echo ""
    echo "     bash $0 \"your_token_here\""
    echo ""
    echo "  Or export it first:"
    echo ""
    echo "     export SONAR_TOKEN=\"your_token_here\""
    echo "     bash $0"
    exit 1
fi

echo "✅ SONAR_TOKEN is set (length: ${#SONAR_TOKEN})"
echo "📁 Repo: $REPO_ROOT"
echo "📝 Log:  $LOG_FILE"
echo ""

# ── Step 2: Verify sonar-scanner is installed ──
if [ ! -x "$SONAR_SCANNER" ]; then
    echo "❌ ERROR: sonar-scanner not found at $SONAR_SCANNER"
    echo "   Install it first:"
    echo "   cd /tmp && curl -sL https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip -o sonar-scanner.zip"
    echo "   unzip -o sonar-scanner.zip -d /home/z/sonar-scanner/"
    exit 1
fi

# ── Step 3: Verify sonar-project.properties exists ──
if [ ! -f "$REPO_ROOT/sonar-project.properties" ]; then
    echo "❌ ERROR: sonar-project.properties not found in $REPO_ROOT"
    exit 1
fi

# ── Step 4: Run the scan ──
echo "🚀 Starting SonarCloud scan..."
echo "   This will take 5-15 minutes depending on codebase size."
echo "   Progress is logged to: $LOG_FILE"
echo ""

cd "$REPO_ROOT"

"$SONAR_SCANNER" \
    -Dsonar.projectKey=ahmdelbaz28-ux_revit \
    -Dsonar.organization=ahmdelbaz28-ux \
    -Dsonar.sources=. \
    -Dsonar.host.url=https://sonarcloud.io \
    -Dsonar.login="$SONAR_TOKEN" \
    -Dsonar.verbose=true \
    2>&1 | tee "$LOG_FILE"

SCAN_EXIT=$?

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "SCAN COMPLETE (exit code: $SCAN_EXIT)"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "📋 Review findings at:"
echo "   https://sonarcloud.io/project/issues?id=ahmdelbaz28-ux_revit&open=AVAILABLE"
echo ""
echo "📊 Metrics dashboard:"
echo "   https://sonarcloud.io/project/metrics?id=ahmdelbaz28-ux_revit"
echo ""
echo "📈 Activity (compare before/after NOSONAR removal):"
echo "   https://sonarcloud.io/project/activity?id=ahmdelbaz28-ux_revit"
echo ""
echo "📝 Full log saved to: $LOG_FILE"
echo ""
echo "─── Triage Workflow ───"
echo "1. Open the Issues URL above"
echo "2. Filter by: Status=Open, Severity=Blocker+Critical+Major"
echo "3. Filter by: Since=Previous 7 days (to see only NOSONAR-removal findings)"
echo "4. For each issue, classify as:"
echo "   - FALSE POSITIVE → mark 'Won't Fix' with reason"
echo "   - ACCEPTED RISK → add per-line '# NOSONAR — <rule>: <reason>'"
echo "   - REAL BUG → create GitHub issue + fix"
echo ""
echo "5. Update NOSONAR_AUDIT.md 'Phase 2 Verification' section with results"
echo ""

exit $SCAN_EXIT
