"""Tests for conversation grouping in the LangChain/LangGraph integration.

LangGraph checkpoints multi-turn state under ``thread_id``, so that is the
identity an app already treats as the conversation. The integration falls back
to it when the caller has not bound one, which is what lets turns of one
conversation share a trace without the app wrapping every turn itself.

Rides the global tracer provider, as OTEL honours only the first
``set_tracer_provider`` and other suites in this run may have installed it.
"""

from typing import Annotated, TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import (
    set_conversation_id,
    set_conversation_trace_id,
    set_root_trace_id,
)
from rhesis.telemetry.conversation import conversation_turn

from rhesis.sdk.telemetry.integrations.langchain.callback import create_langchain_callback

ATTRS = ConversationContext.SpanAttributes


@pytest.fixture(scope="module")
def provider_and_exporter():
    """Ride on the global provider; OTEL honours only the first set_tracer_provider."""
    captured = InMemorySpanExporter()
    existing = otel_trace.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        provider: TracerProvider = existing
    else:
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(captured))
    return provider, captured


@pytest.fixture
def spans(provider_and_exporter):
    provider, captured = provider_and_exporter
    captured.clear()
    yield lambda: (provider.force_flush(), captured.get_finished_spans())[1]
    captured.clear()


@pytest.fixture(autouse=True)
def reset_conversation_state():
    """Keep contextvars and the conversation anchors from leaking between tests."""
    from rhesis.telemetry import conversation as conversation_module

    conversation_module._anchors.clear()
    yield
    conversation_module._anchors.clear()
    set_conversation_id(None)
    set_conversation_trace_id(None)
    set_root_trace_id(None)


@pytest.fixture
def callback():
    return create_langchain_callback()


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_graph(*, checkpointer: bool):
    def llm_node(state: State):
        llm = GenericFakeChatModel(messages=iter([AIMessage(content="reply")] * 9))
        return {"messages": [llm.invoke(state["messages"])]}

    builder = StateGraph(State)
    builder.add_node("researcher", llm_node)
    builder.add_node("summarizer", llm_node)
    builder.add_edge(START, "researcher")
    builder.add_edge("researcher", "summarizer")
    builder.add_edge("summarizer", END)
    return builder.compile(checkpointer=InMemorySaver() if checkpointer else None)


@pytest.fixture
def graph():
    """A graph with a checkpointer, which is what makes thread_id meaningful."""
    return build_graph(checkpointer=True)


@pytest.fixture
def plain_graph():
    """A graph without a checkpointer, so it can run with no thread_id at all."""
    return build_graph(checkpointer=False)


def run_turn(graph, callback, message: str, thread_id: str | None = None):
    config: dict = {"callbacks": [callback]}
    if thread_id is not None:
        config["configurable"] = {"thread_id": thread_id}
    return graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)


def turn_roots(exported):
    return [s for s in exported if (s.attributes or {}).get(ATTRS.IS_TURN_ROOT)]


def conversation_by_trace(exported) -> dict:
    """The exporter's own rule: a turn root publishes its id for its whole trace."""
    return {
        s.context.trace_id: (s.attributes or {}).get(ATTRS.CONVERSATION_ID)
        for s in turn_roots(exported)
    }


class TestThreadIdGroupsTurns:
    def test_turns_sharing_a_thread_id_share_one_trace(self, graph, callback, spans):
        run_turn(graph, callback, "first", thread_id="session-42")
        run_turn(graph, callback, "second", thread_id="session-42")
        exported = spans()

        assert len({s.context.trace_id for s in exported}) == 1
        assert list(conversation_by_trace(exported).values()) == ["session-42"]

    def test_every_span_lands_on_the_attributed_trace(self, graph, callback, spans):
        run_turn(graph, callback, "first", thread_id="session-42")
        run_turn(graph, callback, "second", thread_id="session-42")
        exported = spans()

        attributed = conversation_by_trace(exported)
        assert exported
        assert all(s.context.trace_id in attributed for s in exported)

    def test_distinct_threads_stay_on_distinct_traces(self, graph, callback, spans):
        run_turn(graph, callback, "hi", thread_id="alice")
        run_turn(graph, callback, "hi", thread_id="bob")
        exported = spans()

        assert sorted(v for v in conversation_by_trace(exported).values()) == ["alice", "bob"]
        assert len({s.context.trace_id for s in exported}) == 2

    def test_only_the_graph_root_claims_the_turn(self, graph, callback, spans):
        run_turn(graph, callback, "first", thread_id="session-42")
        exported = spans()

        roots = turn_roots(exported)
        assert len(roots) == 1
        assert roots[0].parent is None

    def test_no_thread_id_claims_no_turn(self, plain_graph, callback, spans):
        run_turn(plain_graph, callback, "hi")
        assert turn_roots(spans()) == []


class TestBoundIdWins:
    def test_explicit_conversation_id_overrides_thread_id(self, graph, callback, spans):
        set_conversation_id("explicit-id")
        run_turn(graph, callback, "hi", thread_id="session-42")

        assert list(conversation_by_trace(spans()).values()) == ["explicit-id"]


class TestStandsDownWhenTurnIsOwnedElsewhere:
    """Two spans claiming is_turn_root makes the exporter detach a subtree."""

    def test_conversation_turn_keeps_ownership(self, graph, callback, spans):
        with conversation_turn("app-owned", input="hello") as turn:
            run_turn(graph, callback, "hello", thread_id="session-42")
            turn.output = "done"
        exported = spans()

        roots = turn_roots(exported)
        assert len(roots) == 1
        assert str(roots[0].name) == "function.conversation_turn"
        assert list(conversation_by_trace(exported).values()) == ["app-owned"]

    def test_stands_down_when_a_root_trace_is_already_published(self, graph, callback, spans):
        set_root_trace_id("a" * 32)
        run_turn(graph, callback, "hi", thread_id="session-42")

        assert turn_roots(spans()) == []

    def test_stands_down_inside_an_ambient_span(self, graph, callback, spans):
        tracer = otel_trace.get_tracer("test.ambient")
        with tracer.start_as_current_span("function.caller"):
            run_turn(graph, callback, "hi", thread_id="session-42")

        assert turn_roots(spans()) == []
