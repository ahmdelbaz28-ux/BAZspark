# Deployment Guide

## Deployment Options

| Method | Best For | Complexity |
|---|---|---|
| Docker Compose | Small/medium deployments | Low |
| Kubernetes + Helm | Production at scale | Medium |
| Manual | Custom setups | High |

---

## Docker Compose (Recommended)

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

### Steps

```bash
# 1. Generate secrets
export FIREAI_API_KEY="your-strong-api-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)
export CORS_ALLOWED_ORIGINS="https://your-domain.com"

# 2. Create .env file
cat > .env << EOF
FIREAI_API_KEY=$FIREAI_API_KEY
FIREAI_SESSION_SECRET=$FIREAI_SESSION_SECRET
FIREAI_ENV=production
CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS
DATABASE_URL=postgresql://fireai:password@db:5432/fireai
REDIS_URL=redis://redis:6379
QDRANT_URL=http://qdrant:6333
NEO4J_URI=neo4j://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
EOF

# 3. Start services
docker-compose up -d

# 4. Verify
curl http://localhost:8000/api/health
```

### Services

| Service | Port | Purpose |
|---|---|---|
| API | 8000 | FastAPI backend |
| Redis | 6379 | Cache + sessions |
| Qdrant | 6333 | Vector database |
| Neo4j | 7687 | Graph database |

### Production Hardening

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  api:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
```

---

## Kubernetes + Helm

### Prerequisites

- Kubernetes 1.24+
- Helm 3.0+

### Steps

```bash
# 1. Add Helm repo
helm repo add fireai deploy/helm/fireai

# 2. Create namespace
kubectl create namespace fireai

# 3. Create secrets
kubectl create secret generic fireai-secrets \
  --from-literal=FIREAI_API_KEY=your-key \
  --from-literal=FIREAI_SESSION_SECRET=your-secret \
  --namespace fireai

# 4. Install
helm install fireai deploy/helm/fireai \
  --namespace fireai \
  --set image.tag=latest

# 5. Verify
kubectl get pods -n fireai
curl http://your-loadbalancer:8000/api/health
```

### Configuration

```yaml
# values.yaml
replicaCount: 3

image:
  repository: ghcr.io/ahmdelbaz28-ux/bazspark
  tag: latest

ingress:
  enabled: true
  hosts:
    - host: api.your-domain.com
      paths:
        - path: /
          pathType: Prefix

resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

---

## Manual Deployment

### Backend

```bash
# 1. Clone and setup
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,parsing]"

# 2. Configure
cp .env.example .env
# Edit .env with production values

# 3. Run with Gunicorn
pip install gunicorn
gunicorn backend.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Frontend

```bash
cd frontend
npm ci
npm run build

# Serve with Nginx or copy to CDN
cp -r dist/* /var/www/html/
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## Monitoring

### Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'fireai-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/api/v1/monitoring/metrics'
```

### Grafana

Import the BAZSpark dashboard from `deploy/observability/grafana/dashboards/`.

### Alerts

```yaml
# alertmanager.yml
groups:
  - name: fireai
    rules:
      - alert: APIDown
        expr: up{job="fireai-api"} == 0
        for: 5m
        labels:
          severity: critical
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
```

---

## Backup

### Database

```bash
# PostgreSQL
pg_dump -U fireai fireai > backup_$(date +%Y%m%d).sql

# Restore
psql -U fireai fireai < backup_20260725.sql
```

### Redis

```bash
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup_redis_$(date +%Y%m%d).rdb
```

### Qdrant

```bash
curl -X POST http://localhost:6333/collections/snapshots
```

---

## SSL/TLS

### Let's Encrypt

```bash
certbot certonly --standalone -d api.your-domain.com
```

### Auto-Renewal

```bash
0 0 1 * * certbot renew --quiet
```

---

## Scaling

### Horizontal

```bash
# Docker Compose
docker-compose up -d --scale api=3

# Kubernetes
kubectl scale deployment fireai-api --replicas=5 -n fireai
```

### Vertical

Increase resources in `docker-compose.yml` or Helm values:

```yaml
resources:
  limits:
    cpus: '4'
    memory: 8Gi
```

---

## Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose logs api

# Check health
curl http://localhost:8000/api/health
```

### Database connection refused

1. Verify database is running: `docker-compose ps`
2. Check connection string in `.env`
3. Verify network: `docker-compose exec api ping db`

### High memory usage

1. Check for memory leaks: `docker stats`
2. Reduce worker count
3. Add memory limits

---

## Next Steps

- [Configuration](configuration.md) — Environment variables
- [Database Setup](database-setup.md) — PostgreSQL, Redis, Qdrant, Neo4j
- [Troubleshooting](troubleshooting.md) — Common issues
