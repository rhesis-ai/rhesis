# Hint: Build this image with an expanded build context
# `docker build -t rhesis-polyphemus -f apps/polyphemus/Dockerfile .`
#
# IMPORTANT: This Dockerfile uses a two-stage build to minimize image size.
# Models are downloaded from GCS at runtime, NOT baked into the image.
#
# For critical deployments, use --no-cache to force a complete rebuild:
# `docker build --no-cache -t rhesis-polyphemus -f apps/polyphemus/Dockerfile .`

# ============================================================================
# STAGE 1: Builder - Install dependencies
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files for polyphemus
COPY apps/polyphemus/pyproject.toml apps/polyphemus/uv.lock ./

# Copy ONLY the minimal Python package structure needed for dependency resolution
# We only need __init__.py files for the package to be recognized
RUN mkdir -p /app/src/rhesis/polyphemus
# Create namespace package __init__.py (polyphemus uses namespace packages like backend/SDK/Penelope)
COPY apps/polyphemus/src/rhesis/__init__.py /app/src/rhesis/__init__.py
COPY apps/polyphemus/src/rhesis/polyphemus/__init__.py /app/src/rhesis/polyphemus/__init__.py

# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1
# Use only system Python provided by the base image
ENV UV_NO_MANAGED_PYTHON=1
# Skip the installation of the dev dependencies
ENV UV_NO_DEV=1

# Copy the SDK, Penelope, and backend directories
COPY sdk /app/sdk/
COPY penelope /app/penelope/
COPY apps/backend /app/apps/backend/

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' /app/pyproject.toml && \
    sed -i 's|path = "../../penelope"|path = "/app/penelope"|g' /app/pyproject.toml && \
    sed -i 's|path = "../backend"|path = "/app/apps/backend"|g' /app/pyproject.toml

# Install dependencies using uv sync
# Install only production dependencies (no cache mount to reduce disk usage)
RUN uv sync --no-dev --no-editable

# Now copy ALL source code - this layer will invalidate when any source changes
COPY apps/polyphemus/src /app/src

# Model configuration (used at runtime, not build time)
# DEFAULT_MODEL tells the app which model to load from GCS at startup
ARG DEFAULT_MODEL
ENV DEFAULT_MODEL=${DEFAULT_MODEL}

# Create empty model cache directory (will be populated from GCS at runtime)
RUN mkdir -p /app/model_cache

# Clean up unnecessary files to reduce disk usage and image size
# This is critical for GitHub Actions runners with limited disk space
# Use conservative cleanup to avoid breaking package installations
RUN echo "🧹 Starting cleanup to reduce image size..." && \
    # Remove Python cache files (safe to delete)
    find /app/.venv -type d -name "__pycache__" -prune -exec rm -rf {} \; 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyo" -delete 2>/dev/null || true && \
    # Remove test directories (safe to delete)
    find /app/.venv -type d -name "tests" -prune -exec rm -rf {} \; 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -prune -exec rm -rf {} \; 2>/dev/null || true && \
    # Remove documentation directories (safe to delete)
    find /app/.venv -type d -name "docs" -prune -exec rm -rf {} \; 2>/dev/null || true && \
    find /app/.venv -name "*.md" -type f -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.rst" -delete 2>/dev/null || true && \
    # Remove example directories (safe to delete)
    find /app/.venv -type d -name "examples" -prune -exec rm -rf {} \; 2>/dev/null || true && \
    echo "✅ Cleanup completed"

# ============================================================================
# STAGE 2: Runtime - Create minimal runtime image
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS runtime

WORKDIR /app

# Install only runtime dependencies (no build tools)
# Minimal dependencies to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/archives/*

# Create non-root user first
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app && \
    chown appuser:appuser /app

# Copy the virtual environment from builder (after cleanup)
# Note: This is a large copy operation (several GB with ML dependencies)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy source code and dependencies with proper ownership
COPY --from=builder --chown=appuser:appuser /app/src /app/src
COPY --from=builder --chown=appuser:appuser /app/sdk /app/sdk
COPY --from=builder --chown=appuser:appuser /app/penelope /app/penelope
COPY --from=builder --chown=appuser:appuser /app/apps/backend /app/apps/backend

# Copy empty model cache directory (will be populated from GCS at runtime)
COPY --from=builder --chown=appuser:appuser /app/model_cache /app/model_cache

# Switch to the non-root user
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/src \
    PATH="/app/.venv/bin:$PATH" \
    TRANSFORMERS_CACHE="/app/model_cache"

# Expose the port the app will run on
EXPOSE 8080

# Start the FastAPI app using Gunicorn with optimized settings
# Module path is rhesis.polyphemus.main:app (package structure is rhesis.polyphemus)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "3600", "--worker-class", "uvicorn.workers.UvicornWorker", "rhesis.polyphemus.main:app", "--preload"]