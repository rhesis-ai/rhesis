from typing import Any, Dict, Optional

from pydantic import BaseModel, model_validator

from rhesis.sdk.clients import APIClient, Endpoints, Methods
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
    # Convenience fields that build test_configuration if not provided
    goal: Optional[str] = None
    instructions: Optional[str] = None
    restrictions: Optional[str] = None
    scenario: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def build_test_configuration(cls, data: Any) -> Any:
        """Build test_configuration from separate fields if not already provided.

        This allows users to provide goal, instructions, restrictions, and scenario
        as separate fields instead of constructing TestConfiguration manually.
        """
        if not isinstance(data, dict):
            return data

        # If test_configuration already provided, use it and remove separate fields
        if "test_configuration" in data and data["test_configuration"] is not None:
            # Remove the separate fields if they exist
            for field in ["goal", "instructions", "restrictions", "scenario"]:
                data.pop(field, None)
            return data

        # Build test_configuration from separate fields if goal is provided
        goal = data.get("goal")
        if goal:
            config_data = {
                "goal": goal,
                "instructions": data.get("instructions", ""),
                "restrictions": data.get("restrictions", ""),
                "scenario": data.get("scenario", ""),
            }
            data["test_configuration"] = config_data
            # Remove the separate fields
            for field in ["goal", "instructions", "restrictions", "scenario"]:
                data.pop(field, None)

        return data

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

        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params="execute",
            data=data,
        )


class Tests(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Test
