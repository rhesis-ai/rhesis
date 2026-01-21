import os
from typing import Optional, Union

# Check if connector should be disabled
# Accept common truthy values: true, 1, yes, on (case-insensitive)
CONNECTOR_DISABLED = os.getenv("RHESIS_CONNECTOR_DISABLE", "false").lower() in (
    "true",
    "1",
    "yes",
    "on",
)


class DisabledClient:
    """
    No-op client implementation used when RHESIS_CONNECTOR_DISABLE is enabled.

    This client accepts all initialization parameters and method calls but
    performs no actual operations. It's used to allow code to run without
    connector/observability overhead in test and CI environments.

    Enabled with: RHESIS_CONNECTOR_DISABLE=true|1|yes|on (case-insensitive)

    When DisabledClient is active:
    - @endpoint and @observe decorators return the original function unmodified
    - No telemetry initialization occurs
    - No connector manager is created
    - All method calls are no-ops
    """

    def __init__(self, *args, **kwargs):
        """Accept any initialization parameters and register as default client."""
        from rhesis.sdk import decorators

        decorators._register_default_client(self)
        import logging

        logger = logging.getLogger(__name__)
        logger.info("✅ DisabledClient initialized successfully")

    @property
    def is_disabled(self) -> bool:
        """Return True to indicate this is a disabled client."""
        return True

    def __getattr__(self, name):
        """
        Handle any method call as a no-op.

        This ensures all Client methods work without needing to explicitly
        implement each one in DisabledClient.

        Returns:
            A function that accepts any arguments and returns None
        """

        def noop(*args, **kwargs):
            return None

        return noop

    @property
    def base_url(self) -> str:
        """Return empty string for base_url property."""
        return ""

    @property
    def project_id(self) -> Optional[str]:
        """Return None for project_id property."""
        return None

    @property
    def environment(self) -> str:
        """Return empty string for environment property."""
        return ""


