FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
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

# Expose gRPC port
EXPOSE 4317

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import grpc; channel = grpc.insecure_channel('localhost:4317'); channel.close()" || exit 1

# Run the processor
CMD ["python", "src/processor.py"]

