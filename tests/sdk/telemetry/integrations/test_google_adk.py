"""Tests for the Google ADK native-instrumentation integration.

Google ADK emits OpenTelemetry spans unconditionally under the
``gcp.vertex.agent`` scope; the integration wraps the Rhesis exporter with a
translator that rewrites them into the ``ai.*`` / ``function.*`` schema.

These tests drive **real** ADK agents backed by a canned ``BaseLlm`` (no
network) and assert on what comes out of the wrapped exporter: the span-name
map under both ADK telemetry schema versions, prompt/completion extraction from
ADK's own JSON blob attributes, tool I/O, token folding, handoff edges for both
multi-agent mechanisms, the drop-and-reparent of ADK's duplicate inner model
span, conversation turn-root stamping, and the integration lifecycle.
"""

import itertools
import json
from typing import Any, AsyncGenerator

import pytest

google_adk = pytest.importorskip("google.adk")

from google.adk.agents import Agent, ParallelAgent, SequentialAgent  # noqa: E402
from google.adk.models.base_llm import BaseLlm  # noqa: E402
from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.tools.agent_tool import AgentTool  # noqa: E402
from google.genai import types  # noqa: E402
from opentelemetry import trace as otel_trace  # noqa: E402
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import (  # noqa: E402
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from rhesis.telemetry.attributes import AIAttributes, validate_span_name  # noqa: E402
from rhesis.telemetry.constants import ConversationContext  # noqa: E402
from rhesis.telemetry.context import (  # noqa: E402
    set_conversation_id,
    set_llm_observation_active,
)
from rhesis.telemetry.schemas import AIOperationType  # noqa: E402

from rhesis.sdk.telemetry.integrations.google_adk import (  # noqa: E402
    GoogleADKIntegration,
    GoogleADKLLMDedupSpanProcessor,
    GoogleADKTranslatingExporter,
    mapping,
    translate_span,
    translator,
    verbose_spans_enabled,
)

APP_NAME = "adk-test-app"
USER_ID = "adk-test-user"

# ---------------------------------------------------------------------------
# A deterministic ADK model
# ---------------------------------------------------------------------------

# Module-level so the counter is shared by every agent in a run: ADK constructs
# one CannedLlm per agent, but a scenario is a single flat script of replies for
# the whole nested run (the same trick reg-advisor's own MockLlm uses).
_REPLIES: list[LlmResponse] = []
_CURSOR = itertools.count()


class CannedLlm(BaseLlm):
    """A real ``BaseLlm`` serving pre-built ``LlmResponse``s. No network.

    Subclassing ``BaseLlm`` is deliberate: it is the lowest point ADK dispatches
    to, so the agent, the flow, the callbacks and -- crucially -- all of ADK's
    telemetry above it run for real.
    """

    model: str = "gemini-3.1-flash-lite"

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield _REPLIES[min(next(_CURSOR), len(_REPLIES) - 1)]


def script(*replies: LlmResponse) -> None:
    """Install the flat reply script for one scenario."""
    global _CURSOR
    _REPLIES[:] = list(replies)
    _CURSOR = itertools.count()


def text(body: str) -> LlmResponse:
    """A finished text answer, with the full ADK token breakdown."""
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=body)]),
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=11,
            candidates_token_count=7,
            total_token_count=18,
            cached_content_token_count=4,
            thoughts_token_count=2,
        ),
        finish_reason=types.FinishReason.STOP,
    )


def tool_call(name: str, arguments: dict, call_id: str = "call-1") -> LlmResponse:
    """A function-call reply that makes ADK execute a tool."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(function_call=types.FunctionCall(name=name, args=arguments, id=call_id))
            ],
        ),
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=5, candidates_token_count=3, total_token_count=8
        ),
    )


def parallel_tool_calls(name: str, *arg_sets: dict) -> LlmResponse:
    """Two function calls in one reply, which makes ADK emit ``execute_tool (merged)``."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(name=name, args=args, id=f"call-{index}")
                )
                for index, args in enumerate(arg_sets)
            ],
        ),
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=5, candidates_token_count=3, total_token_count=8
        ),
    )


