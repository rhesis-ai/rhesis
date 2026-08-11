"""Pre-dispatch checks on tool arguments.

Catches the argument mistakes that the server is guaranteed to reject, so
the agent gets an exact message instead of a raw 422 it has to decode.

Deliberately narrow: only missing required fields are reported. Types and
enum values are left alone because the API normalises a lot of what looks
wrong here -- ``"multi_turn"`` and ``"multi-turn"`` both resolve to
``Multi-Turn``, and numeric strings coerce to integers. Rejecting those
locally would invent failures the server would have accepted, which is the
opposite of the point.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Cap on how many array items to inspect. Bulk payloads run to hundreds of
# tests and the first few are representative -- if item 0 is missing
# ``category``, item 87 almost certainly is too.
_MAX_ITEMS_CHECKED = 5


def _unwrap_optional(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Return the single non-null variant of an ``anyOf``/``oneOf``."""
    for key in ("anyOf", "oneOf"):
        if key in schema:
            variants = [v for v in schema[key] if v.get("type") != "null"]
            if len(variants) == 1:
                return variants[0]
    return schema


def _missing_required(
    value: Dict[str, Any],
    schema: Dict[str, Any],
    path: str,
) -> List[str]:
    """Collect required properties absent from ``value``, recursively."""
    errors: List[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for name in required:
        if value.get(name) is None:
            errors.append(f"{path}{name}")

    for name, prop_schema in properties.items():
        child = value.get(name)
        if child is None:
            continue
        inner = _unwrap_optional(prop_schema)

        if isinstance(child, dict) and inner.get("properties"):
            errors.extend(_missing_required(child, inner, f"{path}{name}."))
        elif isinstance(child, list) and inner.get("type") == "array":
            items = _unwrap_optional(inner.get("items", {}))
            if not items.get("properties"):
                continue
            for i, item in enumerate(child[:_MAX_ITEMS_CHECKED]):
                if isinstance(item, dict):
                    errors.extend(_missing_required(item, items, f"{path}{name}[{i}]."))

    return errors


def find_missing_arguments(
    arguments: Dict[str, Any],
    input_schema: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Return an error message naming missing required fields, or None.

    Args:
        arguments: The arguments the agent intends to send.
        input_schema: The tool's JSON Schema. ``None`` or a schema with no
            ``required`` list means nothing to check.
    """
    if not input_schema:
        return None

    missing = _missing_required(arguments, input_schema, "")
    if not missing:
        return None

    fields = ", ".join(missing)
    if not arguments:
        return (
            f"No arguments were received, but this tool requires: {fields}. "
            "Re-send the call with the arguments as a valid JSON object."
        )
    return (
        f"Missing required argument(s): {fields}. "
        "Add them and call the tool again; do not re-send the same payload."
    )
