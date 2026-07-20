# ═══════════════════════════════════════════════════════════════════════════
# BAZSPARK FireAI — Development Container Image
# ═══════════════════════════════════════════════════════════════════════════
# Mirrors the production Dockerfile runtime (Python 3.12 + Node 20) so the
# devbox behaves identically to HF Spaces. Adds dev-only tooling:
#   - PostgreSQL 15 + Redis 7 (local parity with Supabase + cache layer)
#   - Playwright system deps (Chromium / Firefox / WebKit)
#   - ruff, mypy, bandit, pip-audit, pytest, uv
#   - git, gh CLI, jq, curl, ripgrep, fd-find
# Aligns with: .nvmrc (Node 20) and pyproject.toml (Python >=3.12).
# ═══════════════════════════════════════════════════════════════════════════

FROM mcr.microsoft.com/devcontainers/python:3.12

# ── OS deps: Postgres client, Redis, Playwright browsers deps, build tools ──
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git gnupg jq libasound2 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 fd-find build-essential lsb-release postgresql-client \
        redis-tools libnss3 libnspr4 libpango-1.0-0 libcairo2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libatspi2.0-0 libxshmfence1 \
        fonts-noto-cjk fonts-noto-color-emoji ripgrep \
    && rm -rf /var/lib/apt/lists/*

# ── Node 20 (via features) + global CLI tools ─────────────────────────────
# Node itself is installed by the `node` feature; we only add CLIs here.
RUN npm install -g --no-audit --no-fund \
        @biomejs/biome eslint prettier \
        npm@latest pnpm@latest typescript@latest vitest yarn \
        @playwright/test

# ── Python dev tools (kept separate from runtime requirements.txt) ────────
RUN pip install --no-cache-dir --upgrade pip setuptools>=68 wheel && \
    pip install --no-cache-dir \
        bandit[toml]==1.7.10 httpx==0.27.2 ipython==8.27.0 mypy==1.11.2 \
        pip-audit==2.7.3 pipx pytest==8.3.3 pytest-asyncio==0.24.0 pytest-cov==5.0.0 \
        pytest-timeout==2.3.1 ruff==0.6.9 uv==0.4.18

# ── Non-root dev user (matches common-utils feature) ─────────────────────
ARG USERNAME=devuser
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid $USER_GID $USERNAME 2>/dev/null || true && \
    useradd  --uid $USER_UID --gid $USER_GID -m $USERNAME 2>/dev/null || true && \
    mkdir -p /workspace /home/$USERNAME/.cache /home/$USERNAME/.local && \
    chown -R $USER_UID:$USER_GID /workspace /home/$USERNAME

USER $USERNAME

# ── Default working directory ─────────────────────────────────────────────
WORKDIR /workspace

# ── Shell prompt marker (so devbox feels distinct from prod) ──────────────
ENV FIREAI_DEVBOX=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
