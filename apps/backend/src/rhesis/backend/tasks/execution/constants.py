"""Constants for test execution tasks."""

# Re-export Penelope's ConversationTurn serialisation keys so backend code
# can import from a single, local source without depending on a deep path.
from rhesis.penelope.context import (
    CONVERSATION_SUMMARY_KEY,
    PENELOPE_MESSAGE_KEY,
    TARGET_RESPONSE_KEY,
    TURN_CONTEXT_KEY,
    TURN_METADATA_KEY,
    TURN_TOOL_CALLS_KEY,
)

# Canonical definition lives in schemas.metric; re-export for convenience.
from rhesis.backend.app.schemas.metric import MetricScope

__all__ = [
    "CONVERSATION_SUMMARY_KEY",
    "PENELOPE_MESSAGE_KEY",
    "TARGET_RESPONSE_KEY",
    "TURN_CONTEXT_KEY",
    "TURN_METADATA_KEY",
    "TURN_TOOL_CALLS_KEY",
    "MetricScope",
]
