"""End to end against a running Rhesis, through a real OpenTelemetry Collector.

Opt-in: skipped unless ``RHESIS_E2E_BASE_URL`` is set. Nothing is faked. An agent
instrumented with the real OpenTelemetry SDK exports GenAI-convention spans with
``BatchSpanProcessor`` + ``OTLPSpanExporter`` (http/protobuf) to a Collector, which
batches and relays them with ``otlphttp`` (gzip, bearer header) to the API, which
queues them for a Celery worker. The test then reads the result back through the
public API.

Run it (from apps/backend, against ``./rh dev backend`` + ``./rh dev worker``)::

    docker run --rm -d --name rhesis-otelcol -p 4318:4318 \\
      -e RHESIS_OTLP_ENDPOINT=http://host.docker.internal:8220/telemetry \\
      -e RHESIS_API_TOKEN=rh-local-token \\
      -v $PWD/../../tests/backend/ee/otlp/live/otelcol.yaml:/etc/otelcol/config.yaml \\
      otel/opentelemetry-collector-contrib:0.114.0 --config /etc/otelcol/config.yaml

    RHESIS_E2E_BASE_URL=http://localhost:8220 RHESIS_E2E_TOKEN=rh-local-token \\
    RHESIS_E2E_PROJECT_ID=<project uuid> \\
      uv run pytest ../../tests/backend/ee/otlp/live -p no:xdist -v

The organization needs the ``otlp_ingest`` feature (an Enterprise licence).
"""

import json
import os
import time
import uuid
from typing import Callable, Dict, List, Optional

import pytest
import requests
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

BASE_URL = os.environ.get("RHESIS_E2E_BASE_URL")
TOKEN = os.environ.get("RHESIS_E2E_TOKEN", "")
PROJECT_ID = os.environ.get("RHESIS_E2E_PROJECT_ID", "")
COLLECTOR = os.environ.get("RHESIS_E2E_COLLECTOR", "http://localhost:4318/v1/traces")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="RHESIS_E2E_BASE_URL not set")

MODEL = "example-model"
AGENT = "research-agent"
LONG_ANSWER = "Lisbon has been sunny all week. " + "x" * 32_000
READ_FILES = 20


def _messages(*pairs) -> str:
    return json.dumps(
        [{"role": role, "parts": [{"type": "text", "content": text}]} for role, text in pairs]
    )


def _chat(tracer, prompt: str, reply: str, input_tokens: int, output_tokens: int, cached=0):
    attrs = {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "openai",
        "gen_ai.request.model": MODEL,
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.input.messages": _messages(("user", prompt)),
        "gen_ai.output.messages": _messages(("assistant", reply)),
    }
    if cached:
        attrs["gen_ai.usage.cache_read.input_tokens"] = cached
    with tracer.start_as_current_span(f"chat {MODEL}", kind=SpanKind.CLIENT, attributes=attrs):
        time.sleep(0.01)


def _tool(tracer, name: str, arguments: dict, result, **extra):
    attrs = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": name,
        "gen_ai.tool.call.arguments": json.dumps(arguments),
        "gen_ai.tool.call.result": result if isinstance(result, str) else json.dumps(result),
        **extra,
    }
    return tracer.start_as_current_span(f"execute_tool {name}", attributes=attrs)


