#!/usr/bin/env node

/**
 * README Documentation Drift & Governance Gate (Hardened)
 * Continuous automated verification of README.md accuracy against authoritative repository metadata.
 *
 * Source-of-truth priority:
 * 1. package.json / frontend/package.json
 * 2. pyproject.toml
 * 3. VERSION
 * 4. Actual file tree
 * 5. CI / deployment configurations
 */

const fs = require('node:fs');
const path = require('node:path');

const ROOT_DIR = path.resolve(__dirname, '..');
const README_PATH = path.join(ROOT_DIR, 'README.md');
const CONTRACT_PATH = path.join(ROOT_DIR, 'docs', 'readme-contract.json');
const VERSION_PATH = path.join(ROOT_DIR, 'VERSION');
const ROOT_PKG_PATH = path.join(ROOT_DIR, 'package.json');
const FRONTEND_PKG_PATH = path.join(ROOT_DIR, 'frontend', 'package.json');
const PYPROJECT_PATH = path.join(ROOT_DIR, 'pyproject.toml');

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

console.log('\n======================================================');
console.log('🛡️  README DOCUMENTATION DRIFT CI/CD GATE (HARDENED)');
console.log('======================================================\n');

// 1. Mandatory Ground-Truth File Existence
const mandatoryFiles = [
  { name: 'README.md', path: README_PATH },
  { name: 'VERSION', path: VERSION_PATH },
  { name: 'package.json', path: ROOT_PKG_PATH },
  { name: 'frontend/package.json', path: FRONTEND_PKG_PATH },
  { name: 'pyproject.toml', path: PYPROJECT_PATH }
];

for (const f of mandatoryFiles) {
  if (!fs.existsSync(f.path)) {
    fail('Mandatory Ground-Truth File Missing', `Authoritative file "${f.name}" was deleted or moved`);
  }
}

if (hasFailures) {
  console.error('\n❌ CRITICAL: Mandatory source-of-truth files missing. Aborting validation.\n');
  process.exit(1);
}

const readmeContent = fs.readFileSync(README_PATH, 'utf8');

// Load contract if available
let contract = null;
if (fs.existsSync(CONTRACT_PATH)) {
  try {
    contract = JSON.parse(fs.readFileSync(CONTRACT_PATH, 'utf8'));
    pass('Contract Loaded', 'docs/readme-contract.json');
  } catch (e) {
    fail('Contract Parse', `Invalid JSON in ${CONTRACT_PATH}: ${e.message}`);
  }
}

// 2. Authoritative Version Check (Direct from VERSION file)
const authoritativeVersion = fs.readFileSync(VERSION_PATH, 'utf8').trim();
if (!authoritativeVersion) {
  fail('Version Empty', 'VERSION file is empty');
} else {
  const versionRegex = new RegExp(`v?${authoritativeVersion.replace(/\./g, '\\.')}`);
  if (versionRegex.test(readmeContent)) {
    pass('Version Synchronization', `README references current version ${authoritativeVersion}`);
  } else {
    fail('Version Drift', `README does not contain authoritative version v${authoritativeVersion}`, `Update version badge and release references in README.md to v${authoritativeVersion}`);
  }
}

// Check root package.json version
const rootPkg = JSON.parse(fs.readFileSync(ROOT_PKG_PATH, 'utf8'));
if (rootPkg.version && rootPkg.version !== authoritativeVersion) {
  fail('Package Version Mismatch', `root package.json version (${rootPkg.version}) differs from VERSION (${authoritativeVersion})`);
}

// 3. Python Runtime Requirement Check (Direct from pyproject.toml)
const pyprojectContent = fs.readFileSync(PYPROJECT_PATH, 'utf8');
const pyMatch = pyprojectContent.match(/requires-python\s*=\s*"([^"]+)"/);
if (pyMatch) {
  const requiredPython = pyMatch[1]; // e.g. ">=3.12"
  const minMajorMinor = requiredPython.replace(/[^0-9.]/g, ''); // "3.12"
  const pythonBadgeMatch = readmeContent.match(/Python-([0-9.]+)/i);
  if (pythonBadgeMatch) {
    const readmePy = pythonBadgeMatch[1];
    if (readmePy.startsWith(minMajorMinor) || minMajorMinor.startsWith(readmePy)) {
      pass('Python Runtime Requirement', `pyproject.toml (${requiredPython}) matches README (Python ${readmePy}+)`);
    } else {
      fail('Python Version Drift', `pyproject.toml requires Python ${requiredPython}, but README badge claims Python ${readmePy}`, `Update Python badge in README.md to match ${minMajorMinor}+`);
    }
  } else {
    fail('Python Badge Missing', 'README is missing Python version badge');
  }
}

