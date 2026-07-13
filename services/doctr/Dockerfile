#!/usr/bin/env bash
# NOSONAR
# services/doctr/Dockerfile — DocTR OCR Service for FireAI
# Provides OCR with bounding boxes for scanned floor plans.
# Runs as a separate Docker container — no AGPL contamination.
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for OpenCV + DocTR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# V248 FIX: Resolved git merge conflict. Kept the non-root user + .dockerignore
# approach (Updated upstream) which is more secure. The "Stashed changes"
# version (COPY main.py .) is redundant since COPY . . already includes main.py.
# S6470 fix: .dockerignore (added in this commit) filters secrets/VCS/caches
# so the recursive copy is safe.
# NOSONAR — S6470: recursive COPY is safe because .dockerignore excludes
# .git, .env, *.md, secrets, caches, tests, etc. (see services/doctr/.dockerignore).
COPY . .
# Create non-root user for security (S6471)
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
