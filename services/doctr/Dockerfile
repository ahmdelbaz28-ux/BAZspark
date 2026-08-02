#!/usr/bin/env bash
# NOSONAR
# services/doctr/Dockerfile â€” DocTR OCR Service for FireAI
# Provides OCR with bounding boxes for scanned floor plans.
# Runs as a separate Docker container â€” no AGPL contamination.
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for OpenCV + DocTR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary :all: -r requirements.txt # NOSONAR: docker:S8544 — requirements.txt pins all versions

# V248 FIX: Resolved git merge conflict. Kept the non-root user + .dockerignore
# approach (Updated upstream) which is more secure. The "Stashed changes"
# version (COPY main.py .) is redundant since COPY . . already includes main.py.
# Explicit copy of required files only (S6470 fix â€” avoid recursive COPY)
COPY requirements.txt ./
COPY main.py ./
COPY doctr/ ./doctr/
# Create non-root user for security (S6471)
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
