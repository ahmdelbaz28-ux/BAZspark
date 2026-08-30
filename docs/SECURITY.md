# Security Policy for BAZSpark

**Safety-Critical Security Mandate**

BAZSpark is a safety-critical system for fire protection engineering. Security vulnerabilities directly impact life-safety calculations. Cybersecurity and functional safety are strictly coupled across all execution paths.

---

## 1. Vulnerability Reporting Protocol

Report safety-critical vulnerabilities affecting calculation accuracy directly to our engineering response team.

- **Safety Critical Email:** security@fireai.org
- **Standard Vulnerabilities:** GitHub Security Advisories
- **Response SLA:** Initial triage within 24 hours for safety-critical disclosures

Safety-critical defects include false compliance reporting, calculation tampering, or bypass of NFPA 72 verification rules.

---

## 2. Defense-in-Depth Security Model

Security controls operate continuously across network, application, data, and compute layers.

| Tier | Guard Mechanism | Enforcement |
|---|---|---|
| **Network** | Akamai / Cloudflare Headers | Bot filtering and rate limiting |
| **Application** | Pydantic Strict Schemas | Strict input sanitization and CORS |
| **Data** | Merkle Signed Ledger | HMAC-SHA256 calculation verification |
| **Compute** | Isolated Pod Runtimes | Non-root containers and read-only root |

Startup secret validation inspects signing keys on container boot. Missing or default credentials trigger immediate `RuntimeError` aborts.

---

## 3. Secret Leak Prevention & Automated Scanners

The repository enforces pre-commit and CI/CD secret scanning to prevent accidental credential commits.

- **Gitleaks:** Pattern matching scanner for API keys and tokens
- **detect-secrets:** High-entropy string detection scanner
- **GitHub Actions:** Automated PR workflow scanning via `.gitleaks.toml`

Developers must run `pre-commit run --all-files` before submitting pull requests to ensure no credentials enter git history.

---

## 4. Safety Invariants & Fail-Safe Execution

Calculations must execute deterministically without heuristic fallbacks. The system defaults to conservative safety margins whenever inputs contain ambiguity.

Audit ledgers record calculation parameters with HMAC signatures. This ensures tamper-evident verification for Professional Engineer review.

---

## 5. Incident Response Protocol

Isolate affected pods immediately upon detecting a security breach. Preserve execution logs and verify calculation integrity before restoring operations.

Rotate compromised credentials immediately and issue security advisories via GitHub Security Advisories.