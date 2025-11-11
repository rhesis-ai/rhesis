from pathlib import Path
from typing import ClassVar, Dict, Optional

from jinja2 import Template
from pydantic import BaseModel

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities import BaseEntity
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.test import Test
from rhesis.sdk.utils import count_tokens

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
    test_count: Optional[int] = None
    name: str
    description: str
    short_description: str
    metadata: Optional[dict] = None

    def count_tokens(self, encoding_name: str = "cl100k_base") -> Dict[str, int]:
        """Count tokens for all prompts in the test set.

        Args:
            encoding_name: The name of the encoding to use. Defaults to cl100k_base
                          (used by GPT-4 and GPT-3.5-turbo)

        Returns:
            Dict[str, int]: A dictionary containing token statistics
        """
        # Ensure prompts are loaded
        if self.tests is None:
            self.get_tests()

        if not self.tests:
            return {
                "total": 0,
                "average": 0,
                "max": 0,
                "min": 0,
                "test_count": 0,
            }

        # Count tokens for each prompt's content
        token_counts = []
        for test in self.tests:
            content = test.get("content", "")
            if not isinstance(content, str):
                continue

            token_count = count_tokens(content, encoding_name)
            if token_count is not None:
                token_counts.append(token_count)

        if not token_counts:
            return {
                "total": 0,
                "average": 0,
                "max": 0,
                "min": 0,
                "test_count": 0,
            }

        return {
            "total": sum(token_counts),
            "average": int(round(sum(token_counts) / len(token_counts))),
            "max": max(token_counts),
            "min": min(token_counts),
            "test_count": len(token_counts),
        }

    def set_properties(self) -> None:
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

        response = self.model.generate(formatted_prompt, schema=TestSetProperties)
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
