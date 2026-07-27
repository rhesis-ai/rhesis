"""Tests for LangGraphTarget file-attachment support."""

from typing import Annotated, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from rhesis.penelope.targets.langgraph import LangGraphTarget

SAMPLE_FILES = [
    {"filename": "image.png", "content_type": "image/png", "data": "aW1hZ2U="},
]


class _State(TypedDict):
    messages: Annotated[list, add_messages]


@pytest.fixture
def echo_graph():
    def echo_node(state):
        last = state["messages"][-1]
        return {"messages": [AIMessage(content=f"echo: {type(last.content).__name__}")]}

    graph = StateGraph(_State)
    graph.add_node("agent", echo_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile()


def test_send_message_without_files_uses_plain_string_content(echo_graph):
    target = LangGraphTarget(echo_graph, "test-target")

    target.send_message("hello")

    stored: HumanMessage = target._session_states["default"][0]
    assert stored.content == "hello"


def test_send_message_with_files_builds_content_blocks(echo_graph):
    target = LangGraphTarget(echo_graph, "test-target")

    response = target.send_message("What is this?", files=SAMPLE_FILES)

    assert response.success is True
    stored: HumanMessage = target._session_states["default"][0]
    assert isinstance(stored.content, list)
    assert stored.content[0]["type"] == "text"
    assert stored.content[1]["type"] == "image"
    assert stored.content[1]["mime_type"] == "image/png"


# --- Native async path (a_send_message via ainvoke) ---


def test_a_send_message_uses_native_ainvoke(echo_graph):
    import asyncio
    from unittest.mock import patch

    target = LangGraphTarget(echo_graph, "test-target")

    # a_send_message must go through the graph's native ainvoke, never the
    # sync invoke (which the base-class thread-pool fallback would call).
    with patch.object(
        type(echo_graph), "invoke", side_effect=AssertionError("sync invoke must not be called")
    ):
        response = asyncio.run(target.a_send_message("hello"))

    assert response.success is True
    assert "echo:" in response.content


def test_a_send_message_maintains_session_state(echo_graph):
    import asyncio

    target = LangGraphTarget(echo_graph, "test-target")

    asyncio.run(target.a_send_message("first", conversation_id="s1"))
    response = asyncio.run(target.a_send_message("second", conversation_id="s1"))

    assert response.success is True
    # user+ai per turn, accumulated across both turns
    assert response.metadata["session_messages_count"] == 4


def test_a_send_message_with_files_builds_content_blocks(echo_graph):
    import asyncio

    target = LangGraphTarget(echo_graph, "test-target")

    response = asyncio.run(target.a_send_message("What is this?", files=SAMPLE_FILES))

    assert response.success is True
    stored: HumanMessage = target._session_states["default"][0]
    assert isinstance(stored.content, list)
    assert stored.content[0]["type"] == "text"
    assert stored.content[1]["type"] == "image"


def test_a_send_message_falls_back_without_ainvoke():
    """Regression: validate_configuration only requires invoke(), so a
    duck-typed graph without ainvoke() must fall back to the thread-pool
    path instead of raising AttributeError."""
    import asyncio

    class _SyncOnlyGraph:
        def invoke(self, state):
            return {"messages": [*state["messages"], AIMessage(content="sync ok")]}

    target = LangGraphTarget(_SyncOnlyGraph(), "test-target")

    response = asyncio.run(target.a_send_message("hello"))

    assert response.success is True
    assert response.content == "sync ok"
