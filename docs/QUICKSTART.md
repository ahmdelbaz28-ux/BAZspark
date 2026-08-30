# Quick Start Guide

**BAZSpark Platform Execution Setup**

This guide provides step-by-step instructions to initialize, configure, and execute BAZSpark for fire protection engineering analysis.

---

## 1. Environment Prerequisites

Verify your host environment satisfies the minimum runtime requirements before proceeding with installation.

- **Python:** 3.8+ (Python 3.12+ recommended)
- **Node.js:** 22.0.0+ with npm 11+
- **Docker:** 24.0+ (Required for containerized setup)
- **RAM:** 8GB minimum (16GB recommended)

---

## 2. Interactive Setup Wizard (Recommended)

Quickly configure all required cryptographic keys, database endpoints, AI models, and CI/CD secrets using the interactive wizard:

```bash
chmod +x scripts/setup_wizard.sh
./scripts/setup_wizard.sh
```

---

## 3. Fast Setup from Source

Clone the repository and install core backend dependencies in editable mode.

```bash
git clone https://github.com/ahmdelbaz28-ux/BAZspark.git
cd BAZspark
pip install -e ".[dev,parsing]"
```

Generate secure runtime tokens and start the FastAPI server.

```bash
export FIREAI_API_KEY="your-secure-api-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Install frontend dependencies in a separate terminal window and launch Vite.

```bash
cd frontend
npm ci
npm run dev
```

Navigate to `http://localhost:5173`. Open Settings, enter your `FIREAI_API_KEY`, and log in to access the dashboard.

---

## 4. Docker Deployment

Deploy the full application stack using Docker Compose.

```bash
export FIREAI_API_KEY="your-production-key"
export FIREAI_SESSION_SECRET=$(python3 -m backend.session_secret generate | tail -1)
docker-compose up -d
```

Verify service status via the automated health check endpoint.

```bash
curl http://localhost:8000/api/health
```

---

## 5. Executing Your First Analysis

1. Open `http://localhost:5173` and authenticate.
2. Click **New Project** and enter building metadata.
3. Upload your floorplan layout (`.dwg`, `.dxf`, `.ifc`, or `.pdf`).
4. Select jurisdiction (`NFPA 72-2022`) and run spatial compliance analysis.

Inspect generated detector placement heatmaps, NAC voltage drop reports, and signed audit ledgers directly in the dashboard.

---

## 6. API Quick Reference

Check system status and engine module readiness.

```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/health
```

Create a fire alarm project programmatically via REST API.

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"name":"Building A","jurisdiction":"NFPA_72_2022"}'
```

---

## 7. Common Troubleshooting

- **Server Aborts at Boot:** Verify `FIREAI_SESSION_SECRET` is set and at least 43 characters long.
- **CORS Error:** Add your client URL to `CORS_ORIGINS` in `.env`.
- **Database Connection Error:** Verify PostgreSQL credentials or set `DATABASE_URL=sqlite:////app/data/digital_twin.db`.