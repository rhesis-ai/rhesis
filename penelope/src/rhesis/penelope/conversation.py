"""
Conversation tracking constants and utilities for Penelope.

Matches the backend's conversation tracking approach for consistency.
"""

from typing import Any, Dict, Optional

# Conversation tracking field names (priority-ordered)
# Matches backend's CONVERSATION_FIELD_NAMES for consistency
# Tier 1: Most common (90% of APIs)
CONVERSATION_FIELD_NAMES = [
    "conversation_id",
    "session_id",
    "thread_id",
    "chat_id",
    # Tier 2: Common variants (8% of APIs)
    "dialog_id",
    "dialogue_id",
    "context_id",
    "interaction_id",
]


def extract_conversation_id(data: Dict[str, Any]) -> Optional[str]:
    """
    Extract conversation ID from data using flexible field detection.
    
    Checks common conversation tracking field names in priority order
    and returns the first non-None, non-empty value found.
    
    Args:
        data: Dictionary that may contain conversation tracking fields
        
    Returns:
        The conversation ID if found, None otherwise
        
    Examples:
        >>> extract_conversation_id({"session_id": "abc123"})
        'abc123'
        >>> extract_conversation_id({"thread_id": "xyz789"})
        'xyz789'
        >>> extract_conversation_id({"message": "hello"})
        None
        >>> extract_conversation_id({"conversation_id": "", "session_id": "abc"})
        'abc'
    """
    if not data:
        return None
        
    for field_name in CONVERSATION_FIELD_NAMES:
        if field_name in data and data[field_name] is not None and data[field_name] != "":
            return data[field_name]
    
    return None


def get_conversation_field_name(data: Dict[str, Any]) -> Optional[str]:
    """
    Get the name of the conversation tracking field present in the data.
    
    Args:
        data: Dictionary that may contain conversation tracking fields
        
    Returns:
        The field name if found, None otherwise
        
    Examples:
        >>> get_conversation_field_name({"session_id": "abc123"})
        'session_id'
        >>> get_conversation_field_name({"thread_id": "xyz789"})
        'thread_id'
        >>> get_conversation_field_name({"conversation_id": "", "session_id": "abc"})
        'session_id'
    """
    if not data:
        return None
        
    for field_name in CONVERSATION_FIELD_NAMES:
        if field_name in data and data[field_name] is not None and data[field_name] != "":
            return field_name
    
    return None


def normalize_conversation_params(**kwargs: Any) -> Dict[str, Any]:
    """
    Normalize conversation parameters by extracting conversation ID from any field.

    Takes kwargs that may contain any conversation tracking field and returns
    a normalized dict with the conversation_id extracted.

    Args:
        **kwargs: Parameters that may include conversation tracking fields

    Returns:
        Dict with 'conversation_id' key if any conversation field was found,
        plus all original kwargs

    Examples:
        >>> normalize_conversation_params(message="hi", session_id="abc")
        {'message': 'hi', 'session_id': 'abc', 'conversation_id': 'abc'}
        >>> normalize_conversation_params(message="hi", thread_id="xyz")
        {'message': 'hi', 'thread_id': 'xyz', 'conversation_id': 'xyz'}
    """
    result = kwargs.copy()

    # Extract conversation ID from any field
    conv_id = extract_conversation_id(kwargs)
    if conv_id:
        result["conversation_id"] = conv_id

    return result
