"""Utility functions for common synthesizer operations."""

from typing import Any, Dict, List

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.utils import extract_json_from_text


def retry_llm_call(model: BaseLLM, prompt: str, max_attempts: int = 3) -> Any:
    """Retry LLM calls with error handling."""
    for attempt in range(max_attempts):
        try:
            return model.generate(prompt=prompt)
        except Exception as e:
            if attempt == max_attempts - 1:
                raise e
            print(f"Attempt {attempt + 1} failed: {e}")


def parse_llm_response(response: Any, expected_keys: List[str] = None) -> List[Dict[str, Any]]:
    """Parse LLM response into structured data."""
    if isinstance(response, dict):
        return _extract_from_dict(response, expected_keys)
    elif isinstance(response, str):
        return _extract_from_string(response, expected_keys)
    elif isinstance(response, list):
        return response
    else:
        raise ValueError(f"Unexpected response type: {type(response)}")


def _extract_from_dict(response: Dict, expected_keys: List[str] = None) -> List[Dict[str, Any]]:
    """Extract data from dictionary response."""
    if expected_keys:
        for key in expected_keys:
            if key in response and isinstance(response[key], list):
                return response[key]

    # Fallback to common keys
    for key in ["tests", "test_cases", "data", "results", "items"]:
        if key in response and isinstance(response[key], list):
            return response[key]

    # Check if response itself looks like a single item
    if any(
        key in response for key in ["input", "output", "expected", "question", "answer", "prompt"]
    ):
        return [response]

    return []


def _extract_from_string(response: str, expected_keys: List[str] = None) -> List[Dict[str, Any]]:
    """Extract data from string response."""
    parsed = extract_json_from_text(response)

    if expected_keys:
        for key in expected_keys:
            if key in parsed:
                return parsed[key] if isinstance(parsed[key], list) else [parsed[key]]

    return parsed.get("tests", [])
