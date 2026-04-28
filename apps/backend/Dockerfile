# syntax=docker/dockerfile:1
#
# Unified backend + worker + migrate images (multi-stage). Repository root is the build context.
#
#   docker build --target backend  -t rhesis-backend:latest  -f apps/backend/Dockerfile .
#   docker build --target worker   -t rhesis-worker:latest   -f apps/backend/Dockerfile .
#   docker build --target migrate  -t rhesis-migrate:latest   -f apps/backend/Dockerfile .
#
# For a clean build: add --no-cache --pull as needed.

# =============================================================================
# base-build: shared Python builder + Rust + uv + monorepo libs
# =============================================================================
FROM mirror.gcr.io/library/python:3.12.8-slim AS base-build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    build-essential \
    libpq-dev \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ENV PATH="/root/.cargo/bin:$PATH"

COPY sdk /app/sdk/
COPY penelope /app/penelope/
COPY packages/rhesis /app/packages/rhesis/

# =============================================================================
# build-core: core-only venv (migrations / slim jobs) — no rhesis-sdk / torch
# =============================================================================
FROM base-build AS build-core

# Match monorepo layout so [tool.uv.sources] path deps resolve without rewriting.
WORKDIR /app/apps/backend

COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/README.md ./

RUN mkdir -p src/rhesis/backend
COPY apps/backend/src/rhesis/__init__.py src/rhesis/__init__.py
COPY apps/backend/src/rhesis/backend/__init__.py src/rhesis/backend/__init__.py

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_MANAGED_PYTHON=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cargo/registry \
    uv sync

COPY apps/backend/src ./src

# =============================================================================
# build-backend: full backend venv (API + worker)
# =============================================================================
FROM base-build AS build-backend

WORKDIR /app/apps/backend

COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/README.md ./

RUN mkdir -p src/rhesis/backend
COPY apps/backend/src/rhesis/__init__.py src/rhesis/__init__.py
COPY apps/backend/src/rhesis/backend/__init__.py src/rhesis/backend/__init__.py

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_MANAGED_PYTHON=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cargo/registry \
    uv sync --extra all --extra cpu

RUN uv pip uninstall torch

COPY apps/backend/src ./src

# =============================================================================
# base-runtime: shared slim runtime + uv + rhesis-user + full backend payload
# =============================================================================
FROM mirror.gcr.io/library/python:3.12.8-slim AS base-runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app/apps/backend

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    libpq5 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN adduser --disabled-password --gecos '' rhesis-user && \
    chown rhesis-user:rhesis-user /app

COPY --from=build-backend --chown=rhesis-user:rhesis-user /app/apps/backend/.venv .venv
COPY --from=build-backend --chown=rhesis-user:rhesis-user /app/apps/backend/src src
COPY --from=build-backend --chown=rhesis-user:rhesis-user /app/sdk /app/sdk
COPY --from=build-backend --chown=rhesis-user:rhesis-user /app/penelope /app/penelope
COPY --from=build-backend --chown=rhesis-user:rhesis-user /app/packages/rhesis /app/packages/rhesis
COPY --from=build-backend --chown=rhesis-user:rhesis-user /app/apps/backend/pyproject.toml pyproject.toml

RUN find /app -name ".env" -type f -delete

EXPOSE 8080

# =============================================================================
# migrate: core-only venv + Alembic (Cloud Run migration job)
# =============================================================================
FROM mirror.gcr.io/library/python:3.12.8-slim AS migrate
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app/apps/backend

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    libpq5 \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN adduser --disabled-password --gecos '' rhesis-user && \
    chown rhesis-user:rhesis-user /app

COPY --from=build-core --chown=rhesis-user:rhesis-user /app/apps/backend/.venv .venv
COPY --from=build-core --chown=rhesis-user:rhesis-user /app/apps/backend/src src
COPY --from=build-core --chown=rhesis-user:rhesis-user /app/packages/rhesis /app/packages/rhesis
COPY --from=build-core --chown=rhesis-user:rhesis-user /app/apps/backend/pyproject.toml pyproject.toml

RUN find /app -name ".env" -type f -delete

COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/backend/migrate.sh ./migrate.sh

USER rhesis-user

ENV PYTHONPATH=/app/apps/backend/src \
    PATH="/app/apps/backend/.venv/bin:$PATH"

CMD ["./migrate.sh"]

# =============================================================================
# backend: Bun/npx, postgresql-client, FastAPI entrypoint
# =============================================================================
FROM base-runtime AS backend

COPY --from=oven/bun:latest /usr/local/bin/bun /usr/local/bin/bun
COPY --from=oven/bun:latest /usr/local/bin/bunx /usr/local/bin/bunx

RUN printf '#!/bin/sh\n\
args=""\n\
for arg in "$@"; do\n\
  case "$arg" in\n\
    -y|--yes)\n\
      ;;\n\
    *)\n\
      args="$args $arg"\n\
      ;;\n\
  esac\n\
done\n\
exec bunx --silent $args\n' > /usr/local/bin/npx && chmod +x /usr/local/bin/npx

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/backend/migrate.sh ./migrate.sh
COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/backend/start.sh ./start.sh

USER rhesis-user

ENV RHESIS_BACKEND_CONTAINER=1 \
    PYTHONPATH=/app/apps/backend/src \
    PATH="/usr/local/bin:/app/apps/backend/.venv/bin:$PATH"

CMD ["./start.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# =============================================================================
# worker: jq/procps, Celery entrypoint
# =============================================================================
FROM base-runtime AS worker

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    jq \
    procps \
    ncdu \
    && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/log/celery && \
    chown rhesis-user:rhesis-user /var/log/celery

COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/worker/start.sh /app/start.sh
COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/worker/health_server.py /app/health_server.py

USER rhesis-user

ENV PYTHONHASHSEED=0 \
    PYTHONMALLOC=malloc \
    MALLOC_TRIM_THRESHOLD_=100000 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    MALLOC_TOP_PAD_=131072 \
    PATH="/app/apps/backend/.venv/bin:$PATH" \
    PYTHONPATH=/app/apps/backend/src \
    CELERY_OPTIMIZATION=fair \
    CELERY_DISABLE_RATE_LIMITS=True \
    CELERY_TASK_ALWAYS_EAGER=False \
    CELERY_TASK_EAGER_PROPAGATES=False \
    CELERY_WORKER_CONCURRENCY=2 \
    CELERY_WORKER_PREFETCH_MULTIPLIER=1 \
    CELERY_WORKER_LOGLEVEL=WARNING \
    CELERY_WORKER_OPTS="--without-gossip --without-mingle --without-heartbeat"

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health/basic || exit 1

CMD ["/app/start.sh"]
