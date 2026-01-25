# Hint: Build this image with an expanded build context
# `docker build -t rhesis-backend -f apps/backend/Dockerfile .`
#
# IMPORTANT: This Dockerfile is optimized for layer caching while ensuring migration files
# are always up-to-date. It copies only __init__.py files before dependency installation,
# then copies ALL source code (including migrations) in a later layer.
#
# For critical deployments, use --no-cache to force a complete rebuild:
# `docker build --no-cache -t rhesis-backend -f apps/backend/Dockerfile .`

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
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files for backend
COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/README.md ./

# Copy ONLY the minimal Python package structure needed for dependency resolution
# This prevents migration files from being cached in an early layer
# We only need __init__.py files for the package to be recognized
RUN mkdir -p /app/src/rhesis/backend
COPY apps/backend/src/rhesis/__init__.py /app/src/rhesis/__init__.py
COPY apps/backend/src/rhesis/backend/__init__.py /app/src/rhesis/backend/__init__.py

# Compile bytecode to improve performance
ENV UV_COMPILE_BYTECODE=1
# Use only system Python provided by the base image. It speeds up the build process and limit
# the size of the image.
ENV UV_NO_MANAGED_PYTHON=1

# Use copy mode for linking dependencies (required by the cache)
ENV UV_LINK_MODE=copy
# Skip the installation of the dev dependencies
ENV UV_NO_DEV=1

# Copy the SDK and Penelope directories
COPY sdk /app/sdk/
COPY penelope /app/penelope/

# Fix paths in pyproject.toml to point to the correct locations in Docker
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' /app/pyproject.toml && \
    sed -i 's|path = "../../penelope"|path = "/app/penelope"|g' /app/pyproject.toml

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

# Remove PyTorch to reduce image size (~360MB savings)
# Garak declares torch as a dependency, but our usage (probe enumeration and
# API-based detectors like perspective.Toxicity) doesn't require it at runtime.
# See: apps/backend/src/rhesis/backend/app/services/garak/taxonomy.py
RUN uv pip uninstall torch

# Now copy ALL source code including migrations - this layer will invalidate when any source changes
# This ensures migration files are always up-to-date in the final image
COPY apps/backend/src /app/src

# ============================================================================
# STAGE 2: Runtime - Create minimal runtime image
# ============================================================================
FROM mirror.gcr.io/library/python:3.10.17-slim AS runtime
# Copy Bun from official image (lighter than Node.js, required for bunx to run MCP servers)
COPY --from=oven/bun:latest /usr/local/bin/bun /usr/local/bin/bun
COPY --from=oven/bun:latest /usr/local/bin/bunx /usr/local/bin/bunx
# Create npx wrapper that translates npx flags to bunx flags
# This ensures compatibility when users/code use npx syntax
RUN printf '#!/bin/sh\n\
# Wrapper to translate npx flags to bunx flags\n\
args=""\n\
for arg in "$@"; do\n\
  case "$arg" in\n\
    -y|--yes)\n\
      # Skip -y flag, bunx does not need it\n\
      ;;\n\
    *)\n\
      args="$args $arg"\n\
      ;;\n\
  esac\n\
done\n\
exec bunx --silent $args\n' > /usr/local/bin/npx && chmod +x /usr/local/bin/npx

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*


# Create non-root user first
RUN adduser --disabled-password --gecos '' rhesis-user && \
    mkdir -p /app && \
    chown rhesis-user:rhesis-user /app

# Copy the virtual environment from builder
COPY --from=builder --chown=rhesis-user:rhesis-user /app/.venv /app/.venv

# Copy source code and scripts with proper ownership and permissions
COPY --from=builder --chown=rhesis-user:rhesis-user /app/src /app/src
COPY --from=builder --chown=rhesis-user:rhesis-user /app/sdk /app/sdk
COPY --from=builder --chown=rhesis-user:rhesis-user /app/penelope /app/penelope
COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/backend/migrate.sh /app/migrate.sh
COPY --chown=rhesis-user:rhesis-user --chmod=755 apps/backend/start.sh /app/start.sh

# Remove .env files
RUN find /app -name ".env" -type f -delete

# Switch to the non-root user
USER rhesis-user

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/usr/local/bin:/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8080

# Use the improved startup script
CMD ["/app/start.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
