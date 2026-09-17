import json
from typing import Annotated, Any, Dict, Optional

from pydantic import BeforeValidator, ValidationError

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


#: Byte cap on the serialized ``version_info`` object. Mirrored in
#: ``apps/frontend/src/constants/version-info.ts`` -- keep the two in lockstep.
VERSION_INFO_MAX_BYTES: int = 16 * 1024
VERSION_INFO_MAX_DEPTH: int = 8


def _exceeds_depth(value: Any, max_depth: int) -> bool:
    """Probe nesting depth with an explicit stack.

    Deliberately not recursive: a hostile payload would blow the interpreter stack
    inside the validator and surface as a 500 rather than the 422 it should be.
    """
    stack = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        # Only containers count toward depth -- a scalar leaf is not another level,
        # so {"a": {"b": 1}} is depth 2, not 3.
        if not isinstance(node, (dict, list)):
            continue
        if depth > max_depth:
            return True
        children = node.values() if isinstance(node, dict) else node
        stack.extend((child, depth + 1) for child in children)
    return False


def validate_version_info(value: Any) -> Any:
    """Validate a free-form ``version_info`` object: JSON object, bounded size and depth.

    Used for both the endpoint's configured value and the value an endpoint reports at
    run time, which arrives from the client's own server and is the less trusted of the two.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("version_info must be a JSON object, not an array or a scalar")
    # Depth first: it is the cheap iterative check, and json.dumps below would itself
    # raise RecursionError (not ValueError) on a deeply nested payload, escaping as a 500.
    if _exceeds_depth(value, VERSION_INFO_MAX_DEPTH):
        raise ValueError(
            f"version_info must not nest more than {VERSION_INFO_MAX_DEPTH} levels deep"
        )
    try:
        # Compact separators to match JSON.stringify, so the frontend's mirrored byte cap
        # agrees with this one; Python's defaults add ~2 bytes per pair and would reject
        # borderline payloads the client had already accepted. allow_nan=False because
        # json.loads *accepts* NaN and Infinity, which would otherwise pass here and then
        # fail at JSONB insert as a 500 rather than a 422.
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("version_info must contain only JSON-serializable values") from exc
    size = len(encoded.encode("utf-8"))
    if size > VERSION_INFO_MAX_BYTES:
        raise ValueError(
            f"version_info must be at most {VERSION_INFO_MAX_BYTES} bytes when serialized "
            f"(received {size})"
        )
    return value


#: ``BeforeValidator`` so the "must be a JSON object" message wins over Pydantic's generic
#: "Input should be a valid dictionary" when a client sends an array.
VersionInfoField = Annotated[Optional[Dict[str, Any]], BeforeValidator(validate_version_info)]
