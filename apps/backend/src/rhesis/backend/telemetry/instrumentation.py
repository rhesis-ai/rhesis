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
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.trace import NoOpTracerProvider

from rhesis.backend.logging.rhesis_logger import logger

# Sensitive metadata keys to filter out from telemetry
# This blocklist prevents accidental exposure of credentials and PII
SENSITIVE_METADATA_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "session_token",
    "access_token",
    "refresh_token",
    "bearer",
    "email",
    "ssn",
    "credit_card",
}

# Context variable to track if telemetry is enabled for current request
_telemetry_enabled: ContextVar[bool] = ContextVar("telemetry_enabled", default=False)

# Cache the telemetry enabled status (checked once at startup)
_TELEMETRY_GLOBALLY_ENABLED: Optional[bool] = None

# Context variable to store current user/org IDs for telemetry
_telemetry_user_id: ContextVar[Optional[str]] = ContextVar("telemetry_user_id", default=None)
_telemetry_org_id: ContextVar[Optional[str]] = ContextVar("telemetry_org_id", default=None)


class ConditionalSpanProcessor(BatchSpanProcessor):
    """
    Span processor that only exports spans if telemetry is enabled for the current context.
    Uses BatchSpanProcessor for async processing (production).
    """

    def on_end(self, span):
        """Only process spans if telemetry is enabled (checked via span attribute)"""
        # Check span attribute instead of context variable because BatchSpanProcessor
        # runs in a background thread where context variables are not available
        try:
            telemetry_enabled = (
                span.attributes.get("_rhesis.telemetry_enabled", False)
                if hasattr(span.attributes, "get")
                else span.attributes.get("_rhesis.telemetry_enabled", False)
            )
        except Exception as e:
            logger.error(f"Error checking telemetry_enabled attribute: {e}")
            telemetry_enabled = True  # Default to enabled if we can't check

        if telemetry_enabled:
            super().on_end(span)
        else:
            logger.debug(f"Skipping span: {span.name} (telemetry disabled)")


class ConditionalSimpleSpanProcessor(SimpleSpanProcessor):
    """
    Span processor that only exports spans if telemetry is enabled.
    Uses SimpleSpanProcessor for synchronous processing (local development).
    """

    def on_end(self, span):
        """Only process spans if telemetry is enabled (can check context variable)"""
        # SimpleSpanProcessor runs synchronously in the same thread, so we can check context variable
        telemetry_enabled = _telemetry_enabled.get(False) or span.attributes.get(
            "_rhesis.telemetry_enabled", False
        )

        if telemetry_enabled:
            super().on_end(span)
        else:
            logger.debug(f"Skipping span: {span.name} (telemetry disabled)")


def _hash_id(id_str: str) -> str:
    """
    Applies SHA-256 one-way hash to user/organization identifiers for pseudonymization.

    This implements GDPR Article 32 requirements for data pseudonymization.
    Hashed values cannot be reverse-engineered to reveal original identifiers.

    Args:
        id_str: Original user or organization identifier

    Returns:
        First 16 characters of SHA-256 hash (provides 2^64 unique values)

    Security Properties:
        - One-way: Cannot derive original ID from hash
        - Deterministic: Same ID always produces same hash
        - Collision-resistant: Different IDs produce different hashes
    """
    if not id_str:
        return ""
    return hashlib.sha256(id_str.encode()).hexdigest()[:16]


def _sanitize_metadata(metadata: dict) -> dict:
    """
    Filter out potentially sensitive keys from metadata.

    Implements defense-in-depth by removing any keys that match common patterns
    for sensitive data to prevent accidental exposure via telemetry.

    This function provides automatic protection against accidental inclusion of:
    - Credentials (passwords, API keys, tokens)
    - Personal information (emails, SSN, credit cards)
    - Authentication data (auth tokens, session tokens, bearer tokens)

    Args:
        metadata: Dictionary of metadata to sanitize

    Returns:
        Sanitized dictionary with sensitive keys removed

    Security:
        - Exact match: Filters keys in SENSITIVE_METADATA_KEYS
        - Pattern match: Filters any key containing "password", "token", "key", or "secret"
        - Case insensitive: Catches variations like "Password", "PASSWORD", "password"

    Examples:
        >>> _sanitize_metadata({"username": "john", "password": "secret"})
        {"username": "john"}

        >>> _sanitize_metadata({"api_key": "abc123", "user_agent": "Mozilla"})
        {"user_agent": "Mozilla"}
    """
    return {
        k: v
        for k, v in metadata.items()
        if k.lower() not in SENSITIVE_METADATA_KEYS
        and not any(sensitive in k.lower() for sensitive in ["password", "token", "key", "secret"])
    }


