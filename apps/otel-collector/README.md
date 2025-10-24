# OpenTelemetry Collector

This service collects telemetry data from both cloud-hosted and self-hosted Rhesis instances.

## Architecture

```
User Instances (Cloud + Self-Hosted)
          ↓
  OTLP (gRPC/HTTP)
          ↓
  OpenTelemetry Collector (This Service)
          ↓
  Telemetry Processor (Custom Service)
          ↓
  PostgreSQL (Analytics Tables)
```

## Ports

- **4317**: OTLP gRPC receiver
- **4318**: OTLP HTTP receiver
- **8888**: Collector's own metrics (Prometheus format)
- **8889**: Application metrics exporter
- **13133**: Health check endpoint
- **1777**: pprof profiling endpoint
- **55679**: zpages debugging endpoint

## Configuration

The collector is configured via `otel-collector-config.yaml`. Key features:

### Receivers
- OTLP gRPC and HTTP protocols
- CORS enabled for web applications

### Processors
- **Batch**: Batches spans for efficient export
- **Memory Limiter**: Prevents OOM
- **Attributes**: Filters out sensitive data (passwords, tokens)
- **Resource**: Adds service metadata
- **Transform**: Categorizes events for analytics

### Exporters
- **OTLP**: Forwards to telemetry processor for database insertion
- **Logging**: Debug output
- **Prometheus**: Metrics endpoint

## Privacy & Security

The collector automatically:
- Removes sensitive attributes (passwords, tokens, API keys)
- Respects user opt-in/opt-out preferences
- Uses batch processing to reduce network overhead
- Implements retry logic for reliability

## Health Check

Check collector health:
```bash
curl http://localhost:13133
```

## Debugging

Access zpages for debugging:
```bash
open http://localhost:55679/debug/tracez
```

## Metrics

View collector's own metrics:
```bash
curl http://localhost:8888/metrics
```

## Environment Variables

- `TELEMETRY_PROCESSOR_ENDPOINT`: Endpoint for the telemetry processor service (default: telemetry-processor:4317)

## Testing Locally

```bash
# Build the image
docker build -t rhesis-otel-collector .

# Run locally
docker run -p 4317:4317 -p 4318:4318 -p 13133:13133 \
  -e TELEMETRY_PROCESSOR_ENDPOINT=host.docker.internal:4317 \
  rhesis-otel-collector
```

## Deployment

This service is deployed to Google Cloud Run. See `infrastructure/k8s/manifests/otel-collector-deployment.yaml` for Kubernetes configuration.