def _turn(tracer, conversation: str, question: str, answer: str, history=()):
    """One research agent turn. Only the root carries the conversation id."""
    with tracer.start_as_current_span(
        f"invoke_agent {AGENT}",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": AGENT,
            "gen_ai.conversation.id": conversation,
            "gen_ai.request.model": MODEL,
            "gen_ai.usage.input_tokens": 99_999,  # aggregate; must not be counted
            "gen_ai.usage.output_tokens": 99_999,
            "gen_ai.input.messages": _messages(*history, ("user", question)),
            "gen_ai.output.messages": _messages(("assistant", answer)),
        },
    ):
        with tracer.start_as_current_span(
            "plan research", attributes={"gen_ai.operation.name": "plan"}
        ):
            pass
        _chat(tracer, question, "calling tools", 1000, 50, cached=400)
        with _tool(tracer, "web_search", {"q": "Lisbon forecast"}, {"hits": [{"title": "10-K"}]}):
            pass
        for index in range(READ_FILES):
            with _tool(tracer, "read_file", {"path": f"notes/{index}.md"}, f"# note {index}"):
                pass
        # Agent as tool: control passes to another agent through a tool call.
        with _tool(
            tracer,
            "transfer_to_weather_agent",
            {"city": "Berlin"},
            "sunny",
            **{
                "gen_ai.transfer.mode": "return_to_caller",
                "gen_ai.transfer.target.name": "weather_agent",
            },
        ):
            with tracer.start_as_current_span(
                "invoke_agent weather_agent",
                attributes={
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": "weather_agent",
                },
            ):
                _chat(tracer, "weather in Berlin?", "sunny", 200, 10)
        # A "task" tool running a sub-agent with its own model and tool calls.
        with _tool(tracer, "task", {"goal": "find the forecast"}, "sunny"):
            with tracer.start_as_current_span(
                "invoke_agent researcher",
                attributes={
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": "researcher",
                },
            ):
                _chat(tracer, "find the forecast", "sunny", 300, 20)
                with _tool(tracer, "web_search", {"q": "forecast"}, {"hits": []}):
                    pass
        with _tool(tracer, "flaky_api", {"id": 1}, "", **{"error.type": "TimeoutError"}) as span:
            span.add_event(
                "gen_ai.execute_tool.exception",
                {"exception.type": "TimeoutError", "exception.message": "upstream took 30s"},
            )
            span.set_status(Status(StatusCode.ERROR))
        _chat(tracer, "summarise", answer[:200], 1500, 80)


# Per turn: root, plan, two chats, web_search, the read_files, the handoff with its
# agent and chat, the task tool with its sub-agent, chat and web_search, flaky_api.
SPANS_PER_TURN = 1 + 1 + 2 + 1 + READ_FILES + 3 + 4 + 1
TOKENS_PER_TURN = (1000 + 50) + (200 + 10) + (300 + 20) + (1500 + 80)


def _api(path: str, **params) -> requests.Response:
    return requests.get(
        f"{BASE_URL}{path}",
        params={"project_id": PROJECT_ID, **params},
        headers={"Authorization": f"Bearer {TOKEN}", "X-Project-Id": PROJECT_ID},
        timeout=30,
    )


def _wait_for(check: Callable[[], Optional[dict]], timeout: float = 90) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = check()
        if last is not None:
            return last
        time.sleep(1)
    raise AssertionError(f"timed out waiting for the worker to store the spans: {last}")


def _all_spans(nodes: List[dict]) -> List[dict]:
    out = []
    for node in nodes:
        out.append(node)
        out.extend(_all_spans(node.get("children", [])))
    return out


@pytest.fixture(scope="module")
def conversation() -> Dict[str, object]:
    """Two turns sent through the Collector, then a duplicate resend sent directly."""
    conversation_id = f"e2e-{uuid.uuid4()}"
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "agent-gateway",
                "deployment.environment.name": "e2e",
                "rhesis.project_id": PROJECT_ID,
            }
        )
    )
    collector = OTLPSpanExporter(endpoint=COLLECTOR)
    # Small batches so a turn reaches Rhesis over several requests, root last.
    provider.add_span_processor(BatchSpanProcessor(collector, max_export_batch_size=5))
    copy = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(copy))
    tracer = provider.get_tracer("example.agents", "1.0.0")

    _turn(tracer, conversation_id, "Plan a weekend trip to Lisbon", LONG_ANSWER)
    _turn(
        tracer,
        conversation_id,
        "And how does that compare to Porto?",
        "Porto will be cloudier.",
        history=[("user", "Plan a weekend trip to Lisbon"), ("assistant", "...")],
    )
    provider.force_flush()
    spans = copy.get_finished_spans()
    roots = sorted((s for s in spans if s.parent is None), key=lambda s: s.start_time)
    turn_ids = [format(r.context.trace_id, "032x") for r in roots]

    # An exporter retry of turn 2's early spans, straight to Rhesis.
    direct = OTLPSpanExporter(
        endpoint=f"{BASE_URL}/telemetry/v1/traces",
        headers={"Authorization": f"Bearer {TOKEN}"},
        compression=Compression.Gzip,
    )
    turn_2_children = [
        s
        for s in spans
        if s.parent is not None and format(s.context.trace_id, "032x") == turn_ids[1]
    ]
    assert direct.export(turn_2_children[:8]) == SpanExportResult.SUCCESS
    provider.shutdown()
    return {"id": conversation_id, "turn_ids": turn_ids, "span_count": len(spans)}


