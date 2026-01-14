import os
from enum import Enum
from typing import Optional

import requests

from rhesis.sdk.config import get_api_key, get_base_url

# Check if connector should be disabled
CONNECTOR_DISABLED = os.getenv("RHESIS_CONNECTOR_DISABLE", "0") == "1"


class HTTPStatus:
    """HTTP status codes for consistent testing.
    See tests/backend/routes/endpoints.py for definitions
    """

    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500


class Endpoints(Enum):
    BEHAVIORS = "behaviors"
    METRICS = "metrics"
    HEALTH = "health"
    CATEGORIES = "categories"
    STATUSES = "statuses"
    TEST_SETS = "test_sets"
    TESTS = "tests"
    TOPICS = "topics"
    PROMPTS = "prompts"
    ENDPOINTS = "endpoints"
    TEST_RESULTS = "test_results"
    TEST_RUNS = "test_runs"
    TEST_CONFIGURATIONS = "test_configurations"


class Methods(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class DisabledClient:
    """
    No-op client implementation used when RHESIS_CONNECTOR_DISABLE=1.

    This client accepts all initialization parameters and method calls but
    performs no actual operations. It's used to allow code to run without
    connector/observability overhead in test and CI environments.

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


class Client:
    def __new__(cls, *args, **kwargs):
        """
        Create either a real Client or DisabledClient based on environment flag.

        When RHESIS_CONNECTOR_DISABLE=1, returns a DisabledClient that performs
        no operations. Otherwise, creates a normal Client instance.
        """
        if CONNECTOR_DISABLED:
            import logging

            logger = logging.getLogger(__name__)
            logger.info("⏭️  Rhesis connector disabled (RHESIS_CONNECTOR_DISABLE=1)")
            return DisabledClient()
        return super().__new__(cls)

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        """
        Initialize the Rhesis client.

        Note: This __init__ will NOT be called when RHESIS_CONNECTOR_DISABLE=1
        since __new__ returns a DisabledClient instance instead.

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
        # Existing REST functionality
        self.api_key = api_key if api_key is not None else get_api_key()
        self._base_url = base_url if base_url is not None else get_base_url()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # New: Connector configuration
        self.project_id = project_id or os.getenv("RHESIS_PROJECT_ID")
        self.environment = environment or os.getenv("RHESIS_ENVIRONMENT", "development")

        # New: Lazy connector (not initialized yet)
        self._connector_manager = None

        # Initialize OpenTelemetry tracer provider for @observe decorator
        # This must happen even if @collaborate is never used
        self._init_telemetry()

        # Create tracer instance for direct tracing (when connector manager not active)
        self._init_tracer()

        # Automatically register as default client (transparent)
        self._register_as_default()

    @property
    def is_disabled(self) -> bool:
        """Return False to indicate this is an active client."""
        return False

    @property
    def base_url(self) -> str:
        """Get the base URL with trailing slash removed."""
        return self._base_url.rstrip("/")

    def get_url(self, endpoint: str) -> str:
        """
        Construct a URL by combining base_url and endpoint.

        Args:
            endpoint: The API endpoint path.

        Returns:
            str: The complete URL with proper formatting.
        """
        # Remove leading slash from endpoint if present
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"

    def send_request(
        self,
        endpoint: Endpoints,
        method: Methods,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        url_params: Optional[str] = None,
    ) -> dict:
        """
        Send a request to the API.

        Args:
            endpoint: The API endpoint path.
            method: The HTTP method to use.
            data: The data to send in the request body.
        """
        url = self.get_url(endpoint.value)
        if url_params is not None:
            url = f"{url}/{url_params}"
        response = requests.request(
            method=method.value, url=url, headers=self.headers, json=data, params=params
        )
        response.raise_for_status()
        return response.json()

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
                    "@collaborate requires project_id parameter or "
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
