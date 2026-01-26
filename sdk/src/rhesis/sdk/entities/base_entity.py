import csv
import functools
import logging
from typing import Any, Callable, ClassVar, Dict, Optional, TypeVar

import requests
from pydantic import BaseModel, ConfigDict

from rhesis.sdk.clients import APIClient, Endpoints, HTTPStatus, Methods

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


class BaseEntity(BaseModel):
    """Base class for API entity interactions.

    This class provides basic CRUD operations for interacting with REST API endpoints.
    It handles authentication and common HTTP operations.

    Attributes:
        client (Client): The Rhesis API client instance
        headers (Dict[str, str]): HTTP headers for API requests.
    """

    model_config = ConfigDict(validate_assignment=True)

    endpoint: ClassVar[Endpoints]
    _push_required_fields: ClassVar[tuple[str, ...]] = ()

    def __str__(self) -> str:
        """Return a string representation of the entity."""
        string = self.model_dump_json(indent=2)
        print(type(string))
        return string

    @classmethod
    def _delete(cls, id: str) -> bool:
        """Delete the entity from the database."""
        client = APIClient()
        try:
            client.send_request(
                endpoint=cls.endpoint,
                method=Methods.DELETE,
                url_params=id,
            )
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                return False
            else:
                raise e

    @classmethod
    def _update(cls, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Push the entity to the database."""
        client = APIClient()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.PUT,
            url_params=id,
            data=data,
        )
        return response

    @classmethod
    def _create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        client = APIClient()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.POST,
            data=data,
        )
        return response

    @classmethod
    def _pull(cls, id: str) -> Dict[str, Any]:
        """Pull entity data from the database and validate against schema."""
        client = APIClient()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
            url_params=id,
        )
        # Validate response using Pydantic - automatically filters fields not in schema
        validated_instance = cls.model_validate(response)
        return validated_instance.model_dump(mode="json")

    def _validate_push_requirements(self) -> None:
        """Validate that required fields for push are set.

        Raises:
            ValueError: If any required field is None or empty.
        """
        if not self._push_required_fields:
            return

        missing = [
            field for field in self._push_required_fields if getattr(self, field, None) is None
        ]
        if missing:
            raise ValueError(f"Required fields for push: {', '.join(missing)}")

    def push(self) -> Optional[Dict[str, Any]]:
        """Save the entity to the database."""
        self._validate_push_requirements()
        data = self.model_dump(mode="json")

        if "id" in data and data["id"] is not None:
            response = self._update(data["id"], data)

        else:
            response = self._create(data)
            self.id = response["id"]

        return response

    def pull(self) -> "BaseEntity":
        """Pull the entity from the database and update this instance.

        Returns:
            BaseEntity: Returns self for method chaining.
        """
        data = self.model_dump(mode="json")
        if "id" not in data or data["id"] is None:
            raise ValueError("Entity has no ID")

        pulled_data = self._pull(data["id"])
        # Update self with validated data (already filtered by _pull)
        for field, value in pulled_data.items():
            setattr(self, field, value)

        return self

    def delete(self) -> bool:
        """Delete the entity from the database."""
        data = self.model_dump(mode="json")
        if "id" not in data or data["id"] is None:
            raise ValueError("Entity has no ID")

        return self._delete(data["id"])

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entity to a dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseEntity":
        """Create an entity from a dictionary."""
        return cls(**data)

    def to_csv(self, filename: str) -> None:
        """Write the entity to a CSV file (header + data row).

        Args:
            filename: Path to write the CSV file.
        """
        data = self.model_dump(mode="json")
        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)

    @classmethod
    def from_csv(cls, filename: str) -> "BaseEntity":
        """Create an entity from a CSV file.

        Args:
            filename: Path to the CSV file to read.

        Returns:
            An instance of the entity populated with data from the first row.
        """
        with open(filename, "r", newline="") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        return cls(**row)
