# ═══════════════════════════════════════════════════════════════════════════
# FireAI — Safety-Critical Fire Protection Digital Twin
# Multi-stage Docker build: Frontend (Node) + Python deps + Runtime
# ═══════════════════════════════════════════════════════════════════════════

# ─── Stage 1: Build the React frontend (Vite) ─────────────────────────────
# V206 FIX: The frontend MUST be built and served by the FastAPI app on
# HuggingFace Spaces. Without this stage, the HF Space URL returns 404 for /
# because there is no static file server — only the FastAPI backend runs.
# NOTE (self-critique C2): changed from node:26-slim (doesn't exist) to node:22-slim
# matching .nvmrc. Node 22 is the active LTS (Oct 2024 – Apr 2027).
FROM node:22-slim AS frontend-builder

WORKDIR /build

# Copy package files first to leverage Docker layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --prefer-offline --ignore-scripts 2>&1 | tail -5

# Copy the rest of the frontend source and build
COPY frontend/ ./
# Set the production API URL — same-origin since backend serves frontend
ENV VITE_API_URL=/api/v1
# NOTE (audit P1-6 fix): Aligned with package.json version 1.56.0.
# Was previously 8.1.0 which caused monitoring/debugging confusion.
ENV VITE_APP_VERSION=1.56.0
RUN npm run build

# Verify the build output exists
RUN ls -la dist/ && test -f dist/index.html


# ─── Stage 2: Python Dependencies ─────────────────────────────────────────
# P0-10 FIX: unified on python:3.12-slim — matches deploy/docker/Dockerfile.api
# and Dockerfile.worker (3.14 drifted and broke --only-binary wheel parity).
# Issue #366 FIX (Option B): pin to python:3.12.14-slim-bookworm instead of the
# rolling python:3.12-slim tag. The base image's bundled pip/setuptools/wheel
# rotate as Python's Docker library ships new patch tags; pinning to a specific
# patch makes builds reproducible AND picks up the latest upstream security
# fixes (CVE-2026-8643 pip, CVE-2025-47273 setuptools, etc.).
FROM python:3.12.14-slim-bookworm AS python-builder

WORKDIR /build

# V140 FIX: Install setuptools + wheel BEFORE pip install — required by
# pyproject.toml build-system (setuptools.build_meta backend). Without this,
# pip fails with "Cannot import 'setuptools.build_meta'" when installing
# packages that use PEP 517 builds.
RUN pip install --no-cache-dir --upgrade pip
# P0-14c FIX: install setuptools+wheel into /install (NOT the builder's default
# /usr/local). The runtime stage only `COPY --from=python-builder /install /usr/local`,
# so anything installed to the builder's /usr/local is DISCARDED. Previously this
# bootstrap ran without --prefix, leaving the runtime image with the base
# python:3.12-slim setuptools (vulnerable → CVE-2025-47273 / CVE-2026-59890),
# which Trivy flags and fails the pipeline. With --prefix=/install the upgraded
# setuptools (>=78.1.1) is copied into runtime and overwrites the base version.
RUN pip install --no-cache-dir --prefix=/install "setuptools>=78.1.1" wheel # NOSONAR:S8541,S8544 — pip/setuptools/wheel bootstrap; --prefix=/install so the upgraded setuptools is copied into the runtime image (fixes CVE-2025-47273 / CVE-2026-59890)

COPY requirements.txt .
RUN pip install --no-cache-dir --ignore-installed --only-binary :all: --prefix=/install -r requirements.txt # NOSONAR:S8544 — requirements.txt pins all versions

# ─── Stage 3: Runtime ─────────────────────────────────────────────────────
# Issue #366 FIX (Option B): pin to python:3.12.14-slim-bookworm to match the
# builder stage and pick up the latest upstream security fixes.
FROM python:3.12.14-slim-bookworm

LABEL maintainer="FireAI Engineering Team"
LABEL description="Safety-Critical Fire Protection Digital Twin — NFPA 72-2022"
LABEL version="1.0.0"

# V214: Install LibreDWG (dwg2dxf binary) for real DWG→DXF conversion.
# Without this, dwg_converter.py falls back to a mock that writes an
# entity-empty DXF file (with an explicit warning). Installing libredwg-tools
# enables real DWG parsing in Docker/Linux deployments without AutoCAD.
# apt-get clean + rm -rf /var/lib/apt/lists/* keeps the image small.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libredwg-tools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dwg2dxf --version 2>&1 | head -1 || echo "dwg2dxf installed (version check non-fatal)"

