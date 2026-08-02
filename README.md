# BAZSpark

**Safety-Critical Fire Alarm Engineering Platform**

[![CI/CD](https://github.com/ahmdelbaz28-ux/BAZspark/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ahmdelbaz28-ux/BAZspark/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.55.0-orange)](VERSION)

BAZSpark automates fire detection and alarm system design per NFPA 72-2022. It delivers deterministic engineering calculations and an immutable audit trail for professional review.

The system features a Digital Twin engine for bidirectional AutoCAD and Revit conversion. It eliminates manual drafting errors while verifying compliance across complex building layouts.

**Live Endpoints:** [ba-zspark.vercel.app](https://ba-zspark.vercel.app) (Frontend) | [ahmdelbaz28-bazspark.hf.space](https://ahmdelbaz28-bazspark.hf.space) (Backend)

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite + Tailwind) │
└──────────────────────┬──────────────────────────────┘
                        │ REST + WebSocket
┌──────────────────────▼──────────────────────────────┐
│  Backend (FastAPI 0.138 + Python 3.8+)              │
│  247+ endpoints │ RBAC │ Rate Limiting │ CSP/HSTS    │
└──────────────────────┬──────────────────────────────┘
           ┌────────────┼────────────┐
           ▼            ▼            ▼
    ┌───────────┐ ┌──────────┐ ┌──────────┐
    │ NFPA 72   │ │ Digital  │ │ Database │
    │ Engine    │ │ Twin     │ │ SQLite / │
    │ Voltage   │ │ AutoCAD  │ │ Postgres │
    │ Drop      │ │ ←→ Revit │ │ + Redis  │
    └───────────┘ └──────────┘ └──────────┘
```

The frontend React application communicates with the FastAPI backend via REST and WebSockets. Requests pass through RBAC authorization, rate limiting, and security headers.

Core calculation engines execute deterministic algorithms for spatial coverage and voltage drop. Results persist across PostgreSQL, Redis cache, and Qdrant vector storage.

---

## 2. Core Capabilities

| Capability | Engineering Purpose | Standard |
|---|---|---|
| **NFPA 72 Engine** | Detector spacing and visual coverage verification | NFPA 72-2022 |
| **Digital Twin** | Bidirectional DWG and RVT element translation | IFC 4.3 / ISO 16739 |
| **NAC Circuit Solver** | End-of-line voltage drop and battery capacity sizing | NFPA 72 §10.6.7 |
| **Marine Module** | Vessel fire detection and deluge control rules | SOLAS / IEC 60092 |
| **Immutable Audit** | Merkle tree signed calculation verification | NFPA 72 §14.2.4 |
| **Multi-Format Parsers** | High-throughput DXF, DWG, IFC, and PDF parsing | ISO 32000 |

Every calculation is deterministic and reproducible. The platform never relies on heuristic fallbacks during safety-critical evaluation cycles.

---

## 3. Technology Stack

| Layer | Component | Specification |
|---|---|---|
| **API Layer** | FastAPI 0.138+ | Asynchronous Python 3.8+ runtime |
| **UI Layer** | React 18 & Vite 8 | TypeScript 5.9 with Tailwind CSS 4 |
| **Storage** | PostgreSQL & SQLite | Supabase primary with WAL SQLite |
| **Caching & Search** | Redis & Qdrant | In-memory cache and vector memory |
| **Security** | RBAC & HMAC-SHA256 | Strict origin CORS and Security Headers |

The stack isolates calculation logic from presentation layers. This separation guarantees complete auditability across all execution paths.

---

## 4. Prerequisites

Before installing BAZSpark, verify your environment meets the minimum runtime specifications.

- Python 3.8 or higher
- Node.js 22.0.0 or higher
- npm 11.0.0 or higher
- Git 2.40+

---

## 5. Quick Start Guide

Clone the repository and install backend dependencies in editable mode with development flags.

```bash
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark
pip install -e ".[dev,parsing]"
```

Export required environment tokens and launch the FastAPI server.

```bash
export FIREAI_API_KEY="your-secure-api-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Install frontend dependencies and start the Vite development server.

```bash
cd frontend
npm ci
npm run dev
```

Access the UI at `http://localhost:5173`. Open Settings, input your `FIREAI_API_KEY`, and authenticate.

---

## 6. Directory Structure

```
BAZspark/
├── fireai/              # NFPA 72 engine and audit verification
├── backend/             # FastAPI routers, services, and models
├── frontend/            # React SPA user interface
├── marine/              # SOLAS marine compliance engine
├── qomn_fire/           # Standalone QOMN-FIRE kernel
├── facp_distributed/    # Distributed FACP agent pipeline
├── parsers/             # DXF, DWG, IFC, and PDF parsers
├── deploy/              # Docker, Kubernetes, and Helm manifests
└── tests/               # Unit and integration test suites
```

---

## 7. Verification & Testing

Execute the test suite to verify calculation accuracy and router integrity.

```bash
# Run complete test suite
pytest

# Generate HTML coverage report
pytest --cov=fireai --cov-report=html
```

The repository maintains strict test gate enforcement. Pull requests must pass all security and calculation gates before merge.

---

## 8. Production Deployment

Deploy the platform container using Docker Compose.

```bash
export FIREAI_API_KEY="your-production-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)
docker-compose up -d
```

For Kubernetes clusters, install using the Helm chart.

```bash
helm install fireai deploy/helm/fireai
```

---

## 9. Governance & License

BAZSpark is a safety-critical system. All contributions undergo strict engineering review.

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

Designed and developed by **Eng. Ahmed Elbaz**.