def get_weather(city: str) -> dict:
    """Get the weather for a city."""
    return {"temp": 20, "city": city}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def session_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """A real ``TracerProvider`` plus in-memory exporter for the test session.

    OTEL's :func:`opentelemetry.trace.set_tracer_provider` only honors the first
    call per process; if an earlier test or import already installed a provider,
    a second call is a no-op (warns) and our spans land elsewhere. So we ride on
    whatever real provider is already global and fall back to installing one.
    A :class:`SimpleSpanProcessor` keeps export synchronous, no flush dance.
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
def integration(session_provider) -> GoogleADKIntegration:
    """A fresh :class:`GoogleADKIntegration`, enabled and torn down per test."""
    integ = GoogleADKIntegration()
    assert integ.enable() is True, "GoogleADKIntegration.enable() must succeed"
    try:
        yield integ
    finally:
        integ.disable()


@pytest.fixture
def captured_spans(session_provider, integration) -> InMemorySpanExporter:
    """The in-memory exporter, drained either side of each test."""
    _provider, captured = session_provider
    captured.clear()
    yield captured
    captured.clear()


@pytest.fixture(autouse=True)
def reset_llm_observation_flag():
    """Keep the LLM-observation contextvar from leaking between tests."""
    yield
    set_llm_observation_active(False)


@pytest.fixture(autouse=True)
def reset_conversation_id():
    """Keep the conversation-id contextvar from leaking between tests."""
    yield
    set_conversation_id(None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def run_agent(
    root_agent,
    message: str = "What is the weather in Berlin?",
    *,
    session_id: str = "sess-1",
) -> None:
    """Drive one ADK turn through a real ``Runner`` via ``run_async``."""
    service = InMemorySessionService()
    await service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=service)
    async for _event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    ):
        pass


def names(exporter: InMemorySpanExporter) -> list[str]:
    return [span.name for span in exporter.get_finished_spans()]


def spans_named(exporter: InMemorySpanExporter, name: str) -> list[ReadableSpan]:
    return [span for span in exporter.get_finished_spans() if span.name == name]


def root_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [span for span in exporter.get_finished_spans() if span.parent is None]


def event_bodies(span: ReadableSpan, event_name: str) -> list[str]:
    """Every content string carried by ``event_name`` events on ``span``."""
    bodies = []
    for event in span.events:
        if event.name != event_name:
            continue
        for key, value in (event.attributes or {}).items():
            if key.endswith(("content", ".input", ".output")):
                bodies.append(str(value))
    return bodies


def parent_of(exporter: InMemorySpanExporter, span: ReadableSpan) -> ReadableSpan | None:
    by_id = {s.context.span_id: s for s in exporter.get_finished_spans()}
    parent = span.parent
    return by_id.get(parent.span_id) if parent is not None else None


# ---------------------------------------------------------------------------
# Pure mapping: span names
# ---------------------------------------------------------------------------


class TestSpanNameMapping:
    @pytest.mark.parametrize(
        "original,attributes,expected",
        [
            (
                "invoke_agent bot",
                {mapping.GEN_AI_OPERATION_NAME: "invoke_agent"},
                "ai.agent.invoke",
            ),
            ("call_llm", {}, "ai.llm.invoke"),
            (
                "generate_content gemini-3.1-flash-lite",
                {mapping.GEN_AI_OPERATION_NAME: "generate_content"},
                "ai.llm.invoke",
            ),
            (
                "execute_tool get_weather",
                {
                    mapping.GEN_AI_OPERATION_NAME: "execute_tool",
                    mapping.GEN_AI_TOOL_NAME: "get_weather",
                },
                "ai.tool.invoke",
            ),
            ("invocation", {}, "function.google_adk.invocation"),
            (
                "invoke_workflow pipeline",
                {mapping.GEN_AI_OPERATION_NAME: "invoke_workflow"},
                "function.google_adk.workflow.pipeline",
            ),
            (
                "invoke_node fetch data",
                {mapping.GEN_AI_OPERATION_NAME: "invoke_node"},
                "function.google_adk.node.fetch_data",
            ),
            (
                "managed_agent_interaction",
                {},
                "function.google_adk.managed_agent_interaction",
            ),
        ],
    )
    def test_translate_span_name(self, original, attributes, expected):
        assert mapping.translate_span_name(original, attributes) == expected

    def test_transfer_tool_span_becomes_a_handoff(self):
        attributes = {
            mapping.GEN_AI_OPERATION_NAME: "execute_tool",
            mapping.GEN_AI_TOOL_NAME: "transfer_to_agent",
            mapping.GCP_TOOL_CALL_ARGS: '{"agent_name": "specialist"}',
        }
        assert mapping.translate_span_name("execute_tool transfer_to_agent", attributes) == (
            "ai.agent.handoff"
        )

    @pytest.mark.parametrize(
        "original",
        [
            "some_future_adk_span",
            "execute_tool (merged)",
            "compact_events token_threshold",
            "handle_context_caching",
        ],
    )
    def test_unmapped_names_land_in_the_function_namespace(self, original):
        """An ADK span we do not model must still be a name the backend accepts."""
        translated = mapping.fallback_function_adk_name(original)
        assert translated.startswith("function.google_adk.")
        assert validate_span_name(translated)

    def test_empty_name_has_a_fallback(self):
        assert mapping.fallback_function_adk_name("") == "function.google_adk.unknown"

    def test_every_mapped_name_passes_backend_validation(self):
        """`ai.*` names allow only lowercase letters and forbid the workflow domain."""
        candidates = [
            mapping.translate_span_name(original, attributes)
            for original, attributes in [
                ("invocation", {}),
                ("invoke_agent a", {mapping.GEN_AI_OPERATION_NAME: "invoke_agent"}),
                ("call_llm", {}),
                ("generate_content m", {mapping.GEN_AI_OPERATION_NAME: "generate_content"}),
                ("execute_tool t", {mapping.GEN_AI_OPERATION_NAME: "execute_tool"}),
                ("invoke_workflow w", {mapping.GEN_AI_OPERATION_NAME: "invoke_workflow"}),
                ("invoke_node n", {mapping.GEN_AI_OPERATION_NAME: "invoke_node"}),
                ("brand new thing", {}),
            ]
        ]
        assert all(validate_span_name(name) for name in candidates), candidates
        # The validator rejects "workflow" as an ai.* domain, which is why ADK's
        # workflow spans have to live under function.*
        assert not validate_span_name("ai.workflow.invoke")


# ---------------------------------------------------------------------------
# Pure mapping: attributes and content
# ---------------------------------------------------------------------------


CALL_LLM_ATTRIBUTES = {
    mapping.GEN_AI_SYSTEM: "gcp.vertex.agent",
    mapping.GEN_AI_REQUEST_MODEL: "gemini-3.1-flash-lite",
    mapping.GCP_SESSION_ID: "sess-1",
    mapping.GCP_INVOCATION_ID: "e-abc",
    mapping.GCP_LLM_REQUEST: json.dumps(
        {
            "model": "gemini-3.1-flash-lite",
            "config": {"system_instruction": "You help."},
            "contents": [
                {"role": "user", "parts": [{"text": "weather in Berlin?"}]},
                {
                    "role": "model",
                    "parts": [{"function_call": {"id": "c1", "name": "get_weather"}}],
                },
                {
                    "role": "user",
                    "parts": [{"function_response": {"id": "c1", "response": {"temp": 20}}}],
                },
            ],
        }
    ),
    mapping.GCP_LLM_RESPONSE: json.dumps(
        {
            "content": {"parts": [{"text": "It is 20C in Berlin."}], "role": "model"},
            "finish_reason": "STOP",
        }
    ),
    mapping.GEN_AI_USAGE_INPUT_TOKENS: 11,
    mapping.GEN_AI_USAGE_OUTPUT_TOKENS: 9,
    mapping.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS: 4,
    mapping.GEN_AI_USAGE_REASONING_OUTPUT_TOKENS: 2,
}


class TestAttributeTranslation:
    def test_framework_label_never_becomes_the_model_provider(self):
        """``gen_ai.system`` on ``call_llm`` is the literal ``gcp.vertex.agent``."""
        translated = mapping.translate_attributes(CALL_LLM_ATTRIBUTES)
        assert translated[AIAttributes.MODEL_PROVIDER] == "gemini"
        assert translated[AIAttributes.MODEL_PROVIDER] != mapping.INSTRUMENTATION_SCOPE

    def test_provider_dropped_rather_than_wrong_when_undecidable(self):
        translated = mapping.translate_attributes(
            {mapping.GEN_AI_SYSTEM: "gcp.vertex.agent", mapping.GEN_AI_REQUEST_MODEL: "mystery-1"}
        )
        assert AIAttributes.MODEL_PROVIDER not in translated

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("gemini-3.1-flash-lite", "gemini"),
            ("gemma-2-9b", "gemini"),
            ("projects/p/locations/l/publishers/google/models/gemini-2.5-flash", "vertex_ai"),
            ("openai/gpt-4o", "openai"),
            ("anthropic/claude-sonnet-4", "anthropic"),
            ("vertex_ai/claude-3-7-sonnet@20250219", "vertex_ai"),
            ("gpt-4o", None),
            ("", None),
            (None, None),
        ],
    )
    def test_derive_model_provider(self, model, expected):
        assert mapping.derive_model_provider(model) == expected

    def test_enterprise_mode_switches_google_models_to_vertex(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
        assert mapping.derive_model_provider("gemini-3.1-flash-lite") == "vertex_ai"

    def test_cache_read_tokens_are_folded_into_the_total(self):
        """ADK already counts reasoning tokens in its output total; cache reads it does not."""
        translated = mapping.translate_attributes(CALL_LLM_ATTRIBUTES)
        assert translated[AIAttributes.LLM_TOKENS_INPUT] == 11
        assert translated[AIAttributes.LLM_TOKENS_OUTPUT] == 9
        assert translated[AIAttributes.LLM_TOKENS_TOTAL] == 24

    def test_content_blobs_are_stripped_from_the_translated_attributes(self):
        """Their payload is re-emitted as events; keeping both ships it twice."""
        translated = mapping.translate_attributes(CALL_LLM_ATTRIBUTES)
        for blob in (
            mapping.GCP_LLM_REQUEST,
            mapping.GCP_LLM_RESPONSE,
            mapping.GCP_TOOL_CALL_ARGS,
            mapping.GCP_TOOL_RESPONSE,
            mapping.GCP_DATA,
        ):
            assert blob not in translated

    def test_session_id_is_translated(self):
        translated = mapping.translate_attributes(CALL_LLM_ATTRIBUTES)
        assert translated[AIAttributes.SESSION_ID] == "sess-1"


class TestContentExtraction:
    def test_prompts_and_completion_come_out_of_the_adk_blobs(self):
        events = mapping.synthesize_llm_content_events(CALL_LLM_ATTRIBUTES)
        assert [name for name, _ in events] == [
            "ai.prompt",
            "ai.prompt",
            "ai.prompt",
            "ai.prompt",
            "ai.completion",
        ]
        bodies = [next(iter(attrs.values())) for _, attrs in events]
        assert "system" in bodies[0] or events[0][1][AIAttributes.PROMPT_ROLE] == "system"
        assert events[-1][1][AIAttributes.COMPLETION_CONTENT] == "It is 20C in Berlin."

    def test_non_text_parts_stay_visible_as_json(self):
        events = mapping.synthesize_llm_content_events(CALL_LLM_ATTRIBUTES)
        rendered = " ".join(str(attrs) for _, attrs in events)
        assert "function_call" in rendered
        assert "function_response" in rendered

    def test_model_role_is_renamed_to_assistant(self):
        events = mapping.synthesize_llm_content_events(CALL_LLM_ATTRIBUTES)
        roles = [attrs.get(AIAttributes.PROMPT_ROLE) for _, attrs in events if _ == "ai.prompt"]
        assert "assistant" in roles
        assert "model" not in roles

    def test_conversation_input_is_text_only(self):
        """The tool-result turn is also role ``user`` but carries no text."""
        assert mapping.extract_conversation_input(CALL_LLM_ATTRIBUTES) == "weather in Berlin?"

    def test_conversation_output_is_text_only(self):
        assert mapping.extract_conversation_output(CALL_LLM_ATTRIBUTES) == "It is 20C in Berlin."

    def test_tool_call_response_only_output_yields_nothing(self):
        attributes = {
            mapping.GCP_LLM_RESPONSE: json.dumps(
                {"content": {"parts": [{"function_call": {"name": "t"}}], "role": "model"}}
            )
        }
        assert mapping.extract_conversation_output(attributes) is None

    def test_system_instruction_as_a_content_object(self):
        attributes = {
            mapping.GCP_LLM_REQUEST: json.dumps(
                {"config": {"system_instruction": {"parts": [{"text": "be brief"}]}}}
            )
        }
        events = mapping.synthesize_llm_content_events(attributes)
        assert events[0][1][AIAttributes.PROMPT_CONTENT] == "be brief"

    def test_malformed_json_is_skipped_rather_than_raising(self):
        attributes = {mapping.GCP_LLM_REQUEST: "{not json", mapping.GCP_LLM_RESPONSE: "]["}
        assert mapping.synthesize_llm_content_events(attributes) == []
        assert mapping.extract_conversation_input(attributes) is None

    @pytest.mark.parametrize("blob", ["{}", "", "<not serializable>"])
    def test_content_capture_off_sentinels_yield_nothing(self, blob):
        attributes = {mapping.GCP_LLM_REQUEST: blob, mapping.GCP_LLM_RESPONSE: blob}
        assert mapping.synthesize_llm_content_events(attributes) == []


class TestToolIOEvents:
    def test_tool_args_and_result_become_events(self):
        events = mapping.synthesize_tool_io_events(
            {
                mapping.GCP_TOOL_CALL_ARGS: '{"city": "Berlin"}',
                mapping.GCP_TOOL_RESPONSE: '{"temp": 20}',
            }
        )
        assert [name for name, _ in events] == ["ai.tool.input", "ai.tool.output"]
        assert json.loads(events[0][1][AIAttributes.TOOL_INPUT_CONTENT]) == {"city": "Berlin"}
        assert json.loads(events[1][1][AIAttributes.TOOL_OUTPUT_CONTENT]) == {"temp": 20}

    @pytest.mark.parametrize(
        "args,result",
        [
            ("N/A", "<not serializable>"),  # ADK's merged-tool-call span
            ("{}", "{}"),  # content capture off
            ("{}", '{"result": "<not specified>"}'),  # unreadable function response
        ],
    )
    def test_adk_sentinel_values_never_render_as_tool_io(self, args, result):
        events = mapping.synthesize_tool_io_events(
            {mapping.GCP_TOOL_CALL_ARGS: args, mapping.GCP_TOOL_RESPONSE: result}
        )
        assert events == []


class TestLowValueSpans:
    @pytest.mark.parametrize(
        "name",
        [
            "execute_tool (merged)",
            "send_data",
            "compact_events token_threshold",
            "handle_context_caching",
            "create_cache",
        ],
    )
    def test_infrastructure_spans_are_low_value(self, name):
        assert mapping.is_low_value_span(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "invocation",
            "invoke_agent bot",
            "call_llm",
            "execute_tool get_weather",
            # Wraps a real agent interaction and can parent spans we care about.
            "managed_agent_interaction",
        ],
    )
    def test_meaningful_spans_are_kept(self, name):
        assert mapping.is_low_value_span(name) is False

    def test_verbose_env_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv(translator.VERBOSE_SPANS_ENV, raising=False)
        assert verbose_spans_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "ON"])
    def test_verbose_env_opt_in(self, monkeypatch, value):
        monkeypatch.setenv(translator.VERBOSE_SPANS_ENV, value)
        assert verbose_spans_enabled() is True


# ---------------------------------------------------------------------------
# Real ADK runs
# ---------------------------------------------------------------------------


class TestSingleAgentRun:
    @pytest.mark.asyncio
    async def test_agent_model_and_tool_spans(self, captured_spans):
        script(tool_call("get_weather", {"city": "Berlin"}), text("It is 20C in Berlin."))
        agent = Agent(
            name="root_agent", model=CannedLlm(), instruction="You help.", tools=[get_weather]
        )
        await run_agent(agent)

        emitted = names(captured_spans)
        assert "ai.agent.invoke" in emitted
        assert emitted.count("ai.llm.invoke") == 2
        assert "ai.tool.invoke" in emitted

    @pytest.mark.asyncio
    async def test_every_emitted_name_is_accepted_by_the_backend(self, captured_spans):
        script(tool_call("get_weather", {"city": "Berlin"}), text("Done."))
        agent = Agent(
            name="root_agent", model=CannedLlm(), instruction="You help.", tools=[get_weather]
        )
        await run_agent(agent)

        offenders = [name for name in names(captured_spans) if not validate_span_name(name)]
        assert offenders == []

    @pytest.mark.asyncio
    async def test_agent_span_carries_its_name(self, captured_spans):
        script(text("Hello."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

        agent_spans = spans_named(captured_spans, "ai.agent.invoke")
        assert [s.attributes[AIAttributes.AGENT_NAME] for s in agent_spans] == ["greeter"]

    @pytest.mark.asyncio
    async def test_llm_span_carries_model_provider_and_tokens(self, captured_spans):
        script(text("Hello."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

        llm_span = spans_named(captured_spans, "ai.llm.invoke")[0]
        attributes = llm_span.attributes
        assert attributes[AIAttributes.MODEL_NAME] == "gemini-3.1-flash-lite"
        assert attributes[AIAttributes.MODEL_PROVIDER] == "gemini"
        assert attributes[AIAttributes.LLM_TOKENS_INPUT] == 11
        assert attributes[AIAttributes.LLM_TOKENS_OUTPUT] == 9
        assert attributes[AIAttributes.LLM_TOKENS_TOTAL] == 24
        assert attributes[AIAttributes.LLM_FINISH_REASON] == ("stop",)

    @pytest.mark.asyncio
    async def test_prompts_and_completions_carry_real_text(self, captured_spans):
        script(text("It is 20C in Berlin."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="You help."))

        llm_span = spans_named(captured_spans, "ai.llm.invoke")[0]
        prompts = event_bodies(llm_span, "ai.prompt")
        completions = event_bodies(llm_span, "ai.completion")
        assert any("You help." in p for p in prompts)
        assert any("What is the weather in Berlin?" in p for p in prompts)
        assert completions == ["It is 20C in Berlin."]

    @pytest.mark.asyncio
    async def test_tool_span_carries_io_events(self, captured_spans):
        script(tool_call("get_weather", {"city": "Berlin"}), text("Done."))
        agent = Agent(
            name="root_agent", model=CannedLlm(), instruction="You help.", tools=[get_weather]
        )
        await run_agent(agent)

        tool_span = spans_named(captured_spans, "ai.tool.invoke")[0]
        assert tool_span.attributes[AIAttributes.TOOL_NAME] == "get_weather"
        assert json.loads(event_bodies(tool_span, "ai.tool.input")[0]) == {"city": "Berlin"}
        assert json.loads(event_bodies(tool_span, "ai.tool.output")[0]) == {
            "temp": 20,
            "city": "Berlin",
        }


class TestDuplicateModelSpan:
    """ADK emits ``call_llm`` wrapping ``generate_content {model}`` for one call."""

    @pytest.mark.asyncio
    async def test_exactly_one_llm_span_per_model_call(self, captured_spans):
        script(text("Hello."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

        assert names(captured_spans).count("ai.llm.invoke") == 1

    @pytest.mark.asyncio
    async def test_inner_model_span_is_not_forwarded(self, captured_spans):
        script(text("Hello."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

        assert not any("generate_content" in name for name in names(captured_spans)), names(
            captured_spans
        )

    @pytest.mark.asyncio
    async def test_tool_spans_are_reparented_onto_the_surviving_llm_span(self, captured_spans):
        """ADK parents tool spans on the *inner* model span, which we drop."""
        script(tool_call("get_weather", {"city": "Berlin"}), text("Done."))
        agent = Agent(
            name="root_agent", model=CannedLlm(), instruction="You help.", tools=[get_weather]
        )
        await run_agent(agent)

        tool_span = spans_named(captured_spans, "ai.tool.invoke")[0]
        parent = parent_of(captured_spans, tool_span)
        assert parent is not None, "tool span was orphaned by dropping generate_content"
        assert parent.name == "ai.llm.invoke"

    @pytest.mark.asyncio
    async def test_verbose_mode_keeps_the_inner_model_span(self, monkeypatch, session_provider):
        """With the opt-in set, nothing is dropped and nothing is reparented."""
        monkeypatch.setenv(translator.VERBOSE_SPANS_ENV, "1")
        provider, captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        captured.clear()
        try:
            script(text("Hello."))
            await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))
            emitted = names(captured)
            assert "function.google_adk.generate_content" in emitted
            assert all(validate_span_name(name) for name in emitted)
        finally:
            integ.disable()
            captured.clear()

    @pytest.mark.asyncio
    async def test_merged_tool_span_is_dropped(self, captured_spans):
        """ADK's ``execute_tool (merged)`` carries only sentinel values."""
        script(
            parallel_tool_calls("get_weather", {"city": "Berlin"}, {"city": "Paris"}),
            text("Both 20C."),
        )
        agent = Agent(
            name="root_agent", model=CannedLlm(), instruction="You help.", tools=[get_weather]
        )
        await run_agent(agent)

        emitted = names(captured_spans)
        # The two real per-tool spans survive; the merged summary does not.
        assert emitted.count("ai.tool.invoke") == 2
        assert not any("merged" in name for name in emitted)


