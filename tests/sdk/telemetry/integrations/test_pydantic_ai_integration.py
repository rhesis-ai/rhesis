"""Tests for the Pydantic AI native-instrumentation integration.

The integration enables Pydantic AI's built-in OpenTelemetry instrumentation
(pinned version, binary content excluded) and wraps the exporter with a
``gen_ai.*`` -> ``ai.*`` translator. These tests run real agents backed by
``TestModel`` and assert on the spans that come out of the wrapped exporter:
agent runs, per-model-call LLM spans, tool spans with I/O events, synthesized
handoff spans for multi-agent delegation, and ``run_stream`` coverage.
"""

import asyncio
import json

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.test import TestModel

from rhesis.sdk.telemetry.attributes import AIAttributes, validate_span_name
from rhesis.sdk.telemetry.context import (
    is_llm_observation_active,
    set_llm_observation_active,
)
from rhesis.sdk.telemetry.integrations.pydantic_ai import (
    PINNED_INSTRUMENTATION_VERSION,
    PydanticAIIntegration,
    PydanticAILLMDedupSpanProcessor,
    PydanticAITranslatingExporter,
    mapping,
    translate_span,
)
from rhesis.sdk.telemetry.integrations.pydantic_ai import translator as translator_module

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def session_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """A real ``TracerProvider`` plus in-memory exporter for the test session.

    OTEL's :func:`opentelemetry.trace.set_tracer_provider` only honors the
    first call per process; if some earlier test or import has already
    installed a provider, our second ``set_tracer_provider`` call is a no-op
    (warns) and our spans land elsewhere. To stay robust we ride on whatever
    provider is already global when it's already a real
    :class:`opentelemetry.sdk.trace.TracerProvider`, and fall back to
    installing our own otherwise. Either way we attach a
    :class:`SimpleSpanProcessor` (synchronous export, no flush dance) whose
    exporter is the in-memory capture used by the assertions in this module.
    """
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
def integration(session_provider) -> PydanticAIIntegration:
    """Yield a fresh :class:`PydanticAIIntegration` enabled against the provider.

    The integration is enabled on entry and disabled on teardown (which also
    calls ``Agent.instrument_all(False)``) so tests don't inherit each
    other's instrumentation state.
    """
    integ = PydanticAIIntegration()
    assert integ.enable() is True, "PydanticAIIntegration.enable() must succeed"
    try:
        yield integ
    finally:
        integ.disable()


@pytest.fixture
def captured_spans(session_provider, integration) -> InMemorySpanExporter:
    """Yield the in-memory exporter, drained at the end of each test."""
    _provider, captured = session_provider
    captured.clear()
    yield captured
    captured.clear()


@pytest.fixture
def reset_llm_observation_flag():
    """Always exit a test with the LLM-observation flag cleared."""
    yield
    set_llm_observation_active(False)


def _spans_named(exporter: InMemorySpanExporter, name: str):
    return [s for s in exporter.get_finished_spans() if s.name == name]


def _all_span_text(exporter: InMemorySpanExporter) -> str:
    """Serialize every exported span's attributes and events for leak checks."""
    chunks: list[str] = []
    for span in exporter.get_finished_spans():
        chunks.append(json.dumps(dict(span.attributes or {}), default=str))
        for event in span.events or ():
            chunks.append(json.dumps(dict(event.attributes or {}), default=str))
    return "\n".join(chunks)


def _make_agent(**kwargs) -> Agent:
    return Agent(TestModel(custom_output_text="hello from test model"), **kwargs)


# ---------------------------------------------------------------------------
# Pure mapping tests
# ---------------------------------------------------------------------------


