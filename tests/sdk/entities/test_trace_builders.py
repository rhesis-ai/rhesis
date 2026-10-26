"""Traces built in memory from a response or a conversation."""

import pytest

from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics.conversational.types import ConversationHistory


def test_a_response_reads_back_through_the_trace():
    trace = Trace.from_response(
        "Refund order 42",
        "Done.",
        context=["Refunds take 5 days.", "Contact support."],
        tool_calls=[{"name": "lookup_order", "arguments": {"order": 42}, "output": "found"}],
        metadata={"intent": "refund"},
    )

    assert (trace.input, trace.output) == ("Refund order 42", "Done.")
    assert trace.context == ["Refunds take 5 days.", "Contact support."]
    assert trace.tool_calls == [
        {"name": "lookup_order", "arguments": {"order": 42}, "output": "found"}
    ]
    assert trace.metadata == {"intent": "refund"}
    assert not trace.is_conversation


def test_openai_shaped_tool_calls_read_back_flat():
    trace = Trace.from_response(
        "Book",
        "Booked.",
        tool_calls=[
            {"id": "c1", "type": "function", "function": {"name": "book", "arguments": '{"r": 4}'}}
        ],
    )

    assert trace.tool_calls == [{"name": "book", "arguments": {"r": 4}, "output": None}]


def test_a_bare_response_has_no_spans_beyond_its_invocation():
    trace = Trace.from_response("Hi", "Hello")

    assert len(trace.spans()) == 1
    assert (trace.context, trace.tool_calls, trace.metadata) == ([], [], {})


def test_a_structured_output_is_kept_as_text():
    trace = Trace.from_response("Hi", {"answer": "Hello"})

    assert trace.output == '{"answer": "Hello"}'


def test_a_built_trace_never_fetches_itself():
    """It has a trace_id but nothing stored under it."""
    trace = Trace.from_conversation([])

    assert trace.messages().messages == []
    assert trace.context == []


def test_a_conversation_has_one_turn_per_user_message_and_reply():
    trace = Trace.from_conversation(
        [
            {"role": "system", "content": "You are a travel agent."},
            {"role": "user", "content": "Book Paris."},
            {"role": "assistant", "content": "Which dates?"},
            {"role": "user", "content": "Friday."},
            {"role": "assistant", "content": "Booked."},
        ]
    )

    assert trace.is_conversation
    assert [(t.user_message, t.assistant_response) for t in trace.conversation()] == [
        ("Book Paris.", "Which dates?"),
        ("Friday.", "Booked."),
    ]


def test_a_reply_without_a_user_message_is_a_turn_of_its_own():
    trace = Trace.from_conversation(
        [
            {"role": "assistant", "content": "Welcome!"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "How can I help?"},
        ]
    )

    assert [(t.user_message, t.assistant_response) for t in trace.conversation()] == [
        ("", "Welcome!"),
        ("Hi", "How can I help?"),
    ]


def test_a_reply_with_only_tool_calls_keeps_them():
    trace = Trace.from_conversation(
        [
            {"role": "user", "content": "Book room 4."},
            {"role": "assistant", "content": None, "tool_calls": [{"name": "book"}]},
        ]
    )

    reply = trace.messages().messages[-1]
    assert reply.role == "assistant"
    assert reply.content is None
    assert reply.tool_calls == [{"name": "book", "arguments": None, "output": None}]


def test_a_conversation_keeps_its_id_or_gets_one():
    history = ConversationHistory.from_messages(
        [{"role": "user", "content": "Hi"}], conversation_id="conv-1"
    )

    assert Trace.from_conversation(history).conversation_id == "conv-1"
    assert Trace.from_conversation(history, conversation_id="conv-2").conversation_id == "conv-2"
    assert Trace.from_conversation([{"role": "user", "content": "Hi"}]).conversation_id


def test_a_one_turn_conversation_is_still_a_conversation():
    trace = Trace.from_conversation(
        [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    )

    assert trace.is_conversation


def test_messages_reproduce_the_transcript_a_judge_sees():
    history = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "What does policy X cover?"},
            {
                "role": "assistant",
                "content": "Accidents.",
                "context": ["Policy X covers accidents."],
                "metadata": {"source": "kb"},
            },
            {"role": "user", "content": "Book a call."},
            {
                "role": "assistant",
                "content": "Booked.",
                "tool_calls": [{"name": "book_call", "arguments": {"at": "9"}, "output": "ok"}],
            },
        ]
    )

    rebuilt = Trace.from_conversation(history).messages()

    assert rebuilt.format_conversation() == history.format_conversation()


def test_tool_calls_stay_on_the_turn_that_made_them():
    trace = Trace.from_conversation(
        [
            {"role": "user", "content": "Find order 42."},
            {"role": "assistant", "content": "Found.", "tool_calls": [{"name": "lookup"}]},
            {"role": "user", "content": "Refund it."},
            {"role": "assistant", "content": "Refunded.", "tool_calls": [{"name": "refund"}]},
        ]
    )

    per_turn = trace.messages().get_assistant_tool_calls()

    assert [[call["name"] for call in calls] for calls in per_turn] == [["lookup"], ["refund"]]
    assert [call["name"] for call in trace.tool_calls] == ["lookup", "refund"]


@pytest.mark.parametrize("conversation", ["Hi there", {"role": "user", "content": "Hi"}, [42]])
def test_something_that_is_not_a_conversation_is_refused(conversation):
    with pytest.raises(TypeError, match="ConversationHistory or a list of messages"):
        Trace.from_conversation(conversation)


def test_metadata_that_is_not_a_dict_still_reads_back():
    trace = Trace.from_response("Hi", "Hello", metadata=["source:kb", "lang:en"])

    assert trace.metadata == ["source:kb", "lang:en"]


def test_one_turn_of_a_longer_conversation_is_judged_as_that_turn():
    trace = Trace.from_response("Hi", "Hello")
    trace.conversation_id = "conv-1"

    assert not trace.is_conversation
