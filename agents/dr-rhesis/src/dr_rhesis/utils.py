"""Formatting and JSON parsing helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from haystack.dataclasses import ChatMessage

SLOT_FIELDS = frozenset(
    {
        "chief_complaint",
        "onset",
        "location",
        "character",
        "severity",
        "timing",
        "aggravating",
        "relieving",
        "associated",
        "context",
    }
)


def normalize_slot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Coerce slot field values to strings so LLM JSON with numeric severity etc. validates."""
    normalized = dict(payload)
    for key, value in normalized.items():
        if key in SLOT_FIELDS and value is not None and not isinstance(value, str):
            normalized[key] = str(value)
    return normalized


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output, tolerating markdown fences."""
    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    if fence_match:
        stripped = fence_match.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in model output: {text!r}")
    return json.loads(stripped[start : end + 1])


def reply_text(replies: list[ChatMessage]) -> str:
    """Return the text of the first assistant reply."""
    if not replies:
        raise RuntimeError("Generator returned no replies.")
    return replies[0].text or ""


def format_history(history: list[dict[str, str]], *, limit: int = 12) -> str:
    """Format recent conversation history for prompts."""
    if not history:
        return "(no prior messages)"
    lines: list[str] = []
    for item in history[-limit:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def format_slots(slots: dict[str, str | None]) -> str:
    """Format slot state for prompts."""
    lines = [f"- {key}: {value if value is not None else '(missing)'}" for key, value in slots.items()]
    return "\n".join(lines)


__all__ = [
    "SLOT_FIELDS",
    "extract_json_object",
    "format_history",
    "format_slots",
    "normalize_slot_payload",
    "reply_text",
]
