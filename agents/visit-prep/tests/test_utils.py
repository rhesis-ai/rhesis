"""ChatMessage helpers used by the coordinator tools and the turn layer."""

import pytest
from haystack.dataclasses import ChatMessage, ToolCall

from visit_prep.utils import (
    as_text,
    conversation_messages,
    latest_user_text,
    tool_result_text,
    user_texts,
)


def _tool_message(name: str, result: str) -> ChatMessage:
    return ChatMessage.from_tool(
        tool_result=result, origin=ToolCall(id=f"call-{name}", tool_name=name, arguments={})
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("already text", "already text"), (9, "9"), (2.5, "2.5"), (True, "True"), (None, "")],
)
def test_as_text_coerces_non_strings(value, expected):
    assert as_text(value) == expected


def test_user_texts_coerces_non_string_content():
    """A ChatMessage does not validate its content, so a number can be sitting in one."""
    assert user_texts([ChatMessage.from_user(9)]) == ["9"]


def test_user_texts_skips_other_roles():
    messages = [
        ChatMessage.from_system("system"),
        ChatMessage.from_user("first"),
        ChatMessage.from_assistant("reply"),
        ChatMessage.from_user("second"),
    ]
    assert user_texts(messages) == ["first", "second"]


def test_latest_user_text_picks_the_most_recent():
    messages = [ChatMessage.from_user("old"), ChatMessage.from_user("new")]
    assert latest_user_text(messages) == "new"


def test_latest_user_text_empty_when_no_user_message():
    assert latest_user_text([ChatMessage.from_system("system")]) == ""


def test_conversation_messages_drops_system_tool_and_tool_calls():
    messages = [
        ChatMessage.from_system("system"),
        ChatMessage.from_user("I have a headache"),
        ChatMessage.from_assistant(tool_calls=[ToolCall(id="1", tool_name="t", arguments={})]),
        _tool_message("t", "done"),
        ChatMessage.from_assistant("How severe is it?"),
    ]
    kept = conversation_messages(messages)
    assert [m.text for m in kept] == ["I have a headache", "How severe is it?"]


def test_conversation_messages_keeps_only_the_recent_window():
    messages = [ChatMessage.from_user(str(i)) for i in range(20)]
    assert [m.text for m in conversation_messages(messages, limit=3)] == ["17", "18", "19"]


def test_tool_result_text_reads_the_first_result():
    assert tool_result_text(_tool_message("check_red_flags", "No red flags")) == "No red flags"


def test_tool_result_text_falls_back_to_message_text():
    assert tool_result_text(ChatMessage.from_assistant("plain")) == "plain"
