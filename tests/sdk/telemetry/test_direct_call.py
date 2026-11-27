"""An @endpoint called directly records its turn's input and output itself."""

import asyncio
from unittest.mock import MagicMock, patch

from rhesis.telemetry.constants import ConversationContext

from rhesis.sdk.decorators.direct_call import (
    connector_call,
    recording_turn,
    turn_input,
    turn_output,
)

INPUT = ConversationContext.SpanAttributes.CONVERSATION_INPUT
OUTPUT = ConversationContext.SpanAttributes.CONVERSATION_OUTPUT


def chat(input: str, session_id: str | None = None):
    return {"output": f"echo {input}", "session_id": session_id}


def test_the_input_is_the_argument_mapped_to_input():
    def ask(question, policy_id):
        pass

    assert turn_input(ask, ("hi", 7), {}, {"question": "{{ input }}"}) == "hi"
    assert turn_input(chat, (), {"input": "hello"}, None) == "hello"
    assert turn_input(ask, ("hi", 7), {}, None) is None


def test_the_output_follows_the_response_mapping():
    assert turn_output({"result": {"text": "a"}}, {"output": "$.result.text"}) == "a"
    assert turn_output({"output": "b"}, None) == "b"
    assert turn_output("c", None) == "c"
    assert turn_output({"answer": "d"}, None) is None


def _recorded(func, args, kwargs, run):
    span = MagicMock()
    with patch("opentelemetry.trace.get_current_span", return_value=span):
        result = run(recording_turn(func, args, kwargs, None, None))
    recorded = {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}
    return result, recorded


def test_a_direct_call_records_the_turn():
    result, recorded = _recorded(chat, ("hi",), {}, lambda f: f("hi"))

    assert result["output"] == "echo hi"
    assert recorded == {INPUT: "hi", OUTPUT: "echo hi"}


def test_an_async_direct_call_records_the_turn():
    async def achat(input: str):
        return f"echo {input}"

    _, recorded = _recorded(achat, ("hi",), {}, lambda f: asyncio.run(f("hi")))

    assert recorded == {INPUT: "hi", OUTPUT: "echo hi"}


def test_a_connector_call_is_left_to_the_platform():
    with connector_call():
        assert recording_turn(chat, ("hi",), {}, None, None) is chat


def test_a_nested_call_is_not_a_turn():
    with patch("rhesis.telemetry.context.get_root_trace_id", return_value="a" * 32):
        assert recording_turn(chat, ("hi",), {}, None, None) is chat


def test_a_direct_root_ends_its_trace_and_a_connector_root_does_not():
    from rhesis.telemetry.context import get_root_trace_id, set_root_trace_id

    from rhesis.sdk.telemetry.tracer import _end_direct_root

    set_root_trace_id("a" * 32)
    with connector_call():
        _end_direct_root()
        assert get_root_trace_id() == "a" * 32

    _end_direct_root()
    assert get_root_trace_id() is None
