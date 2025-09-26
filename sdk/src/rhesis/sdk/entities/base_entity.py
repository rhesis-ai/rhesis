import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

import requests

from rhesis.sdk.client import Client, Methods

T = TypeVar("T")

logger = logging.getLogger(__name__)


def handle_http_errors(func: Callable[..., T]) -> Callable[..., Optional[T]]:
    """Decorator to handle HTTP errors in API requests."""

    @functools.wraps(func)
    def wrapper(self_or_cls: Any, *args: Any, **kwargs: Any) -> Optional[T]:
        try:
            return func(self_or_cls, *args, **kwargs)
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            # Handle potential string or bytes content
            content = e.response.content
            if isinstance(content, bytes):
                content = content.decode()
            logger.error(f"Response content: {content}")
            logger.error(f"Request URL: {e.response.request.url}")
            logger.error(f"Request method: {e.response.request.method}")
            logger.error(f"Request headers: {e.response.request.headers}")
            if e.response.request.body:
                body = e.response.request.body
                if isinstance(body, bytes):
                    body = body.decode()
                logger.error(f"Request body: {body}")
            return None

    return wrapper


class BaseEntity:
    """Base class for API entity interactions.

    This class provides basic CRUD operations for interacting with REST API endpoints.
    It handles authentication and common HTTP operations.

    Attributes:
        client (Client): The Rhesis API client instance
        headers (Dict[str, str]): HTTP headers for API requests.
    """

    endpoint: str
    fields: Dict[str, Any]

    def __init__(self, **fields: Any) -> None:
        """Initialize the entity with given fields.

        Args:
            **fields: Arbitrary keyword arguments representing entity fields.
        """
        self.fields = fields

    def __repr__(self) -> str:
        field_strings = []
        for key, value in self.fields.items():
            field_strings.append(f"{key}: {value}\n")
        return f"class_name: {self.__class__.__name__}\n{''.join(field_strings)}"

    @property
    def id(self) -> Optional[str]:
        """Get the entity's ID.

        Provides convenient access to the entity's ID without having to access
        the fields dictionary directly. This is the recommended way to get an
        entity's ID throughout the codebase.

        Returns:
            Optional[str]: The entity's ID if it exists, otherwise None.

        Example:
            >>> entity = BaseEntity(id="123")
            >>> print(entity.id)  # "123"
            >>> entity = BaseEntity()
            >>> print(entity.id)  # None
        """
        return self.fields.get("id")

    @handle_http_errors
    def save(self) -> Optional[Dict[str, Any]]:
        """Save the entity to the database."""
        client = Client()
        data = {k: v for k, v in self.fields.items() if k != "id"}

        if "id" in self.fields:
            response = client.send_request(
                endpoint=self.endpoint,
                method=Methods.PUT,
                url_params=self.fields["id"],
                data=data,
            )
            return response
        else:
            response = client.send_request(
                endpoint=self.endpoint,
                method=Methods.POST,
                data=data,
            )
            return response

    @handle_http_errors
    def delete(self, nano_id: str) -> bool:
        """Delete the entity from the database."""
        client = Client()
        try:
            client.send_request(
                endpoint=self.endpoint,
                method=Methods.DELETE,
                url_params=nano_id,
            )
            return True
        except requests.exceptions.HTTPError:
            return False

    @handle_http_errors
    def fetch(self) -> None:
        """Fetch the current entity's data from the API and update local fields."""
        client = Client()
        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=self.fields["id"],
        )
        self.fields.update(response)

    @classmethod
    def from_id(cls, record_id: str) -> Optional["BaseEntity"]:
        """Create an entity instance from a record ID."""
        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
            url_params=record_id,
        )
        return cls(**response)

    def update(self) -> None:
        """Update entity in database."""
        if not self.exists(self.fields["id"]):
            raise ValueError(
                f"Cannot update {self.__class__.__name__}: "
                f"entity with id {self.fields['id']} does not exist"
            )

    @handle_http_errors
    def get_by_id(cls, id: str) -> Dict[str, Any]:
        """Get entity by id."""
        entity_dict = cls.fields.get(id)
        if entity_dict is None:
            raise ValueError(
                f"Cannot get {cls.__class__.__name__}: "
                f"entity with id {id} does not exist in database"
            )
        return dict(entity_dict)
