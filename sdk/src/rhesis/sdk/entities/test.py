from typing import Any, Dict, Optional

from pydantic import BaseModel

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
    metadata: Optional[dict] = {}
    id: Optional[str] = None
    test_configuration: Optional[TestConfiguration] = None
    test_type: Optional[TestType] = None

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
