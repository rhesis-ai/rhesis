"""Tests for the shape of the spans the LangChain/LangGraph callback emits.

These cover regressions where spans were silently dropped or fragmented:

- Graph nodes were only traced when their name happened to contain a word like
  "agent" or "specialist", so ordinary pipelines (researcher/analyst) and
  LangChain 1.x ``create_agent`` graphs (model/tools) emitted nothing.
- Skipping a chain also discarded it as a parent, so everything beneath a
  skipped run became a root span in its own trace.
"""

from typing import Annotated, List, TypedDict

import pytest
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from rhesis.sdk.telemetry.integrations.langchain.callback import (
    MAX_TRACKED_RUNS,
    create_langchain_callback,
)

AGENT_INVOKE = "ai.agent.invoke"
LLM_INVOKE = "ai.llm.invoke"
RETRIEVAL = "ai.retrieval"


class _FakeSpan:
    """Stands in for a span where only end/status behaviour matters."""

    def __init__(self) -> None:
        self.ended = False

    def set_status(self, *_args, **_kwargs) -> None:
        pass

    def end(self) -> None:
        self.ended = True


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@pytest.fixture
def exporter():
    """In-memory exporter wired to a provider the callback's tracer will use."""
    return InMemorySpanExporter()


@pytest.fixture
def callback(exporter, monkeypatch):
    """A callback handler whose spans land in `exporter`.

    Any span still open at teardown is closed, in reverse order of opening, so
    its OTel context token is released. A leaked token stays attached to the
    ambient context and silently reparents spans in later tests.
    """
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    handler = create_langchain_callback()
    monkeypatch.setattr(handler, "tracer", provider.get_tracer("test"))

    yield handler

    for run_id in reversed(list(handler._spans)):
        handler._end_span(run_id)


def build_pipeline(node_names: List[str]):
    """A linear graph of stub nodes, one per name."""
    graph = StateGraph(State)
    for name in node_names:
        graph.add_node(name, lambda s, n=name: {"messages": [AIMessage(content=n)]})
    graph.add_edge(START, node_names[0])
    for src, dst in zip(node_names, node_names[1:], strict=False):
        graph.add_edge(src, dst)
    graph.add_edge(node_names[-1], END)
    return graph.compile()


def run_pipeline(callback, node_names: List[str]):
    build_pipeline(node_names).invoke(
        {"messages": [HumanMessage(content="hi")]}, config={"callbacks": [callback]}
    )


def named(spans, name):
    return [s for s in spans if s.name == name]


def agent_names(spans):
    return {s.attributes.get("ai.agent.name") for s in named(spans, AGENT_INVOKE)}


class TestNodesAreTracedRegardlessOfName:
    """Every LangGraph node is traced, not only ones named like an agent."""

    @pytest.mark.parametrize(
        "node_names",
        [
            pytest.param(["researcher", "analyst", "summarizer"], id="ordinary-names"),
            pytest.param(["model", "tools"], id="langchain-1x-create-agent"),
            pytest.param(["orchestrator", "safety_specialist"], id="agentish-names"),
        ],
    )
    def test_every_node_gets_a_span(self, callback, exporter, node_names):
        run_pipeline(callback, node_names)
        spans = exporter.get_finished_spans()
        assert agent_names(spans) >= set(node_names)

    def test_graph_root_is_traced(self, callback, exporter):
        run_pipeline(callback, ["researcher", "analyst"])
        spans = exporter.get_finished_spans()
        roots = [s for s in named(spans, AGENT_INVOKE) if s.parent is None]
        assert len(roots) == 1

    def test_conditional_edge_router_is_not_a_second_copy_of_the_node(self, callback, exporter):
        """A routing function inherits the node's metadata verbatim."""
        calls = {"n": 0}

        def model_agent(state: State):
            calls["n"] += 1
            return {"messages": [AIMessage(content="loop")]}

        graph = StateGraph(State)
        graph.add_node("model_agent", model_agent)
        graph.add_node("tool_agent", lambda s: {"messages": [AIMessage(content="tool")]})
        graph.set_entry_point("model_agent")
        graph.add_conditional_edges(
            "model_agent",
            lambda s: "tool_agent" if calls["n"] < 2 else END,
            {"tool_agent": "tool_agent", END: END},
        )
        graph.add_edge("tool_agent", "model_agent")
        graph.compile().invoke(
            {"messages": [HumanMessage(content="go")]}, config={"callbacks": [callback]}
        )

        spans = exporter.get_finished_spans()
        model_spans = [
            s
            for s in named(spans, AGENT_INVOKE)
            if s.attributes.get("ai.agent.name") == "model_agent"
        ]
        assert len(model_spans) == calls["n"]


class TestTraceStaysWhole:
    """A graph run is one trace, with nothing orphaned."""

    def test_single_trace_per_run(self, callback, exporter):
        run_pipeline(callback, ["researcher", "analyst", "summarizer"])
        spans = exporter.get_finished_spans()
        assert len({s.context.trace_id for s in spans}) == 1

    def test_llm_spans_nest_under_their_node(self, callback, exporter):
        """LLM calls inside a node must not become root spans."""

        def llm_node(state: State):
            llm = GenericFakeChatModel(messages=iter([AIMessage(content="ok")] * 5))
            return {"messages": [llm.invoke(state["messages"])]}

        graph = StateGraph(State)
        graph.add_node("researcher", llm_node)
        graph.add_edge(START, "researcher")
        graph.add_edge("researcher", END)
        graph.compile().invoke(
            {"messages": [HumanMessage(content="hi")]}, config={"callbacks": [callback]}
        )

        spans = exporter.get_finished_spans()
        llm_spans = named(spans, LLM_INVOKE)
        assert llm_spans
        assert all(s.parent is not None for s in llm_spans)
        assert len({s.context.trace_id for s in spans}) == 1


