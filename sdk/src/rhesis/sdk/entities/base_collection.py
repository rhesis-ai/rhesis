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
    def pull(cls, id: Optional[str] = None, name: Optional[str] = None) -> T:
        """Pull entity data from the platform by ID or name.

        Either 'id' or 'name' must be provided.

        Args:
            id: The ID of the entity to pull
            name: The name of the entity to pull (case-insensitive)

        Returns:
            T: An instance of the entity class

        Raises:
            ValueError: If neither id nor name is provided, or if name matches multiple entities
        """
        if not id and not name:
            raise ValueError("Either id or name must be provided")

        client = Client()

        if id:
            response = client.send_request(
                endpoint=cls.endpoint,
                method=Methods.GET,
                url_params=id,
            )
        else:
            # name is guaranteed to be not None here due to the check above
            assert name is not None
            response = client.send_request(
                endpoint=cls.endpoint,
                method=Methods.GET,
                params={"$filter": f"tolower(name) eq '{name.lower()}'"},
            )
            if isinstance(response, list):
                if len(response) == 0:
                    raise ValueError(f"No entity found with name '{name}'")
                if len(response) > 1:
                    # Extract IDs from the matching entities to help the user
                    matching_ids = [item.get("id") for item in response if "id" in item]
                    ids_message = (
                        f" Matching entity IDs: {', '.join(map(str, matching_ids))}"
                        if matching_ids
                        else ""
                    )
                    raise ValueError(
                        f"More than one entity found with name '{name}'. "
                        f"Entity names must be unique. "
                        f"Please use the entity id instead.{ids_message}"
                    )
                response = response[0]

        # Validate response using Pydantic - automatically filters fields not in the schema
        validated_instance = cls.entity_class.model_validate(response)
        return validated_instance

    @classmethod
    def exists(cls, id: str) -> bool:
        """Check if an entity exists."""
        client = Client()
        try:
            response = client.send_request(
                endpoint=cls.endpoint,
                method=Methods.GET,
                url_params=id,
            )
            return response is not None
        except HTTPError as e:
            # Get the HTTP status code
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                return False
            else:
                raise e