def initialize_telemetry():
    """
    Initialize OpenTelemetry with conditional export.

    This should be called once during application startup.

    Telemetry Configuration:
    - Cloud deployments: Always enabled (user consent via Terms & Conditions)
    - Self-hosted deployments: Opt-in via TELEMETRY_ENABLED environment variable

    Environment Variables:
        DEPLOYMENT_TYPE: "cloud" or "self-hosted"
        TELEMETRY_ENABLED: "true" or "false" (self-hosted only, defaults to false)
        OTEL_EXPORTER_OTLP_ENDPOINT: Telemetry collector endpoint URL
        OTEL_SERVICE_NAME: Service identifier (default: "rhesis-backend")

    See is_telemetry_enabled() docstring for detailed information about
    data collection practices and privacy protections.
    """
    global _TELEMETRY_GLOBALLY_ENABLED

    # Check if telemetry is enabled based on deployment type
    _TELEMETRY_GLOBALLY_ENABLED = is_telemetry_enabled()

    if not _TELEMETRY_GLOBALLY_ENABLED:
        deployment_type = os.getenv("DEPLOYMENT_TYPE", "unknown")
        logger.info(f"Telemetry disabled for deployment_type={deployment_type}")
        # Set NoOp provider to prevent span creation entirely (zero performance overhead)
        trace.set_tracer_provider(NoOpTracerProvider())
        return

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if not otel_endpoint:
        logger.info("Telemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set")
        _TELEMETRY_GLOBALLY_ENABLED = False
        # Set NoOp provider to prevent span creation entirely
        trace.set_tracer_provider(NoOpTracerProvider())
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

        # Use SimpleSpanProcessor for local development (synchronous, respects context)
        # Use BatchSpanProcessor for production (asynchronous, better performance)
        is_local = deployment_type in ["local", "self-hosted", "unknown"]
        if is_local:
            logger.info("Using ConditionalSimpleSpanProcessor for local development")
            processor = ConditionalSimpleSpanProcessor(exporter)
        else:
            logger.info("Using ConditionalBatchSpanProcessor for production")
            processor = ConditionalSpanProcessor(exporter)

        provider.add_span_processor(processor)

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        logger.info(f"Telemetry initialized: {service_name} -> {otel_endpoint}")

    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")


def is_telemetry_enabled() -> bool:
    """
    Check if telemetry is enabled based on deployment type.

    CLOUD DEPLOYMENTS:
    - Telemetry is always enabled
    - User consent collected via agreement to Terms & Conditions
    - See https://rhesis.ai/terms for full details

    SELF-HOSTED DEPLOYMENTS:
    - Telemetry is disabled by default
    - Opt-in by setting TELEMETRY_ENABLED=true

    IMPORTANT FOR SELF-HOSTED ADMINISTRATORS:
    Setting TELEMETRY_ENABLED=true opts in to anonymous usage analytics.

    Data Collected:
    - Login/logout events with hashed user IDs (SHA-256, irreversible, 16-char truncated)
    - API endpoint usage and response times
    - Feature interaction patterns (e.g., "test created", "report viewed")
    - Deployment type tag ("cloud" or "self-hosted")
    - Service version information

    Data NOT Collected:
    - No email addresses, names, or personally identifiable information
    - No test data, prompts, or LLM responses
    - No API keys, tokens, passwords, or credentials
    - No IP addresses or organization names
    - No file contents or source code

    Privacy & Security:
    - All user/organization IDs are pseudonymized via SHA-256 hashing
    - Data is transmitted over encrypted connections (HTTPS/gRPC with TLS)
    - Sensitive metadata keys are automatically filtered (passwords, tokens, etc.)
    - No data is shared with third parties

    All data is sent to Rhesis's telemetry servers for product improvement.
    For full privacy details, see: https://rhesis.ai/privacy-policy

    You may disable telemetry at any time by setting TELEMETRY_ENABLED=false
    or omitting this variable entirely (defaults to disabled).

    Returns:
        bool: True if telemetry should be collected

    Examples:
        # Self-hosted: Enable telemetry
        DEPLOYMENT_TYPE=self-hosted
        TELEMETRY_ENABLED=true

        # Self-hosted: Disable telemetry (default)
        DEPLOYMENT_TYPE=self-hosted
        TELEMETRY_ENABLED=false

        # Cloud: Always enabled
        DEPLOYMENT_TYPE=cloud
    """
    deployment_type = os.getenv("DEPLOYMENT_TYPE", "unknown")

    # Cloud users: User consent collected via Terms & Conditions agreement
    if deployment_type == "cloud":
        return True

    # Self-hosted users: Check environment variable (default: disabled)
    if deployment_type == "self-hosted":
        return os.getenv("TELEMETRY_ENABLED", "false").lower() in ("true", "1", "yes")

    # Unknown deployment type: Disable telemetry for safety
    return False


