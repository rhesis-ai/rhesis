"""
Response extraction utilities for endpoint responses.

This module provides utilities for extracting meaningful responses from endpoint results
using a fallback hierarchy system.
"""

import json
from typing import Any, Dict, List, Union

from rhesis.backend.logging.rhesis_logger import logger


def extract_response_with_fallback(result: Union[Dict, Any]) -> str:
    """
    Extract response from result using the fallback hierarchy:
    1. First try to extract output from successful response
    2. If no output can be asserted (empty/null/unavailable), use metadata as output if available
    3. If metadata is not available, use error content as output

    Args:
        result: The response dictionary from endpoint invocation,
                or an ErrorResponse Pydantic object
        Expected format: {"output": "...", "session_id": "...", "metadata": "..."}

    Returns:
        The extracted response string
    """
    if not result:
        logger.warning("No result provided, returning empty string")
        return ""

    # Convert ErrorResponse or other Pydantic objects to dict
    if not isinstance(result, dict):
        if hasattr(result, "to_dict"):
            # Use to_dict() method if available (ErrorResponse)
            result = result.to_dict()
        elif hasattr(result, "model_dump"):
            # Use model_dump() for Pydantic v2 models
            result = result.model_dump(exclude_none=True)
        elif hasattr(result, "dict"):
            # Fallback to dict() for Pydantic v1 models
            result = result.dict(exclude_none=True)
        else:
            logger.warning(f"Non-dict input provided: {type(result)}, attempting to convert")
            try:
                result = dict(result)
            except (TypeError, ValueError):
                logger.error(f"Cannot convert {type(result)} to dict, returning empty string")
        return ""

    # Handle error responses first
    if result.get("error", False):
        # If there's an error, use the error message as the actual response
        error_message = result.get("message", "Unknown error occurred")
        return error_message

    # Try to extract output from successful responses
    actual_response = result.get("output", "")

    # Check if we have a valid output
    if actual_response and str(actual_response).strip():
        return str(actual_response)

    # No valid output found, try metadata fallback
    metadata = result.get("metadata")

    if metadata:
        # Use the helper function to extract meaningful content from any metadata type
        metadata_str = extract_meaningful_content_from_metadata(metadata)
        if metadata_str:
            return metadata_str

    # No valid metadata found, use error content as final fallback
    # Try to extract any error content
    error_content = result.get("message", "")
    if not error_content:
        error_content = result.get("error_message", "")
    if not error_content:
        error_content = result.get("error_type", "")
    if not error_content:
        error_content = "No output or metadata available"

    return str(error_content)


def extract_meaningful_content_from_metadata(metadata) -> str:
    """
    Extract meaningful content from metadata (string or dictionary).

    Args:
        metadata: The metadata (string, dict, or other type)

    Returns:
        String representation of meaningful content, or empty string if none found
    """
    # Handle string metadata directly
    if isinstance(metadata, (str, int, float)):
        metadata_str = str(metadata).strip()
        if metadata_str:
            return metadata_str
        else:
            return ""

    # Handle non-dict, non-string types
    if not isinstance(metadata, dict):
        logger.debug(f"Unsupported metadata type: {type(metadata)}")
        return ""

    # Handle dictionary metadata
    # First, identify all meaningful fields
    meaningful_items = []
    for key, value in metadata.items():
        if value is not None and str(value).strip() and not key.startswith("_"):
            meaningful_items.append((key, str(value).strip()))

    # If no meaningful content found, return empty
    if not meaningful_items:
        return ""

    # High-priority fields that should be returned directly if they're the ONLY meaningful content
    high_priority_fields = ["content", "text", "message", "description", "summary"]

    # If there's only one meaningful field and it's high-priority, return it directly
    if len(meaningful_items) == 1:
        key, value = meaningful_items[0]
        if key in high_priority_fields:
            return value

    # Check for single high-priority field that contains substantial content (>20 chars)
    for field in high_priority_fields:
        if field in metadata:
            value = metadata[field]
            if value and str(value).strip() and len(str(value).strip()) > 20:
                # Only return directly if it's the dominant content
                if len(meaningful_items) == 1 or len(str(value).strip()) > 50:
                    result = str(value).strip()
                    return result

    # Create a summary from all meaningful fields
    summary_items = [f"{key}: {value}" for key, value in meaningful_items]
    result = "; ".join(summary_items)
    return result


def normalize_context_to_list(context: Any) -> List[str]:
    """
    Normalize context from various formats to a list of strings.

    SDK functions may return context as:
    - A single string
    - A JSON string representing a list
    - Already a list of strings
    - A list of dicts/objects
    - None or empty

    Args:
        context: The context value in any format

    Returns:
        A list of strings, or empty list if context is None/empty
    """
    if not context:
        return []

    # Already a list
    if isinstance(context, list):
        # Convert all items to strings
        normalized = []
        for item in context:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict):
                # Convert dict to JSON string
                try:
                    normalized.append(json.dumps(item))
                except (TypeError, ValueError) as e:
                    logger.warning(f"Failed to serialize context dict to JSON: {e}")
                    normalized.append(str(item))
            else:
                # Convert other types to string
                normalized.append(str(item))
        return normalized

    # Single string - could be plain text or JSON
    if isinstance(context, str):
        context_str = context.strip()

        # Try to parse as JSON (might be a JSON array)
        if context_str.startswith("[") and context_str.endswith("]"):
            try:
                parsed = json.loads(context_str)
                if isinstance(parsed, list):
                    # Recursively normalize the parsed list
                    return normalize_context_to_list(parsed)
            except json.JSONDecodeError:
                # Not valid JSON, treat as single string
                pass

        # Single string context - wrap in list
        return [context_str] if context_str else []

    # Dict - convert to JSON string and wrap in list
    if isinstance(context, dict):
        try:
            return [json.dumps(context)]
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize context dict to JSON: {e}")
            return [str(context)]

    # Other types - convert to string and wrap in list
    logger.debug(f"Normalizing unexpected context type {type(context)} to list")
    return [str(context)]
