# Installation Guide

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10, macOS 10.15, Ubuntu 20.04 | Latest versions |
| Python | 3.12+ | 3.12+ |
| Node.js | 22+ | 22+ |
| RAM | 8 GB | 16 GB |
| Disk | 10 GB free | 20 GB free |

## Quick Install

### 1. Clone and Setup Backend

```bash
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -e ".[dev,parsing]"
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
FIREAI_API_KEY="your-secure-api-key"
FIREAI_ENV=development
FIREAI_LOG_LEVEL=INFO
```

### 3. Start Backend

```bash
cd backend
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

### 4. Start Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend: http://localhost:5173

### 5. Login

1. Open http://localhost:5173
2. Go to Settings
3. Enter your API Key (same as `FIREAI_API_KEY`)
4. Click Login

---

## Docker Installation

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

### Steps

```bash
# Generate secrets
export FIREAI_API_KEY="your-strong-api-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)
export CORS_ALLOWED_ORIGINS="https://your-domain.com"

# Start services
docker-compose up -d

# Verify
curl http://localhost:8000/api/health
```

### Services Started

| Service | Port | Purpose |
|---|---|---|
| API | 8000 | FastAPI backend |
| Redis | 6379 | Cache + sessions |
| Qdrant | 6333 | Vector database |
| Neo4j | 7687 | Graph database |

---

## Database Setup

### PostgreSQL (Production)

1. Create account at [supabase.com](https://supabase.com)
2. Create a new project
3. Copy the connection string
4. Add to `.env`:

```bash
DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```

### Redis

1. Create account at [upstash.com](https://upstash.com)
2. Create a Redis database
3. Copy the connection URL
4. Add to `.env`:

```bash
REDIS_URL="redis://default:pass@host:6379"
```

### Qdrant (Vector DB for RAG)

1. Create account at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a cluster
3. Copy the URL and API key
4. Add to `.env`:

```bash
QDRANT_URL="https://your-cluster.qdrant.io"
QDRANT_API_KEY="your-api-key"
```

### Neo4j (Graph DB)

1. Create account at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Create a free instance
3. Copy the connection details
4. Add to `.env`:

```bash
NEO4J_URI="neo4j+s://your-instance.databases.neo4j.io"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your-password"
```

### Database Initialization

```bash
# Run Alembic migrations
alembic upgrade head

# Or use the setup script
python setup_databases.py
```

---

## Development Setup

### Python Dependencies

```bash
# Core
pip install -e "."

# Development tools
pip install -e ".[dev]"

# Parsing support
pip install -e ".[parsing]"

# All optional
pip install -e ".[dev,parsing,facp]"
```

### Frontend Dependencies

```bash
cd frontend
npm ci
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=fireai --cov-report=html

# Specific module
pytest tests/test_nfpa72.py -v

# Frontend tests
cd frontend
npm test
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

---

## Platform-Specific Notes

### Windows

- Use `venv\Scripts\activate` instead of `source venv/bin/activate`
- AutoCAD/Revit integration requires Windows + pywin32/pythonnet
- Some parsers may require Visual C++ Build Tools

### macOS

- Use `brew install python@3.12` or pyenv
- LibreDWG available via Homebrew: `brew install libredwg`

### Linux

- Install build dependencies: `sudo apt install build-essential python3-dev`
- LibreDWG: `sudo apt install libredwg-dev`

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'backend'"

Run from the project root, not from inside `backend/`:

```bash
cd BAZspark
uvicorn backend.app:app --reload
```

### "FIREAI_API_KEY not set"

Set the environment variable before starting:

```bash
export FIREAI_API_KEY="your-key"
```

### "Port 8000 already in use"

Use a different port:

```bash
uvicorn backend.app:app --port 8001
```

### Database connection errors

1. Check that your database service is running
2. Verify connection strings in `.env`
3. Ensure your IP is whitelisted (for cloud databases)

### Frontend build fails

```bash
cd frontend
rm -rf node_modules
npm ci
npm run build
```

---

## Next Steps

- [Configuration Guide](configuration.md) — Environment variables and settings
- [Deployment Guide](deployment.md) — Production deployment
- [API Reference](../reference/api-reference.md) — Endpoint documentation