def _set_telemetry_enabled_for_testing(enabled: bool):
    """
    Set telemetry enabled state for testing purposes.

    WARNING: This function is ONLY for use in tests. It modifies global state
    and should be used with proper test isolation (fixtures).

    Args:
        enabled: Whether telemetry should be enabled

    Example:
        ```python
        # In test
        _set_telemetry_enabled_for_testing(True)
        # ... test code ...
        _set_telemetry_enabled_for_testing(False)  # Clean up
        ```
    """
    global _TELEMETRY_GLOBALLY_ENABLED
    _TELEMETRY_GLOBALLY_ENABLED = enabled


def set_telemetry_enabled(
    enabled: bool, user_id: Optional[str] = None, org_id: Optional[str] = None
):
    """
    Set telemetry status for current request context.

    Args:
        enabled: Whether telemetry is enabled for this request
        user_id: User ID hashed using SHA-256 (one-way, 16-character truncated).
                 Original ID is never stored or transmitted.
        org_id: Organization ID hashed using SHA-256 (one-way, 16-character truncated).
                Original ID is never stored or transmitted.

    Note:
        This function automatically applies pseudonymization to provided IDs.
        The hashing occurs before storage in context variables.
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

    Only collects data if telemetry is enabled for the current request context.
    All user/organization IDs are automatically pseudonymized via SHA-256 hashing.

    Args:
        event_type: Type of event (login, logout, session_start, etc.)
        session_id: Session identifier (not hashed, as it's already temporary)
        **metadata: Additional metadata to include (automatically sanitized for sensitive keys)

    Data Collected:
        - Event type and timestamp
        - Hashed user ID (SHA-256, 16-char truncated)
        - Hashed organization ID (if available)
        - Deployment type (cloud/self-hosted)
        - Session ID (temporary identifier)
        - Sanitized metadata (sensitive keys automatically filtered)

    Examples:
        >>> track_user_activity("login", session_id="abc123", login_method="oauth")
        >>> track_user_activity("logout", session_id="abc123")
    """
    if not _telemetry_enabled.get(False):
        return

    tracer = get_tracer(__name__)

    with tracer.start_as_current_span("user.activity") as span:
        # Store telemetry enabled status in span attribute for processor
        span.set_attribute("_rhesis.telemetry_enabled", True)

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

        # Add custom metadata (sanitized to prevent sensitive data leakage)
        sanitized_metadata = _sanitize_metadata(metadata)
        for key, value in sanitized_metadata.items():
            span.set_attribute(f"metadata.{key}", str(value))


def track_feature_usage(feature_name: str, action: str, **metadata):
    """
    Track feature-specific usage patterns.

    Only collects data if telemetry is enabled for the current request context.
    All user/organization IDs are automatically pseudonymized via SHA-256 hashing.

    Args:
        feature_name: Name of the feature (e.g., "test_run", "metric", "prompt")
        action: Action performed (e.g., "created", "updated", "viewed", "deleted")
        **metadata: Additional metadata to include (automatically sanitized for sensitive keys)

    Data Collected:
        - Feature name and action
        - Hashed user ID (SHA-256, 16-char truncated)
        - Hashed organization ID (if available)
        - Deployment type (cloud/self-hosted)
        - Timestamp
        - Sanitized metadata (sensitive keys automatically filtered)

    Data NOT Collected:
        - No feature content (e.g., test data, prompt text)
        - No identifiable information
        - No sensitive credentials or tokens

    Examples:
        >>> track_feature_usage("test_run", "created", test_count=5)
        >>> track_feature_usage("metric", "viewed", metric_type="accuracy")
    """
    if not _telemetry_enabled.get(False):
        return

    tracer = get_tracer(__name__)

    with tracer.start_as_current_span(f"feature.{feature_name}") as span:
        # Store telemetry enabled status in span attribute for processor
        span.set_attribute("_rhesis.telemetry_enabled", True)

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

        # Add custom metadata (sanitized to prevent sensitive data leakage)
        sanitized_metadata = _sanitize_metadata(metadata)
        for key, value in sanitized_metadata.items():
            span.set_attribute(f"metadata.{key}", str(value))