RUN groupadd -r fireai && \
    useradd -r -g fireai -d /app -s /sbin/nologin -c "FireAI Service" fireai

WORKDIR /app

# P0-14d FIX: purge the BASE image's stale setuptools BEFORE the /install overlay
# is copied. python:3.12-slim ships setuptools <78.1.1 in /usr/local, which carries
# CVE-2025-47273 (HIGH, fixed in 78.1.1). `COPY --from=python-builder /install
# /usr/local` only MERGES the upgraded dist-info NEXT TO the vulnerable base one,
# so Trivy still flags the old dist-info and the container gate fails (all runs
# after the Trivy DB recorded this advisory). Deleting the base remnants here
# means the overlay brings in exactly one, clean setuptools (>=78.1.1).
# Issue #366 FIX (Option A, hardened): the original rm only matched
# setuptools / setuptools-*.dist-info / pkg_resources at /usr/local/lib/python3.12/site-packages.
# Trivy was STILL reporting setuptools 70.3.0 after this step (per the SARIF uploaded
# from the 2026-08-14 main run), suggesting leftover dist-info somewhere in the
# scan path (TRIVY_PYTHON_PACKAGES_DIR=/usr/local/lib/python3.12/site-packages).
# The `find`-based purge below catches EVERY setuptools-* and pkg_resources across
# all site-packages locations — including any stragglers from older image layers
# that the simple `rm -rf` glob missed (e.g. partial dist-info dirs left by pip
# upgrade downgrades, or duplicated setuptools-* dirs from base image history).
RUN find /usr/local/lib -type d -name 'setuptools*' -prune -exec rm -rf {} + && \
    find /usr/local/lib -type d -name 'pkg_resources' -exec rm -rf {} + && \
    find /usr/local/lib -type d -name 'msgpack*.dist-info' -exec rm -rf {} + && \
    find /usr/local/lib -type d -name 'msgpack' -path '*/site-packages/msgpack' -exec rm -rf {} +

# Copy installed Python packages
COPY --from=python-builder /install /usr/local

# Issue #366 FIX (Option A — runtime-stage enforcement): even with the find-purge
# above + COPY overlay, Trivy was still detecting setuptools 70.3.0 and msgpack 1.1.2
# in the runtime image (per the SARIF uploaded from commit afaab6b9, 2026-08-14).
# Root cause is suspected to be the COPY overlay merging the upgraded dist-info
# NEXT TO the base image's stale dist-info — Trivy scans the dist-info dir names
# and reports the version it finds there, regardless of which one Python actually
# imports at runtime.
# The reliable fix is to REINSTALL setuptools + msgpack + pip directly in the
# runtime stage (NOT via the /install prefix). This creates a single, clean
# dist-info per package in /usr/local/lib/python3.12/site-packages/, overwriting
# any stale version. The versions are pinned to:
#   - setuptools >=83.0.0 → fixes CVE-2025-47273 (HIGH, fix 78.1.1) AND
#                          CVE-2026-59890 (MEDIUM, fix 83.0.0)
#   - msgpack     >=1.2.1  → fixes GHSA-6v7p-g79w-8964 (HIGH, fix 1.2.1)
#   - pip         >=26.1.2 → fixes CVE-2026-8643 (HIGH, fix 26.1.2) and friends
# --force-reinstall ensures pip overwrites — not skips — the existing install.
RUN pip install --no-cache-dir --upgrade --force-reinstall \
    "setuptools>=83.0.0,<86.0.0" \
    "msgpack>=1.2.1,<2.0.0" \
    "pip>=26.1.2"

# Issue #366 verification step: print the installed versions so the build log
# (and any future SARIF discrepancy investigation) can confirm Trivy will see
# the fixed versions. This step exits 0 unless the installed version is BELOW the
# required minimum — in which case the build fails fast with a clear error.
# NOTE: The Python script is written to /tmp first and then executed. The previous
# inline `RUN python -c "..."` with bare newlines failed on HF Spaces builder
# because its Docker parser treated `import` (a Python keyword on line 2) as a
# Dockerfile instruction → "unknown instruction: import". Writing to a temp file
# avoids all Dockerfile parse ambiguity and works on every Docker version.
RUN printf '%s\n' \
    'import sys, setuptools, msgpack, pip' \
    'required = {"setuptools": (83,0,0), "msgpack": (1,2,1), "pip": (26,1,2)}' \
    'installed = {' \
    '  "setuptools": tuple(int(p) for p in setuptools.__version__.split(".")[:3]),' \
    '  "msgpack": msgpack.version[:3] if isinstance(msgpack.version, tuple) else tuple(int(p) for p in msgpack.version.split(".")[:3]),' \
    '  "pip": tuple(int(p) for p in pip.__version__.split(".")[:3]),' \
    '}' \
    'for pkg, req in required.items():' \
    '    inst = installed[pkg]' \
    '    status = "OK" if inst >= req else "FAIL"' \
    '    print(f"{pkg}: installed={inst} required>={req} -> {status}")' \
    '    if inst < req:' \
    '        print(f"ERROR: {pkg} {inst} < required {req} — Trivy will flag CVEs", file=sys.stderr)' \
    '        sys.exit(1)' \
    'print("All required versions satisfied.")' \
    > /tmp/verify_versions.py && \
    python /tmp/verify_versions.py && \
    rm /tmp/verify_versions.py

