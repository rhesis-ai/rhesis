"""
OpenTelemetry instrumentation with conditional export based on user preferences.
"""

import hashlib
import os
from contextvars import ContextVar
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from rhesis.backend.logging.rhesis_logger import logger

# Context variable to track if telemetry is enabled for current request
_telemetry_enabled: ContextVar[bool] = ContextVar("telemetry_enabled", default=False)

# Context variable to store current user/org IDs for telemetry
_telemetry_user_id: ContextVar[Optional[str]] = ContextVar("telemetry_user_id", default=None)
_telemetry_org_id: ContextVar[Optional[str]] = ContextVar("telemetry_org_id", default=None)


class ConditionalSpanProcessor(BatchSpanProcessor):
    """
    Span processor that only exports spans if telemetry is enabled for the current context.

    This ensures we respect user's opt-in/opt-out preferences without
    modifying the tracer creation logic throughout the codebase.
    """

    def on_end(self, span):
        """Only process spans if telemetry is enabled in current context"""
        if _telemetry_enabled.get(False):
            super().on_end(span)


def _hash_id(id_str: str) -> str:
    """
    One-way hash of user/org IDs for privacy.

    This ensures we can track unique users without storing actual IDs.
    """
    if not id_str:
        return ""
    return hashlib.sha256(id_str.encode()).hexdigest()[:16]


def initialize_telemetry():
    """
    Initialize OpenTelemetry with conditional export.

    This should be called once during application startup.
    If OTEL_EXPORTER_OTLP_ENDPOINT is not set, telemetry is disabled entirely.
    """
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if not otel_endpoint:
        logger.info("Telemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return

    # Determine deployment type
    deployment_type = os.getenv("DEPLOYMENT_TYPE", "unknown")
    service_name = os.getenv("OTEL_SERVICE_NAME", "rhesis-backend")

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "rhesis",
            "deployment.type": deployment_type,
            "service.version": os.getenv("APP_VERSION", "unknown"),
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Create OTLP exporter
    try:
        # For HTTP endpoint, append /v1/traces if not already present
        traces_endpoint = otel_endpoint
        if "/v1/traces" not in traces_endpoint:
            traces_endpoint = f"{otel_endpoint}/v1/traces"

        exporter = OTLPSpanExporter(
            endpoint=traces_endpoint,
            timeout=5,  # 5 second timeout - don't block app if telemetry is slow
        )

        # Use conditional processor
        processor = ConditionalSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        logger.info(f"Telemetry initialized: {service_name} -> {otel_endpoint}")

    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")


def set_telemetry_enabled(
    enabled: bool, user_id: Optional[str] = None, org_id: Optional[str] = None
):
    """
    Set telemetry status for current request context.

    Args:
        enabled: Whether telemetry is enabled for this request
        user_id: User ID to associate with telemetry (will be hashed)
        org_id: Organization ID to associate with telemetry (will be hashed)
    """
    _telemetry_enabled.set(enabled)

    if enabled and user_id:
        _telemetry_user_id.set(_hash_id(str(user_id)))
    if enabled and org_id:
        _telemetry_org_id.set(_hash_id(str(org_id)))


def get_tracer(name: str):
    """
    Get a tracer for creating spans.

    Args:
        name: Name of the tracer (typically __name__ of the module)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def track_user_activity(event_type: str, session_id: Optional[str] = None, **metadata):
    """
    Track user activity events (login, logout, etc.).

    Args:
        event_type: Type of event (login, logout, session_start, etc.)
        session_id: Session identifier
        **metadata: Additional metadata to include
    """
    if not _telemetry_enabled.get(False):
        return

    tracer = get_tracer(__name__)

    with tracer.start_as_current_span("user.activity") as span:
        # Set standard attributes
        span.set_attribute("event.category", "user_activity")
        span.set_attribute("event.type", event_type)

        # Set user context
        user_id = _telemetry_user_id.get()
        org_id = _telemetry_org_id.get()

        if user_id:
            span.set_attribute("user.id", user_id)
        if org_id:
            span.set_attribute("organization.id", org_id)
        if session_id:
            span.set_attribute("session.id", session_id)

        # Set deployment type
        deployment_type = os.getenv("DEPLOYMENT_TYPE", "unknown")
        span.set_attribute("deployment.type", deployment_type)

        # Add custom metadata
        for key, value in metadata.items():
            span.set_attribute(f"metadata.{key}", str(value))


def track_feature_usage(feature_name: str, action: str, **metadata):
    """
    Track feature-specific usage.

    Args:
        feature_name: Name of the feature (e.g., "test_run", "metric")
        action: Action performed (e.g., "created", "updated", "viewed")
        **metadata: Additional metadata to include
    """
    if not _telemetry_enabled.get(False):
        return

    tracer = get_tracer(__name__)

    with tracer.start_as_current_span(f"feature.{feature_name}") as span:
        # Set standard attributes
        span.set_attribute("event.category", "feature_usage")
        span.set_attribute("feature.name", feature_name)
        span.set_attribute("feature.action", action)

        # Set user context
        user_id = _telemetry_user_id.get()
        org_id = _telemetry_org_id.get()

        if user_id:
            span.set_attribute("user.id", user_id)
        if org_id:
            span.set_attribute("organization.id", org_id)

        # Set deployment type
        deployment_type = os.getenv("DEPLOYMENT_TYPE", "unknown")
        span.set_attribute("deployment.type", deployment_type)

        # Add custom metadata
        for key, value in metadata.items():
            span.set_attribute(f"metadata.{key}", str(value))
