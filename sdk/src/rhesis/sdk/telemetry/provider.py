"""TracerProvider singleton for OpenTelemetry."""

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from rhesis.sdk.telemetry.exporter import RhesisOTLPExporter

logger = logging.getLogger(__name__)

_TRACER_PROVIDER: Optional[TracerProvider] = None


def get_tracer_provider(
    service_name: str,
    api_key: str,
    base_url: str,
    project_id: str,
    environment: str,
) -> TracerProvider:
    """
    Get or create the global tracer provider.

    Args:
        service_name: Service identifier for traces
        api_key: Rhesis API key for authentication
        base_url: Backend base URL
        project_id: Rhesis project ID
        environment: Environment name

    Returns:
        TracerProvider instance
    """
    global _TRACER_PROVIDER

    if _TRACER_PROVIDER is not None:
        return _TRACER_PROVIDER

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "rhesis",
            "deployment.environment": environment,
        }
    )

    # Create tracer provider
    _TRACER_PROVIDER = TracerProvider(resource=resource)

    # Create custom exporter
    exporter = RhesisOTLPExporter(
        api_key=api_key,
        base_url=base_url,
        project_id=project_id,
        environment=environment,
    )

    # Add batch span processor for performance
    # Batches spans before sending to reduce HTTP requests
    span_processor = BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,  # Export every 5 seconds
    )

    _TRACER_PROVIDER.add_span_processor(span_processor)

    # Set as global tracer provider
    trace.set_tracer_provider(_TRACER_PROVIDER)

    logger.info(
        f"OpenTelemetry tracer provider initialized for {service_name} "
        f"(project={project_id}, env={environment})"
    )

    return _TRACER_PROVIDER


def shutdown_tracer_provider():
    """Shutdown the tracer provider and flush pending spans."""
    global _TRACER_PROVIDER

    if _TRACER_PROVIDER is not None:
        _TRACER_PROVIDER.shutdown()
        _TRACER_PROVIDER = None
        logger.info("OpenTelemetry tracer provider shut down")