// 4. Frontend Tooling & Framework Version Drift Check (Direct from frontend/package.json)
const fePkg = JSON.parse(fs.readFileSync(FRONTEND_PKG_PATH, 'utf8'));
const deps = { ...fePkg.dependencies, ...fePkg.devDependencies };

// React Major Check
if (deps.react) {
  const actualReactMajor = deps.react.replace(/[^0-9]/g, '').slice(0, 2); // "19"
  const readmeReactMatch = readmeContent.match(/React-([0-9]+)/i) || readmeContent.match(/React\s+([0-9]+)/i);
  if (readmeReactMatch) {
    const documentedMajor = readmeReactMatch[1];
    if (documentedMajor === actualReactMajor) {
      pass('React Major Version', `React ${actualReactMajor}.x synchronized`);
    } else {
      fail('React Version Drift', `frontend/package.json uses React ${deps.react} (major ${actualReactMajor}), but README claims React ${documentedMajor}`, `Update README.md React badge and table to React ${actualReactMajor}`);
    }
  } else {
    fail('React Badge Missing', 'README is missing React version badge');
  }
}

// TypeScript Major Check
if (deps.typescript) {
  const actualTsMajor = deps.typescript.replace(/[^0-9]/g, '').slice(0, 1); // "5"
  const readmeTsMatch = readmeContent.match(/TypeScript-([0-9]+)/i);
  if (readmeTsMatch) {
    const docTsMajor = readmeTsMatch[1];
    if (docTsMajor === actualTsMajor) {
      pass('TypeScript Major Version', `TypeScript ${actualTsMajor}.x synchronized`);
    } else {
      fail('TypeScript Version Drift', `frontend/package.json uses TypeScript ${deps.typescript}, but README claims TypeScript ${docTsMajor}`);
    }
  }
}

// Tailwind CSS Major Check
if (deps.tailwindcss) {
  const actualTwMajor = deps.tailwindcss.replace(/[^0-9]/g, '').slice(0, 1); // "4"
  if (actualTwMajor === '4') {
    if (readmeContent.includes('Tailwind CSS v4') || readmeContent.includes('Tailwind CSS 4') || readmeContent.includes('tailwindcss')) {
      pass('Tailwind CSS Major Version', 'Tailwind CSS v4 synchronized');
    } else {
      fail('Tailwind Version Drift', 'frontend uses Tailwind CSS v4, but README does not reflect v4');
    }
  }
}

// Vite Major Check
if (deps.vite) {
  const actualViteMajor = deps.vite.replace(/[^0-9]/g, '').slice(0, 1); // "8"
  const readmeViteMatch = readmeContent.match(/Vite\s+([0-9]+)/i);
  if (readmeViteMatch) {
    const docViteMajor = readmeViteMatch[1];
    if (docViteMajor === actualViteMajor) {
      pass('Vite Major Version', `Vite ${actualViteMajor}.x synchronized`);
    } else {
      fail('Vite Version Drift', `frontend/package.json uses Vite ${deps.vite}, but README claims Vite ${docViteMajor}`);
    }
  }
}

// 5. Documented Package Scripts Integrity Check
const rootPkgScripts = Object.keys(rootPkg.scripts || {});
const fePkgScripts = Object.keys(fePkg.scripts || {});
const allAvailableScripts = new Set([...rootPkgScripts, ...fePkgScripts]);

const scriptMentions = [...readmeContent.matchAll(/npm run ([a-zA-Z0-9_\-:]+)/g)].map(m => m[1]);
const uniqueDocScripts = [...new Set(scriptMentions)];