class TestMapping:
    def test_scope_detection(self):
        assert mapping.is_pydantic_ai_scope("pydantic-ai") is True
        assert mapping.is_pydantic_ai_scope("pydantic-ai.something") is True
        assert mapping.is_pydantic_ai_scope("agent_framework") is False
        assert mapping.is_pydantic_ai_scope(None) is False

    @pytest.mark.parametrize(
        ("operation", "expected"),
        [
            ("chat", "ai.llm.invoke"),
            ("invoke_agent", "ai.agent.invoke"),
            ("execute_tool", "ai.tool.invoke"),
        ],
    )
    def test_span_name_from_operation(self, operation, expected):
        name = mapping.translate_span_name("anything", {"gen_ai.operation.name": operation})
        assert name == expected
        assert validate_span_name(name)

    def test_span_name_fuzzy_from_name(self):
        assert mapping.translate_span_name("chat gpt-4o", {}) == "ai.llm.invoke"

    def test_span_name_unknown_falls_back(self):
        name = mapping.translate_span_name("brand new thing", {})
        assert name == "function.pydantic_ai.brand_new_thing"
        assert validate_span_name(name)

    def test_fallback_name_empty(self):
        assert mapping.fallback_function_pydantic_ai_name("") == "function.pydantic_ai.unknown"

    def test_aggregated_usage_maps_to_token_attributes(self):
        attrs = mapping.translate_attributes(
            {
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.aggregated_usage.input_tokens": 100,
                "gen_ai.aggregated_usage.output_tokens": 20,
            }
        )
        assert attrs[AIAttributes.LLM_TOKENS_INPUT] == 100
        assert attrs[AIAttributes.LLM_TOKENS_OUTPUT] == 20
        assert attrs[AIAttributes.LLM_TOKENS_TOTAL] == 120

    def test_plain_model_name_maps(self):
        attrs = mapping.translate_attributes({"model_name": "test"})
        assert attrs[AIAttributes.MODEL_NAME] == "test"

    def test_agent_events_from_all_messages_and_final_result(self):
        all_messages = json.dumps(
            [
                {"role": "user", "parts": [{"type": "text", "content": "What is 2+2?"}]},
                {"role": "assistant", "parts": [{"type": "text", "content": "4"}]},
            ]
        )
        events = mapping.synthesize_agent_events(
            {
                "gen_ai.operation.name": "invoke_agent",
                "pydantic_ai.all_messages": all_messages,
                "final_result": "4",
            }
        )
        names = [name for name, _ in events]
        assert names == ["ai.prompt", "ai.completion"]
        prompt_attrs = events[0][1]
        assert prompt_attrs[AIAttributes.PROMPT_ROLE] == "user"
        assert prompt_attrs[AIAttributes.PROMPT_CONTENT] == "What is 2+2?"
        assert events[1][1][AIAttributes.COMPLETION_CONTENT] == "4"

    def test_agent_events_skip_non_agent_spans(self):
        assert (
            mapping.synthesize_agent_events({"gen_ai.operation.name": "chat", "final_result": "4"})
            == []
        )


# ---------------------------------------------------------------------------
# End-to-end instrumented runs
# ---------------------------------------------------------------------------


