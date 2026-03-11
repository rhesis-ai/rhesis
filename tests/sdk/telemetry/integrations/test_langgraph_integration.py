"""Tests for LangGraph auto-instrumentation integration.

Verifies that the SDK correctly patches LangGraph's CompiledStateGraph
to inject telemetry callbacks, and that multi-node graphs with tools
work through the instrumented path.
"""

from typing import Annotated, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

import rhesis.sdk.telemetry.integrations.langgraph as lg_module
from rhesis.sdk.telemetry.integrations.langchain.extractors import (
    extract_agent_name,
)
from rhesis.sdk.telemetry.integrations.langchain.utils import (
    ensure_callback_in_config,
)
from rhesis.sdk.telemetry.integrations.langgraph import (
    GraphPatchState,
    LangGraphIntegration,
)


class SimpleState(TypedDict):
    messages: Annotated[list, add_messages]


@pytest.fixture(autouse=True)
def reset_patch_state():
    """Reset graph patching state before each test."""
    lg_module._graph_patching_done = False
    lg_module._original_graph_invoke = None
    lg_module._original_graph_ainvoke = None
    lg_module._original_graph_stream = None
    lg_module._original_graph_astream = None
    yield


@pytest.fixture
def integration():
    """Create a fresh LangGraphIntegration."""
    return LangGraphIntegration()


@pytest.fixture
def echo_graph():
    """Build a minimal single-node graph."""
    graph = StateGraph(SimpleState)
    graph.add_node("echo", lambda s: {"messages": s["messages"]})
    graph.add_edge(START, "echo")
    graph.add_edge("echo", END)
    return graph.compile()


@tool
def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"Sunny, 72F in {location}"


def _build_tool_graph():
    """Build a multi-node graph with tool calling (research-assistant pattern)."""

    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]

    tools = [get_weather]
    tool_node = ToolNode(tools)

    def reasoning(state):
        msgs = state["messages"]
        last = msgs[-1]
        if isinstance(last, HumanMessage):
            return {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "get_weather",
                                "args": {"location": "NYC"},
                                "id": "call_1",
                            }
                        ],
                    )
                ]
            }
        elif isinstance(last, ToolMessage):
            return {"messages": [AIMessage(content=f"Result: {last.content}")]}
        return {"messages": [AIMessage(content="No action needed")]}

    def should_continue(state):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("reasoning", reasoning)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "reasoning")
    graph.add_conditional_edges("reasoning", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "reasoning")
    return graph.compile()


# --- Import and API surface tests ---


class TestLangGraphImports:
    def test_compiled_state_graph_import(self):
        assert CompiledStateGraph is not None

    def test_compiled_state_graph_has_invoke(self):
        assert hasattr(CompiledStateGraph, "invoke")

    def test_compiled_state_graph_has_ainvoke(self):
        assert hasattr(CompiledStateGraph, "ainvoke")

    def test_compiled_state_graph_has_stream(self):
        assert hasattr(CompiledStateGraph, "stream")

    def test_compiled_state_graph_has_astream(self):
        assert hasattr(CompiledStateGraph, "astream")


# --- Integration enable/patching tests ---


class TestGraphPatching:
    def test_enable_succeeds(self, integration):
        assert integration.enable() is True
        assert integration.enabled is True

    def test_enable_patches_all_methods(self, integration):
        integration.enable()
        assert GraphPatchState.is_done()
        assert GraphPatchState.get_invoke() is not None
        assert GraphPatchState.get_ainvoke() is not None
        assert GraphPatchState.get_stream() is not None
        assert GraphPatchState.get_astream() is not None

    def test_invoke_is_patched(self, integration):
        integration.enable()
        original = GraphPatchState.get_invoke()
        assert CompiledStateGraph.invoke is not original

    def test_callback_is_created(self, integration):
        integration.enable()
        assert integration._callback is not None

    def test_callback_type(self, integration):
        integration.enable()
        assert type(integration._callback).__name__ == "RhesisLangChainCallback"

    def test_enable_idempotent(self, integration):
        integration.enable()
        first_callback = integration._callback
        integration.enable()
        assert integration._callback is first_callback


# --- Callback injection tests ---


class TestCallbackInjection:
    def test_inject_into_none_config(self, integration):
        integration.enable()
        config = ensure_callback_in_config(None, integration._callback)
        assert "callbacks" in config
        assert integration._callback in config["callbacks"]

    def test_inject_preserves_existing_config(self, integration):
        integration.enable()
        config = ensure_callback_in_config(
            {"configurable": {"thread_id": "1"}}, integration._callback
        )
        assert config["configurable"]["thread_id"] == "1"
        assert integration._callback in config["callbacks"]

    def test_inject_deduplicates(self, integration):
        integration.enable()
        cb = integration._callback
        config = ensure_callback_in_config({"callbacks": [cb]}, cb)
        assert len(config["callbacks"]) == 1

    def test_inject_into_empty_callbacks(self, integration):
        integration.enable()
        config = ensure_callback_in_config({"callbacks": []}, integration._callback)
        assert len(config["callbacks"]) == 1


# --- Graph invocation through instrumented path ---


class TestInstrumentedInvocation:
    def test_echo_graph(self, integration, echo_graph):
        integration.enable()
        result = echo_graph.invoke({"messages": [HumanMessage(content="hello")]})
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "hello"

    def test_echo_graph_is_compiled_state_graph(self, echo_graph):
        assert isinstance(echo_graph, CompiledStateGraph)

    def test_multi_node_tool_graph(self, integration):
        integration.enable()
        compiled = _build_tool_graph()
        result = compiled.invoke({"messages": [HumanMessage(content="Weather in NYC?")]})
        assert len(result["messages"]) == 4
        assert isinstance(result["messages"][0], HumanMessage)
        assert isinstance(result["messages"][1], AIMessage)
        assert result["messages"][1].tool_calls
        assert isinstance(result["messages"][2], ToolMessage)
        assert "Sunny" in result["messages"][2].content
        assert isinstance(result["messages"][3], AIMessage)
        assert "Sunny" in result["messages"][3].content

    def test_streaming(self, integration):
        integration.enable()
        compiled = _build_tool_graph()
        chunks = list(compiled.stream({"messages": [HumanMessage(content="Weather?")]}))
        assert len(chunks) == 3
        node_names = [list(c.keys())[0] for c in chunks]
        assert node_names == ["reasoning", "tools", "reasoning"]


# --- Metadata extractor tests ---


class TestMetadataExtractors:
    def test_langgraph_node_extraction(self):
        name = extract_agent_name(None, None, metadata={"langgraph_node": "orchestrator"})
        assert name == "orchestrator"

    def test_langgraph_node_specialist(self):
        name = extract_agent_name(None, None, metadata={"langgraph_node": "safety_specialist"})
        assert name == "safety_specialist"

    def test_agent_name_takes_priority(self):
        name = extract_agent_name(
            None,
            None,
            metadata={
                "agent_name": "custom",
                "langgraph_node": "orchestrator",
            },
        )
        assert name == "custom"

    def test_serialized_name_fallback(self):
        name = extract_agent_name({"name": "ChatGoogleGenerativeAI"}, None, metadata={})
        assert name == "ChatGoogleGenerativeAI"

    def test_no_metadata_returns_unknown(self):
        name = extract_agent_name(None, None, metadata={})
        assert name == "unknown"

    def test_none_metadata_returns_unknown(self):
        name = extract_agent_name(None, None, metadata=None)
        assert name == "unknown"
