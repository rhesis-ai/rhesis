"""What an ``@endpoint`` turn records when the application calls it directly.

Called through the connector, the platform renders the turn's input and maps its output, and
the backend writes both on the turn's root span. Called directly, in production, nobody does,
so the root span would carry only the function's arguments and result and the turn's input and
output would be missing. Here the endpoint records them itself, read through its own
``request_mapping`` and ``response_mapping`` the simple way: the parameter that takes
``{{ input }}`` (or one named ``input``), and the output field (or the result itself).
"""

import contextvars
import json
import re
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, Iterator, Optional

_via_connector: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "rhesis_via_connector", default=False
)

_INPUT_TEMPLATE = re.compile(r"^\s*\{\{\s*input\s*\}\}\s*$")
_SIMPLE_PATH = re.compile(r"^\$(\.[A-Za-z_][A-Za-z0-9_]*)+$")


@contextmanager
def connector_call() -> Iterator[None]:
    """Mark the calls made inside as made by the connector, which records the turn itself."""
    token = _via_connector.set(True)
    try:
        yield
    finally:
        _via_connector.reset(token)


def via_connector() -> bool:
    """Whether the current call was made by the connector."""
    return _via_connector.get()


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return json.dumps(value, default=str)


def turn_input(
    func: Callable, args: tuple, kwargs: dict, request_mapping: Optional[dict]
) -> Optional[str]:
    """The argument the endpoint takes its input in."""
    import inspect

    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs).arguments
    except (TypeError, ValueError):
        return None
    mapped = [
        name
        for name, template in (request_mapping or {}).items()
        if isinstance(template, str) and _INPUT_TEMPLATE.match(template)
    ]
    for name in (*mapped, "input"):
        if name in bound:
            return _text(bound[name])
    return None


def turn_output(result: Any, response_mapping: Optional[dict]) -> Optional[str]:
    """The endpoint's output: its mapped ``output`` field, a dict's ``output``, or the result."""
    path = (response_mapping or {}).get("output")
    if isinstance(path, str) and _SIMPLE_PATH.match(path):
        value = result
        for key in path[2:].split("."):
            value = value.get(key) if isinstance(value, dict) else None
        return _text(value)
    if isinstance(result, dict):
        return _text(result.get("output"))
    return _text(result)


def _is_direct_root() -> bool:
    from rhesis.telemetry.context import get_root_trace_id, get_test_execution_context

    return (
        not _via_connector.get()
        and get_test_execution_context() is None
        and get_root_trace_id() is None
    )


def _record(attribute: str, text: Optional[str]) -> None:
    from opentelemetry import trace

    from rhesis.telemetry.constants import ConversationContext

    if text:
        trace.get_current_span().set_attribute(attribute, text[: ConversationContext.MAX_IO_LENGTH])


def recording_turn(
    func: Callable,
    args: tuple,
    kwargs: dict,
    request_mapping: Optional[dict],
    response_mapping: Optional[dict],
) -> Callable:
    """``func``, recording the turn's input and output on its span when called directly as
    the root of a trace; ``func`` itself otherwise."""
    if not _is_direct_root():
        return func

    from rhesis.telemetry.constants import ConversationContext

    names = ConversationContext.SpanAttributes
    text_in = turn_input(func, args, kwargs, request_mapping)

    if _is_async(func):

        @wraps(func)
        async def recorded_async(*a: Any, **kw: Any) -> Any:
            _record(names.CONVERSATION_INPUT, text_in)
            result = await func(*a, **kw)
            _record(names.CONVERSATION_OUTPUT, turn_output(result, response_mapping))
            return result

        return recorded_async

    @wraps(func)
    def recorded(*a: Any, **kw: Any) -> Any:
        import inspect

        _record(names.CONVERSATION_INPUT, text_in)
        result = func(*a, **kw)
        # A stream's output is only known once it is read; it is left unrecorded.
        if not inspect.isgenerator(result):
            _record(names.CONVERSATION_OUTPUT, turn_output(result, response_mapping))
        return result

    return recorded


def _is_async(func: Callable) -> bool:
    import inspect

    return inspect.iscoroutinefunction(func)