class TestInstrumentedRun:
    def test_run_sync_produces_agent_span(self, captured_spans):
        agent = _make_agent(name="my-agent")
        result = agent.run_sync("What is 2+2?")
        assert result.output == "hello from test model"

        agent_spans = _spans_named(captured_spans, "ai.agent.invoke")
        assert len(agent_spans) == 1
        span = agent_spans[0]
        attrs = span.attributes
        assert attrs[AIAttributes.AGENT_NAME] == "my-agent"
        assert attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_AGENT_INVOKE
        assert attrs[AIAttributes.LLM_TOKENS_TOTAL] > 0

        event_names = [e.name for e in span.events]
        assert "ai.prompt" in event_names
        assert "ai.completion" in event_names

    def test_run_sync_produces_llm_child_span(self, captured_spans):
        agent = _make_agent(name="my-agent")
        agent.run_sync("What is 2+2?")

        llm_spans = _spans_named(captured_spans, "ai.llm.invoke")
        assert len(llm_spans) == 1
        span = llm_spans[0]
        attrs = span.attributes
        assert attrs[AIAttributes.MODEL_NAME] == "test"
        assert attrs[AIAttributes.MODEL_PROVIDER] == "test"
        assert attrs[AIAttributes.LLM_TOKENS_TOTAL] > 0

        # Message events synthesized from gen_ai.input/output.messages
        prompts = [e for e in span.events if e.name == "ai.prompt"]
        completions = [e for e in span.events if e.name == "ai.completion"]
        assert prompts and completions
        assert prompts[0].attributes[AIAttributes.PROMPT_CONTENT] == "What is 2+2?"
        assert completions[0].attributes[AIAttributes.COMPLETION_CONTENT] == "hello from test model"

        # The LLM span is a child of the agent span
        agent_span = _spans_named(captured_spans, "ai.agent.invoke")[0]
        assert span.parent.span_id == agent_span.context.span_id

    def test_tool_call_produces_tool_span_with_io_events(self, captured_spans):
        agent = Agent(TestModel(), name="tool-agent")

        @agent.tool_plain
        def lookup(query: str) -> str:
            """Fake lookup tool."""
            return f"result for {query}"

        agent.run_sync("look something up")

        tool_spans = _spans_named(captured_spans, "ai.tool.invoke")
        assert len(tool_spans) == 1
        span = tool_spans[0]
        assert span.attributes[AIAttributes.TOOL_NAME] == "lookup"
        assert span.attributes[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_TOOL_INVOKE

        event_names = [e.name for e in span.events]
        assert "ai.tool.input" in event_names
        assert "ai.tool.output" in event_names
        output_event = next(e for e in span.events if e.name == "ai.tool.output")
        assert "result for" in output_event.attributes[AIAttributes.TOOL_OUTPUT_CONTENT]

    def test_async_run_covered(self, captured_spans):
        agent = _make_agent(name="async-agent")
        asyncio.run(agent.run("hello"))
        assert len(_spans_named(captured_spans, "ai.agent.invoke")) == 1
        assert len(_spans_named(captured_spans, "ai.llm.invoke")) == 1

    def test_run_stream_covered(self, captured_spans):
        """Regression: run_stream is a separate entry point the old
        Agent.run monkey-patch never saw. Native instrumentation covers it."""
        agent = _make_agent(name="stream-agent")

        async def stream_it():
            async with agent.run_stream("stream me") as stream:
                return await stream.get_output()

        asyncio.run(stream_it())
        assert len(_spans_named(captured_spans, "ai.agent.invoke")) == 1
        assert len(_spans_named(captured_spans, "ai.llm.invoke")) >= 1

    def test_all_exported_span_names_are_valid(self, captured_spans):
        agent = Agent(TestModel(), name="validator-agent")

        @agent.tool_plain
        def noop(x: str) -> str:
            """No-op tool."""
            return x

        agent.run_sync("go")
        spans = captured_spans.get_finished_spans()
        assert spans
        for span in spans:
            assert validate_span_name(span.name), f"invalid span name: {span.name!r}"

    def test_error_status_recorded(self, captured_spans):
        agent = Agent(TestModel(), name="error-agent")

        @agent.tool_plain
        def boom(x: str) -> str:
            """Always raises."""
            raise RuntimeError("tool exploded")

        with pytest.raises(RuntimeError, match="tool exploded"):
            agent.run_sync("trigger the tool")

        agent_spans = _spans_named(captured_spans, "ai.agent.invoke")
        assert len(agent_spans) == 1
        assert agent_spans[0].status.status_code == StatusCode.ERROR


# ---------------------------------------------------------------------------
# Multi-agent delegation -> handoff synthesis
# ---------------------------------------------------------------------------


class TestHandoffSynthesis:
    def test_delegation_synthesizes_handoff_span(self, captured_spans):
        child = Agent(TestModel(custom_output_text="child says hi"), name="child_agent")
        parent = Agent(TestModel(), name="parent_agent")

        @parent.tool_plain
        def delegate(question: str) -> str:
            """Delegate to the child agent."""
            return str(child.run_sync(question).output)

        parent.run_sync("delegate this")

        handoffs = _spans_named(captured_spans, "ai.agent.handoff")
        assert len(handoffs) == 1
        span = handoffs[0]
        attrs = span.attributes
        assert attrs[AIAttributes.AGENT_HANDOFF_FROM] == "parent_agent"
        assert attrs[AIAttributes.AGENT_HANDOFF_TO] == "child_agent"
        assert attrs[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_AGENT_HANDOFF

        # Zero-duration marker span sharing the trace
        assert span.start_time == span.end_time
        child_agent_span = next(
            s
            for s in _spans_named(captured_spans, "ai.agent.invoke")
            if s.attributes[AIAttributes.AGENT_NAME] == "child_agent"
        )
        assert span.context.trace_id == child_agent_span.context.trace_id
        # Sibling of the delegated run: parented to the execute_tool span
        assert span.parent.span_id == child_agent_span.parent.span_id

    def test_single_agent_run_has_no_handoff(self, captured_spans):
        _make_agent(name="solo-agent").run_sync("just me")
        assert _spans_named(captured_spans, "ai.agent.handoff") == []

    def test_synthesize_handoff_span_requires_context(self):
        class NoContext:
            context = None

        assert (
            translator_module.synthesize_handoff_span(NoContext(), "a", "b") is None  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Content safety
# ---------------------------------------------------------------------------


class TestContentSafety:
    def test_binary_content_bytes_never_reach_spans(self, captured_spans):
        """Regression: the previous integration leaked attachment bytes via
        repr(); the native path must exclude them via include_binary_content=False."""
        payload = b"BINARYPAYLOAD" * 200
        agent = _make_agent(name="binary-agent")
        agent.run_sync(
            [
                "describe this image",
                BinaryContent(data=payload, media_type="image/png"),
            ]
        )

        text = _all_span_text(captured_spans)
        assert "BINARYPAYLOAD" not in text
        import base64

        assert base64.b64encode(payload).decode()[:24] not in text

    def test_content_capture_opt_out(self, session_provider, monkeypatch):
        """RHESIS_DISABLE_CONTENT_CAPTURE suppresses prompt/completion content."""
        monkeypatch.setenv("RHESIS_DISABLE_CONTENT_CAPTURE", "1")
        _provider, captured = session_provider
        integ = PydanticAIIntegration()
        assert integ.enable() is True
        captured.clear()
        try:
            _make_agent(name="private-agent").run_sync("super secret prompt")
            text = _all_span_text(captured)
            assert "super secret prompt" not in text
        finally:
            integ.disable()
            captured.clear()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_framework_name_and_installed(self):
        integ = PydanticAIIntegration()
        assert integ.framework_name == "pydantic_ai"
        assert integ.is_installed() is True

    def test_enable_is_idempotent(self, integration):
        assert integration.enable() is True
        assert integration.enable() is True

    def test_enable_fails_without_sdk_provider(self, monkeypatch):
        # `integrations/__init__` rebinds the name `pydantic_ai` in the parent
        # package namespace to the singleton instance, so a dotted monkeypatch
        # path would resolve to that instance instead of the module. Go
        # through importlib to get the actual module unambiguously.
        import importlib

        integ_mod = importlib.import_module(
            "rhesis.sdk.telemetry.integrations.pydantic_ai.integration"
        )
        integ = PydanticAIIntegration()
        monkeypatch.setattr(integ_mod.trace, "get_tracer_provider", lambda: object())
        assert integ.enable() is False

    def test_disable_stops_span_emission(self, session_provider):
        _provider, captured = session_provider
        integ = PydanticAIIntegration()
        assert integ.enable() is True
        integ.disable()
        captured.clear()

        _make_agent(name="after-disable").run_sync("hi")
        assert captured.get_finished_spans() == ()

    def test_disable_unwraps_exporter(self, session_provider):
        from rhesis.sdk.telemetry.integrations.genai import get_processor_exporter

        integ = PydanticAIIntegration()
        assert integ.enable() is True
        assert integ._patched_processors, "enable() should wrap at least one exporter"
        patched = list(integ._patched_processors)
        for proc, _original in patched:
            assert isinstance(get_processor_exporter(proc), PydanticAITranslatingExporter)
        integ.disable()
        assert integ._patched_processors == []
        for proc, original in patched:
            assert get_processor_exporter(proc) is original

    def test_callback_is_dedup_processor(self, integration):
        assert isinstance(integration.callback(), PydanticAILLMDedupSpanProcessor)

    def test_pinned_version_is_explicit(self):
        assert isinstance(PINNED_INSTRUMENTATION_VERSION, int)


# ---------------------------------------------------------------------------
# Translation fallback safety
# ---------------------------------------------------------------------------


class TestTranslationFallback:
    def test_safe_fallback_produces_valid_name(self, session_provider):
        provider, _captured = session_provider
        tracer = provider.get_tracer("pydantic-ai")
        span = tracer.start_span("chat gpt-4o")
        span.end()
        fallback = translator_module._safe_fallback_span(span)
        assert fallback.name == "function.pydantic_ai.chat_gpt-4o"
        assert validate_span_name(fallback.name)
        assert fallback.attributes["gen_ai.original_span_name"] == "chat gpt-4o"

    def test_translate_span_unknown_operation(self, session_provider):
        provider, _captured = session_provider
        tracer = provider.get_tracer("pydantic-ai")
        span = tracer.start_span("mystery operation")
        span.end()
        translated = translate_span(span)
        assert translated.name == "function.pydantic_ai.mystery_operation"
        assert translated.attributes["gen_ai.original_span_name"] == "mystery operation"

    def test_non_pydantic_spans_pass_through(self, session_provider):
        provider, _captured = session_provider

        class RecordingExporter:
            def __init__(self):
                self.batches = []

            def export(self, spans):
                self.batches.append(list(spans))
                from opentelemetry.sdk.trace.export import SpanExportResult

                return SpanExportResult.SUCCESS

            def shutdown(self):
                pass

            def force_flush(self, timeout_millis=30_000):
                return True

        inner = RecordingExporter()
        exporter = PydanticAITranslatingExporter(inner)  # type: ignore[arg-type]
        tracer = provider.get_tracer("some.other.scope")
        span = tracer.start_span("my.custom.span")
        span.end()
        exporter.export([span])
        assert inner.batches[0][0] is span


# ---------------------------------------------------------------------------
# LLM dedup processor
# ---------------------------------------------------------------------------


class TestDedupProcessor:
    def _chat_span(self, provider):
        tracer = provider.get_tracer("pydantic-ai")
        span = tracer.start_span("chat test")
        span.set_attribute("gen_ai.operation.name", "chat")
        return span

    def test_toggles_flag_for_chat_spans(self, session_provider, reset_llm_observation_flag):
        provider, _captured = session_provider
        proc = PydanticAILLMDedupSpanProcessor()
        proc.activate()

        span = self._chat_span(provider)
        assert is_llm_observation_active() is False
        proc.on_start(span)
        assert is_llm_observation_active() is True
        span.end()
        proc.on_end(span)
        assert is_llm_observation_active() is False

    def test_preserves_outer_flag(self, session_provider, reset_llm_observation_flag):
        provider, _captured = session_provider
        proc = PydanticAILLMDedupSpanProcessor()
        proc.activate()

        set_llm_observation_active(True)
        span = self._chat_span(provider)
        proc.on_start(span)
        span.end()
        proc.on_end(span)
        assert is_llm_observation_active() is True

    def test_inactive_processor_is_noop(self, session_provider, reset_llm_observation_flag):
        provider, _captured = session_provider
        proc = PydanticAILLMDedupSpanProcessor()

        span = self._chat_span(provider)
        proc.on_start(span)
        assert is_llm_observation_active() is False

    def test_non_chat_spans_do_not_toggle(self, session_provider, reset_llm_observation_flag):
        provider, _captured = session_provider
        proc = PydanticAILLMDedupSpanProcessor()
        proc.activate()

        tracer = provider.get_tracer("pydantic-ai")
        span = tracer.start_span("invoke_agent my-agent")
        proc.on_start(span)
        assert is_llm_observation_active() is False
