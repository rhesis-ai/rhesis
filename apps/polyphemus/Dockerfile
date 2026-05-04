# Build context MUST be the repository root (parent of apps/), not apps/polyphemus.
#
# From repository root:
#   docker build -t polyphemus:latest -f apps/polyphemus/Dockerfile .
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
FROM python:3.12.8-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

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
ENV UV_NO_MANAGED_PYTHON=1
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy

# Copy the rhesis meta-package and rhesis-backend (the only path-based deps
# polyphemus actually pulls in; rhesis-sdk and rhesis-penelope live in
# rhesis-backend's [all] extra and aren't selected here).
#
# packages/rhesis/pyproject.toml uses [tool.hatch.version] with
# path = "../../sdk/pyproject.toml" to read its version, so we copy that
# single file in (the rest of sdk/ is unused).
COPY packages/rhesis /app/packages/rhesis/
COPY apps/backend /app/apps/backend/
COPY sdk/pyproject.toml /app/sdk/pyproject.toml

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../backend"|path = "/app/apps/backend"|g' /app/pyproject.toml && \
    sed -i 's|path = "../../packages/rhesis"|path = "/app/packages/rhesis"|g' /app/apps/backend/pyproject.toml

# Install dependencies using uv sync
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Now copy ALL source code - this layer will invalidate when any source changes
COPY apps/polyphemus/src /app/src

# ============================================================================
# STAGE 2: Runtime - Create minimal runtime image
# ============================================================================
FROM python:3.12.8-slim AS runtime

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

# Copy source code with proper ownership.
# Only rhesis-backend is editable (its src tree must be on disk at runtime);
# `rhesis` (meta-package) is installed as a non-editable wheel, so its source
# tree is not needed once the venv is built.
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