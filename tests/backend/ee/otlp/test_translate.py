"""OTLP decode and GenAI-convention translation, without a database."""

import gzip
import json

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, ArrayValue, KeyValue, KeyValueList
from rhesis.telemetry import genai
from rhesis.telemetry.schemas import OTELSpan

from rhesis.backend.app.config.settings import get_trace_ingest_settings
from rhesis.backend.app.services.telemetry.ingest import DROPPED_ATTRIBUTES, apply_span_limits
from rhesis.backend.ee.otlp import translate as translate_module
from rhesis.backend.ee.otlp.decode import (
    OTLPDecodeError,
    OTLPEncoding,
    OTLPPayloadTooLarge,
    OTLPUnsupportedMediaType,
    decode_request,
)
from rhesis.backend.ee.otlp.translate import (
    attribute_value,
    translate_request,
)
from tests.backend.ee.otlp import fixtures as fx

LIMIT = 32 * 1024 * 1024


def translate(spans) -> dict:
    result = translate_request(fx.export_request(spans))
    assert result.rejected == 0, result.errors
    by_name: dict = {}
    for span in result.spans:
        # The sub-agent reuses names (chat, web_search); keep the outer, earlier-started one.
        current = by_name.get(span.attributes["function.name"])
        if current is None or span.start_time < current.start_time:
            by_name[span.attributes["function.name"]] = span
    return by_name


class TestDecode:
    def test_protobuf_json_and_gzip_decode_to_the_same_spans(self):
        trace = fx.research_run()
        bodies = [
            (fx.protobuf_body(trace.spans), fx.PROTOBUF, None),
            (fx.json_body(trace.spans), fx.JSON, None),
            (fx.gzip_body(trace.spans), fx.PROTOBUF, "gzip"),
            (gzip.compress(fx.json_body(trace.spans)), "application/json; charset=utf-8", "gzip"),
        ]
        decoded = [
            [
                s.model_dump(mode="json")
                for s in translate_request(decode_request(*b, LIMIT)[0]).spans
            ]
            for b in bodies
        ]
        assert len(decoded[0]) == len(trace.spans)
        assert all(d == decoded[0] for d in decoded[1:])

    def test_json_ids_are_hex_and_unknown_fields_ignored(self):
        trace = fx.research_run()
        payload = json.loads(fx.json_body([trace.root]))
        payload["somethingNew"] = {"x": 1}
        request, encoding = decode_request(json.dumps(payload).encode(), fx.JSON, None, LIMIT)
        assert encoding is OTLPEncoding.JSON
        span = translate_request(request).spans[0]
        assert span.trace_id == trace.trace_id

    @pytest.mark.parametrize(
        "body, content_type, encoding, error",
        [
            (b"\xff\x00garbage", fx.PROTOBUF, None, OTLPDecodeError),
            (b"{not json", fx.JSON, None, OTLPDecodeError),
            (b"[]", fx.JSON, None, OTLPDecodeError),
            (b"not gzip", fx.PROTOBUF, "gzip", OTLPDecodeError),
            (b"", fx.PROTOBUF, "br", OTLPDecodeError),
            (b"", "text/plain", None, OTLPUnsupportedMediaType),
        ],
    )
    def test_undecodable_payloads(self, body, content_type, encoding, error):
        with pytest.raises(error):
            decode_request(body, content_type, encoding, LIMIT)

    def test_gzip_bomb_is_refused(self):
        with pytest.raises(OTLPPayloadTooLarge):
            decode_request(gzip.compress(b"\x00" * 10_000), fx.PROTOBUF, "gzip", 1024)


