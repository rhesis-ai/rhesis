# Telemetry Processor

This service receives OTLP (OpenTelemetry Protocol) data from the OpenTelemetry Collector and writes it to PostgreSQL analytics tables.

## Purpose

The telemetry processor acts as a bridge between the OpenTelemetry Collector and PostgreSQL, transforming OTLP traces into structured analytics data.

## Architecture

```
OpenTelemetry Collector
          ↓ OTLP/gRPC
  Telemetry Processor (This Service)
          ↓ SQL
  PostgreSQL Analytics Tables
```

## Database Tables

The processor writes to three analytics tables:

### analytics_user_activity
Tracks user login, logout, and session events.

### analytics_endpoint_usage
Tracks API endpoint calls and performance.

### analytics_feature_usage
Tracks feature-specific user actions.

## Environment Variables

- `DATABASE_URL`: Full PostgreSQL connection string (optional)
- `SQLALCHEMY_DB_USER`: Database user (default: rhesis-user)
- `SQLALCHEMY_DB_PASS`: Database password
- `SQLALCHEMY_DB_HOST`: Database host (default: postgres)
- `SQLALCHEMY_DB_PORT`: Database port (default: 5432)
- `SQLALCHEMY_DB_NAME`: Database name (default: rhesis-db)
- `PORT`: gRPC port (default: 4317)

## Running Locally

```bash
# Install dependencies
uv pip install -e .

# Set environment variables
export SQLALCHEMY_DB_PASS=your-password

# Run the processor
python src/processor.py
```

## Docker

```bash
# Build
docker build -t rhesis-telemetry-processor .

# Run
docker run -p 4317:4317 \
  -e SQLALCHEMY_DB_PASS=your-password \
  rhesis-telemetry-processor
```

## Testing

Send test OTLP data:

```bash
# Coming soon: test script
```

## Deployment

This service is deployed alongside the OpenTelemetry Collector in Google Cloud Run.

