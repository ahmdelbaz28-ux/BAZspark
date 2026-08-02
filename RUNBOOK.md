# BAZSpark Operational & Emergency Runbook

**Audience:** Site Reliability Engineers (SRE), DevOps, and System Administrators  
**Last Updated:** August 2026

This runbook documents standard operational procedures, emergency incident response workflows, and secret rotation steps for the BAZSpark platform.

---

## 1. When to Use This Runbook

Use this runbook when:
- Investigating system outages or degraded performance
- Performing routine database backups and restores
- Rotating production signing secrets and API keys
- Executing emergency system rollbacks
- Escalating functional safety or calculation errors

---

## 2. Prerequisites & Access Required

Ensure you possess the required elevated credentials before executing commands in this runbook:

- **GitHub PAT:** Fine-grained token with `secrets:write` permissions for `ahmdelbaz28-ux/BAZspark`
- **Kubernetes Access:** `kubectl` configured with cluster admin context (`KUBE_CONFIG_PRODUCTION`)
- **Docker Engine:** Access to production runner nodes with Docker 24.0+
- **Database Access:** Direct credentials for PostgreSQL / Supabase primary database

---

## 3. Standard Operational Procedures

### A. Health & Readiness Diagnostics

Verify system health across backend REST API, database pools, and worker nodes.

```bash
# 1. Quick API health check
curl -f http://127.0.0.1:8000/api/health

# 2. Detailed metrics and component status
curl -H "X-API-Key: $FIREAI_API_KEY" http://127.0.0.1:8000/api/v1/monitoring/health
```

Expected health status payload:
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "version": "1.55.0"
}
```

### B. Secret Rotation Procedure

Rotate application signing secrets (`FIREAI_SESSION_SECRET`, `JWT_SECRET`) without service interruption.

1. **Generate strong replacement secret (min 43 chars / 256-bit entropy):**
   ```bash
   NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
   ```

2. **Update local environment / secret manager:**
   ```bash
   export FIREAI_SESSION_SECRET="$NEW_SECRET"
   ```

3. **Push secret to GitHub Actions repository store:**
   ```bash
   export GH_PAT="<your-access-token>"
   python3 scripts/set_github_secrets.py
   ```

4. **Restart backend application instances:**
   ```bash
   docker-compose restart api
   # or for Kubernetes:
   kubectl rollout restart deployment/fireai-api -n fireai
   ```

### C. Database Backup & Restore

#### PostgreSQL Backup

```bash
# Export full database dump
pg_dump -U fireai -h db.example.com -d fireai -F c -b -v -f /app/data/backups/fireai_$(date +%Y%m%d_%H%M%S).dump

# Restore database dump
pg_restore -U fireai -h db.example.com -d fireai -clean -v /app/data/backups/fireai_20260802_120000.dump
```

#### Redis Snapshot Backup

```bash
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /app/data/backups/redis_$(date +%Y%m%d).rdb
```

---

## 4. Emergency Incident & Rollback Workflows

### A. Emergency System Rollback

If a newly deployed release triggers high 5xx error rates or calculation regressions:

1. **Rollback Helm release to previous revision:**
   ```bash
   helm rollback fireai -n fireai
   ```

2. **Verify pod status and health endpoints:**
   ```bash
   kubectl get pods -n fireai -w
   curl -f http://api.example.com/api/health
   ```

3. **Rollback Git release tag (if necessary):**
   ```bash
   git checkout main
   git reset --hard HEAD~1
   git push origin main --force-with-lease
   ```

---

## 5. Escalation Matrix

| Incident Severity | Trigger Condition | Escalation Contact | SLA |
|---|---|---|---|
| **P0 - Critical** | Safety calculation failure / NFPA 72 verification bypass | `emergency-security@fireai.org` | 15 minutes |
| **P1 - Major** | Complete backend outage / Database connection pool failure | `sre@fireai.org` | 1 hour |
| **P2 - Moderate** | Degradation in RAG memory search or non-critical routers | `devops@fireai.org` | 4 hours |
