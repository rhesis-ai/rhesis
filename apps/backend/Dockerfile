# Hint: Build this image with an expanded build context
# `docker build -t rhesis-backend -f Dockerfile .`

# Single stage build for simplicity
FROM python:3.10-slim

WORKDIR /app

# Install OS-level dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpq5 \
    && pip install --no-cache-dir uv \
    && apt-get purge -y build-essential libpq-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files
COPY pyproject.toml uv.lock README.md ./

# Copy only the minimal source code needed for your local package metadata
# This ensures uv can install your package without invalidating the layer later
COPY src/rhesis /app/src/rhesis

# Install dependencies + local package
RUN uv sync

# Now copy the rest of your source (scripts, modules, etc.)
COPY src /app/src

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
    PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8080

# Command to run the FastAPI application with Gunicorn
CMD ["gunicorn", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "rhesis.backend.app.main:app"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1