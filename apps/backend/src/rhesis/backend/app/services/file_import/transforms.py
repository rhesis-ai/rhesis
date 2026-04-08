"""Row transformation helpers for file import.

Handles column renaming (apply_mapping), flat-to-nested normalisation,
and test-type mismatch detection.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MULTI_TURN_FIELDS = {"goal", "instructions", "restrictions", "scenario", "min_turns", "max_turns"}
_SINGLE_TURN_FIELDS = {"prompt_content", "prompt"}


def apply_mapping(
    rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Rename columns in each row according to the mapping.

    Columns not in the mapping are preserved as-is (they may be
    nested JSON keys like "prompt" that don't need renaming).
    """
    if not mapping:
        return rows

    result = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for key, value in row.items():
            target = mapping.get(key, key)
            new_row[target] = value
        result.append(new_row)
    return result


def normalize_row(
    row: Dict[str, Any],
    default_test_type: str = "Single-Turn",
) -> Dict[str, Any]:
    """Normalize flat format to the nested format expected by the SDK.

    Converts prompt_content/expected_response/language_code into a
    nested ``prompt`` dict if they aren't already nested.

    Args:
        row: A single parsed row.
        default_test_type: The test type to assign when the row
            does not already specify one ("Single-Turn" or
            "Multi-Turn").  Comes from the user's selection in
            the import dialog.
    """
    result = dict(row)

    # If we have flat prompt fields, build the nested prompt object
    prompt_content = result.pop("prompt_content", None)
    expected_response = result.pop("expected_response", None)
    language_code = result.pop("language_code", None)

    # If prompt_content is itself a dict (e.g. {"content": "text"}),
    # unwrap it so we don't double-nest.
    if isinstance(prompt_content, dict):
        nested = prompt_content
        prompt_content = nested.get("content")
        if not expected_response:
            expected_response = nested.get("expected_response")
        if not language_code:
            language_code = nested.get("language_code")

    if prompt_content and "prompt" not in result:
        prompt: Dict[str, Any] = {"content": prompt_content}
        if expected_response:
            prompt["expected_response"] = expected_response
        if language_code:
            prompt["language_code"] = language_code
        result["prompt"] = prompt
    elif "prompt" in result and isinstance(result["prompt"], dict):
        # Unwrap double-nesting: if prompt.content is itself a dict
        # with a "content" key, flatten it to the inner value.
        inner = result["prompt"].get("content")
        if isinstance(inner, dict) and "content" in inner:
            flattened = dict(inner)
            for k, v in result["prompt"].items():
                if k != "content" and k not in flattened:
                    flattened[k] = v
            result["prompt"] = flattened

        # Merge any flat fields into existing prompt dict
        if expected_response and "expected_response" not in result["prompt"]:
            result["prompt"]["expected_response"] = expected_response
        if language_code and "language_code" not in result["prompt"]:
            result["prompt"]["language_code"] = language_code

    # Apply default test_type from the user's selection
    if "test_type" not in result:
        result["test_type"] = default_test_type

    # Parse test_configuration if it's a JSON string (e.g. from CSV column)
    config_raw = result.get("test_configuration")
    if isinstance(config_raw, str):
        try:
            result["test_configuration"] = json.loads(config_raw)
        except json.JSONDecodeError:
            pass  # Leave as string; validation will report invalid format

    return result


def detect_test_type_mismatch(
    mapped_rows: List[Dict[str, Any]],
    selected_type: str,
) -> Tuple[str, Optional[str]]:
    """Detect whether the file content matches the user-selected test type.

    Returns (detected_type, warning_message).  ``warning_message`` is None
    when there is no mismatch or the data is ambiguous.
    """
    if not mapped_rows:
        return selected_type, None

    total = len(mapped_rows)
    multi_turn_count = sum(1 for row in mapped_rows if any(f in row for f in _MULTI_TURN_FIELDS))
    single_turn_count = sum(1 for row in mapped_rows if any(f in row for f in _SINGLE_TURN_FIELDS))

    multi_ratio = multi_turn_count / total
    single_ratio = single_turn_count / total

    # Need a clear majority (>50 %) to make a confident call
    if multi_ratio > 0.5:
        detected = "Multi-Turn"
    elif single_ratio > 0.5:
        detected = "Single-Turn"
    else:
        return selected_type, None

    if detected != selected_type:
        pct = int(multi_ratio * 100 if detected == "Multi-Turn" else single_ratio * 100)
        indicator = (
            "fields such as 'goal', 'instructions', or 'scenario')"
            if detected == "Multi-Turn"
            else "a 'prompt' field but no multi-turn configuration)"
        )
        warning = (
            f"You selected '{selected_type}', but {pct}% of the rows look like "
            f"'{detected}' tests (they contain {indicator}. "
            f"Consider going back and changing the test type."
        )
        return detected, warning

    return detected, None
