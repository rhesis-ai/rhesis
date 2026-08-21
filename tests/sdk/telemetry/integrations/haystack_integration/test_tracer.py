"""Unit tests for the Haystack-to-OpenTelemetry bridge.

Uses recording doubles rather than a real provider where the assertion is about *what* the bridge
writes; ``test_emitted_spans.py`` covers what actually reaches an exporter.
"""

from contextlib import contextmanager
from typing import Any

import pytest

pytest.importorskip("haystack")

from haystack.dataclasses import ChatMessage, ToolCall  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from rhesis.telemetry.attributes import MAX_CONTENT_LENGTH, AIAttributes  # noqa: E402
from rhesis.telemetry.constants import ConversationContext  # noqa: E402
from rhesis.telemetry.context import set_root_trace_id  # noqa: E402

from rhesis.sdk.telemetry.integrations.haystack import mapping  # noqa: E402
from rhesis.sdk.telemetry.integrations.haystack.tracer import (  # noqa: E402
    DefaultSpanHandler,
    RhesisSpan,
    RhesisTelemetry,
    RhesisTracer,
    SpanContext,
    _sanitize_usage_data,
    build_trace_url,
    enforce_flush_enabled,
    resolve_frontend_url,
    rhesis_invocation_context,
    span_stack_var,
)


class RecordingSpan:
    """Stands in for an OTel span, recording everything written to it."""

    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.name = "initial"
        self.status = None
        self.recorded_exceptions: list[BaseException] = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        self.events.append((name, dict(attributes or {})))

    def update_name(self, name):
        self.name = name

    def set_status(self, status):
        self.status = status

    def record_exception(self, exc):
        self.recorded_exceptions.append(exc)

    def get_span_context(self):
        raise AttributeError("no span context on the double")

    def event_names(self):
        return [name for name, _ in self.events]

    def events_named(self, name):
        return [attrs for event_name, attrs in self.events if event_name == name]


@contextmanager
def recording_cm(span):
    yield span


def make_span(operation_name: str = "haystack.component.run") -> tuple[RhesisSpan, RecordingSpan]:
    raw = RecordingSpan()
    return RhesisSpan(recording_cm(raw), operation_name=operation_name), raw


@pytest.fixture
def handler():
    """A DefaultSpanHandler with a real provider, so create_span opens real spans."""
    provider = TracerProvider()
    telemetry = RhesisTelemetry(
        provider=provider,
        otel_tracer=provider.get_tracer("unit-tests"),
        project_id="proj",
        environment="test",
        base_url="http://localhost:8080",
    )
    span_handler = DefaultSpanHandler()
    span_handler.init_tracer(telemetry)
    return span_handler


class TestResolveFrontendUrl:
    @pytest.mark.parametrize(
        ("base_url", "expected"),
        [
            ("http://localhost:8080", "http://localhost:3000"),
            ("http://127.0.0.1:8080", "http://localhost:3000"),
            ("http://localhost:8080/", "http://localhost:3000"),
            ("https://api.rhesis.ai", "https://app.rhesis.ai"),
            ("https://rhesis.acme.internal", ""),
            ("", ""),
        ],
    )
    def test_derives_only_the_well_known_deployments(self, base_url, expected):
        assert resolve_frontend_url(base_url, None) == expected

    def test_explicit_frontend_url_always_wins(self):
        assert (
            resolve_frontend_url("https://api.rhesis.ai", "https://ui.acme/") == "https://ui.acme"
        )


class TestBuildTraceUrl:
    def test_includes_project_id_when_known(self):
        url = build_trace_url("https://app.rhesis.ai", "a" * 32, "proj-1")
        assert url == f"https://app.rhesis.ai/traces?open_trace={'a' * 32}&project_id=proj-1"

    def test_omits_project_id_when_unknown(self):
        assert build_trace_url("https://app.rhesis.ai", "b" * 32, None) == (
            f"https://app.rhesis.ai/traces?open_trace={'b' * 32}"
        )

    @pytest.mark.parametrize(
        ("frontend_url", "trace_id"), [("", "a" * 32), ("https://app.rhesis.ai", "")]
    )
    def test_empty_when_either_half_is_missing(self, frontend_url, trace_id):
        assert build_trace_url(frontend_url, trace_id, "proj") == ""