def _stored_trace(conversation) -> dict:
    def check():
        listed = _api("/telemetry/traces", conversation_id=conversation["id"]).json()["traces"]
        if len(listed) != 1:
            return None
        detail = _api(f"/telemetry/traces/{listed[0]['trace_id']}").json()
        if detail.get("span_count") != conversation["span_count"]:
            return None
        return {"listed": listed[0], "detail": detail}

    return _wait_for(check)


def test_both_turns_are_one_conversation_on_the_first_trace(conversation):
    stored = _stored_trace(conversation)
    first, second = conversation["turn_ids"]
    assert stored["listed"]["trace_id"] == first
    assert stored["detail"]["span_count"] == 2 * SPANS_PER_TURN  # the resend added nothing
    roots = sorted(stored["detail"]["root_spans"], key=lambda r: r["start_time"])
    assert [r["attributes"]["rhesis.conversation.input"] for r in roots] == [
        "Plan a weekend trip to Lisbon",
        "And how does that compare to Porto?",
    ]
    assert roots[1]["attributes"]["rhesis.otlp.source_trace_id"] == second
    # Turn 2 is still found by the id the agent (and other trace backends) know it by.
    found = _api("/telemetry/traces", search=second).json()["traces"]
    assert [t["trace_id"] for t in found] == [first]


def test_span_tree_and_translation(conversation):
    detail = _stored_trace(conversation)["detail"]
    spans = _all_spans(detail["root_spans"])
    by_name: Dict[str, List[dict]] = {}
    for span in spans:
        by_name.setdefault(span["span_name"], []).append(span)

    assert len(by_name["ai.agent.invoke"]) == 2 * 3  # root, weather agent, researcher
    assert len(by_name["ai.agent.plan"]) == 2
    handoffs = by_name["ai.agent.handoff"]
    assert len(handoffs) == 2
    assert {h["attributes"]["ai.agent.handoff.to"] for h in handoffs} == {"weather_agent"}
    # The agent it handed to sits under the handoff span.
    assert [c["span_name"] for c in handoffs[0]["children"]] == ["ai.agent.invoke"]
    assert handoffs[0]["children"][0]["attributes"]["ai.agent.name"] == "weather_agent"

    errors = [s for s in spans if s["status_code"] == "ERROR"]
    assert len(errors) == 2
    assert {e["status_message"] for e in errors} == {"TimeoutError: upstream took 30s"}

    tool = next(
        s for s in by_name["ai.tool.invoke"] if s["attributes"]["ai.tool.name"] == "web_search"
    )
    names = [e["name"] for e in tool["events"]]
    assert "ai.tool.input" in names and "ai.tool.output" in names

    chat = by_name["ai.llm.invoke"][0]
    assert chat["attributes"]["ai.model.name"] == MODEL
    assert {e["name"] for e in chat["events"]} >= {"ai.prompt", "ai.completion"}

    root = min(
        (s for s in spans if s["attributes"].get("rhesis.conversation.input")),
        key=lambda s: s["start_time"],
    )
    # 32k of content arrives whole (under the 128k default cut).
    assert root["attributes"]["rhesis.conversation.output"] == LONG_ANSWER
    assert root["attributes"]["otel.scope.name"] == "example.agents"


def test_tokens_count_model_calls_once(conversation):
    """The agents' aggregate usage is not added on top of their model calls.

    Waits, because the trace is re-enriched after turn 2 joins it.
    """
    first = conversation["turn_ids"][0]

    def check():
        detail = _api(f"/telemetry/traces/{first}").json()
        return detail if detail.get("total_tokens") == 2 * TOKENS_PER_TURN else None

    _stored_trace(conversation)
    assert _wait_for(check, timeout=60)["total_tokens"] == 2 * TOKENS_PER_TURN


def test_agent_filter_and_list(conversation):
    _stored_trace(conversation)
    agents = _api("/telemetry/agents").json()
    assert {AGENT, "weather_agent", "researcher"} <= set(agents)
    first = conversation["turn_ids"][0]
    assert first in [
        t["trace_id"] for t in _api("/telemetry/traces", agent="weather_agent").json()["traces"]
    ]
    listed = _api("/telemetry/traces", conversation_id=conversation["id"]).json()["traces"][0]
    assert listed["agent_name"] == AGENT


def test_unknown_project_is_refused():
    response = requests.post(
        f"{BASE_URL}/telemetry/v1/traces",
        data=b"",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "X-Project-Id": str(uuid.uuid4()),
        },
        timeout=30,
    )
    assert response.status_code == 403
