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
