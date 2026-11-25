"""GenAI-convention traces built with the real OpenTelemetry SDK, encoded as OTLP.

Shapes follow the spec examples (semantic-conventions-genai v0.1.0,
docs/gen-ai/non-normative/examples-agent-calls.md) and a typical research agent run:
an ``invoke_agent`` root with ``chat`` and ``execute_tool`` children, a nested
``task`` tool running a sub-agent, and content capture on.
"""

import base64
import gzip
import json
from contextlib import ExitStack
from dataclasses import dataclass
from typing import List, Optional, Sequence

from google.protobuf import json_format
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

MODEL = "example-model"
AGENT = "research-agent"
SERVICE = "agent-gateway"


def messages(*pairs: tuple) -> str:
    """``("user", "hi")`` pairs as a parts-format messages JSON string."""
    return json.dumps(
        [{"role": role, "parts": [{"type": "text", "content": text}]} for role, text in pairs]
    )


def tool_call_message(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "role": "assistant",
        "parts": [{"type": "tool_call", "id": call_id, "name": name, "arguments": arguments}],
    }


@dataclass
class Trace:
    spans: List[ReadableSpan]

    @property
    def root(self) -> ReadableSpan:
        return next(s for s in self.spans if s.parent is None)

    @property
    def children(self) -> List[ReadableSpan]:
        return [s for s in self.spans if s.parent is not None]

    @property
    def trace_id(self) -> str:
        return format(self.root.context.trace_id, "032x")

    def by_name(self, name: str) -> ReadableSpan:
        return next(s for s in self.spans if s.name == name)


def _provider(project_id: Optional[str], environment: Optional[str]):
    attrs = {"service.name": SERVICE}
    if project_id:
        attrs["rhesis.project_id"] = project_id
    if environment:
        attrs["deployment.environment.name"] = environment
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create(attrs))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def research_run(
    *,
    project_id: Optional[str] = None,
    conversation_id: Optional[str] = "conv-research-1",
    question: str = "Plan a weekend trip to Lisbon",
    answer: str = "Lisbon will be sunny all weekend.",
    environment: Optional[str] = "production",
    history: Sequence[tuple] = (),
    http_root: bool = False,
) -> Trace:
    """One turn of a research agent, optionally inside an HTTP server span."""
    provider, exporter = _provider(project_id, environment)
    tracer = provider.get_tracer("example.agents", "1.0.0")
    conv = {"gen_ai.conversation.id": conversation_id} if conversation_id else {}
    turn_input = messages(*history, ("user", question))

    with ExitStack() as stack:
        if http_root:
            stack.enter_context(tracer.start_as_current_span("POST /chat", kind=SpanKind.SERVER))
        _research_agent(tracer, conv, turn_input, answer)
    return Trace(list(exporter.get_finished_spans()))


def _research_agent(tracer, conv: dict, turn_input: str, answer: str) -> None:
    with tracer.start_as_current_span(
        f"invoke_agent {AGENT}",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.provider.name": "openai",
            "gen_ai.agent.name": AGENT,
            "gen_ai.agent.id": "agent-1",
            "gen_ai.agent.version": "2.1",
            "gen_ai.request.model": MODEL,
            # Aggregate of the chat children below; must not be counted again.
            "gen_ai.usage.input_tokens": 1800,
            "gen_ai.usage.output_tokens": 160,
            "gen_ai.input.messages": turn_input,
            "gen_ai.output.messages": messages(("assistant", answer)),
            "gen_ai.tool.definitions": json.dumps([{"type": "function", "name": "web_search"}]),
            **conv,
        },
    ):
        with tracer.start_as_current_span(
            f"chat {MODEL}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": "openai",
                "gen_ai.request.model": MODEL,
                "gen_ai.response.model": MODEL,
                "gen_ai.usage.input_tokens": 1000,
                "gen_ai.usage.cache_read.input_tokens": 200,
                "gen_ai.usage.output_tokens": 60,
                "gen_ai.system_instructions": json.dumps(
                    [{"type": "text", "content": "You are a travel assistant."}]
                ),
                "gen_ai.input.messages": turn_input,
                "gen_ai.output.messages": json.dumps(
                    [tool_call_message("web_search", {"q": "Lisbon weather"}, "call_1")]
                ),
                **conv,
            },
        ):
            pass
        with tracer.start_as_current_span(
            "execute_tool web_search",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "web_search",
                "gen_ai.tool.type": "function",
                "gen_ai.tool.call.id": "call_1",
                "gen_ai.tool.call.arguments": json.dumps({"q": "Lisbon weather"}),
                "gen_ai.tool.call.result": json.dumps({"hits": [{"title": "Lisbon forecast"}]}),
            },
        ):
            pass
        with tracer.start_as_current_span(
            "execute_tool write_file",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "write_file",
                "gen_ai.tool.call.arguments": json.dumps({"path": "notes.md"}),
                "gen_ai.tool.call.result": "ok",
            },
        ):
            pass
        with tracer.start_as_current_span(
            "execute_tool read_file",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "read_file",
                "gen_ai.tool.call.arguments": json.dumps({"path": "notes.md"}),
                "gen_ai.tool.call.result": "# notes",
            },
        ):
            pass
        # A "task" tool that runs a sub-agent with its own model and tool calls.
        with tracer.start_as_current_span(
            "execute_tool task",
            attributes={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "task"},
        ):
            with tracer.start_as_current_span(
                "invoke_agent researcher",
                attributes={
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": "researcher",
                    "gen_ai.input.messages": messages(("user", "Find the Lisbon forecast")),
                    "gen_ai.output.messages": messages(("assistant", "Sunny, 24C")),
                },
            ):
                with tracer.start_as_current_span(
                    f"chat {MODEL}",
                    attributes={
                        "gen_ai.operation.name": "chat",
                        "gen_ai.request.model": MODEL,
                        "gen_ai.usage.input_tokens": 800,
                        "gen_ai.usage.output_tokens": 100,
                        "gen_ai.input.messages": messages(("user", "Find the Lisbon forecast")),
                        "gen_ai.output.messages": messages(("assistant", "Sunny, 24C")),
                    },
                ):
                    pass
                with tracer.start_as_current_span(
                    "execute_tool web_search",
                    attributes={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": "web_search",
                        "gen_ai.tool.call.arguments": json.dumps({"q": "Lisbon forecast"}),
                        "gen_ai.tool.call.result": json.dumps({"hits": []}),
                    },
                ):
                    pass


