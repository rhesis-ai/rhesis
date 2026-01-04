"""Context variables for test execution context threading."""

from contextvars import ContextVar
from typing import Optional

from rhesis.sdk.telemetry.schemas import TestExecutionContext

# Context variable to thread test execution context through call stack
# This avoids polluting function signatures with internal parameters
_test_execution_context: ContextVar[Optional[TestExecutionContext]] = ContextVar(
    "test_execution_context", default=None
)


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
