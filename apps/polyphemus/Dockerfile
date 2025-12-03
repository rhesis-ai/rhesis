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
# STAGE 1: Builder - Install dependencies and pre-download models
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
# Use cache mount for faster builds and install only production dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-editable

# Now copy ALL source code - this layer will invalidate when any source changes
COPY apps/polyphemus/src /app/src

# Pre-download model during build time
# The model name comes from the DEFAULT_MODEL build argument
# This downloads the model during image build to avoid runtime downloads
ENV TRANSFORMERS_CACHE="/app/model_cache"
ENV HF_HOME="/app/model_cache"
RUN mkdir -p /app/model_cache

# Model name MUST be provided via build argument - no default value
# Format: huggingface/<org>/<model-name>
ARG DEFAULT_MODEL
ENV DEFAULT_MODEL=${DEFAULT_MODEL}

# Pre-download the model during build time
# This uses a Python script to download the model to the cache directory
RUN if [ -n "$DEFAULT_MODEL" ]; then \
        echo "Pre-downloading model: $DEFAULT_MODEL"; \
        python3 -c "import os; from rhesis.sdk.models.factory import get_model; \
model_name = os.environ.get('DEFAULT_MODEL'); \
print(f'Loading model: {model_name}'); \
model = get_model(model_name, auto_loading=False); \
model.load_model(); \
print(f'Model loaded successfully: {model_name}')"; \
    else \
        echo "WARNING: DEFAULT_MODEL not provided, model will be downloaded at runtime"; \
    fi

# Clean up unnecessary files to reduce disk usage before copying to runtime stage
# Remove Python cache files, test files, and documentation to save space
RUN find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyo" -delete 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "doc" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -name "*.md" -type f -delete 2>/dev/null || true && \
    echo "Cleanup completed"

# ============================================================================
# STAGE 2: Runtime - Create minimal runtime image
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS runtime

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app && \
    chown appuser:appuser /app

# Copy the virtual environment from builder (after cleanup)
# Note: This is a large copy operation (several GB with ML dependencies)
# GitHub Actions may appear to hang here, but it's working
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

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
    TRANSFORMERS_CACHE="/app/model_cache" \
    HF_HOME="/app/model_cache" \
    HF_HUB_ENABLE_HF_TRANSFER=1

# Expose the port the app will run on
EXPOSE 8080

# Start the FastAPI app using Gunicorn with optimized settings
# Module path is rhesis.polyphemus.main:app (package structure is rhesis.polyphemus)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "3600", "--worker-class", "uvicorn.workers.UvicornWorker", "rhesis.polyphemus.main:app", "--preload"]