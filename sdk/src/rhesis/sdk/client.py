import os
from enum import Enum
from typing import Optional

import requests

from rhesis.sdk.config import get_api_key, get_base_url


class Endpoints(Enum):
    BEHAVIORS = "behaviors"
    METRICS = "metrics"
    HEALTH = "health"


class Methods(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class Client:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        project_id: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        """
        Initialize the Rhesis client.

        Args:
            api_key: Optional API key. If not provided, will try to get it from
                    module level variable or environment variable.
            base_url: Optional base URL. If not provided, will try to get it from
                     module level variable or environment variable.
            project_id: Optional project ID for collaborative testing. If not provided,
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

        # Automatically register as default client (transparent)
        self._register_as_default()

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
            method.value, url, headers=self.headers, json=data, params=params
        )
        response.raise_for_status()
        return response.json()

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

    def register_collaborative_function(self, name: str, func, metadata: dict) -> None:
        """
        Register a function for remote triggering.

        Args:
            name: Function name
            func: Function callable
            metadata: Additional metadata
        """
        connector = self._ensure_connector()  # Lazy init
        connector.register_function(name, func, metadata)
