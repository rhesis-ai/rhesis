from typing import Any, Dict, Generic, Optional, Type, TypeVar

from requests.exceptions import HTTPError

from rhesis.sdk.client import Client, Endpoints, HTTPStatus, Methods
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors

T = TypeVar("T", bound=BaseEntity)


class BaseCollection(Generic[T]):
    """Base class for API collection interactions.

    This class provides basic CRUD operations for interacting with REST API endpoints.
    It handles authentication and common HTTP operations.
    """

    endpoint: Endpoints
    entity_class: Type[T]

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
    @classmethod
    def first(cls) -> Optional[Dict[str, Any]]:
        """Retrieve the first record matching the query parameters."""
        records = cls.all()
        return records[0] if records else None

    @classmethod
    def pull(cls, record_id: str) -> T:
        """Pull entity data from the platform and return an instance of the entity class."""
        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
            url_params=record_id,
        )
        # Validate response using Pydantic - automatically filters fields not in schema
        validated_instance = cls.entity_class.model_validate(response)
        return validated_instance

    @classmethod
    def exists(cls, record_id: str) -> bool:
        """Check if an entity exists."""
        client = Client()
        try:
            response = client.send_request(
                endpoint=cls.endpoint,
                method=Methods.GET,
                url_params=record_id,
            )
            return response is not None
        except HTTPError as e:
            # Get the HTTP status code
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                return False
            else:
                raise e
