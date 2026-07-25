# BAZSpark

**Safety-Critical Fire Alarm Engineering Platform**

[![CI/CD](https://github.com/ahmdelbaz28-ux/BAZspark/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ahmdelbaz28-ux/BAZspark/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.55.0-orange)](VERSION)

BAZSpark automates fire detection and alarm system design per **NFPA 72-2022**. It provides deterministic engineering calculations, a Digital Twin for bidirectional AutoCAD/Revit conversion, and an immutable audit trail for PE review.

**Live:** [ba-zspark.vercel.app](https://ba-zspark.vercel.app) (frontend) | [ahmdelbaz28-bazspark.hf.space](https://ahmdelbaz28-bazspark.hf.space) (backend)

---

## Features

| Capability | Description |
|---|---|
| **NFPA 72 Engine** | Detector spacing, coverage analysis, compliance verification |
| **Digital Twin** | Bidirectional conversion between AutoCAD and Revit |
| **NAC Design** | Notification appliance circuit calculations with voltage drop and battery sizing |
| **Audit Trail** | HMAC-SHA256 signed, Merkle tree for PE review |
| **Marine Module** | SOLAS, IEC 60092, NFPA 302 for ship fire safety |
| **Multi-Format Parsers** | DXF, DWG, IFC, PDF, Excel, Image |
| **RBAC Security** | Role-based access with 5 roles (Admin, Engineer, Reviewer, Viewer, API) |
| **API** | 188 REST + WebSocket endpoints |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 22+
- npm 11+

### Backend

```bash
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark

pip install -e ".[dev,parsing]"

export FIREAI_API_KEY="your-api-key"
cd backend
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend: http://localhost:5173

### Login

1. Open http://localhost:5173
2. Go to Settings
3. Enter your API Key (same value as `FIREAI_API_KEY`)
4. Click Login

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite + Tailwind) │
└──────────────────────┬──────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────┐
│  Backend (FastAPI 0.138 + Python 3.12)              │
│  188 endpoints │ RBAC │ Rate Limiting │ CSP/HSTS    │
└──────────────────────┬──────────────────────────────┘
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌───────────┐ ┌──────────┐ ┌──────────┐
   │ NFPA 72   │ │ Digital  │ │ Database │
   │ Engine    │ │ Twin     │ │ SQLite / │
   │ Voltage   │ │ AutoCAD  │ │ Postgres │
   │ Drop      │ │ ←→ Revit │ │ + Redis  │
   │ Spatial   │ │          │ │ + Qdrant │
   └───────────┘ └──────────┘ └──────────┘
```

See [docs/reference/architecture.md](docs/reference/architecture.md) for full architecture details.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Pydantic, Shapely/GEOS |
| Frontend | React 18, TypeScript 5.9, Vite 8, Tailwind CSS 4, Three.js |
| Database | PostgreSQL (Supabase), SQLite, Redis, Qdrant (vector), Neo4j (graph) |
| Infrastructure | Docker, Kubernetes, Helm, Prometheus, Grafana |
| CI/CD | GitHub Actions (6 gates), CodeQL, SonarCloud |

---

## Documentation

| Document | Description |
|---|---|
| [Installation](docs/how-to/installation.md) | Setup instructions for all platforms |
| [Configuration](docs/how-to/configuration.md) | Environment variables and settings |
| [API Reference](docs/reference/api-reference.md) | Full endpoint documentation |
| [Architecture](docs/reference/architecture.md) | System design and components |
| [Engineering Formulas](docs/reference/engineering-formulas.md) | NFPA 72 / NEC formulas and constants |
| [Security](docs/reference/security.md) | Security practices and policies |
| [Contributing](CONTRIBUTING.md) | How to contribute |
| [Changelog](CHANGELOG.md) | Release history |

### Guides

| Guide | Description |
|---|---|
| [First Fire Alarm Design](docs/tutorials/first-fire-alarm-design.md) | Step-by-step tutorial |
| [Database Setup](docs/how-to/database-setup.md) | PostgreSQL, Redis, Qdrant, Neo4j |
| [Deployment](docs/how-to/deployment.md) | Docker and production deployment |
| [Troubleshooting](docs/how-to/troubleshooting.md) | Common issues and solutions |

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=fireai --cov-report=html

# Run specific module
pytest tests/test_nfpa72.py -v
```

**Current status:** 8,557+ tests collected.

---

## Deployment

### Docker (Recommended)

```bash
export FIREAI_API_KEY="your-strong-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)

docker-compose up -d
curl http://localhost:8000/api/health
```

### Kubernetes

```bash
helm install fireai deploy/helm/fireai
```

See [docs/how-to/deployment.md](docs/how-to/deployment.md) for full details.

---

## Project Structure

```
BAZspark/
├── fireai/              # Core engine (NFPA 72, spatial analysis, audit trail)
├── backend/             # FastAPI backend (188 endpoints)
├── frontend/            # React SPA (22 pages)
├── marine/              # Marine fire safety (SOLAS, IEC 60092)
├── qomn_fire/           # QOMN-FIRE engine (standalone)
├── facp_distributed/    # Distributed FACP agent system
├── parsers/             # Multi-format file parsers
├── deploy/              # Docker, Kubernetes, Helm, observability
├── tests/               # 8,557+ tests
└── docs/                # Documentation (Diátaxis structure)
    ├── tutorials/       # Learning-oriented guides
    ├── how-to/          # Problem-oriented recipes
    ├── reference/       # Information-oriented specs
    └── explanation/     # Understanding-oriented discussions
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Important:** This is a safety-critical system. All contributions undergo additional review for engineering calculations and compliance verification.

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Acknowledgments

Designed and developed by **Eng. Ahmed Elbaz**.

Built on NFPA 72-2022, NEC 2023, IBC, and SOLAS standards.
