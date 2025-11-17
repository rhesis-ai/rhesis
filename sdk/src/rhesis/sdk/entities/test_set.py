from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

from jinja2 import Template
from pydantic import BaseModel

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.entities import BaseEntity, Endpoint
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import handle_http_errors
from rhesis.sdk.entities.test import Test
from rhesis.sdk.models.base import BaseLLM

ENDPOINT = Endpoints.TEST_SETS


class TestSetProperties(BaseModel):
    name: str
    description: str
    short_description: str


class TestSet(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT

    id: Optional[str] = None
    tests: Optional[list[Test]] = None
    categories: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    behaviors: Optional[list[str]] = None
    test_count: Optional[int] = None
    name: str
    description: str
    short_description: str
    metadata: Optional[dict] = None

    @handle_http_errors
    def execute(self, endpoint: Endpoint) -> Optional[Dict[str, Any]]:
        """Execute the test set against the given endpoint.

        This method sends a request to the Rhesis backend to execute all tests
        in the test set against the specified endpoint.

        Args:
            endpoint: The endpoint to execute tests against

        Returns:
            Dict containing the execution results, or None if error occurred.

        Raises:
            ValueError: If test set ID is not set
            requests.exceptions.HTTPError: If the API request fails

        Example:
            >>> test_set = TestSet(id='test-set-123')
            >>> test_set.fetch()
            >>> result = test_set.execute(endpoint=Endpoint.TESTS)
            >>> print(result)
        """
        if not self.id:
            raise ValueError("Test set ID must be set before executing")

        client = Client()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/execute/{endpoint.id}",
        )

    def set_properties(self, model: BaseLLM) -> None:
        """Set test set attributes using LLM based on categories and topics in tests.

        This method:
        1. Gets the unique categories and topics from tests
        2. Uses the LLM service to generate appropriate name, description, and short description
        3. Updates the test set's attributes

        Example:
            >>> test_set = TestSet(id='123')
            >>> test_set.set_properties()
            >>> print(f"Name: {test_set.name}")
            >>> print(f"Description: {test_set.description}")
        """
        # Ensure tests are loaded
        if self.tests is None:
            self.get_tests()

        # Get unique categories and topics
        categories = set()
        topics = set()
        if self.tests is not None:
            for test in self.tests:
                if isinstance(test, dict):
                    if "category" in test and test["category"]:
                        categories.add(test["category"])
                    if "topic" in test and test["topic"]:
                        topics.add(test["topic"])

        # Load the prompt template
        prompt_path = (
            Path(__file__).parent.parent / "synthesizers" / "assets" / "test_set_properties.md"
        )
        with open(prompt_path, "r") as f:
            template = Template(f.read())

        # Format the prompt
        formatted_prompt = template.render(
            topics=sorted(list(topics)), categories=sorted(list(categories))
        )

        # Get response from LLLM

        response = model.generate(formatted_prompt, schema=TestSetProperties)
        # Update test set attributes
        if isinstance(response, dict):
            self.name = response.get("name")
            self.description = response.get("description")
            self.short_description = response.get("short_description")
            self.categories = sorted(list(categories))
            self.topics = sorted(list(topics))
            self.test_count = len(self.tests) if self.tests is not None else 0
        else:
            raise ValueError("LLM response was not in the expected format")


class TestSets(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestSet


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv("/Users/arek/Desktop/rhesis/.env", override=True)
    endpoint = Endpoint(id="be95b292-c3a9-42b9-a74d-142b28f0b9f0")

    test_set = TestSets.pull("13af7c23-4e43-4257-b402-1ebae66de390")
    test_set.execute(endpoint)
