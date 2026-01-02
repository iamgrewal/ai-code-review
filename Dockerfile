# =============================================================================
# Multi-stage Dockerfile for CortexReview Platform
# Supports two targets: api (FastAPI) and worker (Celery)
# =============================================================================

# -----------------------------------------------------------------------------
# Base stage: Shared dependencies and Python environment
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs


# -----------------------------------------------------------------------------
# API target: FastAPI application (webhook endpoints)
# -----------------------------------------------------------------------------
FROM base AS api

# Expose FastAPI port (default from main.py: 3008)
EXPOSE 3008

# Health check for API container
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:3008/docs', timeout=5)" || exit 1

# Run FastAPI application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3008", "--workers", "1", "--no-access-log"]


# -----------------------------------------------------------------------------
# Worker target: Celery worker for async task processing
# -----------------------------------------------------------------------------
FROM base AS worker

# Install celery beat support (for scheduled tasks)
RUN pip install --no-cache-dir celery[beat,scheduler]

# Health check for worker container (checks Celery worker responsiveness)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD celery -A celery_app inspect ping || exit 1

# Run Celery worker with queues for code_review, indexing, and feedback
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=4", "-Q", "code_review,indexing,feedback,default"]


# -----------------------------------------------------------------------------
# Default target (backward compatibility - runs API)
# -----------------------------------------------------------------------------
FROM api
