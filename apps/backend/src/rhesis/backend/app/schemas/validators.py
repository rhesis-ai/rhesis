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


def resolve_test_type(
    test_data: Dict[str, Any],
    test_set_type: Optional[str] = None,
    default_test_type: Optional[str] = None,
) -> str:
    """Return the effective turn type for one test payload.

    Precedence matches the historical service behavior and must stay in one
    place: explicit test_type, then auto-detection from test_configuration.goal
    or prompt, then the parent test-set type, then the platform default.
    """
    individual_test_type = test_data.get("test_type")
    if individual_test_type is not None:
        return TestType.get_value(individual_test_type)

    test_configuration = test_data.get("test_configuration") or {}
    if isinstance(test_configuration, dict) and "goal" in test_configuration:
        return TestType.MULTI_TURN.value
    if test_data.get("prompt"):
        return TestType.SINGLE_TURN.value
    if test_set_type:
        return TestType.get_value(test_set_type)

    return (
        TestType.get_value(default_test_type) if default_test_type else TestType.SINGLE_TURN.value
    )


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
