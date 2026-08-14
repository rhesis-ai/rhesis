"""
Backwards-compatible re-export of the telemetry context variables.

These moved to ``rhesis.telemetry.context`` so that framework integrations can depend on the
lightweight ``rhesis[telemetry]`` package instead of the full SDK.

The ContextVars themselves live in the new module, so importing from either path reads and writes
the same state — there is no second set.

Import from ``rhesis.telemetry.context``. Every site in this repository does; this module stays only
for consumers outside it — released ``rhesis-haystack`` versions and user code written against the
old path — and is not the path to add new imports to.
"""

from rhesis.telemetry.context import (
    get_conversation_id,
    get_conversation_mapped_input,
    get_conversation_trace_id,
    get_root_trace_id,
    get_test_execution_context,
    is_llm_observation_active,
    is_tracing_disabled,
    set_conversation_id,
    set_conversation_mapped_input,
    set_conversation_trace_id,
    set_llm_observation_active,
    set_root_trace_id,
    set_test_execution_context,
    set_tracing_disabled,
)

__all__ = [
    "get_conversation_id",
    "get_conversation_mapped_input",
    "get_conversation_trace_id",
    "get_root_trace_id",
    "get_test_execution_context",
    "is_llm_observation_active",
    "is_tracing_disabled",
    "set_conversation_id",
    "set_conversation_mapped_input",
    "set_conversation_trace_id",
    "set_llm_observation_active",
    "set_root_trace_id",
    "set_test_execution_context",
    "set_tracing_disabled",
]
