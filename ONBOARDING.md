# Developer Onboarding Guide

**Welcome to the BAZSpark Engineering Team!**

This guide provides everything a new developer needs to set up their environment, understand system architecture, run common tasks, and contribute code safely.

---

## 1. System Map & Architecture Overview

BAZSpark is a safety-critical fire protection engineering platform. It automates NFPA 72-2022 calculation analysis, CAD/BIM Digital Twin translation, and immutable audit logging.

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React 18 SPA)                  │
│              TypeScript 5.9 + Vite 8 + Tailwind CSS 4       │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST / WebSocket
┌──────────────────────────────▼──────────────────────────────┐
│                    Backend (FastAPI 0.138+)                 │
│              Python 3.8+ │ Pydantic Schemas │ RBAC          │
└──────────────────────────────┬──────────────────────────────┘
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
     │ NFPA 72 Engine│   │ Digital Twin │   │ PostgreSQL   │
     │ Spatial / NAC│   │ AutoCAD/Revit│   │ Redis / Qdrant│
     └──────────────┘   └──────────────┘   └──────────────┘
```

### Key Subsystems
- **`fireai/`**: Core NFPA 72 calculation engine and Merkle tree audit ledger
- **`backend/`**: FastAPI web server hosting 247+ endpoints, RBAC, and rate limiters
- **`frontend/`**: Single Page Application with 22 pages built with React 18
- **`facp_distributed/`**: Agent pipeline for Fire Alarm Control Panel network routing
- **`parsers/`**: Multi-format file parsers (DXF, DWG, IFC, PDF, Excel)

---

## 2. Environment Setup Walkthrough

### Step 1: Clone Repository & Create Virtual Environment

```bash
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 2: Install Dependencies

```bash
# Install core + dev dependencies in editable mode
pip install -e ".[dev,parsing]"
```

### Step 3: Configure Local Environment

Copy `.env.example` to `.env` and populate local development keys:

```bash
cp .env.example .env
```

Generate secure ephemeral keys for local testing:

```bash
export FIREAI_API_KEY="dev-api-key-12345"
export FIREAI_SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
```

### Step 4: Run Backend Server

```bash
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Verify backend health by opening `http://127.0.0.1:8000/api/health`.

### Step 5: Run Frontend Development Server

Open a second terminal window:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Go to Settings, enter `dev-api-key-12345`, and log in.

---

## 3. Common Development Tasks

### A. Running Test Suites

```bash
# Run unit tests
pytest

# Run security test suite specifically
pytest tests/test_ssrf_and_security_protocol.py -v

# Run with coverage report
pytest --cov=fireai --cov-report=html
```

### B. Linting & Formatting

```bash
# Run Ruff lint check
python -m ruff check backend/ fireai/

# Auto-fix lint issues
python -m ruff check backend/ fireai/ --fix
```

---

## 4. Engineering Standards & Pull Request Rules

1. **Safety First:** Never alter engineering constants or tolerance bounds in `fireai/constants/nfpa72.py`.
2. **Fail-Fast Secrets:** Never commit hardcoded API keys or secret tokens. Pre-commit hooks (`gitleaks`) run automatically.
3. **Pydantic Validation:** All new route handlers must use strict Pydantic schemas (`extra="forbid"`).

---

## 5. Key Contacts & Support

| Role / Topic | Contact |
|---|---|
| **Lead Architect** | Eng. Ahmed Elbaz (`ahmed@fireai.org`) |
| **Security & Safety Vulnerabilities** | `security@fireai.org` |
| **DevOps & Infrastructure** | `devops@fireai.org` |
