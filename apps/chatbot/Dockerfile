# Hint: Build this image with an expanded build context from repo root
# `docker build -t rhesis-chatbot -f apps/chatbot/Dockerfile .`

# Single stage build for simplicity
# IMPORTANT: The python version must match the version in the .python-version file.
FROM mirror.gcr.io/library/python:3.12-slim

WORKDIR /app

# Install OS-level dependencies and uv with retry logic
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    build-essential \
    curl \
    git \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files for chatbot
COPY apps/chatbot/pyproject.toml apps/chatbot/uv.lock ./

# Compile bytecode to improve performance   
ENV UV_COMPILE_BYTECODE=1 
# Use only system Python provided by the base image. It speeds up the build process and limit 
# the size of the image.
ENV UV_NO_MANAGED_PYTHON=1
# Add the virtual environment to the PATH. It activates the virtual environment allowing to
# call python from the command line.
ENV PATH="/app/.venv/bin:$PATH"

# SDK and rhesis meta-package (SDK depends on rhesis[telemetry]) — same layout as backend
COPY sdk /app/sdk/
COPY packages/rhesis /app/packages/rhesis/

# Fix paths in pyproject.toml to point to the correct locations in Docker (see apps/backend/Dockerfile)
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' pyproject.toml && \
    sed -i 's|path = "../packages/rhesis"|path = "/app/packages/rhesis"|g' /app/sdk/pyproject.toml && \
    uv sync --no-dev

# Now copy the rest of your source (scripts, modules, etc.)
COPY apps/chatbot /app/

# Re-apply path patch: COPY restores repo pyproject.toml (../../sdk).
RUN sed -i 's|path = "../../sdk"|path = "/app/sdk"|g' pyproject.toml && \
    sed -i 's|path = "../packages/rhesis"|path = "/app/packages/rhesis"|g' /app/sdk/pyproject.toml

# Remove build dependencies after installing Python packages
RUN apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and remove .env files
RUN adduser --disabled-password --gecos '' rhesis-user \
    && find /app -name ".env" -type f -delete \
    && chown -R rhesis-user /app

# Switch to the non-root user
USER rhesis-user

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    WORKERS=4

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Command to run the FastAPI application with Gunicorn
# Workers can be overridden via WORKERS environment variable
CMD sh -c "gunicorn --workers ${WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --timeout 300 --graceful-timeout 30 --worker-tmp-dir /dev/shm --max-requests 1000 --max-requests-jitter 50 client:app"