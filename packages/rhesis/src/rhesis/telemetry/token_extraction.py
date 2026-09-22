"""
Provider-agnostic token usage extraction utilities.

This module provides utilities for extracting token usage information from LLM responses
across different providers and frameworks (LangChain, LlamaIndex, direct API calls, etc.).

LLM providers use different key names for the same concepts:
    - Input tokens: "input_tokens", "prompt_tokens", "prompt_token_count"
    - Output tokens: "output_tokens", "completion_tokens", "generated_tokens",
      "candidates_token_count"
    - Total tokens: "total_tokens", "total_token_count"

Cohere nests its counts one level down, under "billed_units" and "tokens"; those are
flattened before the lookup so a caller never has to unwrap them first.

This module handles all variations automatically, making it easy to extract tokens
regardless of the provider or framework being used. Adding a provider means adding its
key names to the lists in :func:`extract_token_usage` and nowhere else: the payload is
flattened whole, so nothing is discarded before those lists are consulted.
"""

import logging
from typing import Any, Dict, Tuple, Union

# Declared, not inferred: the backwards-compatible shim at
# rhesis.sdk.telemetry.utils.token_extraction has to forward this exact set, and a test asserts it
# does.
__all__ = ["extract_token_usage", "get_first_value"]

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> int:
    """Safely convert a value to int, handling None, strings, and floats."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# Every key name a provider might use, grouped by what it means. Adding a provider means
# adding its spellings here and nowhere else: the payload is flattened whole and these
# lists are the only thing consulted, for a dict key and an object attribute alike.
_INPUT_KEYS = [
    "input_tokens",
    "prompt_tokens",
    "prompt_token_count",
    "promptTokenCount",  # camelCase variant
]

_OUTPUT_KEYS = [
    "output_tokens",
    "completion_tokens",
    "generated_tokens",
    "candidates_token_count",
    "candidatesTokenCount",  # camelCase variant
    "completionTokenCount",  # camelCase variant
]

_TOTAL_KEYS = [
    "total_tokens",
    "total_token_count",
    "totalTokenCount",  # camelCase variant
]

# Anthropic cache tokens (billed separately but part of actual usage)
_CACHE_CREATION_KEYS = [
    "cache_creation_input_tokens",
    "cacheCreationInputTokens",  # camelCase variant
]

_CACHE_READ_KEYS = [
    "cache_read_input_tokens",
    "cacheReadInputTokens",  # camelCase variant
]

_ALL_KEYS = (
    *_INPUT_KEYS,
    *_OUTPUT_KEYS,
    *_TOTAL_KEYS,
    *_CACHE_CREATION_KEYS,
    *_CACHE_READ_KEYS,
)


# Where a provider hides its counts one level down. Cohere reports both a raw and a
# billed figure; billed wins, because it is what the invoice charges and cost is what
# these numbers feed.
_NESTED_CONTAINERS = ("billed_units", "tokens", "usage", "usage_metadata", "token_usage")


def _to_plain_dict(value: Any) -> Dict:
    """Whatever a provider handed us, as a plain dict. Empty when it cannot be one."""
    if isinstance(value, dict):
        return dict(value)

    for method in ("model_dump", "dict"):
        converter = getattr(value, method, None)
        if callable(converter):
            try:
                converted = converter()
            except Exception as e:  # a model_dump that needs arguments, say
                logger.debug(f"Error converting usage object via {method}(): {e}")
                continue
            if isinstance(converted, dict):
                return converted

    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return dict(attributes)

    return {}


def _as_mapping(usage: Union[Dict, Any]) -> Dict:
    """Flatten a usage payload into one dict the key lookups can search.

    Converting the whole object rather than copying a list of known attribute names is
    the point. The old shape stopped at the first name it recognised and threw the rest
    away before the lookups below ever ran, so supporting a new provider meant editing
    two lists and forgetting one: that is how Anthropic's cache tokens went missing, and
    why the camelCase spellings were unreachable for anything but a dict.

    A nested container is merged in underneath its parent, so a provider that puts its
    counts one level down (Cohere) resolves without the caller unwrapping first, and a
    count at the top level still wins.
    """
    if usage is None:
        return {}

    flat = _to_plain_dict(usage)
    if not isinstance(usage, dict):
        # A count can live on the class, or behind a property, where neither model_dump
        # nor __dict__ finds it. Probing the same key lists covers that without a second
        # list to keep in step.
        for key in _ALL_KEYS:
            if key in flat:
                continue
            try:
                value = getattr(usage, key, None)
            except Exception as e:
                # A property or a custom __getattr__ can run arbitrary code, and the
                # default argument above only swallows AttributeError. This runs inside
                # the caller's request, so a token count is never worth raising over.
                logger.debug(f"Error reading {key} from usage object: {e}")
                continue
            if value is not None:
                flat[key] = value
    if not flat:
        return {}

    nested: Dict = {}
    for name in _NESTED_CONTAINERS:
        child = flat.get(name)
        if child is None or isinstance(child, (str, bytes, int, float, bool)):
            continue
        # Later containers do not overwrite earlier ones: _NESTED_CONTAINERS is in
        # preference order, so the first one carrying a key keeps it.
        for key, value in _to_plain_dict(child).items():
            nested.setdefault(key, value)

    # The top level wins over anything nested, and a None never displaces a real number.
    merged = {k: v for k, v in nested.items() if v is not None}
    merged.update({k: v for k, v in flat.items() if v is not None})
    return merged


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
    usage = _as_mapping(usage)

    if not usage:
        return 0, 0, 0

    # Extract input tokens (try all common key names)
    input_tokens = get_first_value(usage, _INPUT_KEYS)

    # Extract output tokens (try all common key names)
    output_tokens = get_first_value(usage, _OUTPUT_KEYS)

    # Extract total tokens (try all common key names)
    total_tokens = get_first_value(usage, _TOTAL_KEYS)

    cache_creation_tokens = get_first_value(usage, _CACHE_CREATION_KEYS)
    cache_read_tokens = get_first_value(usage, _CACHE_READ_KEYS)

    # Calculate total if not explicitly provided
    counted = input_tokens or output_tokens or cache_creation_tokens or cache_read_tokens
    if not total_tokens and counted:
        total_tokens = input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens

    return input_tokens, output_tokens, total_tokens