class TestHandoffs:
    @pytest.mark.asyncio
    async def test_transfer_to_agent_draws_an_edge(self, captured_spans):
        script(
            tool_call("transfer_to_agent", {"agent_name": "specialist"}),
            text("Specialist answer."),
        )
        specialist = Agent(
            name="specialist",
            model=CannedLlm(),
            instruction="Specialist.",
            description="Handles specialist questions",
        )
        root = Agent(
            name="root_agent",
            model=CannedLlm(),
            instruction="Route.",
            description="Router",
            sub_agents=[specialist],
        )
        await run_agent(root)

        handoffs = spans_named(captured_spans, "ai.agent.handoff")
        assert len(handoffs) == 1
        attributes = handoffs[0].attributes
        assert attributes[AIAttributes.AGENT_HANDOFF_FROM] == "root_agent"
        assert attributes[AIAttributes.AGENT_HANDOFF_TO] == "specialist"

    @pytest.mark.asyncio
    async def test_transfer_does_not_also_leave_a_tool_span(self, captured_spans):
        """``transfer_to_agent`` is a delegation primitive, not a domain tool."""
        script(
            tool_call("transfer_to_agent", {"agent_name": "specialist"}),
            text("Specialist answer."),
        )
        specialist = Agent(name="specialist", model=CannedLlm(), instruction="S.", description="S")
        root = Agent(
            name="root_agent",
            model=CannedLlm(),
            instruction="Route.",
            description="Router",
            sub_agents=[specialist],
        )
        await run_agent(root)

        tool_spans = spans_named(captured_spans, "ai.tool.invoke")
        assert [s.attributes.get(AIAttributes.TOOL_NAME) for s in tool_spans] == []

    @pytest.mark.asyncio
    async def test_agent_tool_delegation_draws_an_edge(self, captured_spans):
        script(
            tool_call("specialist", {"request": "look into it"}),
            text("Sub answer."),
            text("Final answer."),
        )
        specialist = Agent(
            name="specialist",
            model=CannedLlm(),
            instruction="Specialist.",
            description="Handles specialist questions",
        )
        root = Agent(
            name="root_agent",
            model=CannedLlm(),
            instruction="Use tools.",
            tools=[AgentTool(agent=specialist)],
        )
        await run_agent(root)

        handoffs = spans_named(captured_spans, "ai.agent.handoff")
        assert len(handoffs) == 1, names(captured_spans)
        attributes = handoffs[0].attributes
        assert attributes[AIAttributes.AGENT_HANDOFF_FROM] == "root_agent"
        assert attributes[AIAttributes.AGENT_HANDOFF_TO] == "specialist"
        # An AgentTool call is genuinely both a tool call and a delegation.
        assert "ai.tool.invoke" in names(captured_spans)

    @pytest.mark.asyncio
    async def test_single_agent_run_draws_no_edges(self, captured_spans):
        """The root agent must not resolve itself as its own caller."""
        script(text("Hello."))
        await run_agent(Agent(name="lonely", model=CannedLlm(), instruction="Greet."))

        assert spans_named(captured_spans, "ai.agent.handoff") == []

    @pytest.mark.asyncio
    async def test_transfer_without_content_capture_stays_a_tool_span(
        self, monkeypatch, session_provider
    ):
        """The transfer target lives in the tool args; with no args, no edge."""
        monkeypatch.setenv("RHESIS_DISABLE_CONTENT_CAPTURE", "1")
        provider, captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        captured.clear()
        try:
            script(
                tool_call("transfer_to_agent", {"agent_name": "specialist"}),
                text("Specialist answer."),
            )
            specialist = Agent(
                name="specialist", model=CannedLlm(), instruction="S.", description="S"
            )
            root = Agent(
                name="root_agent",
                model=CannedLlm(),
                instruction="Route.",
                description="Router",
                sub_agents=[specialist],
            )
            await run_agent(root)

            assert spans_named(captured, "ai.agent.handoff") == []
            assert "ai.tool.invoke" in names(captured)
            assert all(validate_span_name(name) for name in names(captured))
        finally:
            integ.disable()
            captured.clear()