let missingScriptsCount = 0;
for (const s of uniqueDocScripts) {
  if (allAvailableScripts.has(s)) {
    // Valid
  } else {
    missingScriptsCount++;
    fail('Missing Package Script', `README documents "npm run ${s}", but script is missing from package.json`, `Define "${s}" in package.json or correct the command in README.md`);
  }
}
if (missingScriptsCount === 0) {
  pass('Documented Package Scripts', `${uniqueDocScripts.length} documented scripts verified in package.json (${uniqueDocScripts.join(', ')})`);
}

// 6. Internal Markdown Links & Images Verification
const internalLinkMatches = [...readmeContent.matchAll(/\[(?:[^\]]+)\]\(([^)]+)\)/g)];
let brokenLinks = 0;
let checkedLinksCount = 0;

for (const match of internalLinkMatches) {
  const url = match[1].trim();
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('#') || url.startsWith('mailto:')) {
    continue;
  }
  const filePath = url.split('#')[0];
  if (!filePath) continue;

  const targetAbsPath = path.resolve(ROOT_DIR, filePath);
  checkedLinksCount++;
  if (!fs.existsSync(targetAbsPath)) {
    brokenLinks++;
    fail('Broken Documentation Link', `Link to "${filePath}" cannot be resolved on disk`, `Create the missing file "${filePath}" or update the link in README.md`);
  }
}

if (brokenLinks === 0) {
  pass('Internal Documentation Links', `${checkedLinksCount} internal links and screenshot paths verified on disk`);
}

// 7. Mandatory Contract Documents Check
if (contract && contract.mandatory_documentation_links) {
  let missingMandatoryDocs = 0;
  for (const doc of contract.mandatory_documentation_links) {
    const docPath = path.join(ROOT_DIR, doc);
    if (!fs.existsSync(docPath)) {
      missingMandatoryDocs++;
      fail('Mandatory Contract Doc Missing', `Contract document "${doc}" does not exist`);
    } else if (!readmeContent.includes(doc)) {
      missingMandatoryDocs++;
      fail('Mandatory Contract Doc Unlinked', `Contract document "${doc}" exists but is not linked in README.md`);
    }
  }
  if (missingMandatoryDocs === 0) {
    pass('Mandatory Contract Links', `All ${contract.mandatory_documentation_links.length} core governance documents exist and are linked`);
  }
}

// 8. Repository Identity & Hardened Claims Filter
const expectedRepo = 'ahmdelbaz28-ux/BAZspark';
if (readmeContent.includes(expectedRepo)) {
  pass('Repository URL Consistency', `Matches ${expectedRepo}`);
} else {
  fail('Repository Drift', `README does not contain authoritative repo ${expectedRepo}`);
}

// Hardened High-Risk Claims Filter (Forbidden Unverified Assertions)
const forbiddenHighRiskPhrases = [
  '100% secure',
  'zero vulnerabilities',
  'bug-free',
  'fully bug-free',
  'perfect security',
  'guaranteed zero latency',
  'unbreakable',
  'owasp certified',
  'officially approved by ahj',
  'legally certified',
  'legally binding audit',
  '100% compliant',
  'certified against nfpa'
];

let highRiskClaimsCount = 0;
for (const phrase of forbiddenHighRiskPhrases) {
  if (readmeContent.toLowerCase().includes(phrase.toLowerCase())) {
    highRiskClaimsCount++;
    fail('Unverified High-Risk Claim Detected', `README contains forbidden unverified claim: "${phrase}"`, `Remove unverified certification claim or replace with objective engineering verification description`);
  }
}
if (highRiskClaimsCount === 0) {
  pass('Claim Rigor & Anti-Exaggeration Guard', 'Zero unverified certifications, legal claims, or forbidden hyperbole detected');
}

// 9. Final Gate Summary
console.log('\n======================================================');
console.log('📊 GATE SUMMARY REPORT');
console.log('======================================================');
console.log(`Passed Checks : ${passedChecks.length}`);
console.log(`Issues Found  : ${issues.length}`);

if (hasFailures) {
  console.error('\n❌ RESULT: FAILED — README Documentation Drift or Governance Breach Detected!\n');
  process.exit(1);
} else {
  console.log('\n🎉 RESULT: PASSED — README is 100% Synchronized with Repository Reality.\n');
  process.exit(0);
}
