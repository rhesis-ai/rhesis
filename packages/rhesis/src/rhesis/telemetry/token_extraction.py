"""
Provider-agnostic token usage extraction utilities.

This module provides utilities for extracting token usage information from LLM responses
across different providers and frameworks (LangChain, LlamaIndex, direct API calls, etc.).

LLM providers use different key names for the same concepts:
    - Input tokens: "input_tokens", "prompt_tokens", "prompt_token_count"
    - Output tokens: "output_tokens", "completion_tokens", "generated_tokens",
      "candidates_token_count"
    - Total tokens: "total_tokens", "total_token_count"

This module handles all variations automatically, making it easy to extract tokens
regardless of the provider or framework being used.
"""

import logging
from typing import Any, Dict, Tuple, Union

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> int:
    """Safely convert a value to int, handling None, strings, and floats."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def get_first_value(data: Union[Dict, Any], keys: list, default: int = 0) -> int:
    """
    Extract first non-zero value from dict or object using multiple possible keys.

    Args:
        data: Dictionary or object to search
        keys: List of keys/attributes to try in order
        default: Default value if no keys found (default: 0)

    Returns:
        First non-zero value found, or default

    Example:
        >>> data = {"completion_tokens": 42}
        >>> get_first_value(data, ["output_tokens", "completion_tokens"])
        42
    """
    if data is None:
        return default

    for key in keys:
        # Try dict access first
        if isinstance(data, dict):
            value = data.get(key)
            if value:
                return _safe_int(value)
        # Then try attribute access (for objects like UsageMetadata)
        elif hasattr(data, key):
            value = getattr(data, key, None)
            if value:
                return _safe_int(value)

    return default


def extract_token_usage(usage: Union[Dict, Any]) -> Tuple[int, int, int]:
    """
    Extract (input, output, total) token counts from a usage dictionary or object.

    This function is provider-agnostic and handles all common key name variations
    used by different LLM providers (OpenAI, Anthropic, Google, Cohere, etc.).

    Supports both dict-style access and object attribute access for compatibility
    with various LangChain response formats.

    Args:
        usage: Dictionary or object containing token usage information

    Returns:
        Tuple of (input_tokens, output_tokens, total_tokens)

    Example:
        >>> # OpenAI format
        >>> usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        >>> extract_token_usage(usage)
        (10, 20, 30)

        >>> # Gemini format
        >>> usage = {"prompt_token_count": 15, "candidates_token_count": 25}
        >>> extract_token_usage(usage)
        (15, 25, 40)

        >>> # Alternative format
        >>> usage = {"input_tokens": 12, "output_tokens": 18}
        >>> extract_token_usage(usage)
        (12, 18, 30)
    """
    if usage is None:
        return 0, 0, 0

    # Convert object to dict if needed for consistent access
    if not isinstance(usage, dict):
        # Try to extract common attributes from object
        usage_dict = {}
        common_attrs = [
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "prompt_token_count",
            "candidates_token_count",
            "total_token_count",
            "generated_tokens",
        ]
        for attr in common_attrs:
            if hasattr(usage, attr):
                value = getattr(usage, attr, None)
                if value is not None:
                    usage_dict[attr] = value

        # If we got values, use them; otherwise try dict conversion
        if usage_dict:
            usage = usage_dict
        else:
            # Last resort: try to convert to dict
            try:
                if hasattr(usage, "model_dump"):
                    usage = usage.model_dump()  # Pydantic v2
                elif hasattr(usage, "dict"):
                    usage = usage.dict()  # Pydantic v1
                elif hasattr(usage, "__dict__"):
                    usage = usage.__dict__
                else:
                    logger.debug(f"Could not convert usage object to dict: {type(usage)}")
                    return 0, 0, 0
            except Exception as e:
                logger.debug(f"Error converting usage object: {e}")
                return 0, 0, 0

    if not usage:
        return 0, 0, 0

    # Extract input tokens (try all common key names)
    input_tokens = get_first_value(
        usage,
        [
            "input_tokens",
            "prompt_tokens",
            "prompt_token_count",
            "promptTokenCount",  # camelCase variant
        ],
    )

    # Extract output tokens (try all common key names)
    output_tokens = get_first_value(
        usage,
        [
            "output_tokens",
            "completion_tokens",
            "generated_tokens",
            "candidates_token_count",
            "candidatesTokenCount",  # camelCase variant
            "completionTokenCount",  # camelCase variant
        ],
    )

    # Extract total tokens (try all common key names)
    total_tokens = get_first_value(
        usage,
        [
            "total_tokens",
            "total_token_count",
            "totalTokenCount",  # camelCase variant
        ],
    )

    # Calculate total if not explicitly provided
    if not total_tokens and (input_tokens or output_tokens):
        total_tokens = input_tokens + output_tokens

    return input_tokens, output_tokens, total_tokens