class TestOperationMapping:
    """Snapshot of the span name and operation type each GenAI operation gets."""

    @pytest.mark.parametrize(
        "name, span_name, operation_type",
        [
            (f"invoke_agent {fx.AGENT}", "ai.agent.invoke", "agent.invoke"),
            (f"chat {fx.MODEL}", "ai.llm.invoke", "llm.invoke"),
            ("execute_tool web_search", "ai.tool.invoke", "tool.invoke"),
            ("execute_tool task", "ai.tool.invoke", "tool.invoke"),
            ("invoke_agent researcher", "ai.agent.invoke", "agent.invoke"),
        ],
    )
    def test_research_run(self, name, span_name, operation_type):
        span = translate(fx.research_run().spans)[name]
        assert span.span_name == span_name
        assert span.attributes["ai.operation.type"] == operation_type

    @pytest.mark.parametrize(
        "name, span_name, operation_type",
        [
            ("invoke_workflow travel_planner", "ai.agent.invoke", "agent.invoke"),
            ("plan travel_agent", "ai.agent.plan", "agent.plan"),
            ("execute_tool transfer_to_weather_agent", "ai.agent.handoff", "agent.handoff"),
            ("retrieval docs", "ai.retrieval.query", "retrieval"),
            ("search_memory profile", "ai.memory.search", "memory.search"),
            ("embeddings text-embedding-3-small", "ai.embedding.generate", "embedding.create"),
            ("create_agent helper", "ai.agent.create", "agent.create"),
            ("GET /healthz", "function.GET_/healthz", None),
        ],
    )
    def test_other_operations(self, name, span_name, operation_type):
        span = translate(fx.operations_run().spans)[name]
        assert span.span_name == span_name
        assert span.attributes.get("ai.operation.type") == operation_type

    def test_workflow_keeps_its_original_operation(self):
        span = translate(fx.operations_run().spans)["invoke_workflow travel_planner"]
        assert span.attributes["gen_ai.operation.name"] == "invoke_workflow"

    def test_operation_falls_back_to_span_name(self):
        assert genai.classify_span("chat gpt-4o", {}) == ("ai.llm.invoke", "llm.invoke")
        assert genai.classify_span("invoke_runner main", {})[0] == "ai.agent.invoke"
        assert genai.classify_span("chatty handler", {})[0] == "function.chatty_handler"

    def test_unknown_operation_is_kept_as_a_function_span(self):
        span_name, operation = genai.classify_span(
            "fetch_response r1", {"gen_ai.operation.name": "fetch_response"}
        )
        assert span_name == "function.fetch_response_r1"
        assert operation is None