# Copy application code (only what's needed for production)
COPY --chown=fireai:fireai backend/ backend/
COPY --chown=fireai:fireai fireai/ fireai/
COPY --chown=fireai:fireai parsers/ parsers/
COPY --chown=fireai:fireai integration/ integration/
COPY --chown=fireai:fireai pyproject.toml ./
COPY --chown=fireai:fireai qomn_conduit/ qomn_conduit/
COPY --chown=fireai:fireai qomn_fire/ qomn_fire/
COPY --chown=fireai:fireai facp_system/ facp_system/
COPY --chown=fireai:fireai core/ core/
COPY --chown=fireai:fireai marine/ marine/
COPY --chown=fireai:fireai adapters/ adapters/

# P0-12 FIX: ship Alembic migrations so `alembic upgrade head` can run
# at container start (see CMD below). Previously alembic.ini + alembic/
# were never copied into the image.
COPY --chown=fireai:fireai alembic.ini ./
COPY --chown=fireai:fireai alembic/ alembic/

# V206: Copy the built frontend (from Stage 1) — served at / by FastAPI StaticFiles
# when BAZSPARK_FRONTEND_DIST is set (see backend/app.py).
COPY --chown=fireai:fireai --from=frontend-builder /build/dist /app/frontend_dist

# Create data, logs, and db directories.
# V174 FIX: /app/db MUST be pre-created and owned by fireai. backend/api_keys.py
# line 648 calls _ensure_default_admin_key() at MODULE LOAD TIME; when
# FIREAI_API_KEY is set (production + CI Gate 6), this calls add_api_key() →
# _save_keys() → path.parent.mkdir(parents=True, exist_ok=True) on the
# KEYS_FILE directory (default "db/api_keys.json" → /app/db). Without this
# pre-created directory, the fireai user (non-root) cannot mkdir under /app
# (owned by root) and the container crashes with:
#   PermissionError: [Errno 13] Permission denied: 'db'
# This was the root cause of CI Gate 6 failures (runs #741–#748+).
# Pre-creating /app/db aligns with the existing pattern for /app/data and
# /app/logs, and requires NO application code change.
RUN mkdir -p /app/data /app/logs /app/db && \
    chown -R fireai:fireai /app/data /app/logs /app/db /app/frontend_dist

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FIREAI_ENV=production \
    LOG_LEVEL=WARNING \
    UDM_DB_PATH=/app/data/udm_elements.db \
    BAZSPARK_FRONTEND_DIST=/app/frontend_dist
# DATABASE_URL is intentionally NOT set here — it comes from the Hugging Face Space secret.
# This allows the container to use the Supabase PostgreSQL instance.
# Fallback: if no secret is provided, the app uses the DIGITAL_TWIN_DB_PATH SQLite file.
# CRITICAL-3: Unified DB path — DATABASE_URL is now the single source of truth.
# Removed DIGITAL_TWIN_DB_PATH (was unused, caused confusion).
# V206: BAZSPARK_FRONTEND_DIST points to the built frontend so backend/app.py
# mounts StaticFiles and serves the SPA at / (see _spa_fallback in app.py).

USER fireai

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health')" || exit 1

# C-2 FIX: Default to 1 worker for SQLite (WAL mode allows concurrent reads
# but concurrent writes from multiple processes risk SQLITE_BUSY/data corruption).
# For multi-worker deployments, use PostgreSQL via deploy/docker/docker-compose.yml
#
# H-3 FIX: Bind to 0.0.0.0 for external routing (required by cloud hosting like HF Spaces).
# P0-12 FIX: run `alembic upgrade head` before uvicorn — schema migrations
# now apply on every container start (idempotent), so a fresh deploy cannot
# boot against a stale DB schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-7860} --workers ${UVICORN_WORKERS:-1}"]
