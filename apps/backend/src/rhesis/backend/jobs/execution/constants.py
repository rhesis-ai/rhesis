"""Constants for test execution tasks."""

# Penelope ConversationTurn serialisation keys.  Values must stay in sync
# with rhesis.penelope.context but are inlined here to avoid pulling the
# entire penelope → sdk → litellm → gRPC import chain into the Celery
# main process at autodiscovery time (gRPC is not fork-safe).
CONVERSATION_SUMMARY_KEY = "conversation_summary"
PENELOPE_MESSAGE_KEY = "penelope_message"
TARGET_RESPONSE_KEY = "target_response"
TURN_CONTEXT_KEY = "context"
TURN_METADATA_KEY = "metadata"
TURN_TOOL_CALLS_KEY = "tool_calls"

# Metric class names that Penelope evaluates internally.
# These must be excluded from the post-execution metric pass to avoid
# double-counting.
PENELOPE_EVALUATED_METRICS = frozenset({"GoalAchievementJudge"})

# The test_metrics key Penelope stores its goal verdict under on every live
# multi-turn test: its default judge's name, "goal_achievement", title-cased
# by rhesis.penelope.context. Present whether or not any requirement has one.
PENELOPE_GOAL_METRIC_KEY = "Goal Achievement"

# Row key of the metric plan's built-in Goal Achievement row. Not a metric
# name, so it can't collide with a real metric keyed "Goal Achievement".
BUILTIN_GOAL_ROW_KEY = "builtin:goal_achievement"

# Canonical definition lives in schemas.metric; re-export for convenience.
from rhesis.backend.app.schemas.metric import MetricScope  # noqa: E402

__all__ = [
    "CONVERSATION_SUMMARY_KEY",
    "PENELOPE_MESSAGE_KEY",
    "TARGET_RESPONSE_KEY",
    "TURN_CONTEXT_KEY",
    "TURN_METADATA_KEY",
    "TURN_TOOL_CALLS_KEY",
    "PENELOPE_EVALUATED_METRICS",
    "PENELOPE_GOAL_METRIC_KEY",
    "BUILTIN_GOAL_ROW_KEY",
    "MetricScope",
]
