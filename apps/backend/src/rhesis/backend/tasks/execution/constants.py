"""Constants for test execution tasks."""

from enum import Enum

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

__all__ = [
    "CONVERSATION_SUMMARY_KEY",
    "PENELOPE_MESSAGE_KEY",
    "TARGET_RESPONSE_KEY",
    "TURN_CONTEXT_KEY",
    "TURN_METADATA_KEY",
    "TURN_TOOL_CALLS_KEY",
    "MetricScope",
]


class MetricScope(str, Enum):
    """
    Metric scope enum for test execution.

    These values must match:
    - Database metric_scope field (stored as JSON array)
    - SDK MetricScope enum values (sdk/src/rhesis/sdk/metrics/base.py)

    Using str as a mixin allows the enum to be used directly in string comparisons
    and serialized naturally to JSON.
    """

    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"
