# Hint: Build this image with an expanded build context
# `docker build -t rhesis-worker -f apps/worker/Dockerfile .`
#
# IMPORTANT: This Dockerfile uses a two-stage build for optimal layer caching
# and minimal image size.
#
# For critical deployments, use --no-cache to force a complete rebuild:
# `docker build --no-cache -t rhesis-worker -f apps/worker/Dockerfile .`
# The python version must match the version in the .python-version file.
# ============================================================================
# STAGE 1: Builder - Install dependencies and build artifacts
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy Celery worker requirements
COPY apps/worker/pyproject.toml /app/pyproject.toml

# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1
# Use only system Python provided by the base image. It speeds up the build process and limit
# the size of the image.
ENV UV_NO_MANAGED_PYTHON=1

# Skip the installation of the dev dependencies
ENV UV_NO_DEV=1

# Copy the SDK, Penelope, and backend directories
COPY sdk /app/sdk/
COPY penelope /app/penelope/
COPY apps/backend /app/backend/

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' /app/pyproject.toml && \
    sed -i 's|path = "../../penelope"|path = "/app/penelope"|g' /app/pyproject.toml

# Install dependencies
RUN uv sync

# ============================================================================
# STAGE 2: Runtime - Create minimal runtime image
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install only runtime dependencies (no build tools)
# Keep git as it's needed by ragas package at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    jq \
    procps \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and directories
RUN adduser --disabled-password --gecos '' celery-user && \
    mkdir -p /app /var/log/celery && \
    chown celery-user:celery-user /app /var/log/celery

# Copy the virtual environment from builder
COPY --from=builder --chown=celery-user:celery-user /app/.venv /app/.venv

# Copy dependencies from builder
COPY --from=builder --chown=celery-user:celery-user /app/sdk /app/sdk
COPY --from=builder --chown=celery-user:celery-user /app/penelope /app/penelope
COPY --from=builder --chown=celery-user:celery-user /app/backend /app/backend

# Copy worker-specific files with proper ownership and permissions
COPY --chown=celery-user:celery-user --chmod=755 apps/worker/start.sh /app/start.sh
COPY --chown=celery-user:celery-user --chmod=755 apps/worker/health_server.py /app/health_server.py

# Switch to the non-root user
USER celery-user

# Set environment variables for Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONMALLOC=malloc \
    MALLOC_TRIM_THRESHOLD_=100000 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    MALLOC_TOP_PAD_=131072 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app:/app/backend/src \
    CELERY_OPTIMIZATION=fair \
    CELERY_DISABLE_RATE_LIMITS=True \
    CELERY_TASK_ALWAYS_EAGER=False \
    CELERY_TASK_EAGER_PROPAGATES=False

# Default Celery configuration (can be overridden at runtime)
ENV CELERY_WORKER_CONCURRENCY=2 \
    CELERY_WORKER_PREFETCH_MULTIPLIER=1 \
    CELERY_WORKER_MAX_TASKS_PER_CHILD=500 \
    CELERY_WORKER_LOGLEVEL=WARNING \
    CELERY_WORKER_OPTS="--without-gossip --without-mingle --without-heartbeat"

# Expose port for health check (Google Cloud Run)
EXPOSE 8080

# Cloud Run needs an HTTP health check, not a Celery inspect ping
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health/basic || exit 1

CMD ["/app/start.sh"]
