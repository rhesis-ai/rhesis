"""TracerProvider construction for OpenTelemetry."""

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from rhesis.telemetry.exporter import RhesisOTLPExporter

logger = logging.getLogger(__name__)

_TRACER_PROVIDER: Optional[TracerProvider] = None


def build_tracer_provider(
    service_name: str,
    api_key: str,
    base_url: str,
    project_id: Optional[str],
    environment: str,
) -> TracerProvider:
    """
    Build a TracerProvider that exports to Rhesis.

    Owns nothing process-wide: no singleton, and the OpenTelemetry global provider is left alone.
    Use this from anywhere Rhesis tracing is embedded in an application that has its own
    observability — a framework integration, a library, a service with an existing APM — where
    claiming the global would silently redirect the host's telemetry.

    ``get_tracer_provider`` remains for callers that do want the global set.

    Args:
        service_name: Service identifier for traces
        api_key: Rhesis API key for authentication
        base_url: Backend base URL
        project_id: Rhesis project ID
        environment: Environment name

    Returns:
        A new TracerProvider with a Rhesis exporter attached
    """
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "rhesis",
            "deployment.environment": environment,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = RhesisOTLPExporter(
        api_key=api_key,
        base_url=base_url,
        project_id=project_id,
        environment=environment,
    )
    # Batches spans before sending, to reduce HTTP requests.
    provider.add_span_processor(
        BatchSpanProcessor(
            exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,  # Export every 5 seconds
        )
    )

    logger.info(
        f"OpenTelemetry tracer provider built for {service_name} "
        f"(project={project_id}, env={environment})"
    )
    return provider


def get_tracer_provider(
    service_name: str,
    api_key: str,
    base_url: str,
    project_id: Optional[str],
    environment: str,
) -> TracerProvider:
    """
    Get or create the global tracer provider.

    Caches the first provider it builds and installs it as the OpenTelemetry global. Both of those
    are process-wide effects, so they are wrong for an embedded caller: the cache means a second
    call with a different ``project_id`` silently gets the first one's provider and routes its
    traces to the wrong project, and setting the global means whichever of Rhesis and the host's
    own APM initialises first wins — OpenTelemetry refuses the loser's override. Use
    ``build_tracer_provider`` there.

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

    _TRACER_PROVIDER = build_tracer_provider(
        service_name=service_name,
        api_key=api_key,
        base_url=base_url,
        project_id=project_id,
        environment=environment,
    )
    trace.set_tracer_provider(_TRACER_PROVIDER)
    return _TRACER_PROVIDER


def shutdown_tracer_provider():
    """Shutdown the tracer provider and flush pending spans."""
    global _TRACER_PROVIDER

    if _TRACER_PROVIDER is not None:
        _TRACER_PROVIDER.shutdown()
        _TRACER_PROVIDER = None
        logger.info("OpenTelemetry tracer provider shut down")
