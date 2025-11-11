import functools
import logging
from typing import Any, Callable, ClassVar, Dict, Optional, TypeVar

import requests
from pydantic import BaseModel

from rhesis.sdk.client import Client, Endpoints, HTTPStatus, Methods

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

    endpoint: ClassVar[Endpoints]

    @classmethod
    def _delete_by_id(cls, id: str) -> bool:
        """Delete the entity from the database."""
        client = Client()
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
    def _push_by_id(cls, id: str, data: Dict[str, Any]) -> None:
        """Push the entity to the database."""
        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.PUT,
            url_params=id,
            data=data,
        )
        return response

    @classmethod
    def _push_without_id(cls, data: Dict[str, Any]) -> None:
        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.POST,
            data=data,
        )
        return response

    @classmethod
    def _pull_by_id(cls, id: str) -> None:
        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
            url_params=id,
        )
        return cls(**response)

    def push(self) -> Optional[Dict[str, Any]]:
        """Save the entity to the database."""
        data = self.model_dump(mode="json")

        if "id" in data and data["id"] is not None:
            response = self._push_by_id(data["id"], data)

            return response
        else:
            response = self._push_without_id(data)
            self.id = response["id"]

            return response

    def pull(self) -> None:
        """Pull the entity from the database."""
        data = self.model_dump(mode="json")
        if "id" not in data or data["id"] is None:
            raise ValueError("Entity has no ID")

        return self._pull_by_id(data["id"])

    def delete(self) -> bool:
        """Delete the entity from the database."""
        data = self.model_dump(mode="json")
        if "id" not in data or data["id"] is None:
            raise ValueError("Entity has no ID")

        return self._delete_by_id(data["id"])
