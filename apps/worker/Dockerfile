# Hint: Build this image with an expanded build context
# `docker build -t rhesis-worker -f apps/worker/Dockerfile .`

# Use Python 3.10.17 base image
# IMPORTANT: The python version must match the version in the .python-version file.
FROM mirror.gcr.io/library/python:3.10.17-slim

# Set environment variables for Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONMALLOC=malloc \
    MALLOC_TRIM_THRESHOLD_=100000 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    MALLOC_TOP_PAD_=131072

# Set working directory
WORKDIR /app

# Install system dependencies including PostgreSQL client and uv
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    curl \
    jq \
    gcc \
    g++ \
    procps \
    git \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK directory
COPY sdk /app/sdk/

# Copy backend directory
COPY apps/backend /app/backend/

# Copy Celery worker requirements
COPY apps/worker/pyproject.toml /app/pyproject.toml

# Copy health check server
COPY apps/worker/health_server.py /app/health_server.py

# Create directory for Celery logs
RUN mkdir -p /var/log/celery

# Create non-root user
RUN useradd -m celery_user && \
    chown -R celery_user:celery_user /app /var/log/celery

# Copy and set permissions for the startup script
COPY apps/worker/start.sh /app/start.sh
RUN chmod +x /app/start.sh && \
    chmod +x /app/health_server.py && \
    chown celery_user:celery_user /app/start.sh && \
    chown celery_user:celery_user /app/health_server.py

# Ensure the script is executable even after volume mounts
RUN chmod +x /app/start.sh


# Compile bytecode to improve performance   
ENV UV_COMPILE_BYTECODE=1 
# Use only system Python provided by the base image. It speeds up the build process and limit 
# the size of the image.
ENV UV_NO_MANAGED_PYTHON=1
# Add the virtual environment to the PATH. It activates the virtual environment allowing to
# call python from the command line.
ENV PATH="/app/.venv/bin:$PATH"
# Set Python path to find the modules and add GC optimizations
ENV PYTHONPATH=/app:/app/backend/src \
    CELERY_OPTIMIZATION=fair \
    CELERY_DISABLE_RATE_LIMITS=True \
    CELERY_TASK_ALWAYS_EAGER=False \
    CELERY_TASK_EAGER_PROPAGATES=False

RUN uv add /app/sdk 

RUN uv sync 

#Add environment variable for the path. This way the Python environment is activated.

# Remove build dependencies after installing Python packages
# Keep git as it's needed by ragas package at runtime
RUN apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*


USER celery_user

# Default Celery configuration (can be overridden at runtime)
ENV CELERY_WORKER_CONCURRENCY=2 \
    CELERY_WORKER_PREFETCH_MULTIPLIER=1 \
    CELERY_WORKER_MAX_TASKS_PER_CHILD=500 \
    CELERY_WORKER_LOGLEVEL=WARNING \
    CELERY_WORKER_OPTS="--without-gossip --without-mingle --without-heartbeat"

# Expose port for health check (Google Cloud Run)
EXPOSE 8080

# Cloud Run needs an HTTP health check, not a Celery inspect ping
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health/basic || exit 1

CMD ["/app/start.sh"]
