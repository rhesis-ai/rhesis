"""Context variables for test execution context threading."""

from contextvars import ContextVar
from typing import Optional

from rhesis.sdk.telemetry.schemas import TestExecutionContext

# Context variable to thread test execution context through call stack
# This avoids polluting function signatures with internal parameters
_test_execution_context: ContextVar[Optional[TestExecutionContext]] = ContextVar(
    "test_execution_context", default=None
)

# Context variable to track if an LLM observation is already active
# This prevents duplicate spans when using both @observe.llm() and auto-instrumentation
_llm_observation_active: ContextVar[bool] = ContextVar("llm_observation_active", default=False)

# Context variable to store the root trace_id for the current execution
# This allows the executor to include trace_id in results for frontend linking
_root_trace_id: ContextVar[Optional[str]] = ContextVar("root_trace_id", default=None)


def set_test_execution_context(context: Optional[TestExecutionContext]) -> None:
    """
    Set test execution context for current execution.

    This is called by the executor when test context is present.
    The tracer reads from this to add span attributes.

    Args:
        context: Test execution context dict, or None to clear
    """
    _test_execution_context.set(context)


def get_test_execution_context() -> Optional[TestExecutionContext]:
    """
    Get test execution context for current execution.

    Returns None if not in a test execution context.
    """
    return _test_execution_context.get()


def set_llm_observation_active(active: bool) -> None:
    """
    Set whether an LLM observation is currently active.

    This is used to prevent duplicate spans when using both
    @observe.llm() decorator and auto-instrumentation (LangChain/LangGraph callbacks).

    Args:
        active: True if an LLM observation is active, False otherwise
    """
    _llm_observation_active.set(active)


def is_llm_observation_active() -> bool:
    """
    Check if an LLM observation is currently active.

    Returns True if @observe.llm() is currently tracing an LLM call,
    allowing auto-instrumentation callbacks to skip duplicate span creation.
    """
    return _llm_observation_active.get()


def set_root_trace_id(trace_id: Optional[str]) -> None:
    """
    Set the root trace_id for the current execution.

    This is called by the tracer when starting the root span for @endpoint functions.
    The executor reads this to include trace_id in results.

    Args:
        trace_id: The 32-char hex trace ID, or None to clear
    """
    _root_trace_id.set(trace_id)


def get_root_trace_id() -> Optional[str]:
    """
    Get the root trace_id for the current execution.

    Returns None if not in a traced execution context.
    """
    return _root_trace_id.get()
