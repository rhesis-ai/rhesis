"""
Response extraction utilities for endpoint responses.

This module provides utilities for extracting meaningful responses from endpoint results
using a fallback hierarchy system.
"""
from typing import Dict

from rhesis.backend.logging.rhesis_logger import logger


def extract_response_with_fallback(result: Dict) -> str:
    """
    Extract response from result using the fallback hierarchy:
    1. First try to extract output from successful response
    2. If no output can be asserted (empty/null/unavailable), use metadata as output if available
    3. If metadata is not available, use error content as output
    
    Args:
        result: The response dictionary from endpoint invocation
        
    Returns:
        The extracted response string
    """
    if not result:
        logger.warning("No result provided, returning empty string")
        return ""
    
    # Handle error responses first
    if result.get("error", False):
        # If there's an error, use the error message as the actual response
        error_message = result.get("message", "Unknown error occurred")
        logger.info(f"Using error message as response for evaluation: {error_message}")
        return error_message
    
    # Try to extract output from successful responses
    actual_response = ""
    
    # New success structure: {"error": false, "data": {...}}
    if "data" in result and isinstance(result["data"], dict):
        actual_response = result["data"].get("output", "")
    elif "output" in result:
        # Fallback to old structure
        actual_response = result.get("output", "")
    
    # Check if we have a valid output
    if actual_response and str(actual_response).strip():
        logger.info(f"Found valid output: {actual_response}")
        return str(actual_response)
    
    # No valid output found, try metadata fallback
    logger.info("No valid output found, trying metadata fallback")
    
    # Try to extract metadata from different possible structures
    metadata = None
    if "data" in result and isinstance(result["data"], dict):
        metadata = result["data"].get("metadata")
    elif "metadata" in result:
        metadata = result.get("metadata")
    
    if metadata:
        # Convert metadata to string representation
        if isinstance(metadata, dict):
            # If metadata is a dict, try to extract meaningful content
            metadata_str = extract_meaningful_content_from_metadata(metadata)
            if metadata_str:
                logger.info(f"Using metadata as output: {metadata_str}")
                return metadata_str
        elif isinstance(metadata, (str, int, float)):
            metadata_str = str(metadata).strip()
            if metadata_str:
                logger.info(f"Using metadata as output: {metadata_str}")
                return metadata_str
    
    # No valid metadata found, use error content as final fallback
    logger.info("No valid metadata found, using error content as final fallback")
    
    # Try to extract any error content
    error_content = result.get("message", "")
    if not error_content:
        error_content = result.get("error_message", "")
    if not error_content:
        error_content = result.get("error_type", "")
    if not error_content:
        error_content = "No output or metadata available"
    
    logger.info(f"Using error content as final fallback: {error_content}")
    return str(error_content)


def extract_meaningful_content_from_metadata(metadata: Dict) -> str:
    """
    Extract meaningful content from metadata dictionary.
    
    Args:
        metadata: The metadata dictionary
        
    Returns:
        String representation of meaningful content, or empty string if none found
    """
    # Common fields that might contain meaningful content
    content_fields = [
        "content", "text", "message", "description", "summary", 
        "response", "output", "result", "data", "value"
    ]
    
    # Try to find content in common fields
    for field in content_fields:
        if field in metadata:
            value = metadata[field]
            if value and str(value).strip():
                return str(value).strip()
    
    # If no specific content field found, try to create a summary
    if len(metadata) > 0:
        # Filter out empty/null values and system fields
        meaningful_items = []
        for key, value in metadata.items():
            if value is not None and str(value).strip() and not key.startswith("_"):
                meaningful_items.append(f"{key}: {value}")
        
        if meaningful_items:
            return "; ".join(meaningful_items)
    
    return ""


def validate_response_structure(result: Dict) -> bool:
    """
    Validate that the response structure contains expected fields.
    
    Args:
        result: The response dictionary to validate
        
    Returns:
        True if the structure is valid, False otherwise
    """
    if not isinstance(result, dict):
        return False
    
    # Check for basic required structure
    has_error_field = "error" in result
    has_data_or_output = "data" in result or "output" in result
    
    return has_error_field or has_data_or_output


def get_response_type(result: Dict) -> str:
    """
    Determine the type of response based on its structure.
    
    Args:
        result: The response dictionary to analyze
        
    Returns:
        String indicating the response type: 'error', 'success', 'empty', or 'unknown'
    """
    if not result:
        return "empty"
    
    if not isinstance(result, dict):
        return "unknown"
    
    if result.get("error", False):
        return "error"
    
    # Check for output in various structures
    has_output = False
    if "data" in result and isinstance(result["data"], dict):
        has_output = bool(result["data"].get("output"))
    elif "output" in result:
        has_output = bool(result.get("output"))
    
    return "success" if has_output else "empty" 