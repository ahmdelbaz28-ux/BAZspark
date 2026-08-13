# Security Practices

BAZSpark is a **safety-critical system** for fire protection engineering. Security vulnerabilities could compromise life-safety functions.

## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────┐
│  Network Layer                          │
│  TLS 1.3 │ CSP │ HSTS │ Rate Limiting  │
├─────────────────────────────────────────┤
│  Application Layer                      │
│  RBAC │ Input Validation │ CSRF         │
├─────────────────────────────────────────┤
│  Data Layer                             │
│  Encryption │ Integrity │ Audit Trail   │
├─────────────────────────────────────────┤
│  Safety Layer                           │
│  Fail-safe │ Deterministic │ Immutable  │
└─────────────────────────────────────────┘
```

### Authentication

- **API Key**: Primary authentication method
- **HttpOnly Cookies**: Session management with HMAC-SHA256 signing
- **No passwords**: API key only — no password storage or reset flows

### Authorization (RBAC)

| Role | Permissions |
|---|---|
| `admin` | Full system access |
| `engineer` | Create/edit/delete projects, run calculations |
| `reviewer` | Read-only, approve/reject changes |
| `viewer` | Read-only access |
| `api` | Programmatic access |

### Input Validation

- All inputs validated at API boundary
- Type checking via Pydantic schemas
- Boundary checks on all calculations
- SQL injection prevention via ORM
- XSS prevention via output encoding

### Secrets Management

- Never commit secrets to version control
- Use environment variables for all secrets
- Rotate secrets regularly (90-day cycle)
- Gitleaks + detect-secrets in CI pipeline

---

## Vulnerability Reporting

### Safety-Critical Vulnerabilities

If you discover a vulnerability that could compromise safety functions:

1. **Email:** security@bazspark.com
2. **Response time:** Within 24 hours
3. **Include:** Description, steps to reproduce, potential impact

Safety-critical vulnerabilities include:
- Incorrect fire safety calculations
- Bypass of compliance verification
- Tampering with safety-critical algorithms
- False safety assurance claims
- Availability attacks on safety functions

### Standard Vulnerabilities

1. Open a GitHub issue with `security-vulnerability` label
2. Use responsible disclosure
3. Allow time for remediation before public disclosure

---

## Security Controls

### Network

| Control | Implementation |
|---|---|
| TLS 1.3 | All production traffic encrypted |
| CSP | Content Security Policy headers |
| HSTS | HTTP Strict Transport Security |
| CORS | Specific origins only (no wildcards) |
| Rate Limiting | SlowAPI (60 req/min default) |

### Application

| Control | Implementation |
|---|---|
| RBAC | Permission-based access control |
| Input Validation | Pydantic schemas at API boundary |
| SQL Injection | SQLAlchemy ORM (parameterized queries) |
| XSS | Output encoding, CSP headers |
| CSRF | SameSite cookies, CSRF tokens |

### Data

| Control | Implementation |
|---|---|
| Encryption at Rest | AES-256 for sensitive data |
| Encryption in Transit | TLS 1.3 |
| Integrity | HMAC-SHA256 for audit trail |
| Backup | Regular encrypted backups |

### Audit

| Control | Implementation |
|---|---|
| Audit Trail | Immutable, HMAC-signed |
| Merkle Tree | Tamper-evident chain |
| Logging | Structured JSON logs |
| Monitoring | Prometheus + Grafana |

---

## Safety-Critical Security

### Deterministic Calculations

All NFPA 72 calculations use deterministic algorithms. This ensures:
- Reproducible results
- No random behavior
- Verifiable by PE review

### Immutable Audit Trail

Every engineering decision is recorded with:
- HMAC-SHA256 signed hash
- Merkle tree chain
- Timestamp
- User identity

The audit trail cannot be modified after creation.

### Fail-Safe Defaults

When in doubt, the system defaults to the most conservative interpretation:
- Coverage calculations err toward lower coverage (flags for review)
- Compliance checks err toward non-compliance (requires manual override)
- Missing data triggers warnings, not silent assumptions

---

## Deployment Security

### Production Checklist

- [ ] `FIREAI_ENV=production`
- [ ] `FIREAI_SECURE_COOKIES=true`
- [ ] `CORS_ALLOWED_ORIGINS` set to specific domains
- [ ] Database credentials in environment variables
- [ ] Redis/Qdrant/Neo4j credentials secured
- [ ] TLS certificate configured
- [ ] Rate limiting enabled
- [ ] Logging to external service
- [ ] Monitoring alerts configured

### Container Security

- Non-root user
- Read-only filesystem (where possible)
- No new privileges
- Resource limits

---

## Compliance

### Standards

| Standard | Coverage |
|---|---|
| OWASP Top 10 | Application security controls |
| NIST Cybersecurity Framework | Defense in depth |
| ISO 27001 | Information security management |
| IEC 61508 | Functional safety (SIL) |

### Auditing

- Monthly: Dependency updates, security patches
- Quarterly: Penetration testing, code review
- Annually: Full security audit

---

## Secret Leak Prevention

### CI Pipeline

```yaml
# .github/workflows/ci.yml
- name: Gitleaks
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

- name: detect-secrets
  run: detect-secrets scan --all-files --baseline .secrets.baseline
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/gitleaks/gitleaks
  hooks:
    - id: gitleaks
```

### If a Secret is Committed

1. **Immediately rotate** the secret
2. **Check git history** for exposure
3. **Notify the team**
4. **Update `.secrets.baseline`** if false positive
5. **Document the incident**
