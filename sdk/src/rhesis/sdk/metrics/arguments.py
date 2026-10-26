"""What a metric's ``evaluate()`` receives.

A metric declares any of four parameters: ``input`` and ``output`` of what it judges, the
``trace`` of what happened, and the ``expectations`` of what should have. Callers may pass the
trace's parts instead of a trace (``context=``, ``tool_calls=``, ``metadata=``,
``conversation=``); ``evaluation_arguments`` builds the trace from them, so a local check
needs no tracing set up.
"""

import inspect
import json
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics.expectations import Expectations

F = TypeVar("F", bound=Callable[..., Any])

EVALUATION_PARAMETERS = ("input", "output", "trace", "expectations")
TRACE_SHORTCUTS = ("context", "tool_calls", "metadata", "conversation")

#: Where each parameter metrics used to declare is read now.
REPLACED_PARAMETERS = {
    "expected_output": "expectations.response",
    "context": "trace.context",
    "tool_calls": "trace.tool_calls",
    "metadata": "trace.metadata",
    "conversation_history": "trace.messages()",
    "goal": "expectations.goal",
    "instructions": "expectations.instructions",
    "contract": "expectations.contract",
}


def judged_input_output(
    trace: Trace, expectations: Optional[Expectations] = None
) -> Tuple[str, str]:
    """The input and output of what a metric judges on this trace.

    For one turn, the turn's input and output. For a conversation, the goal and the
    transcript with each turn's tool calls, context and metadata.
    """
    if trace.is_conversation:
        goal = expectations.goal if expectations else None
        return goal or "", trace.messages().format_conversation().strip()
    return _text(trace.input), _text(trace.output)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, default=str)


def build_trace(
    input: Any = None,
    output: Any = None,
    *,
    context: Any = None,
    tool_calls: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
    conversation: Any = None,
) -> Trace:
    """A trace from a response's parts, or from a conversation."""
    if conversation is not None:
        if any(value is not None for value in (context, tool_calls, metadata)):
            raise ValueError(
                "Pass context, tool_calls and metadata on the conversation's assistant "
                "messages, not beside conversation."
            )
        return Trace.from_conversation(conversation)
    return Trace.from_response(
        input, output, context=context, tool_calls=tool_calls, metadata=metadata
    )


def _prepare(
    signature: inspect.Signature, args: tuple, kwargs: Dict[str, Any]
) -> inspect.BoundArguments:
    shortcuts = {name: kwargs.pop(name) for name in TRACE_SHORTCUTS if name in kwargs}
    bound = signature.bind_partial(*args, **kwargs)
    values = bound.arguments
    declared = signature.parameters

    if "expectations" in declared:
        values["expectations"] = Expectations.coerce(values.get("expectations"))

    if "trace" not in declared:
        passed = [name for name, value in shortcuts.items() if value is not None]
        if passed:
            raise TypeError(
                f"This metric does not read the trace, so it takes no {', '.join(passed)}."
            )
        return bound

    trace = values.get("trace")
    if isinstance(trace, dict):
        trace = Trace.model_validate(trace)
    if trace is not None and not isinstance(trace, Trace):
        raise TypeError(
            f"trace must be a Trace, not {type(trace).__name__}. Pass a conversation as "
            "conversation=, and a response's parts as context=, tool_calls= or metadata=."
        )
    if trace is None:
        trace = build_trace(values.get("input"), values.get("output"), **shortcuts)
    elif any(value is not None for value in shortcuts.values()):
        raise ValueError(
            f"Pass either trace or {', '.join(shortcuts)}: the trace already holds them."
        )
    values["trace"] = trace

    missing = [n for n in ("input", "output") if n in declared and values.get(n) is None]
    if missing:
        input, output = judged_input_output(trace, values.get("expectations"))
        judged = {"input": input, "output": output}
        for name in missing:
            values[name] = judged[name]
    return bound


def evaluation_arguments(func: F) -> F:
    """Prepare what a metric's ``evaluate``/``a_evaluate`` receives.

    Strings become ``Expectations``. When the method declares ``trace`` and none is passed,
    one is built from ``input``, ``output`` and the shortcuts; ``input`` and ``output`` not
    passed are read from the trace.
    """
    signature = inspect.signature(func)

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = _prepare(signature, args, kwargs)
            return await func(*bound.args, **bound.kwargs)

        return async_wrapper  # type: ignore[return-value]

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = _prepare(signature, args, kwargs)
        return func(*bound.args, **bound.kwargs)

    return wrapper  # type: ignore[return-value]
