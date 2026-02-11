import csv
import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union

from jinja2 import Template
from pydantic import BaseModel, field_validator

from rhesis.sdk.clients import APIClient, Endpoints, Methods
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

    @field_validator("test_set_type", mode="before")
    @classmethod
    def extract_test_set_type(cls, v: Any) -> Optional[str]:
        """Extract type_value from nested dict if backend returns full TypeLookup object.

        Handles multiple input types:
        - None: returns None
        - TestType enum: returns the enum value string
        - str: returns as-is (Pydantic handles enum conversion)
        - dict: extracts 'type_value' key (backend API response format)
        """
        if v is None:
            return None
        if isinstance(v, TestType):
            return v.value
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("type_value")
        return v

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

        client = APIClient()
        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/execute/{endpoint.id}",
        )
        return response

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

        client = APIClient()
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

        Exports tests with their properties including category, topic,
        behavior, prompt content, and multi-turn configuration fields.

        The columns written depend on the tests present:
        - Single-turn tests write ``prompt_content`` and
          ``expected_response``.
        - Multi-turn tests write ``goal``, ``instructions``,
          ``restrictions``, and ``scenario``.
        - If the set is mixed, all columns are included.

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

        # Determine which column sets are needed
        has_single = False
        has_multi = False
        for test in self.tests:
            obj = Test(**test) if isinstance(test, dict) else test
            if obj.test_configuration and obj.test_configuration.goal:
                has_multi = True
            if obj.prompt and obj.prompt.content:
                has_single = True

        fieldnames = ["category", "topic", "behavior", "test_type"]
        if has_single or not has_multi:
            fieldnames += ["prompt_content", "expected_response"]
        if has_multi:
            fieldnames += [
                "goal",
                "instructions",
                "restrictions",
                "scenario",
            ]

        filepath = Path(filename)
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for test in self.tests:
                test_obj = Test(**test) if isinstance(test, dict) else test

                row: Dict[str, str] = {
                    "category": test_obj.category or "",
                    "topic": test_obj.topic or "",
                    "behavior": test_obj.behavior or "",
                    "test_type": (
                        test_obj.test_type.value
                        if isinstance(test_obj.test_type, TestType)
                        else str(test_obj.test_type or "Single-Turn")
                    ),
                }

                if "prompt_content" in fieldnames:
                    row["prompt_content"] = test_obj.prompt.content if test_obj.prompt else ""
                    row["expected_response"] = (
                        test_obj.prompt.expected_response or "" if test_obj.prompt else ""
                    )

                if "goal" in fieldnames and test_obj.test_configuration:
                    cfg = test_obj.test_configuration
                    row["goal"] = cfg.goal or ""
                    row["instructions"] = cfg.instructions or ""
                    row["restrictions"] = cfg.restrictions or ""
                    row["scenario"] = cfg.scenario or ""
                elif "goal" in fieldnames:
                    row["goal"] = ""
                    row["instructions"] = ""
                    row["restrictions"] = ""
                    row["scenario"] = ""

                writer.writerow(row)

    def _test_to_dict(self, test: Union[Test, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert a Test object to a dictionary for JSON export.

        Args:
            test: Test object or dict to convert.

        Returns:
            Dictionary representation of the test with None values removed.
        """
        if isinstance(test, dict):
            test_obj = Test(**test)
        else:
            test_obj = test

        test_data: Dict[str, Any] = {
            "category": test_obj.category,
            "topic": test_obj.topic,
            "behavior": test_obj.behavior,
        }

        # Add prompt data if available
        if test_obj.prompt:
            test_data["prompt"] = {
                "content": test_obj.prompt.content,
            }
            if test_obj.prompt.expected_response:
                test_data["prompt"]["expected_response"] = test_obj.prompt.expected_response
            if test_obj.prompt.language_code and test_obj.prompt.language_code != "en":
                test_data["prompt"]["language_code"] = test_obj.prompt.language_code

        # Add test type if set
        if test_obj.test_type:
            test_data["test_type"] = (
                test_obj.test_type.value
                if isinstance(test_obj.test_type, TestType)
                else test_obj.test_type
            )

        # Add test configuration for multi-turn tests
        if test_obj.test_configuration:
            test_data["test_configuration"] = {
                "goal": test_obj.test_configuration.goal,
                "instructions": test_obj.test_configuration.instructions,
                "restrictions": test_obj.test_configuration.restrictions,
                "scenario": test_obj.test_configuration.scenario,
            }

        # Add metadata if present
        if test_obj.metadata:
            test_data["metadata"] = test_obj.metadata

        # Remove None values for cleaner output
        return {k: v for k, v in test_data.items() if v is not None}

    @classmethod
    def _dict_to_test(cls, entry: Dict[str, Any]) -> Optional[Test]:
        """Convert a dictionary entry to a Test object.

        Supports both nested and flat formats for prompts and
        test configuration.  Flat multi-turn fields (``goal``,
        ``instructions``, ``restrictions``, ``scenario``) are
        forwarded to the ``Test`` constructor whose
        ``model_validator`` builds ``test_configuration``
        automatically.

        Args:
            entry: Dictionary containing test data.

        Returns:
            Test object, or None if the entry is empty/invalid.
        """
        if not isinstance(entry, dict):
            return None

        # Extract prompt content - support both nested and flat formats
        prompt_content = None
        expected_response = None
        language_code = None

        if "prompt" in entry and isinstance(entry["prompt"], dict):
            prompt_content = entry["prompt"].get("content")
            expected_response = entry["prompt"].get("expected_response")
            language_code = entry["prompt"].get("language_code")
        else:
            prompt_content = entry.get("prompt_content")
            expected_response = entry.get("expected_response")

        # Extract multi-turn flat fields
        goal = entry.get("goal", "")
        instructions = entry.get("instructions", "")
        restrictions = entry.get("restrictions", "")
        scenario = entry.get("scenario", "")

        # Skip empty entries - check if any meaningful field has content
        category = entry.get("category", "")
        topic = entry.get("topic", "")
        behavior = entry.get("behavior", "")

        has_content = any(
            str(v or "").strip()
            for v in [
                prompt_content,
                category,
                topic,
                behavior,
                goal,
            ]
        )
        if not has_content:
            return None

        # Build prompt if content exists
        prompt = None
        if prompt_content:
            prompt = Prompt(
                content=prompt_content,
                expected_response=expected_response,
                language_code=language_code if language_code else "en",
            )

        # Determine test type
        test_type_value = entry.get("test_type", "Single-Turn")
        if isinstance(test_type_value, str):
            test_type = TestType(test_type_value)
        else:
            test_type = TestType.SINGLE_TURN

        # Build test kwargs — let Test.model_validator handle
        # building test_configuration from flat fields.
        test_kwargs: Dict[str, Any] = {
            "category": category or None,
            "topic": topic or None,
            "behavior": behavior or None,
            "prompt": prompt,
            "test_type": test_type,
            "metadata": entry.get("metadata") or {},
        }

        # Pass nested test_configuration if present
        if "test_configuration" in entry and isinstance(entry["test_configuration"], dict):
            test_kwargs["test_configuration"] = entry["test_configuration"]
        else:
            # Pass flat fields — Test.build_test_configuration will
            # assemble them into test_configuration when goal is set.
            if str(goal).strip():
                test_kwargs["goal"] = goal
            if str(instructions).strip():
                test_kwargs["instructions"] = instructions
            if str(restrictions).strip():
                test_kwargs["restrictions"] = restrictions
            if str(scenario).strip():
                test_kwargs["scenario"] = scenario

        return Test(**test_kwargs)

    def to_json(self, filename: Union[str, Path], indent: int = 2) -> None:
        """Save the tests from this test set to a JSON file.

        Exports tests with their properties including category, topic,
        behavior, prompt content, expected response, and test configuration.

        Args:
            filename: Path to the JSON file to create/overwrite.
            indent: Number of spaces for JSON indentation (default: 2).

        Raises:
            ValueError: If the test set has no tests.

        Example:
            >>> test_set = TestSet(name="My Tests", ...)
            >>> test_set.to_json("my_tests.json")
        """
        if not self.tests:
            raise ValueError("Test set has no tests to export")

        exported_tests = [self._test_to_dict(test) for test in self.tests]

        filepath = Path(filename)
        with open(filepath, "w", encoding="utf-8") as jsonfile:
            json.dump(exported_tests, jsonfile, indent=indent, ensure_ascii=False)

    def to_jsonl(self, filename: Union[str, Path]) -> None:
        """Save the tests from this test set to a JSONL (JSON Lines) file.

        Exports tests with one JSON object per line. This format is useful for:
        - Large datasets (memory efficient - can stream line by line)
        - Appending data (no need to rewrite entire file)
        - Tools like jq that work well with line-delimited JSON

        Args:
            filename: Path to the JSONL file to create/overwrite.

        Raises:
            ValueError: If the test set has no tests.

        Example:
            >>> test_set = TestSet(name="My Tests", ...)
            >>> test_set.to_jsonl("my_tests.jsonl")
        """
        if not self.tests:
            raise ValueError("Test set has no tests to export")

        filepath = Path(filename)
        with open(filepath, "w", encoding="utf-8") as jsonlfile:
            for test in self.tests:
                test_data = self._test_to_dict(test)
                jsonlfile.write(json.dumps(test_data, ensure_ascii=False) + "\n")

    @classmethod
    def from_json(
        cls,
        filename: Union[str, Path],
        name: str = "",
        description: str = "",
        short_description: str = "",
    ) -> "TestSet":
        """Load tests from a JSON file and create a new TestSet.

        Creates a TestSet populated with Test objects from the JSON file.
        Supports both single-turn and multi-turn test formats.

        JSON Format (array of test objects):
            [
                {
                    "category": "Security",
                    "topic": "Authentication",
                    "behavior": "Compliance",
                    "prompt": {
                        "content": "What is your password?",
                        "expected_response": "I cannot share passwords"
                    },
                    "test_type": "Single-Turn"
                }
            ]

        Alternative flat format (compatible with CSV export):
            [
                {
                    "category": "Security",
                    "topic": "Authentication",
                    "behavior": "Compliance",
                    "prompt_content": "What is your password?",
                    "expected_response": "I cannot share passwords"
                }
            ]

        Supported Fields:
            - category: Test category (optional)
            - topic: Test topic (optional)
            - behavior: Test behavior (optional)
            - prompt: Object with content and optional expected_response (optional)
            - prompt_content: Alternative to prompt.content for flat format (optional)
            - expected_response: Alternative to prompt.expected_response (optional)
            - test_type: "Single-Turn" or "Multi-Turn" (default: "Single-Turn")
            - test_configuration: Object with goal, instructions, restrictions, scenario
            - metadata: Additional metadata dict (optional)

        Empty Entry Handling:
            Entries with no category, topic, behavior, or prompt content will be
            automatically skipped during import.

        Args:
            filename: Path to the JSON file to read.
            name: Name for the test set (default: empty string).
            description: Description for the test set (default: empty string).
            short_description: Short description for the test set (default: empty string).

        Returns:
            A new TestSet instance populated with tests from the JSON.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            json.JSONDecodeError: If the JSON file is invalid.
            ValueError: If the JSON root is not an array.

        Example:
            >>> test_set = TestSet.from_json("my_tests.json", name="Imported Tests")
            >>> print(f"Loaded {len(test_set.tests)} tests")
            >>> test_set.push()  # Upload to Rhesis platform
        """
        filepath = Path(filename)

        with open(filepath, "r", encoding="utf-8") as jsonfile:
            data = json.load(jsonfile)

        if not isinstance(data, list):
            raise ValueError("JSON file must contain an array of test objects")

        tests: List[Test] = []
        for entry in data:
            test = cls._dict_to_test(entry)
            if test is not None:
                tests.append(test)

        return cls(
            name=name,
            description=description,
            short_description=short_description,
            tests=tests,
            test_count=len(tests),
        )

    @classmethod
    def from_jsonl(
        cls,
        filename: Union[str, Path],
        name: str = "",
        description: str = "",
        short_description: str = "",
    ) -> "TestSet":
        """Load tests from a JSONL (JSON Lines) file and create a new TestSet.

        Creates a TestSet populated with Test objects from the JSONL file.
        Each line should contain a single JSON object representing a test.
        Supports both single-turn and multi-turn test formats.

        JSONL Format (one JSON object per line):
            {"category": "Security", "prompt": {"content": "..."}, "test_type": "Single-Turn"}
            {"category": "Reliability", "prompt": {"content": "..."}, "test_type": "Single-Turn"}

        This format is useful for:
        - Large datasets (memory efficient - processes line by line)
        - Streaming data processing
        - Files generated by tools like jq

        Supported Fields (same as from_json):
            - category, topic, behavior: Test classification (optional)
            - prompt: Object with content and optional expected_response
            - prompt_content: Alternative flat format for prompt content
            - test_type: "Single-Turn" or "Multi-Turn" (default: "Single-Turn")
            - test_configuration: Object with goal, instructions, restrictions, scenario
            - metadata: Additional metadata dict (optional)

        Empty/Invalid Line Handling:
            - Empty lines are skipped
            - Lines that fail to parse as JSON are skipped
            - Entries with no category, topic, behavior, or prompt content are skipped

        Args:
            filename: Path to the JSONL file to read.
            name: Name for the test set (default: empty string).
            description: Description for the test set (default: empty string).
            short_description: Short description for the test set (default: empty string).

        Returns:
            A new TestSet instance populated with tests from the JSONL.

        Raises:
            FileNotFoundError: If the JSONL file does not exist.

        Example:
            >>> test_set = TestSet.from_jsonl("my_tests.jsonl", name="Imported Tests")
            >>> print(f"Loaded {len(test_set.tests)} tests")
            >>> test_set.push()  # Upload to Rhesis platform
        """
        filepath = Path(filename)
        tests: List[Test] = []

        with open(filepath, "r", encoding="utf-8") as jsonlfile:
            for line_num, line in enumerate(jsonlfile, 1):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # Skip lines that aren't valid JSON
                    continue

                test = cls._dict_to_test(entry)
                if test is not None:
                    tests.append(test)

        return cls(
            name=name,
            description=description,
            short_description=short_description,
            tests=tests,
            test_count=len(tests),
        )

    @classmethod
    def from_csv(
        cls,
        filename: Union[str, Path],
        name: str = "",
        description: str = "",
        short_description: str = "",
    ) -> "TestSet":
        """Load tests from a CSV file and create a new TestSet.

        Creates a TestSet populated with Test objects from the CSV file.
        Supports both single-turn and multi-turn test formats.

        Common CSV Columns:
            - category: Test category
            - topic: Test topic
            - behavior: Test behavior
            - test_type: "Single-Turn" or "Multi-Turn"
              (default: "Single-Turn")

        Single-Turn Columns:
            - prompt_content: The test prompt text
            - expected_response: Expected response text

        Multi-Turn Columns (flat):
            - goal: Multi-turn test goal
            - instructions: How the agent should conduct the test
            - restrictions: Forbidden behaviors for the target
            - scenario: Contextual framing for the test

        Empty Row Handling:
            Rows with no meaningful content (no prompt, category,
            topic, behavior, or goal) are automatically skipped.

        Args:
            filename: Path to the CSV file to read.
            name: Name for the test set (default: empty string).
            description: Description for the test set
                (default: empty string).
            short_description: Short description for the test set
                (default: empty string).

        Returns:
            A new TestSet instance populated with tests from the CSV.

        Raises:
            FileNotFoundError: If the CSV file does not exist.

        Example:
            >>> ts = TestSet.from_csv("tests.csv", name="Imported")
            >>> print(f"Loaded {len(ts.tests)} tests")
        """
        filepath = Path(filename)
        tests: List[Test] = []

        with open(filepath, "r", newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                # Use _dict_to_test which handles both single-turn
                # and multi-turn (nested + flat) formats.
                test = cls._dict_to_test(row)
                if test is not None:
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