class TestWorkflowAgents:
    @pytest.mark.asyncio
    async def test_sequential_agent_nests_its_steps(self, captured_spans):
        script(text("step one"), text("step two"))
        pipeline = SequentialAgent(
            name="pipeline",
            sub_agents=[
                Agent(name="step_a", model=CannedLlm(), instruction="A"),
                Agent(name="step_b", model=CannedLlm(), instruction="B"),
            ],
        )
        await run_agent(pipeline)

        agents = [
            s.attributes[AIAttributes.AGENT_NAME]
            for s in spans_named(captured_spans, "ai.agent.invoke")
        ]
        assert set(agents) == {"pipeline", "step_a", "step_b"}
        assert all(validate_span_name(name) for name in names(captured_spans))

    @pytest.mark.asyncio
    async def test_sequential_steps_draw_orchestrator_edges(self, captured_spans):
        """Step spans nest under the orchestrator's own ``invoke_agent`` span."""
        script(text("step one"), text("step two"))
        pipeline = SequentialAgent(
            name="pipeline",
            sub_agents=[
                Agent(name="step_a", model=CannedLlm(), instruction="A"),
                Agent(name="step_b", model=CannedLlm(), instruction="B"),
            ],
        )
        await run_agent(pipeline)

        edges = {
            (
                s.attributes[AIAttributes.AGENT_HANDOFF_FROM],
                s.attributes[AIAttributes.AGENT_HANDOFF_TO],
            )
            for s in spans_named(captured_spans, "ai.agent.handoff")
        }
        assert edges == {("pipeline", "step_a"), ("pipeline", "step_b")}

    @pytest.mark.asyncio
    async def test_parallel_agent_is_safe_under_concurrency(self, captured_spans):
        script(text("p one"), text("p two"))
        fanout = ParallelAgent(
            name="fanout",
            sub_agents=[
                Agent(name="par_a", model=CannedLlm(), instruction="A"),
                Agent(name="par_b", model=CannedLlm(), instruction="B"),
            ],
        )
        await run_agent(fanout)

        agents = {
            s.attributes[AIAttributes.AGENT_NAME]
            for s in spans_named(captured_spans, "ai.agent.invoke")
        }
        assert {"fanout", "par_a", "par_b"} <= agents
        assert all(validate_span_name(name) for name in names(captured_spans))


class TestSchemaVersions:
    """The v1 root is ``invocation``; the v2 root is ``invoke_workflow {name}``."""

    @pytest.mark.asyncio
    async def test_schema_v1_root(self, monkeypatch, session_provider):
        monkeypatch.setenv("ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN", "1")
        emitted = await self._run_and_collect(session_provider)
        assert "function.google_adk.invocation" in emitted

    @pytest.mark.asyncio
    async def test_schema_v2_root(self, monkeypatch, session_provider):
        monkeypatch.setenv("ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN", "2")
        emitted = await self._run_and_collect(session_provider)
        assert "function.google_adk.workflow.greeter" in emitted
        assert "function.google_adk.invocation" not in emitted

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["1", "2"])
    async def test_both_schemas_translate_the_same_agent_and_model_spans(
        self, monkeypatch, session_provider, version
    ):
        monkeypatch.setenv("ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN", version)
        emitted = await self._run_and_collect(session_provider)
        assert "ai.agent.invoke" in emitted
        assert "ai.llm.invoke" in emitted
        assert all(validate_span_name(name) for name in emitted)

    @staticmethod
    async def _run_and_collect(session_provider) -> list[str]:
        _provider, captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        captured.clear()
        try:
            script(text("Hello."))
            await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))
            return names(captured)
        finally:
            integ.disable()
            captured.clear()


class TestConversationTurnRoot:
    @pytest.mark.asyncio
    async def test_trace_root_is_stamped_with_conversation_attributes(self, captured_spans):
        set_conversation_id("conv-42")
        script(text("It is 20C in Berlin."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

        roots = root_spans(captured_spans)
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes[ConversationContext.SpanAttributes.IS_TURN_ROOT] is True
        assert attributes[ConversationContext.SpanAttributes.CONVERSATION_ID] == "conv-42"
        assert (
            attributes[ConversationContext.SpanAttributes.CONVERSATION_INPUT]
            == "What is the weather in Berlin?"
        )
        assert (
            attributes[ConversationContext.SpanAttributes.CONVERSATION_OUTPUT]
            == "It is 20C in Berlin."
        )

    @pytest.mark.asyncio
    async def test_without_a_conversation_id_the_adk_session_id_is_used(self, captured_spans):
        """An app reusing one ADK session across turns gets grouping for free."""
        script(text("Hi."))
        await run_agent(
            Agent(name="greeter", model=CannedLlm(), instruction="Greet."),
            session_id="adk-session-9",
        )

        attributes = root_spans(captured_spans)[0].attributes
        assert attributes[ConversationContext.SpanAttributes.CONVERSATION_ID] == "adk-session-9"

    @pytest.mark.asyncio
    async def test_nested_under_an_enclosing_span_is_not_stamped(
        self, captured_spans, session_provider
    ):
        """A Rhesis ``@endpoint`` / ``@observe`` parent owns turn-root semantics."""
        provider, _captured = session_provider
        set_conversation_id("conv-42")
        script(text("Hi."))

        tracer = provider.get_tracer("rhesis.sdk")
        with tracer.start_as_current_span("ai.agent.invoke"):
            await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

        adk_roots = [
            s
            for s in captured_spans.get_finished_spans()
            if s.name.startswith("function.google_adk.")
        ]
        assert adk_roots, "expected the ADK run root to still be exported"
        for span in adk_roots:
            assert ConversationContext.SpanAttributes.IS_TURN_ROOT not in (span.attributes or {})

    @pytest.mark.asyncio
    async def test_agent_tool_subagent_does_not_hijack_the_conversation(self, captured_spans):
        """The sub-agent's model span *ends first*, so first-wins would be wrong."""
        set_conversation_id("conv-7")
        script(
            tool_call("specialist", {"request": "look into it"}),
            text("Sub answer."),
            text("Final answer."),
        )
        specialist = Agent(
            name="specialist", model=CannedLlm(), instruction="Specialist.", description="S"
        )
        root = Agent(
            name="root_agent",
            model=CannedLlm(),
            instruction="Use tools.",
            tools=[AgentTool(agent=specialist)],
        )
        await run_agent(root)

        attributes = root_spans(captured_spans)[0].attributes
        assert (
            attributes[ConversationContext.SpanAttributes.CONVERSATION_INPUT]
            == "What is the weather in Berlin?"
        )
        assert attributes[ConversationContext.SpanAttributes.CONVERSATION_OUTPUT] == "Final answer."

    @pytest.mark.asyncio
    async def test_nested_agent_tool_root_is_not_a_turn_root(self, captured_spans):
        """``AgentTool`` spins its own ``Runner``, emitting a second run root."""
        script(
            tool_call("specialist", {"request": "look into it"}),
            text("Sub answer."),
            text("Final answer."),
        )
        specialist = Agent(
            name="specialist", model=CannedLlm(), instruction="Specialist.", description="S"
        )
        root = Agent(
            name="root_agent",
            model=CannedLlm(),
            instruction="Use tools.",
            tools=[AgentTool(agent=specialist)],
        )
        await run_agent(root)

        run_roots = [
            s
            for s in captured_spans.get_finished_spans()
            if s.name.startswith("function.google_adk.")
        ]
        assert len(run_roots) == 2, [s.name for s in run_roots]
        stamped = [
            s
            for s in run_roots
            if (s.attributes or {}).get(ConversationContext.SpanAttributes.IS_TURN_ROOT)
        ]
        assert len(stamped) == 1
        assert stamped[0].parent is None


class TestContentCaptureOptOut:
    @pytest.mark.asyncio
    async def test_no_content_events_when_disabled(self, monkeypatch, session_provider):
        monkeypatch.setenv("RHESIS_DISABLE_CONTENT_CAPTURE", "1")
        _provider, captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        captured.clear()
        try:
            script(tool_call("get_weather", {"city": "Berlin"}), text("It is 20C."))
            agent = Agent(
                name="root_agent", model=CannedLlm(), instruction="Secret.", tools=[get_weather]
            )
            await run_agent(agent)

            everything = json.dumps(
                [
                    {
                        "name": s.name,
                        "attributes": {k: str(v) for k, v in (s.attributes or {}).items()},
                        "events": [
                            {
                                "name": e.name,
                                "attributes": {k: str(v) for k, v in (e.attributes or {}).items()},
                            }
                            for e in s.events
                        ],
                    }
                    for s in captured.get_finished_spans()
                ]
            )
            assert "What is the weather in Berlin?" not in everything
            assert "It is 20C." not in everything
            assert "Secret." not in everything
            # Structure and metrics survive; only content is withheld.
            assert "ai.llm.invoke" in names(captured)
            assert "ai.tool.invoke" in names(captured)
        finally:
            integ.disable()
            captured.clear()

    def test_disabled_capture_sets_adks_three_knobs(self, monkeypatch, session_provider):
        monkeypatch.setenv("RHESIS_DISABLE_CONTENT_CAPTURE", "1")
        monkeypatch.delenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", raising=False)
        monkeypatch.delenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", raising=False)
        monkeypatch.delenv("ADK_TELEMETRY_IGNORE_RUN_CONFIG", raising=False)
        import os

        integ = GoogleADKIntegration()
        assert integ.enable() is True
        try:
            assert os.environ["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] == "false"
            assert os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "NO_CONTENT"
            # The admin lock is what stops a per-request RunConfig.telemetry
            # from putting prompts back on the spans.
            assert os.environ["ADK_TELEMETRY_IGNORE_RUN_CONFIG"] == "1"
        finally:
            integ.disable()
        assert "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS" not in os.environ
        assert "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT" not in os.environ
        assert "ADK_TELEMETRY_IGNORE_RUN_CONFIG" not in os.environ

    def test_enabled_capture_touches_no_env_vars(self, monkeypatch, session_provider):
        """In particular never OTEL_SEMCONV_STABILITY_OPT_IN, a global OTel switch."""
        monkeypatch.delenv("RHESIS_DISABLE_CONTENT_CAPTURE", raising=False)
        monkeypatch.delenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", raising=False)
        monkeypatch.delenv("OTEL_SEMCONV_STABILITY_OPT_IN", raising=False)
        import os

        integ = GoogleADKIntegration()
        assert integ.enable() is True
        try:
            assert "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS" not in os.environ
            assert "OTEL_SEMCONV_STABILITY_OPT_IN" not in os.environ
            assert "ADK_TELEMETRY_IGNORE_RUN_CONFIG" not in os.environ
        finally:
            integ.disable()


class TestExperimentalSemconv:
    """ADK emits the standard ``gen_ai.*.messages`` only under an opt-in."""

    @pytest.mark.asyncio
    async def test_semconv_messages_survive_the_dropped_model_span(
        self, monkeypatch, session_provider
    ):
        monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
        monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")
        # Legacy blobs off, so the content can *only* come from the semconv
        # attributes on the generate_content span we drop.
        monkeypatch.setenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")
        _provider, captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        captured.clear()
        try:
            script(text("Semconv answer."))
            await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))

            llm_spans = spans_named(captured, "ai.llm.invoke")
            assert len(llm_spans) == 1
            completions = event_bodies(llm_spans[0], "ai.completion")
            assert completions == ["Semconv answer."]
            prompts = event_bodies(llm_spans[0], "ai.prompt")
            assert any("What is the weather in Berlin?" in p for p in prompts)
        finally:
            integ.disable()
            captured.clear()

    def test_carrier_only_keeps_message_attributes(self):
        carrier = mapping.semconv_message_carrier(
            {
                mapping.GEN_AI_INPUT_MESSAGES: "[]",
                "gen_ai.output.messages": '[{"role": "assistant", "parts": []}]',
                "gen_ai.request.model": "should-not-be-copied",
            }
        )
        assert "gen_ai.request.model" not in carrier
        assert carrier[mapping.GEN_AI_OPERATION_NAME] == mapping.OP_GENERATE_CONTENT


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class _NotAProvider:
    """Stands in for a non-Rhesis (e.g. proxy / no-op) tracer provider."""

    def get_tracer(self, *args, **kwargs):  # pragma: no cover - never called
        raise AssertionError("should not be used")


class _RecordingExporter(SpanExporter):
    def __init__(self) -> None:
        self.batches: list[Any] = []

    def export(self, spans):
        self.batches.append(list(spans))
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


class TestLifecycle:
    def test_singleton_is_stable(self):
        from rhesis.sdk.telemetry.integrations.google_adk import get_integration

        assert get_integration() is get_integration()

    def test_framework_name(self):
        assert GoogleADKIntegration().framework_name == "google_adk"

    def test_is_installed(self):
        assert GoogleADKIntegration().is_installed() is True

    def test_enable_is_idempotent(self, session_provider):
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        try:
            assert integ.enable() is True
            assert integ.enabled is True
        finally:
            integ.disable()

    def test_enable_wraps_the_exporter(self, session_provider):
        provider, _captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        try:
            children = provider._active_span_processor._span_processors
            wrapped = [
                child
                for child in children
                if isinstance(
                    translator.__dict__["GoogleADKTranslatingExporter"],
                    type,
                )
                and isinstance(getattr(child, "span_exporter", None), GoogleADKTranslatingExporter)
            ]
            assert wrapped, "no processor ended up with a translating exporter"
        finally:
            integ.disable()

    def test_disable_reverts_the_exporter(self, session_provider):
        provider, _captured = session_provider
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        integ.disable()
        for child in provider._active_span_processor._span_processors:
            exporter = getattr(child, "span_exporter", None)
            assert not isinstance(exporter, GoogleADKTranslatingExporter)

    def test_enable_returns_false_when_the_provider_is_not_rhesis(self, monkeypatch):
        """Fail loudly: ADK cannot be turned off, so untranslated spans would 422."""
        # Patched on the otel module object rather than by dotted path: the
        # ``rhesis.sdk.telemetry.integrations`` package binds the name
        # ``google_adk`` to the integration *singleton*, so a dotted target
        # resolves to that object instead of the submodule.
        monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: _NotAProvider())
        integ = GoogleADKIntegration()
        assert integ.enable() is False
        assert integ.enabled is False

    def test_enable_returns_false_without_a_wrappable_exporter(self, monkeypatch):
        """A provider with no batch/simple processor cannot be translated."""
        empty = TracerProvider()
        monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: empty)
        integ = GoogleADKIntegration()
        assert integ.enable() is False

    def test_enable_returns_false_when_not_installed(self, monkeypatch, session_provider):
        integ = GoogleADKIntegration()
        monkeypatch.setattr(integ, "is_installed", lambda: False)
        assert integ.enable() is False

    def test_callback_is_the_span_processor(self, session_provider):
        integ = GoogleADKIntegration()
        assert integ.enable() is True
        try:
            assert isinstance(integ.callback(), GoogleADKLLMDedupSpanProcessor)
        finally:
            integ.disable()

    def test_registered_under_both_its_name_and_alias(self):
        from rhesis.sdk.telemetry.integrations import get_all_integrations

        available = get_all_integrations()
        assert "google_adk" in available
        assert "adk" in available
        # The alias must be the *same instance*: auto_instrument dedupes by id().
        assert available["adk"] is available["google_adk"]
        assert available["google_adk"].framework_name == "google_adk"


class TestTranslationFallback:
    def test_translation_failure_falls_back_to_a_valid_name(self, monkeypatch):
        """A raw ADK name would be rejected by the backend, so never forward one."""

        def boom(*args, **kwargs):
            raise RuntimeError("translation exploded")

        monkeypatch.setattr(translator, "translate_span", boom)

        recording = _RecordingExporter()
        exporter = GoogleADKTranslatingExporter(recording)

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer(mapping.INSTRUMENTATION_SCOPE)
        with tracer.start_as_current_span("invoke_agent boom") as span:
            span.set_attribute(mapping.GEN_AI_OPERATION_NAME, "invoke_agent")
        provider.force_flush()

        forwarded = [s for batch in recording.batches for s in batch]
        assert forwarded, "the span must still be forwarded"
        assert all(validate_span_name(s.name) for s in forwarded)
        assert forwarded[0].name.startswith("function.google_adk.")
        assert forwarded[0].attributes[mapping.ORIGINAL_SPAN_NAME] == "invoke_agent boom"

    def test_non_adk_spans_pass_through_untouched(self):
        recording = _RecordingExporter()
        exporter = GoogleADKTranslatingExporter(recording)

        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("some.other.library")
        with tracer.start_as_current_span("ai.llm.invoke"):
            pass
        provider.force_flush()

        forwarded = [s for batch in recording.batches for s in batch]
        assert [s.name for s in forwarded] == ["ai.llm.invoke"]
        assert not isinstance(forwarded[0], translator.TranslatedSpan)

    def test_exporter_shutdown_and_flush_swallow_errors(self):
        class Exploding(SpanExporter):
            def export(self, spans):  # pragma: no cover - not exercised
                return SpanExportResult.SUCCESS

            def shutdown(self):
                raise RuntimeError("nope")

            def force_flush(self, timeout_millis=30_000):
                raise RuntimeError("nope")

        exporter = GoogleADKTranslatingExporter(Exploding())
        exporter.shutdown()
        assert exporter.force_flush() is False


class TestDedupProcessor:
    def test_inactive_until_activated(self):
        processor = GoogleADKLLMDedupSpanProcessor()
        # Hooks on an inactive processor must be inert, not raise.
        processor.on_start(object())
        processor.on_end(object())  # type: ignore[arg-type]
        assert processor.force_flush() is True
        assert processor.shutdown() is None

    @pytest.mark.asyncio
    async def test_llm_flag_is_restored_after_a_run(self, captured_spans):
        from rhesis.telemetry.context import is_llm_observation_active

        assert is_llm_observation_active() is False
        script(text("Hi."))
        await run_agent(Agent(name="greeter", model=CannedLlm(), instruction="Greet."))
        assert is_llm_observation_active() is False

    def test_deactivate_clears_state(self):
        processor = GoogleADKLLMDedupSpanProcessor()
        processor.activate()
        processor._prev_flags[123] = True
        processor.deactivate()
        assert processor._prev_flags == {}


class TestPureTranslateSpan:
    def test_translate_span_is_usable_without_an_exporter(self):
        provider = TracerProvider()
        tracer = provider.get_tracer(mapping.INSTRUMENTATION_SCOPE)
        with tracer.start_as_current_span("call_llm") as span:
            for key, value in CALL_LLM_ATTRIBUTES.items():
                span.set_attribute(key, value)
        readable = span  # the ended span is readable

        translated = translate_span(readable)
        assert translated.name == AIOperationType.LLM_INVOKE.value
        assert translated.attributes[AIAttributes.MODEL_PROVIDER] == "gemini"
        assert [e.name for e in translated.events].count("ai.prompt") == 4
        assert [e.name for e in translated.events].count("ai.completion") == 1
        # Delegation to the original span still works for everything else.
        assert translated.kind == readable.kind
        assert translated.context is readable.context
