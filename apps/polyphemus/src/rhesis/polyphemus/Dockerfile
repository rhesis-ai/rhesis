# Start with NVIDIA CUDA base image with more recent CUDA version
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    apt-utils \
    && rm -rf /var/lib/apt/lists/*

# Create and use virtual environment
RUN python3 -m venv $VIRTUAL_ENV

# Create a non-root user to run the app
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install basic build dependencies first (within venv)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir packaging wheel setuptools

# Install uv for modern dependency management
RUN pip install --no-cache-dir uv

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

# Install dependencies using uv with PyTorch CUDA index
# This will install both SDK and Polyphemus dependencies
RUN uv pip install --system --extra-index-url https://download.pytorch.org/whl/cu121 -e .

# Install flash-attn separately with a specific pre-built wheel for CUDA 12.1
# Directly using a compatible wheel URL to avoid compilation
RUN pip install --no-cache-dir "https://github.com/Dao-AILab/flash-attention/releases/download/v2.3.3/flash_attn-2.3.3+cu122torch2.1cxx11abiFALSE-cp310-cp310-linux_x86_64.whl"

# Copy the application code (from build context repo root)
COPY apps/polyphemus/src/rhesis/polyphemus /app/src/rhesis/polyphemus/

# Ensure SDK is in Python path
ENV PYTHONPATH="/app:/app/src:$PYTHONPATH"

# For caching models (optional - can be overridden at runtime)
ENV TRANSFORMERS_CACHE="/app/model_cache"
RUN mkdir -p /app/model_cache && chown -R appuser:appuser /app

# Expose the port the app will run on
EXPOSE 8080

# Switch to non-root user
USER appuser

# Start the FastAPI app using Gunicorn with optimized settings
# Module path is rhesis.polyphemus.main:app (package structure is rhesis.polyphemus)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "3600", "--worker-class", "uvicorn.workers.UvicornWorker", "rhesis.polyphemus.main:app", "--preload"]