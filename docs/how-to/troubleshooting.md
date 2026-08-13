# Troubleshooting Guide

## Emergency Procedures

If you suspect a safety-critical issue:

1. **Stop using the system** for engineering decisions immediately
2. **Verify calculations manually** using published NFPA 72 tables
3. **Contact the team** at security@bazspark.com

---

## Common Issues

### Backend

#### "ModuleNotFoundError: No module named 'backend'"

**Cause:** Running from inside `backend/` directory.

**Fix:** Run from the project root:

```bash
cd BAZspark
uvicorn backend.app:app --reload
```

#### "FIREAI_API_KEY not set"

**Cause:** Environment variable not configured.

**Fix:**

```bash
export FIREAI_API_KEY="your-api-key"
# Or add to .env file
```

#### "Port 8000 already in use"

**Cause:** Another process using the port.

**Fix:**

```bash
# Find and kill the process
lsof -i :8000
kill -9 <PID>

# Or use a different port
uvicorn backend.app:app --port 8001
```

#### "CORS error"

**Cause:** Frontend origin not in allowed list.

**Fix:** Update `CORS_ALLOWED_ORIGINS` in `.env`:

```bash
CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:3000"
```

#### "Database connection refused"

**Cause:** Database not running or wrong connection string.

**Fix:**

```bash
# Check if database is running
docker-compose ps

# Verify connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

#### Slow performance

**Cause:** Missing indexes, large queries, or no caching.

**Fix:**

```bash
# Enable Redis caching
REDIS_URL="redis://localhost:6379"

# Add database indexes
alembic upgrade head

# Check slow queries
tail -f logs/app.log | grep "slow query"
```

### Frontend

#### "npm ci" fails

**Cause:** Corrupted node_modules or lockfile mismatch.

**Fix:**

```bash
cd frontend
rm -rf node_modules
npm ci
```

#### Blank page after build

**Cause:** Environment variables not configured for production.

**Fix:** Set `VITE_API_URL` before building:

```bash
VITE_API_URL="https://api.your-domain.com" npm run build
```

#### Hot reload not working

**Cause:** File system watching issue.

**Fix:**

```bash
# Linux: Increase inotify limit
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# macOS: Use polling
npm run dev -- --forcePolling
```

### Calculations

#### "Coverage below minimum threshold"

**Cause:** Room geometry or detector placement results in < 90% coverage.

**Fix:**

1. Check room dimensions
2. Verify ceiling height (max 18.288m for smoke, 15.24m for heat)
3. Add more detectors
4. Review detector spacing

#### "Voltage drop exceeds 10%"

**Cause:** Cable too long or wire gauge too small.

**Fix:**

1. Use larger wire gauge (lower AWG number)
2. Reduce cable length
3. Add power supplies closer to loads
4. Check calculations against NEC Table 8

#### "Battery capacity insufficient"

**Cause:** Battery too small for required standby + alarm time.

**Fix:**

1. Check standby current (must be in Amps, not mA)
2. Verify standby time (typically 24 hours)
3. Verify alarm time (typically 5-15 minutes)
4. Use formula: `C = (I_standby × T_standby) + (I_alarm × T_alarm)`

### Deployment

#### Docker build fails

**Fix:**

```bash
# Clean build
docker-compose build --no-cache

# Check Docker resources
docker system df
docker system prune
```

#### Health check fails after deployment

**Fix:**

```bash
# Check logs
docker-compose logs api

# Verify environment
docker-compose exec api env | grep FIREAI

# Test manually
curl -v http://localhost:8000/api/health
```

#### Database migration fails

**Fix:**

```bash
# Check migration status
alembic history

# Force current state
alembic stamp head

# Re-run migrations
alembic upgrade head
```

---

## Error Codes

| Code | Description | Action |
|---|---|---|
| `FAC-001` | Calculation overflow | Reduce input values |
| `FAC-002` | Invalid room geometry | Check for self-intersecting or degenerate shapes |
| `FAC-003` | Coverage below 90% | Add detectors or increase spacing |
| `FAC-004` | Voltage drop > 10% | Use larger wire gauge or reduce length |
| `FAC-005` | Battery insufficient | Increase battery capacity |

---

## Diagnostic Commands

### System Health

```bash
# API health
curl http://localhost:8000/api/health

# Detailed health
curl http://localhost:8000/api/v1/monitoring/health

# Prometheus metrics
curl http://localhost:8000/api/v1/monitoring/metrics
```

### Database

```bash
# PostgreSQL
psql $DATABASE_URL -c "SELECT version()"

# Redis
redis-cli -u $REDIS_URL info

# Qdrant
curl http://localhost:6333/healthz

# Neo4j
curl http://localhost:7474
```

### Logs

```bash
# Docker
docker-compose logs -f api

# Local
tail -f logs/app.log

# Filter errors
grep ERROR logs/app.log
```

### Performance

```bash
# Response times
curl -o /dev/null -s -w "%{time_total}\n" http://localhost:8000/api/health

# Database queries
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

---

## Getting Help

1. Check this guide
2. Search [GitHub Issues](https://github.com/ahmdelbaz28-ux/BAZspark/issues)
3. Open a new issue with:
   - Steps to reproduce
   - Error message/logs
   - Environment details
   - Expected vs actual behavior

For security vulnerabilities, email security@bazspark.com directly.
