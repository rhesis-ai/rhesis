from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, cast

import pandas as pd
from jinja2 import Template
from pydantic import BaseModel

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities import BaseEntity
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.utils import count_tokens

ENDPOINT = Endpoints.TEST_SETS


class TestSetProperties(BaseModel):
    name: str
    description: str
    short_description: str


class TestSet(BaseEntity):
    """A class representing a test set in the API.

    This class provides functionality to interact with test sets, including
    retrieving prompts, loading data in different formats, and downloading test sets.

    Examples:
        Create and load a test set:
        >>> test_set = TestSet(id='123')
        >>> df = test_set.load(format='pandas')  # Load as pandas DataFrame
        >>> prompts = test_set.load(format='dict')  # Load as list of dictionaries

        Get prompts directly:
        >>> prompts = test_set.get_prompts()
        >>> print(f"Number of prompts: {len(prompts)}")

        Download test set to local file:
        >>> # Download to current directory as CSV
        >>> test_set.download()
        >>> # Download to specific path as different format
        >>> test_set.download(format='json', path='data/my_test_set.json')
    """

    #: :no-index: The API endpoint for test sets
    endpoint: ClassVar[Endpoints] = ENDPOINT

    #: :no-index: Cached list of tests for the test set
    id: Optional[str] = None
    tests: Optional[list[Any]] = None
    categories: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    test_count: Optional[int] = None
    name: str
    description: str
    short_description: str
    metadata: Optional[dict] = None

    def _prepare_test_set_data(self) -> dict:
        """Prepare the test set data for upload.

        Returns:
            dict: The prepared test set data.
        """
        if not self.tests:
            raise ValueError("No tests to upload. Please add tests to the test set first.")

        return {
            "name": self.name,
            "description": self.description,
            "short_description": self.short_description,
            "test_set_type": self.test_set_type,
            "metadata": self.metadata,
            "tests": self.tests,
        }

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

    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert the test set tests to a list of dictionaries.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing test data
        """
        if self.tests is None:
            self.get_tests()
        if self.tests is None:  # Double-check after get_tests
            return []
        return cast(List[Dict[str, Any]], self.tests)

    def to_pandas(self) -> pd.DataFrame:
        """Convert the test set tests to a pandas DataFrame.

        Returns:
            pd.DataFrame: A DataFrame containing the test data

        Example:
            >>> test_set = TestSet(id='123')
            >>> df = test_set.to_pandas()
            >>> print(df.columns)
        """
        if self.tests is None:
            self.get_tests()
        return pd.DataFrame(self.tests)

    def to_csv(self, path: Optional[str] = None) -> pd.DataFrame:
        """Convert the test set tests to a CSV file.

        Args:
            path: The path where the CSV file should be saved.
                 If None, uses 'test_set_{id}.csv'

        Returns:
            pd.DataFrame: The DataFrame that was saved to CSV

        Example:
            >>> test_set = TestSet(id='123')
            >>> df = test_set.to_csv('my_test_set.csv')
        """
        df = self.to_pandas()

        if path is None:
            path = f"test_set_{self.id}.csv"

        df.to_csv(path, index=False)
        return df

    def get_properties(self) -> Dict[str, Any]:
        """Get the test set properties including basic info and test analysis.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - basic properties (name, description, short_description)
                - unique categories and topics from tests
                - total number of tests

        Example:
            >>> test_set = TestSet(id='123')
            >>> props = test_set.get_properties()
            >>> print(f"Categories: {props['categories']}")
            >>> print(f"Topics: {props['topics']}")
        """
        # Ensure tests are loaded
        if self.tests is None:
            self.get_tests()

        # Initialize sets for unique categories and topics
        categories = set()
        topics = set()

        # Extract unique categories and topics from tests
        if self.tests is not None:
            for test in self.tests:
                if isinstance(test, dict):
                    if "category" in test and test["category"]:
                        categories.add(test["category"])
                    if "topic" in test and test["topic"]:
                        topics.add(test["topic"])

        return {
            "name": self.name,
            "description": self.description,
            "short_description": self.short_description,
            "categories": sorted(list(categories)),
            "topics": sorted(list(topics)),
            "test_count": len(self.tests) if self.tests is not None else 0,
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
