# Hint: Build this image with an expanded build context
# `docker build -t rhesis-polyphemus -f apps/polyphemus/Dockerfile .`
#
# IMPORTANT: This Dockerfile uses a two-stage build to minimize image size
# and optimize layer caching. The builder stage installs dependencies and
# pre-downloads ML models, while the runtime stage creates a minimal image.
#
# For critical deployments, use --no-cache to force a complete rebuild:
# `docker build --no-cache -t rhesis-polyphemus -f apps/polyphemus/Dockerfile .`

# ============================================================================
# STAGE 1: Builder - Export dependencies for efficient installation
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

# Copy the SDK, Penelope, and backend directories (needed for dependency resolution)
COPY sdk /app/sdk/
COPY penelope /app/penelope/
COPY apps/backend /app/apps/backend/

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' /app/pyproject.toml && \
    sed -i 's|path = "../../penelope"|path = "/app/penelope"|g' /app/pyproject.toml && \
    sed -i 's|path = "../backend"|path = "/app/apps/backend"|g' /app/pyproject.toml

# Export requirements to avoid copying the entire venv (saves disk space)
# This generates a requirements.txt that can be used to install dependencies in runtime
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --no-dev --no-hashes > /tmp/requirements.txt

# Now copy ALL source code - this layer will invalidate when any source changes
COPY apps/polyphemus/src /app/src

# Set default model environment variable (used at runtime)
ARG DEFAULT_MODEL=huggingface/Goekdeniz-Guelmez/Josiefied-Qwen3-8B-abliterated-v1
ENV DEFAULT_MODEL=${DEFAULT_MODEL}

# ============================================================================
# STAGE 2: Runtime - Install dependencies efficiently
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install runtime dependencies and build tools (needed for compiling native extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app && \
    chown appuser:appuser /app

# Copy requirements file from builder (tiny file, not the entire venv)
COPY --from=builder /tmp/requirements.txt /app/requirements.txt

# Create virtual environment and install dependencies using uv
# This is much more space-efficient than copying the entire venv
ENV VIRTUAL_ENV=/app/.venv
RUN python -m venv $VIRTUAL_ENV

# Use only system Python provided by the base image
ENV UV_NO_MANAGED_PYTHON=1
# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1

# Install dependencies using pip (uv pip requires project context, so use regular pip)
# Use cache mount for faster builds and install into the venv
RUN --mount=type=cache,target=/root/.cache/pip \
    . $VIRTUAL_ENV/bin/activate && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    chown -R appuser:appuser /app/.venv

# Copy source code and dependencies with proper ownership
COPY --from=builder --chown=appuser:appuser /app/src /app/src
COPY --from=builder --chown=appuser:appuser /app/sdk /app/sdk
COPY --from=builder --chown=appuser:appuser /app/penelope /app/penelope
COPY --from=builder --chown=appuser:appuser /app/apps/backend /app/apps/backend

# Create model cache directory (model will be downloaded on first startup)
# Cloud Run instances have persistent local storage, so the model will be cached
RUN mkdir -p /app/model_cache && chown -R appuser:appuser /app/model_cache

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