class RhesisClient:
    """
    Rhesis client with observability and telemetry capabilities.

    This is the main user-facing client for applications that need:
    - OpenTelemetry tracing (@observe decorator)
    - Remote function execution (@endpoint decorator)
    - Automatic instrumentation

    Users should create this via `RhesisClient.from_environment()` for
    automatic configuration from environment variables.

    Example:
        ```python
        from rhesis.sdk import RhesisClient

        # Recommended: environment-based initialization
        client = RhesisClient.from_environment()

        # Or explicit configuration
        client = RhesisClient(
            api_key="your-key",
            project_id="your-project",
            environment="production"
        )
        ```
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        """
        Initialize the Rhesis observability client.

        Args:
            api_key: Optional API key. If not provided, will try to get it from
                    module level variable or environment variable.
            base_url: Optional base URL. If not provided, will try to get it from
                     module level variable or environment variable.
            project_id: Optional project ID for remote endpoint testing. If not provided,
                       will try to get from RHESIS_PROJECT_ID environment variable.
            environment: Optional environment name. If not provided, will try to get
                        from RHESIS_ENVIRONMENT environment variable (default: "development").
        """
        from rhesis.sdk.config import get_api_key, get_base_url

        # API configuration
        self.api_key = api_key if api_key is not None else get_api_key()
        self._base_url = base_url if base_url is not None else get_base_url()

        # Observability configuration
        self.project_id = project_id or os.getenv("RHESIS_PROJECT_ID")
        self.environment = environment or os.getenv("RHESIS_ENVIRONMENT", "development")

        # Lazy connector (not initialized yet)
        self._connector_manager = None

        # Initialize OpenTelemetry tracer provider for @observe decorator
        self._init_telemetry()

        # Create tracer instance for direct tracing
        self._init_tracer()

        # Automatically register as default client for decorators
        self._register_as_default()

    @classmethod
    def from_environment(cls) -> Union["RhesisClient", DisabledClient]:
        """
        Create a RhesisClient from environment variables.

        This is the recommended way to initialize the client in applications.
        Returns a DisabledClient if RHESIS_CONNECTOR_DISABLE is set or if
        required credentials (RHESIS_PROJECT_ID, RHESIS_API_KEY) are missing.

        Environment Variables:
            RHESIS_CONNECTOR_DISABLE: Set to 'true' to disable the connector
            RHESIS_PROJECT_ID: Required project ID
            RHESIS_API_KEY: Required API key
            RHESIS_ENVIRONMENT: Optional, defaults to 'development'
            RHESIS_BASE_URL: Optional, defaults to 'http://localhost:8080'

        Returns:
            RhesisClient or DisabledClient instance
        """
        import logging

        logger = logging.getLogger(__name__)

        if CONNECTOR_DISABLED:
            logger.info("Connector explicitly disabled (RHESIS_CONNECTOR_DISABLE=true)")
            return DisabledClient()

        project_id = os.getenv("RHESIS_PROJECT_ID")
        api_key = os.getenv("RHESIS_API_KEY")
        if not project_id or not api_key:
            logger.info(
                "Using DisabledClient: Missing "
                f"{'RHESIS_PROJECT_ID' if not project_id else 'RHESIS_API_KEY'}"
            )
            return DisabledClient()

        return cls(
            project_id=project_id,
            api_key=api_key,
            environment=os.getenv("RHESIS_ENVIRONMENT", "development"),
            base_url=os.getenv("RHESIS_BASE_URL", "http://localhost:8080"),
        )

    def _init_telemetry(self) -> None:
        """
        Initialize OpenTelemetry tracer provider.

        Raises:
            RuntimeError: If telemetry initialization fails
        """
        import logging

        logger = logging.getLogger(__name__)

        try:
            from rhesis.sdk.telemetry.provider import get_tracer_provider

            # Initialize OTEL provider with current client config
            provider = get_tracer_provider(
                service_name="rhesis-sdk",
                api_key=self.api_key,
                base_url=self._base_url,
                project_id=self.project_id or "unknown",
                environment=self.environment,
            )

            # Verify provider was initialized correctly
            if provider is None:
                raise RuntimeError("TracerProvider initialization returned None")

            # Log successful initialization
            logger.info(
                f"✅ Telemetry initialized successfully\n"
                f"   Project: {self.project_id or 'unknown'}\n"
                f"   Environment: {self.environment}\n"
                f"   Endpoint: {self._base_url}/telemetry/traces\n"
                f"   Note: Traces are batched and exported every 5 seconds"
            )

        except ImportError as e:
            logger.error(f"❌ Failed to import telemetry modules: {e}")
            raise RuntimeError(
                f"Telemetry initialization failed: Missing dependencies. "
                f"Make sure opentelemetry-sdk is installed. Error: {e}"
            ) from e

        except Exception as e:
            logger.error(
                f"❌ Failed to initialize telemetry: {e}\n"
                f"   API Key: {'SET' if self.api_key else 'NOT SET'}\n"
                f"   Base URL: {self._base_url}\n"
                f"   Project ID: {self.project_id or 'NOT SET'}"
            )
            raise RuntimeError(
                f"Telemetry initialization failed: {e}. "
                f"Check your API key, base URL, and backend connectivity."
            ) from e

    def _init_tracer(self) -> None:
        """
        Initialize Tracer instance for direct tracing.

        This allows @endpoint decorated functions to be traced even when
        the connector manager is not active (e.g., direct HTTP calls).
        """
        from rhesis.sdk.telemetry import Tracer

        self._tracer = Tracer(
            api_key=self.api_key,
            project_id=self.project_id or "unknown",
            environment=self.environment,
            base_url=self._base_url,
        )

    def _register_as_default(self) -> None:
        """Register this client as the default for decorators."""
        # Import here to avoid circular dependency
        from rhesis.sdk import decorators

        decorators._register_default_client(self)

    def _ensure_connector(self):
        """Lazy-initialize connector when first needed."""
        if self._connector_manager is None:
            if not self.project_id:
                raise RuntimeError(
                    "@endpoint requires project_id parameter or "
                    "RHESIS_PROJECT_ID environment variable"
                )
            from rhesis.sdk.connector.manager import ConnectorManager

            self._connector_manager = ConnectorManager(
                api_key=self.api_key,
                project_id=self.project_id,
                environment=self.environment,
                base_url=self._base_url,
            )
            self._connector_manager.initialize()
        return self._connector_manager

    def register_endpoint(self, name: str, func, metadata: dict) -> None:
        """
        Register a function as a remotely callable endpoint.

        Args:
            name: Endpoint function name
            func: Function callable
            metadata: Additional metadata
        """
        connector = self._ensure_connector()  # Lazy init
        connector.register_function(name, func, metadata)
