"""Utility functions for the Rhesis SDK."""

import json
import re
from typing import Any, Dict, List

import tiktoken
from nanoid import generate

CUSTOM_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def generate_nano_id() -> str:
    return generate(size=12, alphabet=CUSTOM_ALPHABET)


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count the number of tokens in a given text string using tiktoken.

    Args:
        text: The input text to count tokens for
        encoding_name: The name of the encoding to use. Defaults to cl100k_base
                      (used by GPT-4 and GPT-3.5-turbo)

    Returns:
        Optional[int]: The number of tokens in the text, or None if encoding fails

    Examples:
        >>> count_tokens("Hello, world!")
        4
        >>> count_tokens("Complex text", encoding_name="p50k_base")
        2
    """
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        raise ValueError("Failed to count tokens")


def extract_json_from_text(text: str, fallback_to_partial: bool = True) -> Dict[str, Any]:
    """
    Extract JSON from text that may contain markdown, extra text, or malformed JSON.

    Args:
        text: The text containing JSON
        fallback_to_partial: Whether to attempt partial extraction if full parsing fails

    Returns:
        Dict containing the parsed JSON

    Raises:
        ValueError: If no valid JSON can be extracted
    """
    # Remove markdown code blocks
    cleaned_text = re.sub(r"```json\s*", "", text)
    cleaned_text = re.sub(r"```\s*$", "", cleaned_text)

    # Find the JSON object (look for the first { and last })
    start_idx = cleaned_text.find("{")
    end_idx = cleaned_text.rfind("}")

    if start_idx == -1 or end_idx == -1:
        if fallback_to_partial:
            return extract_partial_json(text)
        raise ValueError("No valid JSON object found in text")

    json_text = cleaned_text[start_idx : end_idx + 1].strip()

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        if fallback_to_partial:
            return extract_partial_json(text)
        raise


def extract_partial_json(text: str) -> Dict[str, Any]:
    """
    Extract partial JSON when full parsing fails.
    Attempts to find and parse individual objects or arrays.

    Args:
        text: The text containing malformed JSON

    Returns:
        Dict with extracted data, may contain empty structures
    """
    result = {}

    # Try to extract common patterns
    patterns = {
        "tests": r'"tests"\s*:\s*\[(.*?)\]',
        "data": r'"data"\s*:\s*\[(.*?)\]',
        "results": r'"results"\s*:\s*\[(.*?)\]',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        if match:
            array_content = match.group(1)
            objects = extract_objects_from_array(array_content)
            if objects:
                result[key] = objects
                break

    return result if result else {"tests": []}


def extract_objects_from_array(array_content: str) -> List[Dict[str, Any]]:
    """
    Extract individual JSON objects from array content.

    Args:
        array_content: String content of a JSON array

    Returns:
        List of parsed objects
    """
    objects = []

    # Look for individual objects with common patterns
    object_patterns = [
        r'\{[^{}]*"prompt"[^{}]*\}',  # Objects with prompt field
        r'\{[^{}]*"content"[^{}]*\}',  # Objects with content field
        r'\{[^{}]*"test"[^{}]*\}',  # Objects with test field
    ]

    for pattern in object_patterns:
        matches = re.findall(pattern, array_content, re.DOTALL)
        for match in matches:
            try:
                obj = json.loads(match)
                if obj not in objects:  # Avoid duplicates
                    objects.append(obj)
            except json.JSONDecodeError:
                continue

    return objects


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely load JSON with fallback to default value.

    Args:
        text: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def validate_test_case(test_case: Dict[str, Any]) -> bool:
    """
    Validate that a test case has the required structure.

    Args:
        test_case: Dictionary representing a test case

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(test_case, dict):
        return False

    # Check for required prompt structure
    if "prompt" not in test_case:
        return False

    prompt = test_case["prompt"]
    if not isinstance(prompt, dict):
        return False

    if "content" not in prompt:
        return False

    if not isinstance(prompt["content"], str) or not prompt["content"].strip():
        return False

    return True


def clean_and_validate_tests(tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean and validate a list of test cases.

    Args:
        tests: List of test case dictionaries

    Returns:
        List of valid test cases
    """
    if not isinstance(tests, list):
        return []

    valid_tests = []
    for test in tests:
        if validate_test_case(test):
            # Ensure required fields have defaults
            cleaned_test = {
                "prompt": test["prompt"],
                "behavior": test.get("behavior", "Unknown"),
                "category": test.get("category", "Unknown"),
                "topic": test.get("topic", "General"),
                **test,  # Keep any additional fields
            }
            valid_tests.append(cleaned_test)

    return valid_tests


def get_file_content(file_path: str) -> str:
    """Get file content with error handling."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError, UnicodeDecodeError) as e:
        raise ValueError(f"Could not read file {file_path}: {e}")


def ensure_directory_exists(directory_path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    import os

    os.makedirs(directory_path, exist_ok=True)
