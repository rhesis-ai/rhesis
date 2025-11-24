from enum import Enum
from typing import Optional

import requests

from rhesis.sdk.config import get_api_key, get_base_url


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


class Methods(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class Client:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Rhesis client.

        Args:
            api_key: Optional API key. If not provided, will try to get it from
                    module level variable or environment variable.
            base_url: Optional base URL. If not provided, will try to get it from
                     module level variable or environment variable.
        """
        self.api_key = api_key if api_key is not None else get_api_key()
        self._base_url = base_url if base_url is not None else get_base_url()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
