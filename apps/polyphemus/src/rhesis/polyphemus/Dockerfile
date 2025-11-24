# Use standard Python base image (CUDA runtime provided by Cloud Run GPU environment)
# The SDK will install torch with appropriate CUDA support
FROM mirror.gcr.io/library/python:3.10.17-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app:/app/src

# Install OS-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for modern dependency management
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy pyproject.toml first for better caching
# Build context is repo root, so pyproject.toml is at apps/polyphemus/
COPY apps/polyphemus/pyproject.toml apps/polyphemus/uv.lock* ./

# Copy SDK directory (required dependency for rhesis.sdk imports)
# Build context is repo root, SDK is at sdk/
COPY sdk /app/sdk/

# Copy ONLY the minimal Python package structure needed for dependency resolution
# This prevents source code changes from invalidating the dependency cache
RUN mkdir -p /app/src/rhesis/polyphemus
# Create __init__.py files if they don't exist (package structure)
RUN touch /app/src/rhesis/__init__.py || true
COPY apps/polyphemus/src/rhesis/polyphemus/__init__.py /app/src/rhesis/polyphemus/__init__.py

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' /app/pyproject.toml || true

# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1
# Use only system Python provided by the base image
ENV UV_NO_MANAGED_PYTHON=1
# Skip the installation of the dev dependencies
ENV UV_NO_DEV=1

# Install dependencies using uv
# The SDK (rhesis-sdk[huggingface]) will install torch with appropriate CUDA support
RUN uv sync

# Copy the application code (from build context repo root)
COPY apps/polyphemus/src/rhesis/polyphemus /app/src/rhesis/polyphemus/

# For caching models (optional - can be overridden at runtime)
ENV TRANSFORMERS_CACHE="/app/model_cache"
RUN mkdir -p /app/model_cache

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

# Expose the port the app will run on
EXPOSE 8080

# Switch to non-root user
USER appuser

# Start the FastAPI app using Gunicorn with optimized settings
# Module path is rhesis.polyphemus.main:app (package structure is rhesis.polyphemus)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "3600", "--worker-class", "uvicorn.workers.UvicornWorker", "rhesis.polyphemus.main:app", "--preload"]