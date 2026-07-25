# Configuration Guide

BAZSpark is configured via environment variables. All configuration is read at startup.

## Required Variables

| Variable | Description | Example |
|---|---|---|
| `FIREAI_API_KEY` | API key for authentication | `sk-abc123...` |
| `FIREAI_SESSION_SECRET` | Secret for HMAC-SHA256 session signing | Generated via `python -m backend.session_secret generate` |
| `FIREAI_ENV` | Environment mode | `development` or `production` |

## Optional Variables

### Server

| Variable | Default | Description |
|---|---|---|
| `FIREAI_HOST` | `0.0.0.0` | Server bind address |
| `FIREAI_PORT` | `8000` | Server port |
| `FIREAI_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FIREAI_WORKERS` | `1` | Number of worker processes |

### CORS

| Variable | Default | Description |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

**Production note:** Do not use wildcards (`*`). Specify exact origins.

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/fireai.db` | PostgreSQL connection string |
| `REDIS_URL` | None | Redis connection string |
| `QDRANT_URL` | None | Qdrant vector database URL |
| `QDRANT_API_KEY` | None | Qdrant API key |
| `NEO4J_URI` | None | Neo4j connection URI |
| `NEO4J_USER` | None | Neo4j username |
| `NEO4J_PASSWORD` | None | Neo4j password |

### Security

| Variable | Default | Description |
|---|---|---|
| `FIREAI_RATE_LIMIT` | `60/minute` | API rate limit |
| `FIREAI_CORS_ALLOW_CREDENTIALS` | `true` | Allow credentials in CORS |
| `FIREAI_SECURE_COOKIES` | `false` (dev) | Set `true` in production |

### File Handling

| Variable | Default | Description |
|---|---|---|
| `FIREAI_MAX_UPLOAD_SIZE` | `104857600` (100MB) | Maximum file upload size in bytes |
| `FIREAI_ALLOWED_EXTENSIONS` | `.dwg,.dxf,.ifc,.pdf,.xlsx` | Allowed file extensions |

### AI / LLM

| Variable | Default | Description |
|---|---|---|
| `FIREAI_LLM_PROVIDER` | None | LLM provider (`openai`, `anthropic`) |
| `FIREAI_LLM_API_KEY` | None | LLM API key |
| `FIREAI_LLM_MODEL` | None | Model name |

## Production Configuration

### Generate Secrets

```bash
# Generate API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate session secret
python -m backend.session_secret generate
```

### Required Production Settings

```bash
FIREAI_ENV=production
FIREAI_API_KEY="<generated-key>"
FIREAI_SESSION_SECRET="<generated-secret>"
CORS_ALLOWED_ORIGINS="https://your-domain.com"
FIREAI_SECURE_COOKIES=true
DATABASE_URL="postgresql://user:pass@host:5432/dbname"
REDIS_URL="redis://default:pass@host:6379"
```

### Environment-Specific Behavior

| Feature | Development | Production |
|---|---|---|
| Auth | Relaxed (dev keys accepted) | Strict (HMAC validation) |
| CORS | `localhost:5137` allowed | Specific origins only |
| Cookies | Not secure | Secure, HttpOnly, SameSite |
| Logging | Console | Structured JSON |
| Database | SQLite | PostgreSQL |
| Rate limiting | Disabled | Enforced |

## Docker Configuration

### Environment File

Create `.env` in the project root:

```bash
FIREAI_API_KEY=your-key
FIREAI_SESSION_SECRET=your-secret
FIREAI_ENV=production
CORS_ALLOWED_ORIGINS=https://your-domain.com
DATABASE_URL=postgresql://user:pass@db:5432/fireai
REDIS_URL=redis://redis:6379
QDRANT_URL=http://qdrant:6333
NEO4J_URI=neo4j://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
```

### Docker Compose

```bash
docker-compose up -d
```

The `docker-compose.yml` reads from `.env` automatically.

## Configuration Validation

BAZSpark validates configuration at startup. Missing required variables cause an immediate error with a clear message.

To test your configuration:

```bash
python -c "from backend.config import settings; print(settings)"
```

## Updating Configuration

Changes to environment variables require a server restart. There is no hot-reload for configuration.

```bash
# Stop the server (Ctrl+C)
# Update .env
# Restart
uvicorn backend.app:app --reload
```
