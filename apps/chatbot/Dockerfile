# Hint: Build this image with an expanded build context from repo root
# `docker build -t rhesis-chatbot -f apps/chatbot/Dockerfile .`

# Single stage build for simplicity
# IMPORTANT: The python version must match the version in the .python-version file.
FROM mirror.gcr.io/library/python:3.10.17-slim

WORKDIR /app

# Install OS-level dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Copy the SDK directory (required dependency)
COPY sdk /app/sdk/

# Add SDK to the project dependencies
RUN uv add /app/sdk

# Install chatbot dependencies (which includes the SDK)
RUN uv sync

# Now copy the rest of your source (scripts, modules, etc.)
COPY apps/chatbot /app/

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
CMD sh -c "gunicorn --workers ${WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --timeout 120 --graceful-timeout 30 client:app"