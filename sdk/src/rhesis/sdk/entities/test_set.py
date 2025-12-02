import csv
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union

from jinja2 import Template
from pydantic import BaseModel

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.entities import BaseEntity, Endpoint
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import handle_http_errors
from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.entities.test import Test
from rhesis.sdk.enums import TestType
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
    test_set_type: Optional[TestType] = None
    metadata: dict = {}

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
            raise ValueError("Test set must have at least one test before setting properties")

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
            self.name = response["name"]
            self.description = response["description"]
            self.short_description = response["short_description"]
            self.categories = sorted(list(categories))
            self.topics = sorted(list(topics))
            self.test_count = len(self.tests) if self.tests is not None else 0
        else:
            raise ValueError("LLM response was not in the expected format")

    @classmethod
    def _create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a test set using the bulk endpoint.

        Args:
            data: Dictionary containing test set data including tests

        Returns:
            Dict containing the created test set data from the API

        Raises:
            ValueError: If tests are not provided
        """
        if not data.get("tests"):
            raise ValueError("Test set must have at least one test before creating")

        client = Client()
        response = client.send_request(
            endpoint=cls.endpoint,
            method=Methods.POST,
            url_params="bulk",
            data=data,
        )
        return response

    def push(self) -> Optional[Dict[str, Any]]:
        """Save the test set to the database.

        Uses the bulk endpoint to create test set with tests.

        Returns:
            Dict containing the response from the API, or None if error occurred.

        Example:
            >>> test_set = TestSet(
            ...     name="My Test Set",
            ...     description="Test set description",
            ...     short_description="Short desc",
            ...     tests=[test1, test2, test3]
            ... )
            >>> result = test_set.push()
            >>> print(f"Created test set with ID: {test_set.id}")
        """
        # mode="json": Ensures enums are serialized as strings instead of enum objects
        # exclude_none=True: Excludes None values so backend uses defaults
        data = self.model_dump(mode="json", exclude_none=True)

        response = self._create(data)
        if response and "id" in response:
            self.id = response["id"]

        return response

    def to_csv(self, filename: Union[str, Path]) -> None:
        """Save the tests from this test set to a CSV file.

        Exports single-turn tests with their properties including category, topic,
        behavior, and prompt content.

        Args:
            filename: Path to the CSV file to create/overwrite.

        Raises:
            ValueError: If the test set has no tests.

        Example:
            >>> test_set = TestSet(name="My Tests", ...)
            >>> test_set.to_csv("my_tests.csv")
        """
        if not self.tests:
            raise ValueError("Test set has no tests to export")

        fieldnames = [
            "category",
            "topic",
            "behavior",
            "prompt_content",
        ]

        filepath = Path(filename)
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for test in self.tests:
                if isinstance(test, dict):
                    test_obj = Test(**test)
                else:
                    test_obj = test

                row = {
                    "category": test_obj.category or "",
                    "topic": test_obj.topic or "",
                    "behavior": test_obj.behavior or "",
                    "prompt_content": test_obj.prompt.content if test_obj.prompt else "",
                }
                writer.writerow(row)

    @classmethod
    def from_csv(
        cls,
        filename: Union[str, Path],
        name: str = "",
        description: str = "",
        short_description: str = "",
    ) -> "TestSet":
        """Load single-turn tests from a CSV file and create a new TestSet.

        Creates a TestSet populated with Test objects from the CSV file.

        Required CSV Columns:
            - prompt_content: The test prompt text (required for valid tests)
            - category: Test category (required for valid tests)
            - topic: Test topic (required for valid tests)
            - behavior: Test behavior (required for valid tests)

        Optional CSV Columns:
            - test_type: Test type (defaults to "Single-Turn")
            - expected_response: Expected response text
            - Any other columns will be ignored

        Empty Row Handling:
            Rows with empty or whitespace-only values for all required fields
            (prompt_content, category, topic, behavior) will be automatically
            skipped during import.

        Args:
            filename: Path to the CSV file to read.
            name: Name for the test set (default: empty string).
            description: Description for the test set (default: empty string).
            short_description: Short description for the test set (default: empty string).

        Returns:
            A new TestSet instance populated with tests from the CSV.

        Raises:
            FileNotFoundError: If the CSV file does not exist.

        Example:
            >>> test_set = TestSet.from_csv("my_tests.csv", name="Imported Tests")
            >>> print(f"Loaded {len(test_set.tests)} tests")
        """
        filepath = Path(filename)
        tests: List[Test] = []

        with open(filepath, "r", newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                # Skip empty rows - check if any required field has content
                if not any(
                    [
                        row.get("prompt_content", "").strip(),
                        row.get("category", "").strip(),
                        row.get("topic", "").strip(),
                        row.get("behavior", "").strip(),
                    ]
                ):
                    continue  # Skip this empty row

                # Build prompt if content exists
                prompt = None
                if row.get("prompt_content"):
                    prompt = Prompt(
                        content=row["prompt_content"],
                        expected_response=row.get("expected_response"),
                    )

                test = Test(
                    category=row.get("category") or None,
                    topic=row.get("topic") or None,
                    behavior=row.get("behavior") or None,
                    prompt=prompt,
                    test_type=TestType.SINGLE_TURN,
                )
                tests.append(test)

        return cls(
            name=name,
            description=description,
            short_description=short_description,
            tests=tests,
            test_count=len(tests),
        )


class TestSets(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestSet
