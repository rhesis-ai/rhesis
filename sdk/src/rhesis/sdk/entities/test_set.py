import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import pandas as pd
import requests
import tqdm
from jinja2 import Template
from pydantic import BaseModel

from rhesis.sdk.entities import BaseEntity
from rhesis.sdk.entities.base_entity import handle_http_errors
from rhesis.sdk.utils import count_tokens


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
    endpoint = "test_sets"

    #: :no-index: Cached list of tests for the test set
    tests: Optional[list[Any]] = None
    categories: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    test_count: Optional[int] = None

    def __init__(self, **fields: Any) -> None:
        """Initialize a TestSet instance.

        Args:
            **fields: Arbitrary keyword arguments representing test set fields.
        """
        super().__init__(**fields)

        self.name = fields.get("name", None)
        self.description = fields.get("description", None)
        self.short_description = fields.get("short_description", None)
        self.test_set_type = fields.get("test_set_type", "Single-Turn")  # Default to Single-Turn
        self.tests = fields.get("tests", None)
        self.metadata = fields.get("metadata", None)
        self.model = fields.get("model", None)

    @handle_http_errors
    def get_tests(self, **kwargs: Any) -> list[Any]:
        """Retrieve tests for the test set from the API.

        If tests are already cached, returns the cached version.
        Otherwise, fetches tests from the API.

        Args:
            **kwargs: Additional query parameters for the API request.

        Returns:
            list[Any]: A list of tests associated with the test set.
        """
        if self.tests is not None:
            return self.tests

        response = requests.get(
            self.client.get_url(f"{self.endpoint}/{self.id}/tests"),
            params=kwargs,
            headers=self.headers,
        )
        response.raise_for_status()
        return cast(list[Any], response.json())

    @handle_http_errors
    def load(self, format: str = "pandas") -> Union[pd.DataFrame, list[Any]]:
        """Load and format the test set tests.

        Fetches the test set data and its tests, then returns them in the specified format.

        Args:
            format (str, optional): The desired output format.
                Options are "pandas" or "dict". Defaults to "pandas".

        Returns:
            Union[pd.DataFrame, list[Any]]: The tests in the specified format.
                Returns a pandas DataFrame if format="pandas"
                or a list of dictionaries if format="dict".

        Raises:
            ValueError: If an invalid format is specified.
        """
        self.fetch()
        tests = self.get_tests()
        if tests is None:
            raise ValueError("Failed to fetch tests")
        self.tests = tests

        if format == "pandas":
            return pd.DataFrame(self.tests)
        elif format == "dict":
            return self.tests
        else:
            raise ValueError(f"Invalid format: {format}")

    @handle_http_errors
    def download(self, format: str = "csv", path: str = ".") -> bool:
        """Download the test set to a local file.

        Downloads the test set data and saves it to the specified path
        in the requested format.

        Args:
            format: The file format to download. Defaults to "csv".
            path: The path where the file should be saved.
                Can be a directory or a full file path. Defaults to current directory.

        Returns:
            bool: True if the download was successful.

        Note:
            The file will be named 'test_set_{id}.{format}' where id is the test set ID.
        """
        response = requests.get(
            self.client.get_url(f"{self.endpoint}/{self.id}/download"),
            headers=self.headers,
        )
        response.raise_for_status()

        # Get the directory path
        dir_path = os.path.dirname(path)

        # Only try to create directory if there's actually a directory path
        if dir_path:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

        file_path = os.path.join(path, f"test_set_{self.id}.{format}")
        with open(file_path, "wb") as f:
            f.write(response.content)
        return True

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

    def _update_from_response(self, response_data: dict) -> None:
        """Update instance fields from API response.

        Args:
            response_data: The response data from the API.
        """
        # Update general fields
        self.fields.update(response_data)

        # Update specific fields
        if "id" in response_data:
            self.fields["id"] = response_data["id"]
        if "name" in response_data:
            self.name = response_data["name"]
        if "description" in response_data:
            self.description = response_data["description"]
        if "short_description" in response_data:
            self.short_description = response_data["short_description"]
        if "test_set_type" in response_data:
            self.test_set_type = response_data["test_set_type"]

        # Handle metadata merging - ensure we merge rather than replace
        if "metadata" in response_data and response_data["metadata"]:
            if self.metadata is None:
                self.metadata = response_data["metadata"]
            else:
                # Merge metadata dictionaries, giving preference to new values in case of conflicts
                if isinstance(self.metadata, dict) and isinstance(response_data["metadata"], dict):
                    self.metadata.update(response_data["metadata"])
                else:
                    # If either is not a dict, just use the response value
                    self.metadata = response_data["metadata"]

    def upload(self) -> None:
        """Upload a new test set to the API.

        Uploads the test set data to the /test_set/bulk endpoint to create
        a test set with multiple tests in a single operation. This method
        is only for test sets that do not yet exist in the database.

        Returns:
            None: Updates the current TestSet instance with the server response.

        Raises:
            ValueError: If the test set already has an ID.
            requests.exceptions.HTTPError: If the API request fails.
        """
        # Check if the test set already has an ID
        if self.id is not None:
            raise ValueError(
                "Cannot upload test set: test set already has an ID. "
                "This test set already exists in the database."
            )

        # Prepare test set data
        test_set = self._prepare_test_set_data()
        if self.tests is None:
            raise ValueError("Tests cannot be None")
        test_count = len(self.tests)

        try:
            # Show progress indicator during the request
            with tqdm.tqdm(
                total=100, desc=f"Uploading test set with {test_count} tests", unit="%"
            ) as pbar:
                pbar.update(10)  # Start with 10% for initialization

                # Send request
                response = requests.post(
                    self.client.get_url("test_sets/bulk"),
                    json=test_set,
                    headers=self.headers,
                )
                pbar.update(40)  # 50% after sending

                # Process response
                response.raise_for_status()
                pbar.update(40)  # 90% after receiving response

                # Update from response
                self._update_from_response(response.json())
                pbar.update(10)  # 100% complete

            # Print success message
            print(f"☑️ Successfully uploaded test set with ID: {self.id}")
            print(f" - Name: {self.name}")
            print(f" - Tests: {test_count}")

        except requests.exceptions.HTTPError as e:
            error_msg = f"Error uploading test set: {str(e)}"
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    if "message" in error_data:
                        error_msg = f"Error: {error_data['message']}"
                except ValueError:
                    pass
            print(f"✗ {error_msg}")
            raise
        except Exception as e:
            print(f"✗ Unexpected error: {str(e)}")
            raise

    def update(self) -> None:
        if not self.exists(self.id):
            raise ValueError(f"Cannot update test set: test set with id {self.id} does not exist")

    def _validate_update(self) -> None:
        if not isinstance(self.fields.get("created_at"), datetime):
            raise ValueError("Cannot update test set: created_at must be a datetime object")

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
