# Hint: Build this image with an expanded build context
# `docker build -t rhesis-worker -f apps/worker/Dockerfile .`

# Use Python 3.10 base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install system dependencies including PostgreSQL client and uv
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    curl \
    jq \
    gcc \
    && pip install --no-cache-dir uv \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK directory
COPY sdk /app/sdk/

# Copy backend directory
COPY apps/backend /app/backend/

# Copy Celery worker requirements
COPY apps/worker/requirements.txt /app/requirements.txt

# Copy health check server
COPY apps/worker/health_server.py /app/health_server.py

# Install dependencies with uv using --system flag
RUN uv pip install --system -r /app/requirements.txt && \
    uv pip install --system -e /app/sdk && \
    uv pip install --system -e /app/backend

# Set Python path to find the modules
ENV PYTHONPATH=/app

# Create directory for Celery logs
RUN mkdir -p /var/log/celery

# Create non-root user
RUN useradd -m celery_user && \
    chown -R celery_user:celery_user /app /var/log/celery

# Copy and set permissions for the startup script
COPY apps/worker/start.sh /app/start.sh
RUN chmod +x /app/start.sh
RUN chmod +x /app/health_server.py

# Switch to non-root user
USER celery_user

# Default Celery configuration (can be overridden at runtime)
ENV CELERY_WORKER_CONCURRENCY=8 \
    CELERY_WORKER_PREFETCH_MULTIPLIER=4 \
    CELERY_WORKER_MAX_TASKS_PER_CHILD=1000 \
    CELERY_WORKER_LOGLEVEL=INFO \
    CELERY_WORKER_OPTS="--without-heartbeat --without-gossip"

# Expose port for health check (Google Cloud Run)
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD celery -A rhesis.backend.worker.app inspect ping || exit 1

# Set the startup script as the entry point
CMD ["/app/start.sh"]