def handoff_run() -> Trace:
    """An agent handing control to another agent through a transfer tool call."""
    provider, exporter = _provider(None, None)
    tracer = provider.get_tracer("example.agents", "1.0.0")
    with tracer.start_as_current_span(
        "invoke_agent travel_agent",
        attributes={"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "travel_agent"},
    ):
        with tracer.start_as_current_span(
            "execute_tool transfer_to_weather_agent",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "transfer_to_weather_agent",
                "gen_ai.transfer.mode": "pass_control",
                "gen_ai.transfer.target.name": "weather_agent",
            },
        ):
            pass
    return Trace(list(exporter.get_finished_spans()))


def operations_run(*, project_id: Optional[str] = None) -> Trace:
    """The other operations: workflow, plan, handoff, retrieval, memory, refs, an error."""
    provider, exporter = _provider(project_id, None)
    tracer = provider.get_tracer("spec.examples", "0.1.0")
    with tracer.start_as_current_span(
        "invoke_workflow travel_planner",
        attributes={
            "gen_ai.operation.name": "invoke_workflow",
            "gen_ai.input.messages_ref": "s3://bucket/inputs.json",
            "gen_ai.output.messages_ref": "s3://bucket/outputs.json",
        },
    ):
        with tracer.start_as_current_span(
            "plan travel_agent",
            attributes={"gen_ai.operation.name": "plan", "gen_ai.agent.name": "travel_agent"},
        ):
            pass
        with tracer.start_as_current_span(
            "execute_tool transfer_to_weather_agent",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "transfer_to_weather_agent",
                "gen_ai.transfer.mode": "pass_control",
                "gen_ai.transfer.target.name": "weather_agent",
            },
        ):
            pass
        with tracer.start_as_current_span(
            "retrieval docs", attributes={"gen_ai.operation.name": "retrieval"}
        ):
            pass
        with tracer.start_as_current_span(
            "search_memory profile", attributes={"gen_ai.operation.name": "search_memory"}
        ):
            pass
        with tracer.start_as_current_span(
            "embeddings text-embedding-3-small",
            attributes={"gen_ai.operation.name": "embeddings", "gen_ai.usage.input_tokens": 9},
        ):
            pass
        with tracer.start_as_current_span(
            "create_agent helper", attributes={"gen_ai.operation.name": "create_agent"}
        ):
            pass
        with tracer.start_as_current_span(
            "execute_tool flaky_api",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "flaky_api",
                "error.type": "TimeoutError",
            },
        ) as span:
            span.add_event(
                "gen_ai.execute_tool.exception",
                {"exception.type": "TimeoutError", "exception.message": "upstream took 30s"},
            )
            span.set_status(Status(StatusCode.ERROR))
        with tracer.start_as_current_span(
            "GET /healthz", attributes={"http.request.method": "GET", "x.custom": "kept"}
        ):
            pass
    return Trace(list(exporter.get_finished_spans()))


# ---------------------------------------------------------------------------
# Encodings
# ---------------------------------------------------------------------------


def export_request(spans: Sequence[ReadableSpan]) -> ExportTraceServiceRequest:
    return encode_spans(list(spans))


def protobuf_body(spans: Sequence[ReadableSpan]) -> bytes:
    return export_request(spans).SerializeToString()


def json_body(spans: Sequence[ReadableSpan]) -> bytes:
    """OTLP JSON: hex ids, lowerCamelCase, int64 as strings."""
    payload = json_format.MessageToDict(export_request(spans))
    for resource_spans in payload.get("resourceSpans", []):
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                for key in ("traceId", "spanId", "parentSpanId"):
                    if key in span:
                        span[key] = base64.b64decode(span[key]).hex()
    return json.dumps(payload).encode()


def gzip_body(spans: Sequence[ReadableSpan]) -> bytes:
    return gzip.compress(protobuf_body(spans))


PROTOBUF = "application/x-protobuf"
JSON = "application/json"
