"""Normalize raw endpoint invocation results into a processed output field."""

import copy
import logging
from typing import Any, Dict

from rhesis.backend.app.utils.response_extractor import extract_response_with_fallback

logger = logging.getLogger(__name__)


def process_endpoint_result(result: Any) -> Dict:
    """
    Process endpoint result to ensure output field is populated.

    Uses fallback logic from response_extractor.
    Handles both dict results and ErrorResponse Pydantic objects.

    Returns:
        Processed result with output field populated using the fallback hierarchy
    """
    if not result:
        return {}

    # Handle ErrorResponse Pydantic objects by converting to dict
    if hasattr(result, "to_dict"):
        # Use to_dict() method if available (ErrorResponse)
        result_dict = result.to_dict()
    elif hasattr(result, "model_dump"):
        # Use model_dump() for Pydantic v2 models
        result_dict = result.model_dump(exclude_none=True)
    elif hasattr(result, "dict"):
        # Fallback to dict() for Pydantic v1 models
        result_dict = result.dict(exclude_none=True)
    elif isinstance(result, dict):
        # Already a dict
        result_dict = result
    else:
        logger.warning(f"Unexpected result type: {type(result)}, attempting to convert")
        result_dict = dict(result) if result else {}

    # Create a DEEP copy of the result to avoid modifying the original or sharing references
    processed_result = copy.deepcopy(result_dict)

    # Use the existing fallback logic to get the processed output
    processed_output = extract_response_with_fallback(processed_result)

    # Set the output field to the processed response
    processed_result["output"] = processed_output

    return processed_result
