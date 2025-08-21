# Hint: Build this image with an expanded build context
# `docker build -t rhesis-backend -f apps/backend/Dockerfile .`

# Single stage build for simplicity
FROM python:3.10-slim

WORKDIR /app

# Install OS-level dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpq5 \
    postgresql-client \
    curl \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files for backend
COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/README.md ./

# Copy only the minimal source code needed for your local package metadata
# This ensures uv can install your package without invalidating the layer later
COPY apps/backend/src/rhesis /app/src/rhesis

# Copy the SDK directory
COPY sdk /app/sdk/

# Note: pyproject.toml already has the correct path ../sdk

# Install backend dependencies (which includes the SDK)
RUN uv sync

# Now copy the rest of your source (scripts, modules, etc.)
COPY apps/backend/src /app/src

# Copy the migration and startup scripts
COPY apps/backend/migrate.sh /app/migrate.sh
COPY apps/backend/start.sh /app/start.sh

# Remove build dependencies after installing Python packages
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