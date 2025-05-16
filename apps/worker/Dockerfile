# Use Python 3.10 base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    curl \
    jq \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Celery and dependencies
RUN pip install --no-cache-dir \
    "celery[postgres,redis]==5.3.6" \
    "psycopg2-binary==2.9.9" \
    "kombu==5.3.5" \
    "fastapi==0.104.1" \
    "uvicorn==0.24.0" \
    "redis>=4.5.2,<6.0.0,!=4.5.5"

# Install the SDK with upgrade flag to ensure latest version
RUN pip install --upgrade --no-cache-dir rhesis-sdk

# Copy rhesis requirements and install dependencies
COPY rhesis/requirements.txt /app/rhesis/requirements.txt
RUN pip install --no-cache-dir -r /app/rhesis/requirements.txt

# Copy the rhesis folder (backend code with sdk.py wrapper already included)
COPY rhesis/ /app/rhesis/

# Set Python path to find the rhesis module (backend)
ENV PYTHONPATH=/app:${PYTHONPATH}

# Create directory for Celery logs
RUN mkdir -p /var/log/celery

# Create non-root user
RUN useradd -m celery_user && \
    chown -R celery_user:celery_user /app /var/log/celery

# Copy and set permissions for the startup script
COPY celery/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Switch to non-root user
USER celery_user

# Set the startup script as the entry point
CMD ["/app/start.sh"]
