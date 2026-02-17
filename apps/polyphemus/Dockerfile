# Hint: Build this image with an expanded build context
# `docker build -t rhesis-polyphemus -f apps/polyphemus/Dockerfile .`
#
# IMPORTANT: This Dockerfile uses a two-stage build to minimize image size
# and optimize layer caching. The builder stage installs dependencies,
# while the runtime stage creates a minimal image.
#
# Polyphemus is now an API-only service that proxies requests to Vertex AI.
# No local models are loaded - all inference happens on Vertex AI endpoints.

# ============================================================================
# STAGE 1: Builder - Install dependencies
# ============================================================================
FROM python:3.10-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files for polyphemus
COPY apps/polyphemus/pyproject.toml apps/polyphemus/uv.lock ./

# Copy ONLY the minimal Python package structure needed for dependency resolution
RUN mkdir -p /app/src/rhesis/polyphemus
COPY apps/polyphemus/src/rhesis/__init__.py /app/src/rhesis/__init__.py
COPY apps/polyphemus/src/rhesis/polyphemus/__init__.py /app/src/rhesis/polyphemus/__init__.py

# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1
# Use only system Python provided by the base image
ENV UV_NO_MANAGED_PYTHON=1
# Skip the installation of the dev dependencies
ENV UV_NO_DEV=1
# Use copy mode for better cache mount compatibility
ENV UV_LINK_MODE=copy

# Copy the backend directory (needed for auth models)
COPY apps/backend /app/apps/backend/

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../backend"|path = "/app/apps/backend"|g' /app/pyproject.toml

# Install dependencies using uv sync
# Use cache mount for faster builds and install only production dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Now copy ALL source code - this layer will invalidate when any source changes
COPY apps/polyphemus/src /app/src

# ============================================================================
# STAGE 2: Runtime - Create minimal runtime image
# ============================================================================
FROM python:3.10-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app && \
    chown appuser:appuser /app

# Copy the virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy source code and dependencies with proper ownership
COPY --from=builder --chown=appuser:appuser /app/src /app/src
COPY --from=builder --chown=appuser:appuser /app/apps/backend /app/apps/backend

# Clean up any .env files for security
RUN find /app -name ".env" -type f -delete

# Switch to the non-root user
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/src \
    PATH="/app/.venv/bin:$PATH"

# Expose the port the app will run on
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the FastAPI app using Gunicorn with optimized settings
# Module path is rhesis.polyphemus.main:app (package structure is rhesis.polyphemus)
# Increased workers since we're not doing heavy computation locally
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "600", "--worker-class", "uvicorn.workers.UvicornWorker", "rhesis.polyphemus.main:app"]