class TestAttributes:
    def test_originals_resource_and_scope_are_kept(self):
        span = translate(fx.research_run().spans)[f"invoke_agent {fx.AGENT}"]
        assert span.attributes["gen_ai.agent.name"] == fx.AGENT
        assert span.attributes["otel.scope.name"] == "example.agents"
        assert span.attributes["otel.scope.version"] == "1.0.0"
        assert span.attributes["rhesis.ingest.source"] == "otlp"
        assert span.resource["service.name"] == fx.SERVICE
        assert span.resource["telemetry.sdk.language"] == "python"
        assert span.environment == "production"

    def test_agent_identity(self):
        span = translate(fx.research_run().spans)[f"invoke_agent {fx.AGENT}"]
        assert span.attributes["ai.agent.name"] == fx.AGENT
        assert span.attributes["ai.agent.id"] == "agent-1"
        assert span.attributes["ai.agent.version"] == "2.1"
        assert span.attributes["ai.model.name"] == fx.MODEL
        assert span.attributes["ai.model.provider"] == "openai"

    def test_chat_tokens_split_out_cache_reads(self):
        span = translate(fx.research_run().spans)[f"chat {fx.MODEL}"]
        assert span.attributes["ai.llm.tokens.input"] == 800
        assert span.attributes["ai.llm.tokens.cache_read"] == 200
        assert span.attributes["ai.llm.tokens.output"] == 60
        assert span.attributes["ai.llm.tokens.total"] == 1060

    @pytest.mark.parametrize(
        "cache_attribute",
        ["gen_ai.usage.cache_write.input_tokens", "gen_ai.usage.cache_creation.input_tokens"],
    )
    def test_cache_writes_under_either_name(self, cache_attribute):
        attributes = genai.translate_attributes(
            {"gen_ai.usage.input_tokens": 1000, cache_attribute: 300}
        )
        assert attributes["ai.llm.tokens.cache_write"] == 300
        assert attributes["ai.llm.tokens.input"] == 700

    @pytest.mark.parametrize("count", [float("inf"), float("nan"), "lots", [1], None])
    def test_unusable_token_counts_are_skipped(self, count):
        attributes = genai.translate_attributes(
            {"gen_ai.usage.input_tokens": count, "gen_ai.usage.output_tokens": 5}
        )
        assert "ai.llm.tokens.input" not in attributes
        assert attributes["ai.llm.tokens.output"] == 5

    def test_tool_attributes_and_io_events(self):
        span = translate(fx.research_run().spans)["execute_tool web_search"]
        assert span.attributes["ai.tool.name"] == "web_search"
        assert span.attributes["ai.tool.call.id"] == "call_1"
        events = {e.name: e.attributes for e in span.events}
        assert json.loads(events["ai.tool.input"]["ai.tool.input"]) == {"q": "Lisbon weather"}
        assert "Lisbon forecast" in events["ai.tool.output"]["ai.tool.output"]

    def test_handoff_target(self):
        span = translate(fx.operations_run().spans)["execute_tool transfer_to_weather_agent"]
        assert span.attributes["ai.agent.handoff.to"] == "weather_agent"

    def test_refs_are_kept_not_fetched(self):
        span = translate(fx.operations_run().spans)["invoke_workflow travel_planner"]
        assert span.attributes["gen_ai.input.messages_ref"] == "s3://bucket/inputs.json"
        assert not span.events

    def test_unknown_attributes_pass_through(self):
        span = translate(fx.operations_run().spans)["GET /healthz"]
        assert span.attributes["x.custom"] == "kept"

    def test_long_content_is_not_truncated(self):
        long_answer = "x" * 32_000
        trace = fx.research_run(answer=long_answer)
        span = translate(trace.spans)[f"invoke_agent {fx.AGENT}"]
        assert span.attributes["rhesis.conversation.output"] == long_answer
        assert long_answer in span.attributes["gen_ai.output.messages"]


