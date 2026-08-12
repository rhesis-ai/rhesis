"""
Backwards-compatible re-export of the AI semantic conventions.

These moved to ``rhesis.telemetry.attributes`` so that framework integrations can depend on the
lightweight ``rhesis[telemetry]`` package instead of the full SDK. Nothing here imports anything
heavier than stdlib, so there was no reason for it to sit behind torch and deepeval.

New code should import from ``rhesis.telemetry.attributes``. This module stays for the ~64 existing
import sites.
"""

from rhesis.telemetry.attributes import (
    MAX_CONTENT_LENGTH,
    AIAttributes,
    AIEvents,
    create_llm_attributes,
    create_tool_attributes,
    validate_span_name,
)

__all__ = [
    "MAX_CONTENT_LENGTH",
    "AIAttributes",
    "AIEvents",
    "create_llm_attributes",
    "create_tool_attributes",
    "validate_span_name",
]
