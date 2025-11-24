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
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for modern dependency management
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy SDK directory first (required dependency for rhesis.sdk imports)
# Build context is repo root, SDK is at sdk/
COPY sdk /app/sdk/

# Copy polyphemus source code and pyproject.toml
# Build context is repo root, so paths are relative to that
COPY apps/polyphemus /app/apps/polyphemus/

# Set up the source structure to match the package layout
# Create a proper namespace package (no __init__.py in rhesis to allow namespace sharing)
RUN mkdir -p /app/src/rhesis && \
    cp -r /app/apps/polyphemus/src/rhesis/polyphemus /app/src/rhesis/ && \
    cp -r /app/sdk/src/rhesis/sdk /app/src/rhesis/

# Create virtual environment first (matching rh script: uv venv)
RUN uv venv

# Add the virtual environment to the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1
# Use only system Python provided by the base image
ENV UV_NO_MANAGED_PYTHON=1
# Skip the installation of the dev dependencies
ENV UV_NO_DEV=1

# Install SDK first in editable mode with huggingface extras (matching rh script: uv pip install -e sdk)
RUN uv pip install -e /app/sdk[huggingface]

# Install polyphemus in editable mode (matching rh script: uv pip install -e apps/polyphemus)
RUN cd /app && uv pip install -e apps/polyphemus

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