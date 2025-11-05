import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.services.context_generator import ContextGenerator


@dataclass
class Test:
    """
    Represents a single test case for LLM benchmarking.
    Includes prompt, system prompt, expected output, and additional parameters.
    """

    # invocation
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    context: Optional[List[str]] = None  # RAG-style context chunks
    additional_params: Optional[Dict[str, Any]] = field(default_factory=dict)
    # expectation
    expected_text: Optional[str] = None

    def __eq__(self, other: Any) -> bool:
        """
        Custom equality method to compare tests by prompt, system prompt, context, expected text,
        and additional params.
        """
        if not isinstance(other, Test):
            return False
        if self.prompt != other.prompt:
            return False
        if self.system_prompt != other.system_prompt:
            return False
        if self.context != other.context:
            return False
        if self.expected_text != other.expected_text:
            return False
        # Handle None values for additional_params
        if self.additional_params is None and other.additional_params is None:
            return True
        if self.additional_params is None or other.additional_params is None:
            return False
        for key, value in self.additional_params.items():
            if key not in other.additional_params or value != other.additional_params[key]:
                return False
        return True


@dataclass
class TestResult:
    """
    Stores the result of a single test case run on a model.
    Includes model id, response text, error, invocation details, expected output, score,
    and metadata.
    """

    # response
    model_id: Optional[str] = None
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # invocation
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    context: Optional[List[str]] = None  # RAG-style context chunks
    additional_params: Optional[Dict[str, Any]] = field(default_factory=dict)
    # expectation
    expected_text: Optional[str] = None
    # evaluation
    cost: Optional[float] = None
    score: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


def results_matches_test(test_result: TestResult, test: Test) -> bool:
    """
    Check if a TestResult corresponds to a given Test based on key fields.
    Returns True if prompt, system prompt, context, expected text, and additional params match.
    """
    if test_result.prompt != test.prompt:
        return False
    if test_result.system_prompt != test.system_prompt:
        return False
    if test_result.context != test.context:
        return False
    if test_result.expected_text != test.expected_text:
        return False
    # Handle None values for additional_params
    if test_result.additional_params is None and test.additional_params is None:
        return True
    if test_result.additional_params is None or test.additional_params is None:
        return False
    for key, value in test.additional_params.items():
        if key not in test_result.additional_params or value != test_result.additional_params[key]:
            return False
    return True


def update_if_result_matches_test(test_result: TestResult, test: Test) -> bool:
    """
    Checks if a TestResult corresponds to a given Test based on key fields.
    If they match, update the TestResult with information from the Test.
    If expected_text or context changes, resets score and details.
    """
    if test_result.prompt != test.prompt:
        return False
    if test_result.system_prompt != test.system_prompt:
        return False
    if test_result.context != test.context:
        test_result.context = test.context
        test_result.score = None
        test_result.details = None
    if test_result.expected_text != test.expected_text:
        test_result.expected_text = test.expected_text
        test_result.score = None
        test_result.details = None
    for key, value in test.additional_params.items():
        if key not in test_result.additional_params or value != test_result.additional_params[key]:
            return False
    return True


def prepare_context(
    context: Optional[Union[str, List[str]]], max_tokens_per_chunk: int = 1500
) -> Optional[List[str]]:
    """
    Prepare context for SDK compatibility using ContextGenerator.

    Handles three cases:
    1. None -> returns None
    2. List[str] -> returns as-is (already chunked)
    3. str -> automatically chunks using SDK's ContextGenerator

    Args:
        context: Raw context (None, string, or list of strings)
        max_tokens_per_chunk: Maximum tokens per context chunk (default: 1500)

    Returns:
        List[str] of context chunks, or None if no context
    """
    if context is None:
        return None

    if isinstance(context, list):
        # Already chunked - return as-is
        return context

    if isinstance(context, str):
        # Use SDK ContextGenerator for intelligent semantic chunking
        generator = ContextGenerator(max_context_tokens=max_tokens_per_chunk)
        chunks = generator.generate_contexts(context)
        return chunks

    # Fallback for unexpected types
    return [str(context)]


def read_tests_json(json_path, auto_chunk_context: bool = True) -> List[Test] | None:
    """
    Helper method to extract tests from a json file.

    Args:
        json_path: Path to the JSON file containing tests
        auto_chunk_context: If True, automatically chunk string context using SDK ContextGenerator

    Returns:
        List of Test objects, or None if file not found

    Context handling:
    - If context is a list, it's used as-is (pre-chunked)
    - If context is a string and auto_chunk_context=True, it's intelligently chunked
    - If context is a string and auto_chunk_context=False, it's converted to a single-item list
    """
    test_set = []

    if json_path is None:
        return None
    try:
        with open(json_path, mode="r") as f:
            json_data = json.load(f)
            test_set = []
            for test_data in json_data.get("tests", []):
                # Handle context field specially if auto_chunk_context is enabled
                if auto_chunk_context and "context" in test_data:
                    test_data["context"] = prepare_context(test_data["context"])
                test_set.append(Test(**test_data))

    except FileNotFoundError:
        return None
    except json.decoder.JSONDecodeError:
        print("Invalid JSON format. File could not be read.")

    return test_set


def write_tests_json(tests: List[Test], json_path: Path):
    """
    Helper method to write tests to a json file
    """
    if json_path is None:
        return

    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, mode="w") as f:
            json.dump(
                {
                    "tests": [asdict(test) for test in tests],
                },
                f,
                indent=2,
                default=str,
            )
            print(f"Tests saved to file: {json_path.absolute()}")
    except FileNotFoundError:
        print("No valid json_path specified. File is not saved.")
        return


def read_results_json(json_path) -> List[TestResult]:
    """
    Helper method to extract test results from a json file
    """
    results = []

    if json_path is None:
        return []
    try:
        with open(json_path, mode="r") as f:
            json_data = json.load(f)
            results = []
            for result in json_data.get("results", []):
                results.append(TestResult(**result))

    except FileNotFoundError:
        return []
    except json.decoder.JSONDecodeError:
        print("Invalid JSON format. File could not be read.")

    return results


def write_results_json(results: List[TestResult], json_path: Path):
    """
    Helper method to write test results to a json file
    """
    if json_path is None:
        return

    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, mode="w") as f:
            json.dump(
                {
                    "results": [asdict(result) for result in results],
                },
                f,
                indent=2,
                default=str,
            )
            print(f"Results saved to file: {json_path.absolute()}")
    except FileNotFoundError:
        print("No valid json_path specified. File is not saved.")
        return
