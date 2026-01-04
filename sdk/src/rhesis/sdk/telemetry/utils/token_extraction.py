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

from typing import Dict, Tuple


def get_first_value(data: Dict, keys: list, default: int = 0) -> int:
    """
    Extract first non-zero value from dict using multiple possible keys.

    Args:
        data: Dictionary to search
        keys: List of keys to try in order
        default: Default value if no keys found (default: 0)

    Returns:
        First non-zero value found, or default

    Example:
        >>> data = {"completion_tokens": 42}
        >>> get_first_value(data, ["output_tokens", "completion_tokens"])
        42
    """
    for key in keys:
        value = data.get(key)
        if value:
            return int(value)
    return default


def extract_token_usage(usage_dict: Dict) -> Tuple[int, int, int]:
    """
    Extract (input, output, total) token counts from a usage dictionary.

    This function is provider-agnostic and handles all common key name variations
    used by different LLM providers (OpenAI, Anthropic, Google, Cohere, etc.).

    Args:
        usage_dict: Dictionary containing token usage information

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
    if not usage_dict:
        return 0, 0, 0

    # Extract input tokens (try all common key names)
    input_tokens = get_first_value(
        usage_dict,
        ["input_tokens", "prompt_tokens", "prompt_token_count"],
    )

    # Extract output tokens (try all common key names)
    output_tokens = get_first_value(
        usage_dict,
        [
            "output_tokens",
            "completion_tokens",
            "generated_tokens",
            "candidates_token_count",
        ],
    )

    # Extract total tokens (try all common key names)
    total_tokens = get_first_value(
        usage_dict,
        ["total_tokens", "total_token_count"],
    )

    # Calculate total if not explicitly provided
    if not total_tokens and (input_tokens or output_tokens):
        total_tokens = input_tokens + output_tokens

    return input_tokens, output_tokens, total_tokens
