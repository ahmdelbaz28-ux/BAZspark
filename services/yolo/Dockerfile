#!/usr/bin/env bash
# NOSONAR
# services/yolo/Dockerfile — YOLO Layout Segmentation Service for FireAI
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# V248 FIX: Resolved git merge conflict. Kept the non-root user + .dockerignore
# approach (Updated upstream) which is more secure. The "Stashed changes"
# version (COPY main.py .) is redundant since COPY . . already includes main.py.
# Explicit copy of required files only (S6470 fix — avoid recursive COPY)
COPY requirements.txt ./
COPY main.py ./
COPY yolo/ ./yolo/
# Create non-root user for security (S6471)
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
