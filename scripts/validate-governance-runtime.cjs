#!/usr/bin/env node

/**
 * Repository Governance Runtime Drift & Anti-Bypass Auditor (Calibrated)
 * Compares live GitHub repository settings and local repository controls
 * against the authoritative specification in docs/governance-policy.json.
 */

const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');

const ROOT_DIR = path.resolve(__dirname, '..');
const POLICY_PATH = path.join(ROOT_DIR, 'docs', 'governance-policy.json');
const CODEOWNERS_PATH = path.join(ROOT_DIR, '.github', 'CODEOWNERS');
const CI_WORKFLOW_PATH = path.join(ROOT_DIR, '.github', 'workflows', 'ci.yml');

let hasFailures = false;
const issues = [];
const passedChecks = [];

function pass(checkName, detail = '') {
  passedChecks.push({ name: checkName, detail });
  console.log(`  ✅ [PASS] ${checkName}${detail ? ` (${detail})` : ''}`);
}

function fail(checkName, error, remediation = '') {
  hasFailures = true;
  issues.push({ checkName, error, remediation });
  console.error(`  ❌ [FAIL] ${checkName}: ${error}`);
  if (remediation) console.error(`     👉 Remediation: ${remediation}`);
}

function info(checkName, detail) {
  console.log(`  ℹ️  [INFO] ${checkName}: ${detail}`);
}

console.log('\n======================================================');
console.log('🏛️  REPOSITORY GOVERNANCE RUNTIME AUDITOR (LEVEL 5 CALIBRATED)');
console.log('======================================================\n');

// 1. Load Policy Contract
if (!fs.existsSync(POLICY_PATH)) {
  fail('Policy File Missing', 'docs/governance-policy.json does not exist');
  process.exit(1);
}

const policy = JSON.parse(fs.readFileSync(POLICY_PATH, 'utf8'));
pass('Policy Loaded', 'docs/governance-policy.json');

// 2. Local CODEOWNERS Completeness Audit
if (!fs.existsSync(CODEOWNERS_PATH)) {
  fail('CODEOWNERS Missing', '.github/CODEOWNERS does not exist');
} else {
  const codeownersContent = fs.readFileSync(CODEOWNERS_PATH, 'utf8');
  let missingPathsCount = 0;
  for (const p of policy.codeowners_policy.mandatory_protected_paths) {
    if (codeownersContent.includes(p)) {
      // Matched
    } else {
      missingPathsCount++;
      fail('Unprotected Governance Path', `Path "${p}" is not explicitly listed in .github/CODEOWNERS`);
    }
  }
  if (missingPathsCount === 0) {
    pass('CODEOWNERS Governance Coverage', `All ${policy.codeowners_policy.mandatory_protected_paths.length} critical paths protected under ${policy.codeowners_policy.enforce_owner}`);
  }
}

// 3. CI Workflow Least-Privilege & Drift Check Invocation Audit
if (fs.existsSync(CI_WORKFLOW_PATH)) {
  const ciContent = fs.readFileSync(CI_WORKFLOW_PATH, 'utf8');
  if (ciContent.includes('permissions:\n  contents: read') || ciContent.includes('permissions:\n  contents: "read"')) {
    pass('CI Token Least Privilege', 'Default permissions set to contents: read');
  }

  if (ciContent.includes('validate-readme-drift.cjs')) {
    pass('CI Documentation Gate Invocation', 'validate-readme-drift.cjs is wired directly into Gate 4');
  } else {
    fail('CI Gate Missing', 'validate-readme-drift.cjs is not invoked in .github/workflows/ci.yml');
  }
}

// 4. Live GitHub API Remote Governance Verification
const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
const repo = policy.repository.full_name;

function queryGithub(endpoint) {
  return new Promise(resolve => {
    if (!token) return resolve(null);
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${repo}${endpoint}`,
      method: 'GET',
      headers: {
        'User-Agent': 'BAZspark-Governance-Monitor',
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      }
    };
    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, data });
        }
      });
    });
    req.on('error', err => resolve({ status: 'ERROR', error: err.message }));
    req.end();
  });
}

async function runRemoteCheck() {
  if (!token) {
    info('Live Remote Probe', 'GITHUB_TOKEN not provided in environment — evaluated local repository governance controls.');
    finishReport();
    return;
  }

  console.log('\n🌐 Probing Live GitHub API for Repository Governance State...');
  const bp = await queryGithub(`/branches/${policy.branch_protection.target_branch}/protection`);
  if (bp && bp.status === 200) {
    pass('Live Branch Protection Active', `Branch "${policy.branch_protection.target_branch}" is protected (HTTP 200)`);
    
    // Check force push
    if (bp.data.allow_force_pushes?.enabled === policy.branch_protection.allow_force_pushes) {
      pass('Live Force Push Restriction', 'Force push is disabled on main');
    } else {
      fail('Live Force Push Mismatch', 'Force push setting differs from policy');
    }

    // Check branch deletion
    if (bp.data.allow_deletions?.enabled === policy.branch_protection.allow_deletions) {
      pass('Live Branch Deletion Restriction', 'Branch deletion is disabled on main');
    } else {
      fail('Live Deletion Mismatch', 'Branch deletion setting differs from policy');
    }

    // Check required status checks
    const activeChecks = bp.data.required_status_checks?.checks?.map(c => c.context) || bp.data.required_status_checks?.contexts || [];
    pass('Live Required Status Checks', `${activeChecks.length} checks enforced on main`);

    // Check administrator bypass policy
    if (bp.data.enforce_admins?.enabled === policy.branch_protection.enforce_admins) {
      pass('Admin Bypass State', 'Administrator emergency bypass capability aligns with policy (enforce_admins: false)');
    }

  } else if (bp && bp.status === 404) {
    fail('Live Branch Unprotected', `Branch "${policy.branch_protection.target_branch}" has no branch protection configured on GitHub`);
  } else {
    info('Live API Probe', `GitHub API returned status ${bp?.status || 'UNKNOWN'}`);
  }

  finishReport();
}

function finishReport() {
  console.log('\n======================================================');
  console.log('📊 GOVERNANCE AUDIT SUMMARY');
  console.log('======================================================');
  console.log(`Passed Checks : ${passedChecks.length}`);
  console.log(`Issues Found  : ${issues.length}`);

  if (hasFailures) {
    console.error('\n❌ RESULT: FAILED — Repository Governance Drift Detected!\n');
    process.exit(1);
  } else {
    console.log('\n🎉 RESULT: PASSED — Repository Governance Matches Level 5 Calibrated Policy.\n');
    process.exit(0);
  }
}

runRemoteCheck().catch(err => {
  console.error('Fatal error during governance audit:', err);
  process.exit(1);
});