class TestContent:
    def test_llm_span_gets_prompt_and_completion_events(self):
        span = translate(fx.research_run().spans)[f"chat {fx.MODEL}"]
        prompts = [e.attributes for e in span.events if e.name == "ai.prompt"]
        assert prompts[0] == {
            "ai.prompt.role": "system",
            "ai.prompt.content": "You are a travel assistant.",
        }
        assert prompts[1]["ai.prompt.role"] == "user"
        completion = next(e for e in span.events if e.name == "ai.completion")
        assert "web_search" in completion.attributes["ai.completion.content"]

    def test_agent_span_gets_agent_io_events(self):
        span = translate(fx.research_run().spans)[f"invoke_agent {fx.AGENT}"]
        names = [e.name for e in span.events]
        assert names == ["ai.agent.input", "ai.agent.output"]

    def test_root_agent_carries_the_turn(self):
        trace = fx.research_run(history=[("user", "earlier"), ("assistant", "ok")])
        spans = translate(trace.spans)
        root = spans[f"invoke_agent {fx.AGENT}"]
        assert root.attributes["rhesis.conversation.input"] == "Plan a weekend trip to Lisbon"
        assert root.attributes["rhesis.conversation.output"] == "Lisbon will be sunny all weekend."
        assert root.conversation_id == "conv-research-1"
        # A sub-agent is not a turn.
        assert "rhesis.conversation.input" not in spans["invoke_agent researcher"].attributes

    def test_no_conversation_id_is_invented(self):
        spans = translate(fx.research_run(conversation_id=None).spans)
        root = spans[f"invoke_agent {fx.AGENT}"]
        assert root.conversation_id is None
        assert not any(k.startswith("gen_ai.conversation") for k in root.attributes)

    def test_structured_messages_are_read_like_json_strings(self):
        message = AnyValue(
            kvlist_value=KeyValueList(
                values=[
                    KeyValue(key="role", value=AnyValue(string_value="user")),
                    KeyValue(
                        key="parts",
                        value=AnyValue(
                            array_value=ArrayValue(
                                values=[
                                    AnyValue(
                                        kvlist_value=KeyValueList(
                                            values=[
                                                KeyValue(
                                                    key="type", value=AnyValue(string_value="text")
                                                ),
                                                KeyValue(
                                                    key="content",
                                                    value=AnyValue(string_value="hello"),
                                                ),
                                            ]
                                        )
                                    )
                                ]
                            )
                        ),
                    ),
                ]
            )
        )
        stored = attribute_value(AnyValue(array_value=ArrayValue(values=[message])))
        assert json.loads(stored) == [
            {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
        ]
        assert genai.agent_turn_input({"gen_ai.input.messages": stored}) == "hello"

    def test_scalar_arrays_stay_lists(self):
        value = AnyValue(array_value=ArrayValue(values=[AnyValue(string_value="stop")]))
        assert attribute_value(value) == ["stop"]

    def test_root_that_is_not_an_agent_takes_the_turn_of_its_agent(self):
        spans = translate(fx.research_run(http_root=True).spans)
        root = spans["POST /chat"]
        assert root.span_name == "function.POST_/chat"
        assert root.attributes["rhesis.conversation.input"] == "Plan a weekend trip to Lisbon"
        assert root.conversation_id == "conv-research-1"
        # The agent span is not the root, so it is not stamped itself.
        assert "rhesis.conversation.input" not in spans[f"invoke_agent {fx.AGENT}"].attributes


class TestErrors:
    def test_exception_event_becomes_the_status_message(self):
        span = translate(fx.operations_run().spans)["execute_tool flaky_api"]
        assert span.status_code.value == "ERROR"
        assert span.status_message == "TimeoutError: upstream took 30s"
        assert "gen_ai.execute_tool.exception" in [e.name for e in span.events]

    def test_error_type_without_status_marks_the_span_failed(self):
        attrs = {"error.type": "RateLimitError"}
        request = fx.export_request(fx.research_run().spans[:1])
        span = request.resource_spans[0].scope_spans[0].spans[0]
        span.status.Clear()
        span.attributes.append(
            KeyValue(key="error.type", value=AnyValue(string_value=attrs["error.type"]))
        )
        translated = translate_request(request).spans[0]
        assert translated.status_code.value == "ERROR"
        assert translated.status_message == "RateLimitError"

    def test_invalid_spans_are_rejected_not_fatal(self):
        request = fx.export_request(fx.research_run().spans)
        spans = request.resource_spans[0].scope_spans[0].spans
        spans[0].trace_id = b"\x00" * 16
        spans[1].span_id = b"\x01\x02"
        result = translate_request(request)
        assert result.rejected == 2
        assert len(result.spans) == len(spans) - 2
        assert "trace_id" in result.errors[0]

    def test_empty_request(self):
        assert translate_request(ExportTraceServiceRequest()).spans == []


def _spans_by_name(request: ExportTraceServiceRequest) -> dict:
    return {
        span.name: span
        for resource in request.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    }


class TestMalformedInput:
    @pytest.mark.timeout(10)
    def test_parent_loops_do_not_hang(self):
        research, operations = fx.research_run(), fx.operations_run()
        request = fx.export_request(research.spans + operations.spans)
        spans = _spans_by_name(request)
        root = spans[f"invoke_agent {fx.AGENT}"]
        root.parent_span_id = root.span_id
        task, sub_agent = spans["execute_tool task"], spans["invoke_agent researcher"]
        task.parent_span_id, sub_agent.parent_span_id = sub_agent.span_id, task.span_id
        transfer = spans["execute_tool transfer_to_weather_agent"]
        plan = spans["plan travel_agent"]
        transfer.parent_span_id, plan.parent_span_id = plan.span_id, transfer.span_id

        result = translate_request(request)

        assert result.rejected == 0, result.errors
        assert len(result.spans) == len(research.spans) + len(operations.spans)

    def test_operation_name_sent_as_an_array(self):
        request = fx.export_request(fx.research_run().spans)
        chat = _spans_by_name(request)[f"chat {fx.MODEL}"]
        for attribute in chat.attributes:
            if attribute.key == "gen_ai.operation.name":
                attribute.value.CopyFrom(
                    AnyValue(array_value=ArrayValue(values=[AnyValue(string_value="chat")]))
                )

        result = translate_request(request)

        assert result.rejected == 0, result.errors
        as_array = {"gen_ai.operation.name": ["chat"]}
        assert (
            genai.extract_conversation_output(as_array, chat_operations=genai.INFERENCE_OPERATIONS)
            is None
        )

    def test_unexpected_error_rejects_only_that_span(self, monkeypatch):
        original = translate_module.translate_span

        def flaky(span, *args):
            if span.name == "execute_tool write_file":
                raise RuntimeError("boom")
            return original(span, *args)

        monkeypatch.setattr(translate_module, "translate_span", flaky)
        trace = fx.research_run()

        result = translate_request(fx.export_request(trace.spans))

        assert result.rejected == 1
        assert "could not be translated" in result.errors[0]
        assert len(result.spans) == len(trace.spans) - 1

    def test_deeply_nested_json_is_a_decode_error(self):
        depth = 100_000
        attribute = {"key": "x", "value": {"stringValue": "[" * depth + "]" * depth}}
        nested = '{"resourceSpans": [{"resource": {"attributes": [], "x": ' + (
            "[" * depth + "]" * depth + "}}]}"
        )
        with pytest.raises(OTLPDecodeError):
            decode_request(nested.encode(), fx.JSON, None, LIMIT)
        # The same text inside a string value is just a string.
        payload = {"resourceSpans": [{"resource": {"attributes": [attribute]}}]}
        decode_request(json.dumps(payload).encode(), fx.JSON, None, LIMIT)


class TestAgentLinks:
    def test_transfer_names_the_agent_handing_off(self):
        span = translate(fx.handoff_run().spans)["execute_tool transfer_to_weather_agent"]
        assert span.attributes["ai.agent.handoff.from"] == "travel_agent"
        assert span.attributes["ai.agent.handoff.to"] == "weather_agent"

    def test_non_genai_root_takes_the_agent_name(self):
        root = translate(fx.research_run(http_root=True).spans)["POST /chat"]
        assert root.attributes["ai.agent.name"] == fx.AGENT


class TestSpanLimits:
    def _root(self) -> OTELSpan:
        spans = translate(fx.research_run().spans)
        return spans[f"invoke_agent {fx.AGENT}"]

    def test_own_attributes_are_kept_first(self):
        span = self._root()
        span.attributes = {
            "a.first": 1,
            "b.second": 2,
            "ai.agent.name": "agent",
            "rhesis.conversation.input": "hi",
        }
        limits = get_trace_ingest_settings().model_copy(update={"max_attributes_per_span": 3})

        apply_span_limits([span], limits)

        assert span.attributes["ai.agent.name"] == "agent"
        assert span.attributes["rhesis.conversation.input"] == "hi"
        assert span.attributes[DROPPED_ATTRIBUTES] == 1
        assert len([k for k in span.attributes if k.startswith(("a.", "b."))]) == 1

    def test_nul_is_removed_from_conversation_and_environment(self):
        span = self._root()
        span.conversation_id = "conv\x00-1"
        span.environment = "prod\x00"

        apply_span_limits([span], get_trace_ingest_settings())

        assert span.conversation_id == "conv-1"
        assert span.environment == "prod"


def _roots(spans) -> list:
    return [
        s for s in translate_request(fx.export_request(spans)).spans if s.parent_span_id is None
    ]


class TestTurnText:
    """Shapes real instrumentations produce, where the turn text is not on the root."""

    def _record(self, build) -> list:
        provider, exporter = fx._provider("project", None)
        build(provider.get_tracer("t"))
        return list(exporter.get_finished_spans())

    @staticmethod
    def _chat(tracer, inputs, outputs, **extra):
        with tracer.start_as_current_span("chat model") as span:
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.input.messages", inputs)
            span.set_attribute("gen_ai.output.messages", outputs)
            for key, value in extra.items():
                span.set_attribute(key, value)

    def test_agent_span_without_messages_takes_them_from_its_model_calls(self):
        """Pydantic AI records messages only on its chat spans."""

        def build(tracer):
            with tracer.start_as_current_span("invoke_agent helper") as agent:
                agent.set_attribute("gen_ai.operation.name", "invoke_agent")
                agent.set_attribute("gen_ai.agent.name", "helper")
                call = fx.tool_call_message("lookup", {"q": "x"}, "c1")
                self._chat(tracer, fx.messages(("user", "What is up?")), json.dumps([call]))
                self._chat(
                    tracer,
                    fx.messages(("user", "What is up?"), ("assistant", "looking")),
                    fx.messages(("assistant", "All good.")),
                )

        (root,) = _roots(self._record(build))
        assert root.attributes["rhesis.conversation.input"] == "What is up?"
        assert root.attributes["rhesis.conversation.output"] == "All good."

    def test_a_model_call_as_the_root_is_a_turn(self):
        """An app instrumented only with an LLM client library."""

        def build(tracer):
            self._chat(tracer, fx.messages(("user", "hi")), fx.messages(("assistant", "hello")))

        (root,) = _roots(self._record(build))
        assert root.attributes["rhesis.conversation.input"] == "hi"
        assert root.attributes["rhesis.conversation.output"] == "hello"

    def test_handoff_turn_takes_the_last_agents_answer(self):
        """Two agents side by side under a workflow span: triage hands off to weather."""

        def build(tracer):
            with tracer.start_as_current_span("workflow.run"):
                with tracer.start_as_current_span("invoke_agent triage") as triage:
                    triage.set_attribute("gen_ai.operation.name", "invoke_agent")
                    triage.set_attribute("gen_ai.agent.name", "triage")
                    triage.set_attribute("gen_ai.input.messages", fx.messages(("user", "Rain?")))
                    handoff = fx.tool_call_message("handoff_to_weather", {}, "h1")
                    triage.set_attribute("gen_ai.output.messages", json.dumps([handoff]))
                with tracer.start_as_current_span("invoke_agent weather") as weather:
                    weather.set_attribute("gen_ai.operation.name", "invoke_agent")
                    weather.set_attribute("gen_ai.agent.name", "weather")
                    weather.set_attribute("gen_ai.input.messages", fx.messages(("user", "Rain?")))
                    weather.set_attribute(
                        "gen_ai.output.messages", fx.messages(("assistant", "No rain."))
                    )

        (root,) = _roots(self._record(build))
        assert root.attributes["rhesis.conversation.input"] == "Rain?"
        assert root.attributes["rhesis.conversation.output"] == "No rain."
        assert root.attributes["ai.agent.name"] == "triage"

    def test_instructions_repeated_as_a_system_message_give_one_prompt(self):
        def build(tracer):
            self._chat(
                tracer,
                fx.messages(("system", "Be brief."), ("user", "hi")),
                fx.messages(("assistant", "hello")),
                **{
                    "gen_ai.system_instructions": json.dumps(
                        [{"type": "text", "content": "Be brief."}]
                    )
                },
            )

        (root,) = _roots(self._record(build))
        system = [
            e
            for e in root.events
            if e.name == "ai.prompt" and e.attributes["ai.prompt.role"] == "system"
        ]
        assert len(system) == 1

    @pytest.mark.parametrize(
        "value,expected",
        [('["tool_calls"]', "tool_calls"), (["stop", "length"], "stop, length"), ("stop", "stop")],
    )
    def test_finish_reasons_become_one_string(self, value, expected):
        attributes = genai.translate_attributes({"gen_ai.response.finish_reasons": value})
        assert attributes["ai.llm.finish_reason"] == expected