class TestEnforceFlushEnabled:
    def test_defaults_to_on(self, monkeypatch):
        monkeypatch.delenv("RHESIS_HAYSTACK_ENFORCE_FLUSH", raising=False)
        monkeypatch.delenv("HAYSTACK_RHESIS_ENFORCE_FLUSH", raising=False)
        assert enforce_flush_enabled() is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
    def test_falsy_values_switch_it_off(self, monkeypatch, value):
        monkeypatch.setenv("RHESIS_HAYSTACK_ENFORCE_FLUSH", value)
        assert enforce_flush_enabled() is False

    def test_upstream_env_var_name_still_works(self, monkeypatch):
        """A config written against the upstream rhesis-haystack package must keep working."""
        monkeypatch.delenv("RHESIS_HAYSTACK_ENFORCE_FLUSH", raising=False)
        monkeypatch.setenv("HAYSTACK_RHESIS_ENFORCE_FLUSH", "false")
        assert enforce_flush_enabled() is False

    def test_new_name_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("RHESIS_HAYSTACK_ENFORCE_FLUSH", "true")
        monkeypatch.setenv("HAYSTACK_RHESIS_ENFORCE_FLUSH", "false")
        assert enforce_flush_enabled() is True


class TestSanitizeUsageData:
    def test_maps_openai_style_usage(self):
        assert _sanitize_usage_data(
            {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
        ) == {
            AIAttributes.LLM_TOKENS_INPUT: 3,
            AIAttributes.LLM_TOKENS_OUTPUT: 4,
            AIAttributes.LLM_TOKENS_TOTAL: 7,
        }

    def test_drops_zero_values(self):
        """A zero input count is omitted; the total is still derived from what is known."""
        assert _sanitize_usage_data({"prompt_tokens": 0, "completion_tokens": 5}) == {
            AIAttributes.LLM_TOKENS_OUTPUT: 5,
            AIAttributes.LLM_TOKENS_TOTAL: 5,
        }

    def test_empty_usage_writes_nothing(self):
        assert _sanitize_usage_data({}) == {}

    def test_non_dict_is_ignored(self):
        assert _sanitize_usage_data("nonsense") == {}


class TestRhesisSpanTags:
    def test_pipeline_payloads_are_capped_but_data_keeps_the_whole_value(self):
        span, raw = make_span()
        payload = {"text": "x" * (MAX_CONTENT_LENGTH * 2)}
        span.set_tag(mapping.PIPELINE_INPUT, payload)
        assert len(raw.attributes[mapping.PIPELINE_INPUT]) == MAX_CONTENT_LENGTH
        assert span.get_data()[mapping.PIPELINE_INPUT] == payload

    def test_other_tags_are_not_capped(self):
        span, raw = make_span()
        span.set_tag("haystack.component.name", "llm")
        assert raw.attributes["haystack.component.name"] == "llm"

    def test_none_becomes_empty_string(self):
        span, raw = make_span()
        span.set_tag("haystack.component.type", None)
        assert raw.attributes["haystack.component.type"] == ""

    def test_set_tags_applies_every_key(self):
        span, raw = make_span()
        span.set_tags({"a": 1, "b": "two"})
        assert raw.attributes["a"] == 1
        assert raw.attributes["b"] == "two"

    def test_correlation_data_is_empty_when_unavailable(self):
        span, _ = make_span()
        assert span.get_correlation_data_for_logs() == {}


class TestRhesisSpanContent:
    def test_content_tag_is_a_noop_when_content_tracing_is_off(self, monkeypatch):
        from haystack import tracing

        monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
        span, raw = make_span()
        span.set_content_tag(mapping.COMPONENT_INPUT, {"messages": []})
        assert raw.events == []
        assert raw.attributes == {}

    def test_messages_become_one_prompt_event_each_with_roles(self):
        span, raw = make_span()
        span.set_content_tag(
            mapping.COMPONENT_INPUT,
            {
                "messages": [
                    ChatMessage.from_system("be brief"),
                    ChatMessage.from_user("hello"),
                ]
            },
        )
        prompts = raw.events_named("ai.prompt")
        assert [p[AIAttributes.PROMPT_ROLE] for p in prompts] == ["system", "user"]
        assert [p[AIAttributes.PROMPT_CONTENT] for p in prompts] == ["be brief", "hello"]

    def test_generation_kwargs_are_kept_alongside_the_messages(self):
        span, raw = make_span()
        span.set_content_tag(
            mapping.COMPONENT_INPUT,
            {"messages": [ChatMessage.from_user("hi")], "generation_kwargs": {"temperature": 0}},
        )
        assert len(raw.events_named("ai.prompt")) == 1

    def test_replies_become_completion_events(self):
        span, raw = make_span()
        span.set_content_tag(
            mapping.COMPONENT_OUTPUT,
            {
                "replies": [
                    ChatMessage.from_assistant("first"),
                    ChatMessage.from_assistant("second"),
                ]
            },
        )
        contents = [e[AIAttributes.COMPLETION_CONTENT] for e in raw.events_named("ai.completion")]
        assert contents == ["first", "second"]

    def test_agent_input_gets_attribute_and_event(self):
        span, raw = make_span(mapping.AGENT_RUN)
        span.set_content_tag(mapping.AGENT_INPUT, "what is the weather")
        assert raw.attributes[AIAttributes.AGENT_INPUT_CONTENT] == "what is the weather"
        assert raw.events_named("ai.agent.input")

    def test_agent_output_gets_attribute_and_event(self):
        span, raw = make_span(mapping.AGENT_RUN)
        span.set_content_tag(mapping.AGENT_OUTPUT, "it is sunny")
        assert raw.attributes[AIAttributes.AGENT_OUTPUT_CONTENT] == "it is sunny"
        assert raw.events_named("ai.agent.output")

    def test_agent_step_tool_io_uses_tool_attributes_not_prompt_events(self):
        span, raw = make_span(mapping.AGENT_STEP_TOOL)
        span.set_content_tag(mapping.AGENT_STEP_TOOL_INPUT, {"city": "Berlin"})
        span.set_content_tag(mapping.AGENT_STEP_TOOL_OUTPUT, "18C")
        assert AIAttributes.TOOL_INPUT_CONTENT in raw.attributes
        assert raw.attributes[AIAttributes.TOOL_OUTPUT_CONTENT] == "18C"
        assert raw.events == []

    def test_content_is_truncated(self):
        span, raw = make_span()
        span.set_content_tag(
            mapping.COMPONENT_OUTPUT, {"replies": [ChatMessage.from_assistant("y" * 20000)]}
        )
        content = raw.events_named("ai.completion")[0][AIAttributes.COMPLETION_CONTENT]
        assert len(content) == MAX_CONTENT_LENGTH

    def test_agent_input_attribute_uses_the_conversation_bound(self):
        """Agent I/O attributes use MAX_IO_LENGTH; their events use MAX_CONTENT_LENGTH."""
        span, raw = make_span(mapping.AGENT_RUN)
        span.set_content_tag(mapping.AGENT_INPUT, "z" * 50000)
        assert (
            len(raw.attributes[AIAttributes.AGENT_INPUT_CONTENT])
            == ConversationContext.MAX_IO_LENGTH
        )
        event = raw.events_named("ai.agent.input")[0]
        assert len(event[AIAttributes.AGENT_INPUT_CONTENT]) == MAX_CONTENT_LENGTH


class TestSpanContextValidation:
    @pytest.mark.parametrize(
        ("field", "value"),
        [("name", ""), ("operation_name", ""), ("trace_name", "")],
    )
    def test_empty_required_fields_are_rejected(self, field, value):
        kwargs = {
            "name": "llm",
            "operation_name": "haystack.component.run",
            "component_type": None,
            "tags": {},
            "parent_span": None,
            "trace_name": "Haystack",
            field: value,
        }
        with pytest.raises(ValueError):
            SpanContext(**kwargs)


class TestDefaultSpanHandlerCreateSpan:
    def test_uninitialised_handler_raises(self):
        with pytest.raises(RuntimeError, match="Tracer is not initialized"):
            DefaultSpanHandler().create_span(
                SpanContext(
                    name="llm",
                    operation_name=mapping.COMPONENT_RUN,
                    component_type=None,
                    tags={},
                    parent_span=None,
                )
            )

    def test_root_span_records_trace_name_and_owns_the_turn(self, handler):
        span = handler.create_span(
            SpanContext(
                name="p",
                operation_name=mapping.PIPELINE_RUN,
                component_type=None,
                tags={},
                parent_span=None,
                trace_name="My App",
                is_root=True,
            )
        )
        assert span.is_root is True
        assert span.owns_conversation_turn is True

    def test_an_sdk_endpoint_root_takes_the_turn(self, handler):
        """A pipeline inside an @endpoint span is a child of that turn, not a turn of its own."""
        set_root_trace_id("a" * 32)
        try:
            span = handler.create_span(
                SpanContext(
                    name="p",
                    operation_name=mapping.PIPELINE_RUN,
                    component_type=None,
                    tags={},
                    parent_span=None,
                    is_root=True,
                )
            )
            assert span.owns_conversation_turn is False
        finally:
            set_root_trace_id(None)

    def test_tool_invoker_component_gets_tool_attributes(self, handler):
        span = handler.create_span(
            SpanContext(
                name="tools",
                operation_name=mapping.COMPONENT_RUN,
                component_type="ToolInvoker",
                tags={},
                parent_span=None,
            )
        )
        assert span.raw_span().attributes[AIAttributes.TOOL_NAME] == "tools"
        assert span.raw_span().attributes[AIAttributes.TOOL_TYPE] == "haystack"

    def test_agent_step_tool_names_the_tool_from_tags(self, handler):
        span = handler.create_span(
            SpanContext(
                name="step",
                operation_name=mapping.AGENT_STEP_TOOL,
                component_type=None,
                tags={mapping.TOOL_NAME: "get_weather"},
                parent_span=None,
            )
        )
        assert span.raw_span().attributes[AIAttributes.TOOL_NAME] == "get_weather"


class TestHandoffPromotion:
    def test_agent_inside_a_tool_span_promotes_the_parent_to_a_handoff(self, handler):
        """An Agent running inside a tool call is how Haystack models a handoff."""
        parent = handler.create_span(
            SpanContext(
                name="step",
                operation_name=mapping.AGENT_STEP_TOOL,
                component_type=None,
                tags={mapping.TOOL_NAME: "billing_specialist"},
                parent_span=None,
            )
        )
        parent.set_tag(mapping.TOOL_NAME, "billing_specialist")

        coordinator = make_span(mapping.COMPONENT_RUN)[0]
        coordinator.set_tag(mapping.COMPONENT_NAME, "coordinator")
        token = span_stack_var.set([coordinator, parent])
        try:
            child = handler.create_span(
                SpanContext(
                    name="specialist",
                    operation_name=mapping.AGENT_RUN,
                    component_type=None,
                    tags={},
                    parent_span=parent,
                )
            )
        finally:
            span_stack_var.reset(token)

        parent_attrs = parent.raw_span().attributes
        assert parent.raw_span().name == "ai.agent.handoff"
        assert parent_attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_AGENT_HANDOFF
        assert parent_attrs[AIAttributes.AGENT_HANDOFF_TO] == "billing_specialist"
        assert parent_attrs[AIAttributes.AGENT_HANDOFF_FROM] == "coordinator"
        assert child.raw_span().attributes[AIAttributes.AGENT_NAME] == "billing_specialist"

    def test_agent_under_a_component_parent_is_named_after_it(self, handler):
        parent = make_span(mapping.COMPONENT_RUN)[0]
        parent.set_tag(mapping.COMPONENT_NAME, "assistant")
        child = handler.create_span(
            SpanContext(
                name="assistant",
                operation_name=mapping.AGENT_RUN,
                component_type="Agent",
                tags={},
                parent_span=parent,
            )
        )
        assert child.raw_span().attributes[AIAttributes.AGENT_NAME] == "assistant"


class TestInvocationContextStamping:
    def test_every_span_gets_the_ids_but_only_the_root_gets_turn_root(self):
        root, root_raw = make_span(mapping.PIPELINE_RUN)
        root.is_root = True
        child, child_raw = make_span(mapping.COMPONENT_RUN)

        with rhesis_invocation_context({"session_id": "s1", "user_id": "u1"}):
            DefaultSpanHandler._apply_invocation_context(root)
            DefaultSpanHandler._apply_invocation_context(child)

        turn_root = ConversationContext.SpanAttributes.IS_TURN_ROOT
        conv_id = ConversationContext.SpanAttributes.CONVERSATION_ID
        assert root_raw.attributes[turn_root] is True
        assert turn_root not in child_raw.attributes
        assert child_raw.attributes[conv_id] == "s1"
        assert child_raw.attributes["haystack.invocation.user_id"] == "u1"

    def test_a_root_that_does_not_own_the_turn_gets_no_turn_root_flag(self):
        root, raw = make_span(mapping.PIPELINE_RUN)
        root.is_root = True
        root.owns_conversation_turn = False
        with rhesis_invocation_context({"session_id": "s1"}):
            DefaultSpanHandler._apply_invocation_context(root)
        assert ConversationContext.SpanAttributes.IS_TURN_ROOT not in raw.attributes


class TestConversationIoPromotion:
    def test_pipeline_messages_are_promoted(self):
        span, raw = make_span(mapping.PIPELINE_RUN)
        span.set_tag(mapping.PIPELINE_INPUT, {"chat": {"messages": [ChatMessage.from_user("hi")]}})
        span.set_tag(
            mapping.PIPELINE_OUTPUT, {"llm": {"replies": [ChatMessage.from_assistant("hello")]}}
        )
        DefaultSpanHandler._promote_conversation_io(span)
        attrs = ConversationContext.SpanAttributes
        assert raw.attributes[attrs.CONVERSATION_INPUT] == "hi"
        assert raw.attributes[attrs.CONVERSATION_OUTPUT] == "hello"

    def test_nothing_is_stamped_when_no_chat_text_exists(self):
        """A serialized dict dump is never a valid rendering of what the user said."""
        span, raw = make_span(mapping.PIPELINE_RUN)
        span.set_tag(mapping.PIPELINE_INPUT, {"reader": {"documents": ["a", "b"]}})
        span.set_tag(mapping.PIPELINE_OUTPUT, {"reader": {"documents": ["c"]}})
        DefaultSpanHandler._promote_conversation_io(span)
        attrs = ConversationContext.SpanAttributes
        assert attrs.CONVERSATION_INPUT not in raw.attributes
        assert attrs.CONVERSATION_OUTPUT not in raw.attributes

    def test_last_message_is_preferred_for_the_reply(self):
        span, raw = make_span(mapping.PIPELINE_RUN)
        span.set_tag(mapping.PIPELINE_INPUT, {"a": {"messages": [ChatMessage.from_user("q")]}})
        span.set_tag(
            mapping.PIPELINE_OUTPUT,
            {"agent": {"last_message": ChatMessage.from_assistant("final answer")}},
        )
        DefaultSpanHandler._promote_conversation_io(span)
        assert (
            raw.attributes[ConversationContext.SpanAttributes.CONVERSATION_OUTPUT] == "final answer"
        )

    def test_skipped_when_an_sdk_span_owns_the_turn(self):
        span, raw = make_span(mapping.PIPELINE_RUN)
        span.owns_conversation_turn = False
        span.set_tag(mapping.PIPELINE_INPUT, {"chat": {"messages": [ChatMessage.from_user("hi")]}})
        DefaultSpanHandler._promote_conversation_io(span)
        assert ConversationContext.SpanAttributes.CONVERSATION_INPUT not in raw.attributes

    def test_skipped_when_content_tracing_is_off(self, monkeypatch):
        from haystack import tracing

        monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
        span, raw = make_span(mapping.PIPELINE_RUN)
        span.set_tag(mapping.PIPELINE_INPUT, {"chat": {"messages": [ChatMessage.from_user("hi")]}})
        DefaultSpanHandler._promote_conversation_io(span)
        assert ConversationContext.SpanAttributes.CONVERSATION_INPUT not in raw.attributes

    def test_rhesis_content_opt_out_is_honoured(self, monkeypatch):
        """RHESIS_DISABLE_CONTENT_CAPTURE must work here as it does for every other integration."""
        monkeypatch.setenv("RHESIS_DISABLE_CONTENT_CAPTURE", "1")
        span, raw = make_span(mapping.PIPELINE_RUN)
        span.set_tag(mapping.PIPELINE_INPUT, {"chat": {"messages": [ChatMessage.from_user("hi")]}})
        DefaultSpanHandler._promote_conversation_io(span)
        assert ConversationContext.SpanAttributes.CONVERSATION_INPUT not in raw.attributes

    def test_agent_io_only_promoted_on_the_outermost_agent_span(self):
        span, raw = make_span(mapping.AGENT_RUN)
        span.set_tag(mapping.AGENT_INPUT, {"messages": [ChatMessage.from_user("hi")]})
        span.set_tag(mapping.AGENT_OUTPUT, {"messages": [ChatMessage.from_assistant("yo")]})
        # A stack deeper than root + agent means this is a nested agent.
        deep = [make_span()[0] for _ in range(4)]
        token = span_stack_var.set(deep)
        try:
            DefaultSpanHandler._promote_conversation_io(span)
        finally:
            span_stack_var.reset(token)
        assert ConversationContext.SpanAttributes.CONVERSATION_INPUT not in raw.attributes


class TestToolInvokerRename:
    def _span_with_tool_calls(self, calls):
        span, raw = make_span(mapping.COMPONENT_RUN)
        span.set_tag(mapping.COMPONENT_NAME, "tools")
        span.set_tag(
            mapping.COMPONENT_INPUT,
            {"messages": [ChatMessage.from_assistant(tool_calls=calls)]},
        )
        return span, raw

    def test_renamed_after_the_tools_it_called(self):
        span, raw = self._span_with_tool_calls(
            [
                ToolCall(id="1", tool_name="search", arguments={"q": "a"}),
                ToolCall(id="2", tool_name="search", arguments={"q": "b"}),
                ToolCall(id="3", tool_name="calc", arguments={"x": 1}),
            ]
        )
        DefaultSpanHandler._rename_tool_invoker(span, "ToolInvoker")
        assert raw.name == "tools - [calc, search (x2)]"

    def test_tool_io_is_replaced_with_the_calls_and_results(self):
        span, raw = self._span_with_tool_calls(
            [ToolCall(id="1", tool_name="search", arguments={"q": "a"})]
        )
        DefaultSpanHandler._rename_tool_invoker(span, "ToolInvoker")
        assert "search" in raw.attributes[AIAttributes.TOOL_INPUT_CONTENT]

    def test_content_flag_gates_only_the_content_not_the_rename(self, monkeypatch):
        from haystack import tracing

        monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
        span, raw = self._span_with_tool_calls(
            [ToolCall(id="1", tool_name="search", arguments={"q": "a"})]
        )
        DefaultSpanHandler._rename_tool_invoker(span, "ToolInvoker")
        assert raw.name == "tools - [search]"
        assert AIAttributes.TOOL_INPUT_CONTENT not in raw.attributes

    def test_other_components_are_left_alone(self):
        span, raw = self._span_with_tool_calls([ToolCall(id="1", tool_name="search", arguments={})])
        DefaultSpanHandler._rename_tool_invoker(span, "OpenAIChatGenerator")
        assert raw.name == "initial"

    def test_no_tool_calls_means_no_rename(self):
        span, raw = make_span(mapping.COMPONENT_RUN)
        span.set_tag(mapping.COMPONENT_INPUT, {"messages": [ChatMessage.from_user("hi")]})
        DefaultSpanHandler._rename_tool_invoker(span, "ToolInvoker")
        assert raw.name == "initial"


class TestModelMetadata:
    def test_chat_generator_replies(self):
        span, raw = make_span(mapping.COMPONENT_RUN)
        reply = ChatMessage.from_assistant(
            "hi",
            meta={"model": "gpt-4o-mini", "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
        )
        span.set_tag(mapping.COMPONENT_OUTPUT, {"replies": [reply]})
        DefaultSpanHandler._apply_model_metadata(span, "OpenAIChatGenerator")
        assert raw.attributes[AIAttributes.MODEL_NAME] == "gpt-4o-mini"
        assert raw.attributes[AIAttributes.LLM_TOKENS_INPUT] == 5
        assert raw.attributes[AIAttributes.LLM_TOKENS_OUTPUT] == 2

    def test_agent_step_llm_output(self):
        span, raw = make_span(mapping.AGENT_STEP_LLM)
        reply = ChatMessage.from_assistant("hi", meta={"model": "m1"})
        span.set_tag(mapping.AGENT_STEP_LLM_OUTPUT, {"replies": [reply]})
        DefaultSpanHandler._apply_model_metadata(span, None)
        assert raw.attributes[AIAttributes.MODEL_NAME] == "m1"

    def test_dict_replies_do_not_raise(self):
        """The 3.0 agent-loop span reports whatever the generator put in its tags."""
        span, raw = make_span(mapping.AGENT_STEP_LLM)
        span.set_tag(mapping.AGENT_STEP_LLM_OUTPUT, {"replies": [{"meta": {"model": "m2"}}]})
        DefaultSpanHandler._apply_model_metadata(span, None)
        assert raw.attributes[AIAttributes.MODEL_NAME] == "m2"

    def test_unreadable_replies_are_ignored_quietly(self):
        span, raw = make_span(mapping.AGENT_STEP_LLM)
        span.set_tag(mapping.AGENT_STEP_LLM_OUTPUT, {"replies": ["just a string"]})
        DefaultSpanHandler._apply_model_metadata(span, None)
        assert AIAttributes.MODEL_NAME not in raw.attributes

    def test_plain_generator_meta_list(self):
        span, raw = make_span(mapping.COMPONENT_RUN)
        span.set_tag(
            mapping.COMPONENT_OUTPUT,
            {"meta": [{"model": "text-davinci", "usage": {"total_tokens": 9}}]},
        )
        DefaultSpanHandler._apply_model_metadata(span, "OpenAIGenerator")
        assert raw.attributes[AIAttributes.MODEL_NAME] == "text-davinci"
        assert raw.attributes[AIAttributes.LLM_TOKENS_TOTAL] == 9

    def test_embedder_meta_dict(self):
        span, raw = make_span(mapping.COMPONENT_RUN)
        span.set_tag(
            mapping.COMPONENT_OUTPUT,
            {"meta": {"model": "embed-1", "usage": {"prompt_tokens": 4}}},
        )
        DefaultSpanHandler._apply_model_metadata(span, "OpenAITextEmbedder")
        assert raw.attributes[AIAttributes.MODEL_NAME] == "embed-1"
        assert raw.attributes[AIAttributes.LLM_TOKENS_INPUT] == 4

    def test_embedder_billed_units_fallback(self):
        span, raw = make_span(mapping.COMPONENT_RUN)
        span.set_tag(mapping.COMPONENT_OUTPUT, {"meta": {"billed_units": {"prompt_tokens": 6}}})
        DefaultSpanHandler._apply_model_metadata(span, "CohereTextEmbedder")
        assert raw.attributes[AIAttributes.LLM_TOKENS_INPUT] == 6

    def test_bad_completion_start_time_is_logged_not_raised(self, caplog):
        span, raw = make_span(mapping.COMPONENT_RUN)
        reply = ChatMessage.from_assistant("hi", meta={"completion_start_time": "not-a-date"})
        span.set_tag(mapping.COMPONENT_OUTPUT, {"replies": [reply]})
        with caplog.at_level("ERROR"):
            DefaultSpanHandler._apply_model_metadata(span, "OpenAIChatGenerator")
        assert "completion_start_time" in caplog.text
        assert mapping.COMPLETION_START_TIME_ATTRIBUTE not in raw.attributes

    def test_valid_completion_start_time_is_recorded(self):
        span, raw = make_span(mapping.COMPONENT_RUN)
        reply = ChatMessage.from_assistant(
            "hi", meta={"completion_start_time": "2026-01-02T03:04:05"}
        )
        span.set_tag(mapping.COMPONENT_OUTPUT, {"replies": [reply]})
        DefaultSpanHandler._apply_model_metadata(span, "OpenAIChatGenerator")
        assert raw.attributes[mapping.COMPLETION_START_TIME_ATTRIBUTE] == "2026-01-02T03:04:05"


class TestRhesisTracerLifecycle:
    def _tracer(self, provider=None):
        provider = provider or TracerProvider()
        telemetry = RhesisTelemetry(
            provider=provider,
            otel_tracer=provider.get_tracer("t"),
            project_id="proj",
            environment="test",
            base_url="http://localhost:8080",
        )
        tracer = RhesisTracer(telemetry=telemetry, name="app")
        tracer.enforce_flush = False
        return tracer

    def test_span_stack_is_restored(self):
        tracer = self._tracer()
        assert tracer.current_span() is None
        with tracer.trace(mapping.PIPELINE_RUN) as outer:
            assert tracer.current_span() is outer
            with tracer.trace(mapping.COMPONENT_RUN) as inner:
                assert tracer.current_span() is inner
            assert tracer.current_span() is outer
        assert tracer.current_span() is None

    def test_trace_id_is_published_during_the_root_span_only(self):
        tracer = self._tracer()
        assert tracer.get_trace_id() == ""
        with tracer.trace(mapping.PIPELINE_RUN):
            assert len(tracer.get_trace_id()) == 32
        assert tracer.get_trace_id() == ""

    def test_trace_url_is_built_from_the_live_trace_id(self):
        tracer = self._tracer()
        with tracer.trace(mapping.PIPELINE_RUN):
            url = tracer.get_trace_url()
        assert url.startswith("http://localhost:3000/traces?open_trace=")
        assert "project_id=proj" in url

    def test_exceptions_are_recorded_and_re_raised(self):
        tracer = self._tracer()
        with pytest.raises(ValueError, match="boom"):
            with tracer.trace(mapping.PIPELINE_RUN) as span:
                raw = span.raw_span()
                raise ValueError("boom")
        assert raw.attributes[AIAttributes.ERROR_TYPE] == "ValueError"
        assert raw.status.status_code.name == "ERROR"

    def test_invocation_context_does_not_leak_between_runs(self):
        tracer = self._tracer()
        with tracer.trace(mapping.PIPELINE_RUN) as span:
            from rhesis.sdk.telemetry.integrations.haystack.tracer import tracing_context_var

            tracing_context_var.set({"session_id": "run-1"})
            span.raw_span()
        with tracer.trace(mapping.PIPELINE_RUN) as span2:
            from rhesis.sdk.telemetry.integrations.haystack.tracer import tracing_context_var

            assert tracing_context_var.get({}) == {}
            span2.raw_span()

    def test_enforce_flush_runs_once_per_run_not_per_span(self):
        tracer = self._tracer()
        tracer.enforce_flush = True
        calls = []
        tracer._telemetry.flush = lambda: calls.append(1)
        with tracer.trace(mapping.PIPELINE_RUN):
            with tracer.trace(mapping.COMPONENT_RUN):
                pass
            with tracer.trace(mapping.COMPONENT_RUN):
                pass
        assert len(calls) == 1

    def test_no_flush_when_disabled(self):
        tracer = self._tracer()
        calls = []
        tracer._telemetry.flush = lambda: calls.append(1)
        with tracer.trace(mapping.PIPELINE_RUN):
            pass
        assert calls == []

    def test_flush_failures_are_swallowed(self):
        provider = TracerProvider()
        telemetry = RhesisTelemetry(
            provider=provider,
            otel_tracer=provider.get_tracer("t"),
            project_id=None,
            environment="test",
            base_url="http://localhost:8080",
        )

        def boom(**_):
            raise RuntimeError("network down")

        provider.force_flush = boom
        telemetry.flush()  # must not raise

    def test_warns_when_content_tracing_is_off(self, monkeypatch, caplog):
        from haystack import tracing

        monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
        with caplog.at_level("WARNING"):
            self._tracer()
        assert "HAYSTACK_CONTENT_TRACING_ENABLED" in caplog.text


class TestConcurrency:
    def test_concurrent_traces_keep_separate_stacks_and_trace_ids(self):
        import asyncio

        provider = TracerProvider()
        telemetry = RhesisTelemetry(
            provider=provider,
            otel_tracer=provider.get_tracer("t"),
            project_id="p",
            environment="test",
            base_url="http://localhost:8080",
        )
        tracer = RhesisTracer(telemetry=telemetry, name="app")
        tracer.enforce_flush = False

        async def one_run(label):
            with tracer.trace(mapping.PIPELINE_RUN):
                trace_id = tracer.get_trace_id()
                await asyncio.sleep(0)
                with tracer.trace(mapping.COMPONENT_RUN):
                    await asyncio.sleep(0)
                    depth = len(span_stack_var.get() or [])
                # The id must not have been overwritten by the sibling task.
                assert tracer.get_trace_id() == trace_id
                return label, trace_id, depth

        async def run_all():
            return await asyncio.gather(*(one_run(i) for i in range(4)))

        results = asyncio.run(run_all())
        trace_ids = {trace_id for _, trace_id, _ in results}
        assert len(trace_ids) == 4, "each concurrent run must get its own trace id"
        assert {depth for _, _, depth in results} == {2}
