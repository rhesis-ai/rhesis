import csv
import json
import logging
import uuid as uuid_mod
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
from rhesis.sdk.enums import ExecutionMode, TestType
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_metric_id(
        self,
        metric: Union[Dict[str, Any], str],
        client: Optional[APIClient] = None,
    ) -> str:
        """Resolve a single metric reference to an ID.

        Accepts:
            - A dict with an ``"id"`` key
            - A UUID string (used directly)
            - A metric name string (looked up via ``GET /metrics``)

        Args:
            metric: Metric reference (dict, UUID string, or name).
            client: Optional shared APIClient instance.
        """
        if isinstance(metric, dict):
            mid = metric.get("id")
            if not mid:
                raise ValueError("Metric dict must contain an 'id' key")
            return str(mid)

        metric_str = str(metric)

        # Check if it looks like a UUID
        try:
            uuid_mod.UUID(metric_str)
            return metric_str
        except ValueError:
            pass

        # Treat as a name – look up via the metrics endpoint
        if client is None:
            client = APIClient()
        results = client.send_request(
            endpoint=Endpoints.METRICS,
            method=Methods.GET,
            params={"$filter": f"name eq '{metric_str}'"},
        )
        if not results:
            raise ValueError(f"Metric not found: {metric_str}")

        items = results if isinstance(results, list) else [results]
        if not items:
            raise ValueError(f"Metric not found: {metric_str}")

        return str(items[0]["id"])

    def _resolve_metrics(self, metrics: List[Union[Dict[str, Any], str]]) -> List[Dict[str, Any]]:
        """Resolve a mixed list of metric dicts / name strings."""
        client = APIClient()
        resolved: List[Dict[str, Any]] = []
        for m in metrics:
            if isinstance(m, dict):
                resolved.append(m)
            else:
                metric_id = self._resolve_metric_id(m, client=client)
                resolved.append({"id": metric_id, "name": str(m)})
        return resolved

    def _resolve_run_id(self, run: Union[str, Any]) -> str:
        """Resolve a test run reference to an ID.

        Accepts a TestRun instance, a UUID string, or a test run name.
        """
        if hasattr(run, "id") and run.id:
            return str(run.id)

        run_str = str(run)

        try:
            uuid_mod.UUID(run_str)
            return run_str
        except ValueError:
            pass

        # Treat as a name
        from rhesis.sdk.entities.test_run import TestRuns

        resolved = TestRuns.pull(name=run_str)
        if resolved is None or not getattr(resolved, "id", None):
            raise ValueError(f"Test run not found: {run_str}")
        return str(resolved.id)

    def _build_execution_body(
        self,
        *,
        mode: Union[str, ExecutionMode] = ExecutionMode.PARALLEL,
        metrics: Optional[List[Union[Dict[str, Any], str]]] = None,
        reference_test_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the request body for the execute endpoint."""
        resolved_mode = ExecutionMode.from_string(mode)
        body: Dict[str, Any] = {
            "execution_options": {
                "execution_mode": resolved_mode.value,
            },
        }
        if metrics:
            body["metrics"] = self._resolve_metrics(metrics)
        if reference_test_run_id:
            body["reference_test_run_id"] = reference_test_run_id
        return body

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @handle_http_errors
    def execute(
        self,
        endpoint: Endpoint,
        *,
        mode: Union[str, ExecutionMode] = ExecutionMode.PARALLEL,
        metrics: Optional[List[Union[Dict[str, Any], str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute the test set against the given endpoint.

        Args:
            endpoint: The endpoint to execute tests against.
            mode: Execution mode – ``ExecutionMode.PARALLEL`` (default),
                ``ExecutionMode.SEQUENTIAL``, or ``"parallel"`` / ``"sequential"``.
            metrics: Optional list of metrics for this execution.
                Overrides test set and behavior metrics.  Each item
                can be a dict with ``"id"``, ``"name"``, and optional
                ``"scope"``; or a metric name string (resolved via
                the ``/metrics`` API).

        Returns:
            Dict containing the execution submission response, or
            ``None`` if an error occurred.

        Raises:
            ValueError: If test set ID is not set.

        Example:
            >>> test_set = TestSets.pull(name="Safety Tests")
            >>> endpoint = Endpoints.pull(name="GPT-4o")
            >>> result = test_set.execute(endpoint)
            >>> result = test_set.execute(endpoint, mode=ExecutionMode.SEQUENTIAL)
            >>> result = test_set.execute(endpoint, mode="sequential")
        """
        if not self.id:
            raise ValueError("Test set ID must be set before executing")

        body = self._build_execution_body(mode=mode, metrics=metrics)
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/execute/{endpoint.id}",
            data=body,
        )

    @handle_http_errors
    def rescore(
        self,
        endpoint: Endpoint,
        run: Optional[Union[str, Any]] = None,
        *,
        mode: Union[str, ExecutionMode] = ExecutionMode.PARALLEL,
        metrics: Optional[List[Union[Dict[str, Any], str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Re-score outputs from an existing test run.

        Re-evaluates metrics on stored outputs without calling the
        endpoint again.

        Args:
            endpoint: The endpoint the original run was executed
                against.
            run: The test run whose outputs to re-score.  Accepts:

                - A ``TestRun`` instance
                - A string test run ID (UUID)
                - A string test run name (resolved via
                  ``TestRuns`` collection)
                - ``None`` (default) – uses the latest completed run

            mode: Execution mode – ``ExecutionMode.PARALLEL`` (default),
                ``ExecutionMode.SEQUENTIAL``, or ``"parallel"`` / ``"sequential"``.
            metrics: Optional list of metrics for re-scoring.

        Returns:
            Dict containing the execution submission response, or
            ``None`` if an error occurred.

        Raises:
            ValueError: If test set ID is not set or no completed
                run is found when *run* is ``None``.

        Example:
            >>> test_set.rescore(endpoint)
            >>> test_set.rescore(endpoint, run="Safety - Run 42")
            >>> test_set.rescore(endpoint, metrics=["Accuracy"])
        """
        if not self.id:
            raise ValueError("Test set ID must be set before rescoring")

        if run is None:
            last = self.last_run(endpoint)
            if not last:
                raise ValueError("No completed test run found for this test set and endpoint")
            run_id = str(last["id"])
        else:
            run_id = self._resolve_run_id(run)

        body = self._build_execution_body(
            mode=mode,
            metrics=metrics,
            reference_test_run_id=run_id,
        )
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/execute/{endpoint.id}",
            data=body,
        )

    @handle_http_errors
    def last_run(self, endpoint: Endpoint) -> Optional[Dict[str, Any]]:
        """Get the most recent completed test run.

        Returns a summary dict for the latest completed run of this
        test set against the given endpoint, or ``None`` if no
        completed run exists.

        The dict contains: ``id``, ``nano_id``, ``name``, ``status``,
        ``created_at``, ``test_count``, and ``pass_rate``.

        Args:
            endpoint: The endpoint to look up the last run for.

        Raises:
            ValueError: If test set ID is not set.

        Example:
            >>> last = test_set.last_run(endpoint)
            >>> if last:
            ...     print(last["pass_rate"])
        """
        if not self.id:
            raise ValueError("Test set ID must be set before fetching last run")

        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/last-run/{endpoint.id}",
        )

    # ------------------------------------------------------------------
    # Test set metric management
    # ------------------------------------------------------------------

    @handle_http_errors
    def get_metrics(self) -> Optional[List[Dict[str, Any]]]:
        """Get metrics associated with this test set.

        Returns:
            A list of metric dicts, or an empty list if none are
            assigned.

        Raises:
            ValueError: If test set ID is not set.
        """
        if not self.id:
            raise ValueError("Test set ID must be set before fetching metrics")

        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/metrics",
        )

    @handle_http_errors
    def add_metric(self, metric: Union[Dict[str, Any], str]) -> Optional[List[Dict[str, Any]]]:
        """Add a metric to this test set.

        Args:
            metric: The metric to add.  Accepts a dict with an
                ``"id"`` key, a UUID string, or a metric name string
                (resolved via the ``/metrics`` API).

        Returns:
            The updated list of metrics on this test set.

        Raises:
            ValueError: If test set ID is not set or the metric
                cannot be resolved.
        """
        if not self.id:
            raise ValueError("Test set ID must be set before adding metrics")

        metric_id = self._resolve_metric_id(metric)
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/metrics/{metric_id}",
        )

    def add_metrics(
        self, metrics: List[Union[Dict[str, Any], str]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Add multiple metrics to this test set.

        Args:
            metrics: A list where each item can be a dict, UUID
                string, or metric name string.

        Returns:
            The updated list of metrics on this test set after all
            additions.
        """
        result = None
        for metric in metrics:
            result = self.add_metric(metric)
        return result

    @handle_http_errors
    def remove_metric(self, metric: Union[Dict[str, Any], str]) -> Optional[List[Dict[str, Any]]]:
        """Remove a metric from this test set.

        Accepts the same input types as :meth:`add_metric`.

        Returns:
            The updated list of metrics on this test set.

        Raises:
            ValueError: If test set ID is not set or the metric
                cannot be resolved.
        """
        if not self.id:
            raise ValueError("Test set ID must be set before removing metrics")

        metric_id = self._resolve_metric_id(metric)
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.DELETE,
            url_params=f"{self.id}/metrics/{metric_id}",
        )

    def remove_metrics(
        self, metrics: List[Union[Dict[str, Any], str]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Remove multiple metrics from this test set.

        Args:
            metrics: A list where each item can be a dict, UUID
                string, or metric name string.

        Returns:
            The updated list of metrics on this test set after all
            removals.
        """
        result = None
        for metric in metrics:
            result = self.remove_metric(metric)
        return result

    # ------------------------------------------------------------------
    # Properties / LLM
    # ------------------------------------------------------------------

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

        Args:
            entry: Dictionary containing test data.

        Returns:
            Test object, or None if the entry is empty/invalid.
        """
        from rhesis.sdk.entities.test import TestConfiguration

        if not isinstance(entry, dict):
            return None

        # Extract prompt content - support both nested and flat formats
        prompt_content = None
        expected_response = None
        language_code = None

        if "prompt" in entry and isinstance(entry["prompt"], dict):
            # Nested format: {"prompt": {"content": "...", "expected_response": "..."}}
            prompt_content = entry["prompt"].get("content")
            expected_response = entry["prompt"].get("expected_response")
            language_code = entry["prompt"].get("language_code")
        else:
            # Flat format: {"prompt_content": "...", "expected_response": "..."}
            prompt_content = entry.get("prompt_content")
            expected_response = entry.get("expected_response")

        # Skip empty entries - check if any required field has content
        category = entry.get("category", "")
        topic = entry.get("topic", "")
        behavior = entry.get("behavior", "")

        if not any(
            [
                str(prompt_content or "").strip(),
                str(category).strip(),
                str(topic).strip(),
                str(behavior).strip(),
            ]
        ):
            return None  # Empty entry

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

        # Build test configuration if present (for multi-turn tests)
        test_configuration = None
        if "test_configuration" in entry and isinstance(entry["test_configuration"], dict):
            config = entry["test_configuration"]
            test_configuration = TestConfiguration(
                goal=config.get("goal", ""),
                instructions=config.get("instructions", ""),
                restrictions=config.get("restrictions", ""),
                scenario=config.get("scenario", ""),
            )

        # Build metadata if present
        metadata = entry.get("metadata", {})

        return Test(
            category=category or None,
            topic=topic or None,
            behavior=behavior or None,
            prompt=prompt,
            test_type=test_type,
            test_configuration=test_configuration,
            metadata=metadata if metadata else {},
        )

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
