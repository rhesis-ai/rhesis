# syntax=docker/dockerfile:1
FROM mirror.gcr.io/library/python:3.12.8-slim
COPY --from=mirror.gcr.io/astral/uv:0.11.19 /uv /uvx /bin/

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

COPY pyproject.toml uv.lock ./

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_MANAGED_PYTHON=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# --locked installs exactly the lock's versions and fails if it is stale, rather than
# resolving the newest release (SQLAlchemy 2.1 changed the default Postgres driver).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

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

