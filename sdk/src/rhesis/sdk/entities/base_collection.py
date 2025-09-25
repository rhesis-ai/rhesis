from typing import Any, Dict, Optional

from rhesis.sdk.client import Client, Methods
from rhesis.sdk.entities.base_entity import handle_http_errors


class BaseCollection:
    """Base class for API collection interactions.

    This class provides basic CRUD operations for interacting with REST API endpoints.
    It handles authentication and common HTTP operations.
    """

    endpoint: str

    @classmethod
    def all(cls) -> Optional[list[Any]]:
        """Retrieve all records from the API for the given endpoint."""
        client = Client()

        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
        )
        return response

    @handle_http_errors
    def first(cls) -> Optional[Dict[str, Any]]:
        """Retrieve the first record matching the query parameters."""
        records = cls.all()
        return records[0] if records else None

    @classmethod
    def exists(cls, record_id: str) -> bool:
        """Check if an entity exists."""
        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
            url_params=record_id,
        )
        return response is not None
