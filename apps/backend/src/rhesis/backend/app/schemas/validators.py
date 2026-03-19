from typing import Any, Dict, Optional

from pydantic import ValidationError

from rhesis.backend.app.constants import TestSetType, TestType
from rhesis.backend.app.schemas.multi_turn_test_config import validate_multi_turn_config


def format_test_type(v: Optional[str]) -> Optional[str]:
    """Format test type to title case and validate against allowed types."""
    if v is None:
        return None

    formatted = v.title()
    allowed_types = [t.value for t in TestType]

    if formatted not in allowed_types:
        raise ValueError(f"Invalid test type '{v}'. Allowed values are: {', '.join(allowed_types)}")

    return formatted


def format_test_set_type(v: Optional[str]) -> Optional[str]:
    """Format test set type to title case and validate against allowed types."""
    if v is None:
        return None

    formatted = v.title()
    allowed_types = [t.value for t in TestSetType]

    if formatted not in allowed_types:
        raise ValueError(
            f"Invalid test set type '{v}'. Allowed values are: {', '.join(allowed_types)}"
        )

    return formatted


def validate_test_config_content(v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Validate test_configuration JSON based on content.

    For multi-turn tests (when goal is present), validates against MultiTurnTestConfig schema.
    """
    if v is None:
        return None

    # If 'goal' is present, this is a multi-turn test configuration
    if "goal" in v:
        try:
            # Validate using multi-turn config schema
            validated_config = validate_multi_turn_config(v)
            # Return as dict for storage
            return validated_config.model_dump(exclude_none=True)
        except ValidationError as e:
            # Re-raise with more context
            error_messages = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_messages.append(f"{field}: {error['msg']}")
            raise ValueError(f"Invalid multi-turn test configuration: {'; '.join(error_messages)}")

    # For other configurations, allow any valid JSON
    return v
