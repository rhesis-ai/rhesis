import base64
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_serializer

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.enums import TestType

ENDPOINT = Endpoints.TESTS


class TestConfiguration(BaseModel):
    goal: str
    instructions: str = ""  # Optional - how Penelope should conduct the test
    restrictions: str = ""  # Optional - forbidden behaviors for the target
    scenario: str = ""  # Optional - contextual framing for the test


class Test(BaseEntity):
    endpoint = ENDPOINT

    category: Optional[str] = None
    topic: Optional[str] = None
    behavior: Optional[str] = None
    prompt: Optional[Prompt] = None
    metadata: dict = {}
    id: Optional[str] = None
    test_configuration: Optional[TestConfiguration] = None
    test_type: Optional[TestType] = None
    # Binary content for image tests (MIME type stored in metadata.binary_mime_type)
    # Uses serialization_alias to rename to test_binary_base64 for API transport
    test_binary: Optional[bytes] = Field(default=None, serialization_alias="test_binary_base64")

    @field_serializer("test_binary", when_used="always")
    @classmethod
    def serialize_test_binary(cls, value: Optional[bytes]) -> Optional[str]:
        """Serialize test_binary to base64 string for API transport."""
        if value is None:
            return None
        return base64.b64encode(value).decode("utf-8")

    @handle_http_errors
    def execute(self, endpoint: Endpoint) -> Optional[Dict[str, Any]]:
        """Execute the test against the given endpoint.

        Args:
            endpoint: The endpoint to execute the test against

        Returns:
            Dict containing the execution results, or None if error occurred.

        Example:
            >>> test = Test(id='test-123')
            >>> endpoint = Endpoint(id='endpoint-123')
            >>> result = test.execute(endpoint=endpoint)
        """
        if not endpoint.id:
            raise ValueError("Endpoint ID must be set before executing")

        if not self.id:
            raise ValueError("Test ID must be set before executing")

        data: Dict[str, Any] = {
            "test_id": self.id,
            "endpoint_id": endpoint.id,
            "evaluate_metrics": True,
        }

        client = Client()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params="execute",
            data=data,
        )


class Tests(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Test
