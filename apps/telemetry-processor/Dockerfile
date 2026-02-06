FROM mirror.gcr.io/library/python:3.11-slim

WORKDIR /app

# Install system dependencies with retry logic
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    --allow-unauthenticated \
    -o Acquire::Retries=3 \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .

# Install uv for faster installs
RUN pip install --no-cache-dir uv

# Install dependencies
RUN uv pip install --system -e .

# Copy source code
COPY src/ /app/src/

# Copy alembic configuration and migrations
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY migrate.sh /app/migrate.sh

# Make migration script executable
RUN chmod +x /app/migrate.sh

# Expose gRPC port
EXPOSE 4317

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import grpc; channel = grpc.insecure_channel('localhost:4317'); channel.close()" || exit 1

# Run migrations then start the processor
CMD ["sh", "-c", "./migrate.sh && python src/processor.py"]

