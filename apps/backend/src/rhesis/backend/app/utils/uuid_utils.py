from typing import Any, List, Optional
from uuid import UUID

from rhesis.backend.logging import logger


def sanitize_uuid_field(value: Any) -> Optional[str]:
    """
    Sanitize UUID field values to handle empty strings and validate format.
    
    Args:
        value: The value to sanitize (could be None, empty string, or valid UUID string)
        
    Returns:
        None if value is None, empty string, or invalid UUID format, otherwise returns the value as string
    """
    logger.debug(f"sanitize_uuid_field - Input: value='{value}', type={type(value)}")
    
    if value is None or value == "" or (isinstance(value, str) and value.strip() == ""):
        logger.debug(f"sanitize_uuid_field - Returning None for empty/None value: '{value}'")
        return None
    
    # Validate UUID format
    try:
        # Try to convert to UUID to validate format
        UUID(str(value))
        result = str(value)
        logger.debug(f"sanitize_uuid_field - Valid UUID, returning: '{result}'")
        return result
    except (ValueError, TypeError) as e:
        logger.debug(f"sanitize_uuid_field - Invalid UUID format provided: {value}, error: {e}")
        return None


def validate_uuid_parameters(*uuid_values: str) -> Optional[str]:
    """
    Validate multiple UUID parameters.
    
    Args:
        *uuid_values: Variable number of UUID strings to validate
        
    Returns:
        None if all UUIDs are valid, otherwise returns error message
    """
    try:
        for value in uuid_values:
            if value is not None:  # Allow None values
                UUID(value)
        return None
    except (ValueError, TypeError) as e:
        return f"Invalid UUID format in parameters: {str(e)}"


def validate_uuid_list(uuid_list: List[str]) -> Optional[str]:
    """
    Validate a list of UUID strings.
    
    Args:
        uuid_list: List of UUID strings to validate
        
    Returns:
        None if all UUIDs are valid, otherwise returns error message
    """
    try:
        for uuid_str in uuid_list:
            UUID(uuid_str)
        return None
    except (ValueError, TypeError) as e:
        return f"Invalid UUID format in list: {str(e)}"


def ensure_owner_id(owner_id: Optional[str], user_id: str) -> str:
    """
    Ensure owner_id is set, defaulting to user_id if not provided.
    
    Args:
        owner_id: Optional owner ID that might be None or empty
        user_id: User ID to use as default
        
    Returns:
        Valid owner ID (either provided owner_id or user_id as fallback)
    """
    sanitized_owner_id = sanitize_uuid_field(owner_id)
    if sanitized_owner_id is None:
        logger.debug(f"Setting owner_id to user_id: {user_id}")
        return user_id
    return sanitized_owner_id 