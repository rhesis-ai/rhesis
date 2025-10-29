# Hint: Build this image with an expanded build context
# `docker build -t rhesis-backend -f apps/backend/Dockerfile .`
#
# IMPORTANT: This Dockerfile is optimized for layer caching while ensuring migration files
# are always up-to-date. It copies only __init__.py files before dependency installation,
# then copies ALL source code (including migrations) in a later layer.
#
# For critical deployments, use --no-cache to force a complete rebuild:
# `docker build --no-cache -t rhesis-backend -f apps/backend/Dockerfile .`

# Single stage build for simplicity
# IMPORTANT: The python version must match the version in the .python-version file.
FROM mirror.gcr.io/library/python:3.10.17-slim

WORKDIR /app

# Install OS-level dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpq5 \
    postgresql-client \
    curl \
    git \
    && pip install --no-cache-dir uv \
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
# Add the virtual environment to the PATH. It activates the virtual environment allowing to
# call python from the command line.
ENV PATH="/app/.venv/bin:$PATH"
# Set Python path to find the modules
ENV PYTHONPATH=/app:/app/backend/src
# Copy the SDK directory
COPY sdk /app/sdk/

RUN uv add /app/sdk

# Install backend dependencies (which includes the SDK)
RUN uv sync

# Now copy ALL source code including migrations - this layer will invalidate when any source changes
# This ensures migration files are always up-to-date in the final image
COPY apps/backend/src /app/src

# Copy the migration and startup scripts
COPY apps/backend/migrate.sh /app/migrate.sh
COPY apps/backend/start.sh /app/start.sh

# Remove build dependencies after installing Python packages
# Keep git as it's needed by ragas package at runtime
RUN apt-get purge -y build-essential libpq-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and remove .env files
RUN adduser --disabled-password --gecos '' rhesis-user \
    && find /app -name ".env" -type f -delete \
    && chown -R rhesis-user /app \
    && chmod +x /app/migrate.sh /app/start.sh

# Switch to the non-root user
USER rhesis-user

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8080

# Use the improved startup script
CMD ["/app/start.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1