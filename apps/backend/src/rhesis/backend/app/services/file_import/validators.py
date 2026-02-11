"""Row-level validation for imported test data.

Validates each parsed row against the expected test data schema,
producing per-row errors and warnings plus an aggregate summary.
"""

from typing import Any, Dict, List, Tuple

VALID_TEST_TYPES = {"Single-Turn", "Multi-Turn"}

# Fields that must have a non-empty value
REQUIRED_FIELDS = ["category", "topic", "behavior"]


def validate_rows(
    rows: List[Dict[str, Any]],
) -> Tuple[
    List[List[Dict[str, str]]],
    List[List[Dict[str, str]]],
    Dict[str, Any],
]:
    """Validate all parsed rows.

    Returns:
        (row_errors, row_warnings, validation_summary)

        row_errors:   list (one per row) of error dicts
        row_warnings: list (one per row) of warning dicts
        validation_summary: aggregate counts
    """
    all_errors: List[List[Dict[str, str]]] = []
    all_warnings: List[List[Dict[str, str]]] = []
    rows_with_errors = 0
    rows_with_warnings = 0
    error_types: Dict[str, int] = {}

    for i, row in enumerate(rows):
        errors, warnings = _validate_single_row(row, i)
        all_errors.append(errors)
        all_warnings.append(warnings)

        # Count rows with at least one error/warning, not total error messages
        if len(errors) > 0:
            rows_with_errors += 1
        if len(warnings) > 0:
            rows_with_warnings += 1

        for e in errors:
            etype = e.get("type", "unknown")
            error_types[etype] = error_types.get(etype, 0) + 1

    valid_rows = sum(1 for errs in all_errors if len(errs) == 0)

    summary = {
        "total_rows": len(rows),
        "valid_rows": valid_rows,
        "error_count": rows_with_errors,
        "warning_count": rows_with_warnings,
        "error_types": error_types,
    }

    return all_errors, all_warnings, summary


def _validate_single_row(
    row: Dict[str, Any],
    index: int,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Validate a single row, returning (errors, warnings)."""
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        value = row.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(
                {
                    "type": "missing_required",
                    "field": field,
                    "message": f"Missing required field: {field}",
                }
            )

    # Check prompt content (required for single-turn only; not for multi-turn)
    test_type = row.get("test_type")
    if test_type != "Multi-Turn":
        prompt = row.get("prompt")
        if isinstance(prompt, dict):
            content = prompt.get("content")
        else:
            content = row.get("prompt_content")

        if not content or (isinstance(content, str) and not content.strip()):
            errors.append(
                {
                    "type": "missing_required",
                    "field": "prompt_content",
                    "message": "Missing required field: prompt content",
                }
            )

    # Validate test_type
    test_type = row.get("test_type")
    if test_type and test_type not in VALID_TEST_TYPES:
        warnings.append(
            {
                "type": "invalid_value",
                "field": "test_type",
                "message": (
                    f"Invalid test_type '{test_type}'. "
                    f"Expected: {', '.join(VALID_TEST_TYPES)}. "
                    "Defaulting to 'Single-Turn'."
                ),
            }
        )

    # Multi-turn: requires goal via test_configuration (nested) OR goal (flat)
    # Supports both nested and flat format like the SDK
    if test_type == "Multi-Turn":
        config = row.get("test_configuration")
        goal_flat = row.get("goal")
        goal_nested = config.get("goal") if isinstance(config, dict) and config else None
        has_goal = bool(
            (goal_flat and str(goal_flat).strip()) or (goal_nested and str(goal_nested).strip())
        )
        if not has_goal:
            errors.append(
                {
                    "type": "missing_required",
                    "field": "test_configuration.goal",
                    "message": (
                        "Multi-Turn tests require a goal "
                        "(in test_configuration or as a separate column)"
                    ),
                }
            )

    return errors, warnings