class TestLcelNoiseIsStillFiltered:
    """Anonymous LCEL steps stay out of the trace."""

    def test_plain_lcel_chain_emits_no_agent_spans(self, callback, exporter):
        llm = GenericFakeChatModel(messages=iter([AIMessage(content="ok")] * 5))
        chain = ChatPromptTemplate.from_template("say {x}") | llm | StrOutputParser()
        chain.invoke({"x": "hi"}, config={"callbacks": [callback]})

        spans = exporter.get_finished_spans()
        assert named(spans, AGENT_INVOKE) == []
        assert len(named(spans, LLM_INVOKE)) == 1


class TestSequentialEdgesAreNotHandoffs:
    """Only an explicit transfer is a handoff; a graph edge is not."""

    def test_linear_pipeline_emits_no_handoff_spans(self, callback, exporter):
        run_pipeline(callback, ["orchestrator", "safety_specialist", "synthesis_agent"])
        spans = exporter.get_finished_spans()
        assert named(spans, "ai.agent.handoff") == []


class TestPromptCapture:
    """The whole prompt is recorded, not just its first message."""

    def test_every_message_becomes_a_prompt_event(self, callback, exporter):
        llm = GenericFakeChatModel(messages=iter([AIMessage(content="ok")] * 5))
        llm.invoke(
            [
                SystemMessage(content="You are helpful."),
                HumanMessage(content="earlier question"),
                AIMessage(content="earlier answer"),
                HumanMessage(content="the real question"),
            ],
            config={"callbacks": [callback]},
        )

        spans = exporter.get_finished_spans()
        events = [e for e in named(spans, LLM_INVOKE)[0].events if e.name == "ai.prompt"]
        assert len(events) == 4
        contents = [e.attributes.get("ai.prompt.content") for e in events]
        assert "the real question" in contents
        assert [e.attributes.get("ai.prompt.role") for e in events] == [
            "system",
            "human",
            "ai",
            "human",
        ]


class FakeRetriever(BaseRetriever):
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        return [Document(page_content=f"about {query}"), Document(page_content="second")]


class TestRetrievalSpans:
    """Retrieval is traced, so RAG pipelines are not invisible."""

    def test_retriever_emits_a_span_with_query_and_results(self, callback, exporter):
        FakeRetriever().invoke("refund policy", config={"callbacks": [callback]})

        spans = exporter.get_finished_spans()
        retrieval = named(spans, RETRIEVAL)
        assert len(retrieval) == 1

        span = retrieval[0]
        assert span.attributes.get("ai.retrieval.top_k") == 2
        event_names = {e.name for e in span.events}
        assert {"ai.retrieval.query", "ai.retrieval.results"} <= event_names

    def test_retriever_error_marks_the_span(self, callback, exporter):
        class Failing(BaseRetriever):
            def _get_relevant_documents(self, query, *, run_manager):
                raise RuntimeError("index offline")

        with pytest.raises(RuntimeError):
            Failing().invoke("q", config={"callbacks": [callback]})

        retrieval = named(exporter.get_finished_spans(), RETRIEVAL)
        assert len(retrieval) == 1
        assert retrieval[0].status.status_code.name == "ERROR"


class TestBookkeepingIsBounded:
    """Runs that never complete must not accumulate forever.

    Driven through the tracking helpers rather than ``on_chain_start``: the real
    path attaches an OTel context token per span, and thousands of those left
    open would leak into the ambient context of later tests.
    """

    def test_skipped_run_tracking_is_capped(self, callback):
        for i in range(MAX_TRACKED_RUNS + 100):
            callback._skip_run(f"run-{i}", None)

        assert len(callback._skipped_parents) <= MAX_TRACKED_RUNS

    def test_open_span_tracking_is_capped(self, callback):
        for i in range(MAX_TRACKED_RUNS + 50):
            callback._track_span(f"run-{i}", (_FakeSpan(), None, ()))

        assert len(callback._spans) <= MAX_TRACKED_RUNS

    def test_evicted_span_is_ended_so_it_still_exports(self, callback):
        oldest = _FakeSpan()
        callback._track_span("run-oldest", (oldest, None, ()))
        for i in range(MAX_TRACKED_RUNS):
            callback._track_span(f"run-{i}", (_FakeSpan(), None, ()))

        assert "run-oldest" not in callback._spans
        assert oldest.ended, "an evicted span must be ended, or it never exports"

    def test_eviction_clears_the_matching_agent_entry(self, callback):
        callback._track_span("run-oldest", (_FakeSpan(), None, ()))
        callback._agent_run_ids["run-oldest"] = "some-agent"
        for i in range(MAX_TRACKED_RUNS):
            callback._track_span(f"run-{i}", (_FakeSpan(), None, ()))

        assert "run-oldest" not in callback._agent_run_ids
