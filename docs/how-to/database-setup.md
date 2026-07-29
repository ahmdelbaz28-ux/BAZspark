# Database Setup

BAZSpark supports multiple databases for different purposes. This guide covers setup for each.

## Database Overview

| Database | Purpose | Required |
|---|---|---|
| PostgreSQL | Primary data store | Production |
| SQLite | Development database | Development |
| Redis | Cache, sessions, rate limiting | Production |
| Qdrant | Vector database (RAG) | Optional |
| Neo4j | Graph database (network topology) | Optional |

---

## PostgreSQL (Production)

### Option 1: Supabase (Recommended)

1. Create account at [supabase.com](https://supabase.com)
2. Create a new project
3. Go to Settings → Database
4. Copy the connection string (URI mode)

```bash
DATABASE_URL="postgresql://postgres.xxxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
```

### Option 2: Neon

1. Create account at [neon.tech](https://neon.tech)
2. Create a project
3. Copy the connection string

### Option 3: Self-Hosted

```bash
# Docker
docker run -d \
  --name fireai-db \
  -e POSTGRES_DB=fireai \
  -e POSTGRES_USER=fireai \
  -e POSTGRES_PASSWORD=your-password \
  -p 5432:5432 \
  -v fireai-data:/var/lib/postgresql/data \
  postgres:16-alpine
```

Connection string:

```bash
DATABASE_URL="postgresql://fireai:your-password@localhost:5432/fireai"
```

### Configuration

Add to `.env`:

```bash
DATABASE_URL="your-connection-string"
```

### Run Migrations

```bash
alembic upgrade head
```

---

## Redis (Production)

### Option 1: Upstash (Recommended)

1. Create account at [upstash.com](https://upstash.com)
2. Create a Redis database
3. Copy the connection URL

```bash
REDIS_URL="redis://default:password@us1-mock-redis.upstash.io:6379"
```

### Option 2: Self-Hosted

```bash
# Docker
docker run -d \
  --name fireai-redis \
  -p 6379:6379 \
  -v fireai-redis:/data \
  redis:7-alpine redis-server --appendonly yes
```

Connection string:

```bash
REDIS_URL="redis://localhost:6379"
```

### Configuration

Add to `.env`:

```bash
REDIS_URL="your-connection-url"
```

---

## Qdrant (Vector Database for RAG)

Qdrant stores document embeddings for the RAG (Retrieval-Augmented Generation) system. Used by the 24+ AI agents for context retrieval.

### Option 1: Qdrant Cloud (Recommended)

1. Create account at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a free cluster (1GB)
3. Copy the URL and API key

```bash
QDRANT_URL="https://your-cluster.qdrant.io"
QDRANT_API_KEY="your-api-key"
```

### Option 2: Self-Hosted

```bash
# Docker
docker run -d \
  --name fireai-qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v fireai-qdrant:/qdrant/storage \
  qdrant/qdrant:latest
```

Connection string:

```bash
QDRANT_URL="http://localhost:6333"
```

### Configuration

Add to `.env`:

```bash
QDRANT_URL="your-url"
QDRANT_API_KEY="your-api-key"  # Not needed for self-hosted
```

---

## Neo4j (Graph Database)

Neo4j stores network topology and relationships between building elements. Used for graph-based queries and analysis.

### Option 1: Neo4j Aura (Recommended)

1. Create account at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Create a free instance (free tier available)
3. Copy the connection details

```bash
NEO4J_URI="neo4j+s://your-instance.databases.neo4j.io"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your-password"
```

### Option 2: Self-Hosted

```bash
# Docker
docker run -d \
  --name fireai-neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  -v fireai-neo4j:/data \
  neo4j:5-community
```

Connection string:

```bash
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your-password"
```

### Configuration

Add to `.env`:

```bash
NEO4J_URI="your-uri"
NEO4J_USER="your-user"
NEO4J_PASSWORD="your-password"
```

---

## SQLite (Development)

SQLite is used for local development by default. No setup required.

```bash
# Default location
DATABASE_URL="sqlite:///./data/fireai.db"
```

### Limitations

- No concurrent writes
- No network access
- Not recommended for production

---

## Full .env Example

```bash
# Database
DATABASE_URL="postgresql://fireai:password@localhost:5432/fireai"

# Redis
REDIS_URL="redis://localhost:6379"

# Qdrant (optional)
QDRANT_URL="http://localhost:6333"

# Neo4j (optional)
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"
```

---

## Initialization

### Run Migrations

```bash
alembic upgrade head
```

### Create Tables Manually (Development)

```bash
python -c "from backend.models import Base; from backend.db import engine; Base.metadata.create_all(engine)"
```

### Setup Script

```bash
python setup_databases.py
```

This script:
1. Tests all database connections
2. Runs migrations
3. Creates initial data

---

## Health Checks

### PostgreSQL

```bash
psql $DATABASE_URL -c "SELECT 1"
```

### Redis

```bash
redis-cli -u $REDIS_URL ping
```

### Qdrant

```bash
curl http://localhost:6333/healthz
```

### Neo4j

```bash
curl http://localhost:7474
```

---

## Troubleshooting

### "connection refused"

- Verify the database service is running
- Check the hostname and port
- Ensure your IP is whitelisted (cloud databases)

### "authentication failed"

- Verify username and password
- Check that the user has access to the database
- Ensure the database exists

### "database does not exist"

```bash
# PostgreSQL
createdb -U fireai fireai

# Or let Alembic create it
alembic upgrade head
```

### "too many connections"

Increase `max_connections` in PostgreSQL config or use connection pooling.

---

## Next Steps

- [Configuration](configuration.md) — Environment variables
- [Deployment](deployment.md) — Production deployment
- [Troubleshooting](troubleshooting.md) — Common issues
