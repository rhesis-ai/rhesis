# syntax=docker/dockerfile:1
#
# Multi-stage build for the chatbot service. Repository root is the build context.
#
#   docker build -t rhesis-chatbot -f apps/chatbot/Dockerfile .
#
# For a clean build: add --no-cache --pull as needed.

# =============================================================================
# build: Python builder with uv and all build dependencies
# =============================================================================
FROM mirror.gcr.io/library/python:3.12-slim AS build
COPY --from=mirror.gcr.io/astral/uv:0.11.19 /uv /uvx /bin/

# Match monorepo layout so [tool.uv.sources] path deps resolve without rewriting.
WORKDIR /app/apps/chatbot

# Install OS-level build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better layer caching
COPY apps/chatbot/pyproject.toml apps/chatbot/uv.lock ./

# SDK and rhesis meta-package (SDK depends on rhesis[telemetry])
COPY sdk /app/sdk/
COPY packages/rhesis /app/packages/rhesis/
# Hatch force-includes skill refs into the SDK wheel (see sdk/pyproject.toml).
COPY skills/rhesis/references /app/skills/rhesis/references/

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_MANAGED_PYTHON=1 \
    UV_LINK_MODE=copy

# Install dependencies with cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

RUN uv pip uninstall torch

# Copy the rest of the chatbot source
COPY apps/chatbot ./

# =============================================================================
# runtime: Slim production image with only runtime dependencies
# =============================================================================
FROM mirror.gcr.io/library/python:3.12-slim AS runtime

WORKDIR /app/apps/chatbot

# Install only runtime OS dependencies (curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN adduser --disabled-password --gecos '' rhesis-user

# Copy all built artifacts from build stage
COPY --from=build --chown=rhesis-user:rhesis-user /app /app

# Remove any .env files that might have been copied
RUN find /app -name ".env" -type f -delete

USER rhesis-user

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/apps/chatbot \
    PATH="/app/apps/chatbot/.venv/bin:$PATH" \
    PORT=8080 \
    WORKERS=4

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Command to run the FastAPI application with Gunicorn
CMD sh -c "gunicorn --workers ${WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --timeout 120 --graceful-timeout 30 client:app"
