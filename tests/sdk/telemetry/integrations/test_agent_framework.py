"""Real-MAF integration tests for the Microsoft Agent Framework integration.

This file uses the **real** ``agent_framework`` package end-to-end. Every
``Agent``, chat client, ``@tool`` function, and ``HandoffBuilder`` workflow
is the real MAF class — there are no fakes and no
``monkeypatch.setitem(sys.modules, ...)`` calls. The
:class:`DeterministicChatClient` defined below subclasses MAF's real
:class:`agent_framework.BaseChatClient` (with the same telemetry +
function-invocation layers ``OpenAIChatClient`` uses) and serves canned
responses, which is *using* MAF, not faking it — it's the same shape as
``langchain.llms.fake.FakeListLLM``.

Tests are gated on ``pytest.importorskip("agent_framework")`` so they skip
gracefully when the optional ``agent-framework`` extra isn't installed.
"""

from __future__ import annotations

import pytest

# Import-skip the entire module when MAF is not installed.
agent_framework = pytest.importorskip("agent_framework")

from collections.abc import Mapping, Sequence  # noqa: E402
from typing import Any  # noqa: E402

from agent_framework import (  # noqa: E402
    Agent,
    BaseChatClient,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    Message,
    tool,
)
from agent_framework._middleware import ChatMiddlewareLayer  # noqa: E402
from agent_framework._tools import FunctionInvocationLayer  # noqa: E402
from agent_framework._types import ResponseStream  # noqa: E402
from agent_framework.observability import (  # noqa: E402
    OBSERVABILITY_SETTINGS,
    ChatTelemetryLayer,
    enable_instrumentation,
)
from opentelemetry import trace as otel_trace  # noqa: E402
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from rhesis.telemetry.attributes import AIAttributes, validate_span_name  # noqa: E402
from rhesis.telemetry.constants import ConversationContext  # noqa: E402
from rhesis.telemetry.context import (  # noqa: E402
    is_llm_observation_active,
    set_conversation_id,
    set_conversation_trace_id,
    set_llm_observation_active,
    set_root_trace_id,
)
from rhesis.telemetry.conversation import conversation_turn  # noqa: E402

from rhesis.sdk.telemetry.integrations.agent_framework import (  # noqa: E402
    MAFIntegration,
    MAFLLMDedupSpanProcessor,
    MAFTranslatingExporter,
    get_integration,
    mapping,
    translate_span,
)

# ---------------------------------------------------------------------------
# Deterministic real-MAF chat client
# ---------------------------------------------------------------------------


class DeterministicChatClient(
    FunctionInvocationLayer,
    ChatMiddlewareLayer,
    ChatTelemetryLayer,
    BaseChatClient,
):
    """Real MAF chat client whose responses are pre-programmed.

    Composes the same layers as :class:`agent_framework.openai.OpenAIChatClient`
    (function invocation + middleware + telemetry on top of ``BaseChatClient``)
    so MAF's :class:`ChatTelemetryLayer` emits real ``chat <model>`` spans
    when ``enable_instrumentation()`` has flipped its flag. The ``responses``
    list is consumed in order; once exhausted, the last response is repeated
    so a tool-followup turn still gets a final answer.
    """

    OTEL_PROVIDER_NAME = "deterministic-test"

    def __init__(
        self,
        responses: Sequence[ChatResponse],
        *,
        model: str = "test-model-1",
    ) -> None:
        super().__init__(otel_provider_name="deterministic-test")
        self.model = model
        self._responses: list[ChatResponse] = list(responses)
        self._index = 0
        self.call_count = 0
        self.calls: list[list[Message]] = []

    def _next_response(self, messages: Sequence[Message]) -> ChatResponse:
        self.calls.append(list(messages))
        self.call_count += 1
        idx = min(self._index, len(self._responses) - 1)
        self._index += 1
        response = self._responses[idx]
        if response.model is None:
            response.model = self.model
        return response

    def _inner_get_response(  # type: ignore[override]
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ):
        # MAF's :class:`BaseChatClient.get_response` *short-circuits* (returns
        # the raw ``_inner_get_response`` value untouched) when no compaction
        # strategy is configured — so this method MUST return the right type
        # synchronously: an ``Awaitable[ChatResponse]`` (i.e. a coroutine) for
        # ``stream=False``, a :class:`ResponseStream` for ``stream=True``.
        # Defining this method as ``async def`` would yield a coroutine for
        # both, breaking the streaming path with
        # ``'coroutine' object has no attribute 'with_cleanup_hook'``.
        if stream:
            response = self._next_response(messages)

            async def _stream_updates():
                msgs = response.messages or []
                for msg_idx, msg in enumerate(msgs):
                    is_last = msg_idx == len(msgs) - 1
                    update_contents = list(msg.contents or [])
                    if is_last and response.usage_details:
                        update_contents.append(
                            Content("usage", usage_details=response.usage_details)
                        )
                    yield ChatResponseUpdate(
                        role=msg.role,
                        contents=update_contents,
                        finish_reason=response.finish_reason if is_last else None,
                        model=response.model,
                    )

            return ResponseStream(
                _stream_updates(),
                finalizer=lambda updates: ChatResponse.from_updates(updates),
            )

        async def _get() -> ChatResponse:
            await self._validate_options(options)
            return self._next_response(messages)

        return _get()

    def service_url(self) -> str:  # noqa: D401
        return "http://test.invalid"


def _text_response(
    text: str,
    *,
    model: str | None = None,
    response_model: str | None = None,
    finish_reason: str = "stop",
    input_tokens: int = 7,
    output_tokens: int = 11,
) -> ChatResponse:
    """Build a one-message text :class:`ChatResponse` with realistic usage."""
    msg = Message(role="assistant", contents=[Content.from_text(text=text)])
    return ChatResponse(
        messages=[msg],
        model=response_model or model,
        finish_reason=finish_reason,
        usage_details={
            "input_token_count": input_tokens,
            "output_token_count": output_tokens,
            "total_token_count": input_tokens + output_tokens,
        },
    )


def _function_call_response(
    *,
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    model: str | None = None,
    input_tokens: int = 5,
    output_tokens: int = 3,
) -> ChatResponse:
    """Build a :class:`ChatResponse` whose only message is a function-call."""
    msg = Message(
        role="assistant",
        contents=[Content.from_function_call(call_id=call_id, name=name, arguments=arguments)],
    )
    return ChatResponse(
        messages=[msg],
        model=model,
        finish_reason="tool_calls",
        usage_details={
            "input_token_count": input_tokens,
            "output_token_count": output_tokens,
            "total_token_count": input_tokens + output_tokens,
        },
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def session_provider() -> tuple[TracerProvider, InMemorySpanExporter, BatchSpanProcessor]:
    """A real ``TracerProvider`` plus in-memory exporter for the test session.

    OTEL's :func:`opentelemetry.trace.set_tracer_provider` only honors the
    first call per process; if some earlier test or import has already
    installed a provider, our second ``set_tracer_provider`` call is a no-op
    (warns) and our spans land elsewhere. To stay robust we ride on whatever
    provider is already global when it's already a real
    :class:`opentelemetry.sdk.trace.TracerProvider`, and fall back to
    installing our own otherwise. Either way we attach a
    :class:`BatchSpanProcessor` whose exporter is the in-memory capture used
    by the assertions in this module.
    """
    captured = InMemorySpanExporter()
    existing = otel_trace.get_tracer_provider()
    if isinstance(existing, TracerProvider):
        provider: TracerProvider = existing
    else:
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    bsp = BatchSpanProcessor(captured)
    provider.add_span_processor(bsp)
    return provider, captured, bsp


@pytest.fixture
def captured_spans(session_provider, integration) -> InMemorySpanExporter:
    """Yield the in-memory exporter, drained at the end of each test."""
    _provider, captured, _bsp = session_provider
    yield captured
    captured.clear()


@pytest.fixture
def integration(session_provider) -> MAFIntegration:
    """Yield a fresh :class:`MAFIntegration` enabled against the session provider.

    The integration is enabled on entry and disabled on teardown so tests
    don't inherit each other's state. ``enable()`` is idempotent against
    already-wrapped exporters, so reusing the session provider is safe.
    """
    integ = MAFIntegration()
    assert integ.enable() is True, "MAFIntegration.enable() must succeed"
    try:
        yield integ
    finally:
        integ.disable()


@pytest.fixture
def reset_observability_settings():
    """Restore ``OBSERVABILITY_SETTINGS`` to its pre-test state.

    ``enable_instrumentation()`` flips the global flag; this fixture saves
    and restores it so tests cannot bleed into each other when MAF's chat
    span emission is keyed off it.
    """
    saved = (
        OBSERVABILITY_SETTINGS.enable_instrumentation,
        OBSERVABILITY_SETTINGS.enable_sensitive_data,
    )
    yield
    (
        OBSERVABILITY_SETTINGS.enable_instrumentation,
        OBSERVABILITY_SETTINGS.enable_sensitive_data,
    ) = saved


@pytest.fixture
def reset_llm_observation_flag():
    """Always exit a test with the LLM-observation flag cleared."""
    yield
    set_llm_observation_active(False)


@pytest.fixture(autouse=True)
def reset_conversation_context():
    """Keep the conversation contextvars from leaking between tests."""
    yield
    set_conversation_id(None)
    set_conversation_trace_id(None)
    set_root_trace_id(None)


def _drain_spans(provider: TracerProvider, exporter: InMemorySpanExporter):
    """Force a flush so all pending spans hit the in-memory exporter."""
    provider.force_flush()
    return list(exporter.get_finished_spans())


# ---------------------------------------------------------------------------
# Mapping / translator unit-style coverage (still uses real MAF span types)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_name, attrs, expected",
    [
        ("chat gpt-4", {mapping.GEN_AI_OPERATION_NAME: "chat"}, "ai.llm.invoke"),
        (
            "invoke_agent assistant",
            {mapping.GEN_AI_OPERATION_NAME: "invoke_agent"},
            "ai.agent.invoke",
        ),
        (
            "create_agent assistant",
            {mapping.GEN_AI_OPERATION_NAME: "create_agent"},
            "ai.agent.invoke",
        ),
        (
            "execute_tool calculator",
            {mapping.GEN_AI_OPERATION_NAME: "execute_tool"},
            "ai.tool.invoke",
        ),
        (
            "embeddings text-embedding-3-small",
            {mapping.GEN_AI_OPERATION_NAME: "embeddings"},
            "ai.embedding.generate",
        ),
        # No attribute -> fuzzy parse from the name.
        ("chat gpt-4o", {}, "ai.llm.invoke"),
        ("invoke_agent foo", {}, "ai.agent.invoke"),
        # Workflow span prefixes.
        ("workflow.run", {}, "function.workflow.run"),
        ("workflow.build", {}, "function.workflow.build"),
        ("executor.process", {}, "function.workflow.executor.process"),
        ("edge_group.process", {}, "function.workflow.edge_group.process"),
        ("message.send", {}, "function.workflow.message.send"),
    ],
)
def test_translate_span_name(raw_name, attrs, expected):
    assert mapping.translate_span_name(raw_name, attrs) == expected


def test_translate_span_name_unknown_lands_in_function_maf():
    """Unknown ops must always land in ``function.maf.*`` so they pass validation."""
    out = mapping.translate_span_name("brand_new_op some_target", {})
    assert out.startswith("function.maf.")
    assert " " not in out
    assert validate_span_name(out)


def test_translate_span_name_empty_input_falls_back():
    assert mapping.translate_span_name("", {}) == "function.maf.unknown"


def test_translate_span_first_model_wins():
    """``request.model`` wins over ``response.model`` when both are present.

    This is the contract documented in :data:`mapping._DIRECT_ATTR_MAP`.
    Downstream cost / quota analytics expect the *requested* model identity.
    """
    span_attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_REQUEST_MODEL: "gpt-4-mini",
        mapping.GEN_AI_RESPONSE_MODEL: "gpt-4-mini-2024-09-12",
    }
    out = mapping.translate_attributes(span_attrs)
    assert out[AIAttributes.MODEL_NAME] == "gpt-4-mini"


def test_translate_span_response_model_wins_when_request_missing():
    span_attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_RESPONSE_MODEL: "gpt-4-mini-2024-09-12",
    }
    out = mapping.translate_attributes(span_attrs)
    assert out[AIAttributes.MODEL_NAME] == "gpt-4-mini-2024-09-12"


# ---------------------------------------------------------------------------
# synthesize_tool_io_events: JSON encoding of tool I/O payloads
# ---------------------------------------------------------------------------


def test_synthesize_tool_io_events_dict_args_emits_valid_json():
    """``dict`` args must be JSON-encoded, not str()'d (which yields repr)."""
    import json as _json

    events = mapping.synthesize_tool_io_events(
        {
            mapping.GEN_AI_TOOL_CALL_ARGS: {"a": 1, "b": "two"},
            mapping.GEN_AI_TOOL_CALL_RESULT: [1, 2, 3],
        }
    )
    by_name = dict(events)
    in_payload = by_name["ai.tool.input"][AIAttributes.TOOL_INPUT_CONTENT]
    out_payload = by_name["ai.tool.output"][AIAttributes.TOOL_OUTPUT_CONTENT]

    # Must be parseable JSON (str(dict) would produce single-quoted repr that
    # json.loads would reject).
    assert _json.loads(in_payload) == {"a": 1, "b": "two"}
    assert _json.loads(out_payload) == [1, 2, 3]


def test_synthesize_tool_io_events_string_args_pass_through_verbatim():
    """JSON-string args (the OpenAI-compat path) must NOT be double-encoded."""
    pre_encoded = '{"a": 1, "b": "two"}'
    events = mapping.synthesize_tool_io_events(
        {
            mapping.GEN_AI_TOOL_CALL_ARGS: pre_encoded,
            mapping.GEN_AI_TOOL_CALL_RESULT: "plain text result",
        }
    )
    by_name = dict(events)
    assert by_name["ai.tool.input"][AIAttributes.TOOL_INPUT_CONTENT] == pre_encoded
    assert by_name["ai.tool.output"][AIAttributes.TOOL_OUTPUT_CONTENT] == "plain text result"


def test_synthesize_tool_io_events_non_serialisable_falls_back_to_str():
    """``default=str`` must keep us safe for objects ``json.dumps`` rejects.

    A datetime is the canonical example of a value that ``json.dumps`` refuses
    to encode without ``default=``. The event must still be emitted with a
    deterministic string payload so we never drop a trace.
    """
    import datetime as _dt

    when = _dt.datetime(2024, 1, 2, 3, 4, 5)
    events = mapping.synthesize_tool_io_events({mapping.GEN_AI_TOOL_CALL_ARGS: {"when": when}})
    payload = dict(events)["ai.tool.input"][AIAttributes.TOOL_INPUT_CONTENT]
    # ``json.dumps(..., default=str)`` calls ``str()`` on the datetime, which
    # yields the ISO-ish "2024-01-02 03:04:05" form.
    assert "2024-01-02 03:04:05" in payload


def test_synthesize_tool_io_events_skips_missing_attributes():
    """Absent args/result must not produce empty events."""
    assert mapping.synthesize_tool_io_events({}) == []
    only_args = mapping.synthesize_tool_io_events({mapping.GEN_AI_TOOL_CALL_ARGS: {"x": 1}})
    assert [name for name, _ in only_args] == ["ai.tool.input"]


# ---------------------------------------------------------------------------
# extract_handoff_targets_from_messages: chat-output handoff detection
# ---------------------------------------------------------------------------


def _chat_output_attrs(messages: Any) -> dict[str, Any]:
    """Build chat-span attrs with ``gen_ai.output.messages`` as a JSON string.

    MAF serializes output messages as JSON text (see
    ``agent_framework.observability``), so we exercise the string path here.
    """
    import json as _json

    return {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(messages),
    }


def test_extract_handoff_targets_parses_tool_call_parts():
    """A ``handoff_to_<x>`` tool_call part yields the stripped target id."""
    attrs = _chat_output_attrs(
        [
            {
                "role": "assistant",
                "parts": [
                    {"type": "text", "content": "Routing to the specialist."},
                    {
                        "type": "tool_call",
                        "id": "call-1",
                        "name": "handoff_to_destination_finder",
                        "arguments": "{}",
                    },
                ],
            }
        ]
    )
    assert mapping.extract_handoff_targets_from_messages(attrs) == ["destination_finder"]


def test_extract_handoff_targets_accepts_decoded_list():
    """The helper also tolerates an already-decoded list (not just JSON text)."""
    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: [
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "name": "handoff_to_specialist", "arguments": "{}"}
                ],
            }
        ],
    }
    assert mapping.extract_handoff_targets_from_messages(attrs) == ["specialist"]


def test_extract_handoff_targets_ignores_real_tool_calls():
    """Non-handoff tool calls (real domain tools) must be ignored."""
    attrs = _chat_output_attrs(
        [
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "name": "get_random_destination", "arguments": "{}"}
                ],
            }
        ]
    )
    assert mapping.extract_handoff_targets_from_messages(attrs) == []


def test_extract_handoff_targets_skips_non_chat_spans():
    """Only chat spans carry the model's handoff decision."""
    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "invoke_agent",
        mapping.GEN_AI_OUTPUT_MESSAGES: '[{"role": "assistant", "parts": '
        '[{"type": "tool_call", "name": "handoff_to_x"}]}]',
    }
    assert mapping.extract_handoff_targets_from_messages(attrs) == []


def test_extract_handoff_targets_empty_without_output_messages():
    """No output messages (e.g. content capture disabled) -> no targets."""
    assert (
        mapping.extract_handoff_targets_from_messages({mapping.GEN_AI_OPERATION_NAME: "chat"}) == []
    )


# ---------------------------------------------------------------------------
# is_low_value_workflow_span: span-noise classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("edge_group.process SomeEdge", True),
        ("edge_group.process", True),
        ("message.send", True),
        ("message.send Foo", True),
        # workflow.build is a standalone build-time trace with no run payload.
        ("workflow.build", True),
        # Structural spans must be kept.
        ("executor.process coordinator", False),
        ("workflow.run", False),
        ("invoke_agent coordinator", False),
        ("chat gpt-4", False),
        ("execute_tool calc", False),
        (None, False),
        ("", False),
    ],
)
def test_is_low_value_workflow_span(name, expected):
    assert mapping.is_low_value_workflow_span(name) is expected


# ---------------------------------------------------------------------------
# synthesize_message_events: attribute-based GenAI message convention
# ---------------------------------------------------------------------------


def test_synthesize_message_events_builds_prompt_and_completion():
    """System + input messages -> ai.prompt; output -> a single ai.completion."""
    import json as _json

    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_SYSTEM_INSTRUCTIONS: _json.dumps(
            [{"type": "text", "content": "You are helpful."}]
        ),
        mapping.GEN_AI_INPUT_MESSAGES: _json.dumps(
            [{"role": "user", "parts": [{"type": "text", "content": "Hi there"}]}]
        ),
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(
            [{"role": "assistant", "parts": [{"type": "text", "content": "Hello!"}]}]
        ),
    }
    events = mapping.synthesize_message_events(attrs)

    prompts = [a for n, a in events if n == "ai.prompt"]
    completions = [a for n, a in events if n == "ai.completion"]

    assert {p[AIAttributes.PROMPT_ROLE] for p in prompts} == {"system", "user"}
    assert any(p[AIAttributes.PROMPT_CONTENT] == "You are helpful." for p in prompts)
    assert any(p[AIAttributes.PROMPT_CONTENT] == "Hi there" for p in prompts)
    assert len(completions) == 1
    assert completions[0][AIAttributes.COMPLETION_CONTENT] == "Hello!"


def test_synthesize_message_events_skips_non_chat_spans():
    """Only chat spans get LLM message translation (avoids duplicate content)."""
    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "invoke_agent",
        mapping.GEN_AI_INPUT_MESSAGES: (
            '[{"role":"user","parts":[{"type":"text","content":"x"}]}]'
        ),
    }
    assert mapping.synthesize_message_events(attrs) == []


def test_synthesize_message_events_tolerates_decoded_lists_and_bad_json():
    """Already-decoded lists are accepted; malformed JSON is skipped, not raised."""
    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_INPUT_MESSAGES: [
            {"role": "user", "parts": [{"type": "text", "content": "decoded"}]}
        ],
        mapping.GEN_AI_OUTPUT_MESSAGES: "not json{",
    }
    events = mapping.synthesize_message_events(attrs)
    assert [n for n, _ in events] == ["ai.prompt"]
    assert events[0][1][AIAttributes.PROMPT_CONTENT] == "decoded"


def test_synthesize_message_events_stringifies_non_text_parts():
    """Non-text parts (tool calls, blobs) are JSON-encoded so they stay visible."""
    import json as _json

    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_INPUT_MESSAGES: _json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "tool_call",
                            "id": "c1",
                            "name": "lookup",
                            "arguments": {"q": "x"},
                        }
                    ],
                }
            ]
        ),
    }
    events = mapping.synthesize_message_events(attrs)
    assert len(events) == 1
    content = events[0][1][AIAttributes.PROMPT_CONTENT]
    assert "tool_call" in content
    assert "lookup" in content


def test_synthesize_message_events_empty_when_no_attributes():
    """A chat span with no message attributes (capture off) yields nothing."""
    assert mapping.synthesize_message_events({mapping.GEN_AI_OPERATION_NAME: "chat"}) == []


# ---------------------------------------------------------------------------
# Agent.run() emits translated agent + LLM spans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_run_emits_translated_agent_and_llm_spans(
    captured_spans,
    integration,
    reset_observability_settings,
    reset_llm_observation_flag,
    session_provider,
):
    """A real ``agent.run()`` produces ``ai.agent.invoke`` + ``ai.llm.invoke`` spans."""
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    client = DeterministicChatClient(
        [_text_response("Hello!", model="gpt-4-mini", response_model="gpt-4-mini-2024-09-12")],
        model="gpt-4-mini",
    )
    agent = Agent(
        client=client,
        instructions="You are a tester.",
        name="hello_agent",
    )

    response = await agent.run("Say hi")
    assert "Hello" in response.text

    spans = _drain_spans(provider, captured_spans)
    span_names = [s.name for s in spans]

    # Both the translated agent invoke and chat invoke must be present.
    assert "ai.agent.invoke" in span_names, f"missing ai.agent.invoke; got {span_names}"
    assert "ai.llm.invoke" in span_names, f"missing ai.llm.invoke; got {span_names}"

    # No raw ``chat <model>`` or ``invoke_agent <name>`` names should leak through.
    for name in span_names:
        assert not name.startswith("chat "), f"raw MAF chat span leaked: {name!r}"
        assert not name.startswith("invoke_agent "), f"raw MAF agent span leaked: {name!r}"

    llm_spans = [s for s in spans if s.name == "ai.llm.invoke"]
    assert llm_spans, "no llm spans"
    llm_span = llm_spans[0]
    attrs = dict(llm_span.attributes or {})
    # Model + token + operation-type attributes were translated.
    assert attrs.get(AIAttributes.MODEL_NAME) == "gpt-4-mini"
    assert attrs.get(AIAttributes.LLM_TOKENS_INPUT) == 7
    assert attrs.get(AIAttributes.LLM_TOKENS_OUTPUT) == 11
    assert attrs.get(AIAttributes.LLM_TOKENS_TOTAL) == 18
    assert attrs.get(AIAttributes.OPERATION_TYPE) == AIAttributes.OPERATION_LLM_INVOKE

    agent_spans = [s for s in spans if s.name == "ai.agent.invoke"]
    assert agent_spans, "no agent spans"
    assert agent_spans[0].attributes.get(AIAttributes.AGENT_NAME) == "hello_agent"


# ---------------------------------------------------------------------------
# @tool invocation emits a translated tool span
# ---------------------------------------------------------------------------


@tool
def add_numbers(a: float, b: float) -> float:
    """Return ``a + b``. Used by :func:`test_tool_invocation_emits_translated_tool_span`."""
    return a + b


@pytest.mark.asyncio
async def test_tool_invocation_emits_translated_tool_span(
    captured_spans,
    integration,
    reset_observability_settings,
    reset_llm_observation_flag,
    session_provider,
):
    """A function-call response routed through ``FunctionInvocationLayer``
    triggers a real ``execute_tool`` span that the integration translates to
    ``ai.tool.invoke``, with synthesized ``ai.tool.input`` / ``ai.tool.output``
    events from the original ``gen_ai.tool.call.*`` attributes.

    MAF only sets ``gen_ai.tool.call.arguments`` and
    ``gen_ai.tool.call.result`` when sensitive-data capture is enabled, so we
    flip that flag here. The reset fixture restores it after the test.
    """
    enable_instrumentation(enable_sensitive_data=True)
    provider, _captured, _bsp = session_provider

    client = DeterministicChatClient(
        [
            _function_call_response(
                call_id="call-1",
                name="add_numbers",
                arguments={"a": 2.0, "b": 3.0},
                model="gpt-4-mini",
            ),
            _text_response("The sum is 5.", model="gpt-4-mini"),
        ],
        model="gpt-4-mini",
    )
    agent = Agent(
        client=client,
        instructions="Use the tool to add numbers.",
        name="tool_agent",
        tools=[add_numbers],
    )

    response = await agent.run("Add 2 and 3")
    assert "5" in response.text

    spans = _drain_spans(provider, captured_spans)
    span_names = [s.name for s in spans]

    assert "ai.tool.invoke" in span_names, f"no ai.tool.invoke span; got {span_names}"
    tool_spans = [s for s in spans if s.name == "ai.tool.invoke"]
    tool_span = tool_spans[0]
    tool_attrs = dict(tool_span.attributes or {})
    assert tool_attrs.get(AIAttributes.TOOL_NAME) == "add_numbers"
    assert tool_attrs.get(AIAttributes.OPERATION_TYPE) == AIAttributes.OPERATION_TOOL_INVOKE

    # synthesize_tool_io_events should have produced an ai.tool.input + an
    # ai.tool.output event for this span (since MAF stores args/result as
    # span attributes, not events).
    event_names = [e.name for e in tool_span.events]
    assert "ai.tool.input" in event_names, f"missing ai.tool.input event; got {event_names}"
    assert "ai.tool.output" in event_names, f"missing ai.tool.output event; got {event_names}"


# ---------------------------------------------------------------------------
# HandoffBuilder workflow emits translated function.workflow.* spans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handoff_workflow_emits_function_workflow_spans(
    captured_spans,
    integration,
    reset_observability_settings,
    reset_llm_observation_flag,
    session_provider,
):
    """A real ``HandoffBuilder`` workflow produces translated workflow spans.

    We only assert that the root ``function.workflow.run`` span shows up;
    the executor/edge_group spans are MAF-version-dependent and asserting
    them tightly would couple the test to MAF's internal trace shape. The
    translator-level mapping for each prefix is covered by the parameterised
    name test above.
    """
    pytest.importorskip("agent_framework_orchestrations")
    from agent_framework.orchestrations import HandoffBuilder

    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    coord_client = DeterministicChatClient(
        [_text_response("Routing to specialist.", model="gpt-4-mini")],
        model="gpt-4-mini",
    )
    spec_client = DeterministicChatClient(
        [_text_response("Specialist done.", model="gpt-4-mini")],
        model="gpt-4-mini",
    )
    coordinator = Agent(
        client=coord_client,
        instructions="You are the coordinator.",
        name="coordinator",
        require_per_service_call_history_persistence=True,
    )
    specialist = Agent(
        client=spec_client,
        instructions="You are the specialist.",
        name="specialist",
        require_per_service_call_history_persistence=True,
    )

    workflow = (
        HandoffBuilder(
            name="test_handoff",
            participants=[coordinator, specialist],
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [specialist])
        .add_handoff(specialist, [coordinator])
        .with_autonomous_mode(turn_limits={"coordinator": 2, "specialist": 1})
        .build()
    )

    # Drive the workflow once. Some events stream out, but for trace-shape
    # assertions we only need the workflow to run to completion.
    async for _event in workflow.run("Hi", stream=True):
        pass

    spans = _drain_spans(provider, captured_spans)
    span_names = [s.name for s in spans]

    workflow_spans = [n for n in span_names if n.startswith("function.workflow.")]
    assert workflow_spans, f"no function.workflow.* spans found; got {span_names!r}"
    # Sanity: every translated workflow span name passes the Rhesis validator.
    for name in workflow_spans:
        assert validate_span_name(name), f"workflow span name rejected: {name!r}"


@pytest.mark.asyncio
async def test_handoff_workflow_emits_synthesized_agent_handoff_spans(
    captured_spans,
    integration,
    reset_observability_settings,
    reset_llm_observation_flag,
    session_provider,
):
    """A real ``HandoffBuilder`` handoff must produce an ``ai.agent.handoff`` span.

    MAF short-circuits ``handoff_to_*`` tool calls (no ``execute_tool`` span),
    so the handoff is only visible in the chat span's ``gen_ai.output.messages``.
    The integration must synthesize the ``ai.agent.handoff`` span (with
    ``from``/``to``) the Graph View needs to connect agents. Sensitive-data
    capture must be on for MAF to record output messages.
    """
    pytest.importorskip("agent_framework_orchestrations")
    from agent_framework.orchestrations import HandoffBuilder

    enable_instrumentation(enable_sensitive_data=True)
    provider, _captured, _bsp = session_provider

    # Coordinator hands off to the specialist via the auto-generated handoff
    # tool; the specialist replies with plain text and the run winds down.
    coord_client = DeterministicChatClient(
        [
            _function_call_response(
                call_id="handoff-1",
                name="handoff_to_specialist",
                arguments={},
                model="gpt-4-mini",
            ),
            _text_response("All done.", model="gpt-4-mini"),
        ],
        model="gpt-4-mini",
    )
    spec_client = DeterministicChatClient(
        [_text_response("Specialist done.", model="gpt-4-mini")],
        model="gpt-4-mini",
    )
    coordinator = Agent(
        client=coord_client,
        instructions="You are the coordinator.",
        name="coordinator",
        require_per_service_call_history_persistence=True,
    )
    specialist = Agent(
        client=spec_client,
        instructions="You are the specialist.",
        name="specialist",
        require_per_service_call_history_persistence=True,
    )

    workflow = (
        HandoffBuilder(
            name="test_handoff_edges",
            participants=[coordinator, specialist],
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [specialist])
        .add_handoff(specialist, [coordinator])
        .with_autonomous_mode(turn_limits={"coordinator": 1, "specialist": 1})
        .build()
    )

    async for _event in workflow.run("Route me to the specialist", stream=True):
        pass

    spans = _drain_spans(provider, captured_spans)
    handoffs = [s for s in spans if s.name == "ai.agent.handoff"]
    assert handoffs, (
        f"no ai.agent.handoff span synthesized from chat output; got {[s.name for s in spans]!r}"
    )
    targets = {s.attributes.get(AIAttributes.AGENT_HANDOFF_TO) for s in handoffs}
    assert "specialist" in targets
    # The calling agent should resolve from the enclosing invoke_agent span.
    froms = {s.attributes.get(AIAttributes.AGENT_HANDOFF_FROM) for s in handoffs}
    assert "coordinator" in froms


# ---------------------------------------------------------------------------
# Dedup processor: real-MAF span emission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_processor_toggles_flag_only_during_chat_span(
    captured_spans,
    integration,
    reset_observability_settings,
    reset_llm_observation_flag,
    session_provider,
):
    """The LLM-observation flag is True inside the chat span and False after.

    We piggyback on a fresh span processor that records the flag value at
    ``on_start`` and ``on_end`` boundaries to capture the transition. After
    the agent's chat span closes the flag must be back to False.
    """
    provider, _captured, _bsp = session_provider
    enable_instrumentation()

    flag_log: list[tuple[str, str, bool]] = []

    class _FlagRecorder(SpanProcessor):
        """Span processor that snapshots the LLM-observation flag."""

        def on_start(self, span, parent_context=None):
            flag_log.append(("start", span.name, is_llm_observation_active()))

        def on_end(self, span):
            flag_log.append(("end", span.name, is_llm_observation_active()))

        def shutdown(self):
            return None

        def force_flush(self, timeout_millis: int = 30_000) -> bool:
            return True

    recorder = _FlagRecorder()
    provider.add_span_processor(recorder)
    try:
        client = DeterministicChatClient(
            [_text_response("ok", model="gpt-4-mini")],
            model="gpt-4-mini",
        )
        agent = Agent(client=client, instructions="hi", name="flag_agent")
        await agent.run("hi")
    finally:
        # OTEL has no API to remove a span processor. The recorder stays
        # attached for the rest of the session, but the test's assertions
        # only consult ``flag_log`` collected up to this point.
        recorder.shutdown()

    chat_starts = [
        (name, flag)
        for kind, name, flag in flag_log
        if kind == "start" and name.startswith("chat ")
    ]
    chat_ends = [
        (name, flag) for kind, name, flag in flag_log if kind == "end" and name.startswith("chat ")
    ]
    assert chat_starts, f"no chat-span on_start in flag log: {flag_log}"
    assert chat_ends, f"no chat-span on_end in flag log: {flag_log}"
    assert all(flag is True for _name, flag in chat_starts), (
        f"flag should be True during chat on_start: {chat_starts}"
    )
    # After the chat span ends the flag should be cleared (no outer scope).
    assert is_llm_observation_active() is False


@pytest.mark.asyncio
async def test_dedup_processor_preserves_outer_observe_llm_flag(
    captured_spans,
    integration,
    reset_observability_settings,
    reset_llm_observation_flag,
    session_provider,
):
    """An enclosing ``@observe.llm`` flag must survive the agent run.

    The dedup processor's ``on_end`` must NOT clear the flag when the outer
    scope had already set it. This is the regression covered by the
    Priority 1.2 fix in ``maf-integration-fixes_27b9bea7.plan.md``.
    """
    enable_instrumentation()

    set_llm_observation_active(True)
    client = DeterministicChatClient(
        [_text_response("ok", model="gpt-4-mini")],
        model="gpt-4-mini",
    )
    agent = Agent(client=client, instructions="hi", name="flag_outer_agent")
    await agent.run("hi")

    assert is_llm_observation_active() is True, (
        "outer @observe.llm flag was clobbered by the dedup processor"
    )


# ---------------------------------------------------------------------------
# Cross-batch handoff from_agent resolution
# ---------------------------------------------------------------------------


class _FakeCtx:
    """Minimal stand-in for an OTel ``SpanContext`` (only ``span_id``)."""

    def __init__(self, span_id: int) -> None:
        self.span_id = span_id


class _FakeScope:
    """Instrumentation scope that ``_is_maf_span`` accepts."""

    name = mapping.INSTRUMENTATION_SCOPE_PREFIX


class _FakeSpan:
    """Lightweight ReadableSpan-ish object for ancestry/exporter unit tests.

    Carries just enough surface (``context``/``parent``/``name``/
    ``attributes``/``events``/``instrumentation_scope``) for the registry to
    index it and for :class:`MAFTranslatingExporter` to translate it.
    """

    def __init__(self, *, span_id, name, parent_id=None, attributes=None, events=()):
        self.context = _FakeCtx(span_id)
        self.parent = _FakeCtx(parent_id) if parent_id is not None else None
        self.name = name
        self.attributes = attributes or {}
        self.events = tuple(events)
        self.instrumentation_scope = _FakeScope()


def test_handoff_ancestry_registry_resolves_parent_chain():
    """The registry hops tool -> chat -> invoke_agent to find the caller."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._HandoffAncestryRegistry()
    agent = _FakeSpan(span_id=10, name="invoke_agent coordinator")
    chat = _FakeSpan(span_id=20, name="chat gpt-4", parent_id=10)
    tool = _FakeSpan(span_id=30, name="execute_tool handoff_to_specialist", parent_id=20)
    for span in (agent, chat, tool):
        reg.record(span)

    assert reg.find_ancestor_agent(tool) == "coordinator"


def test_handoff_ancestry_registry_returns_none_without_agent_ancestor():
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._HandoffAncestryRegistry()
    chat = _FakeSpan(span_id=21, name="chat gpt-4")
    tool = _FakeSpan(span_id=31, name="execute_tool handoff_to_specialist", parent_id=21)
    reg.record(chat)
    reg.record(tool)

    assert reg.find_ancestor_agent(tool) is None


def test_handoff_exporter_resolves_from_agent_across_batches():
    """A handoff tool span exported WITHOUT its agent parent in the batch must
    still resolve ``ai.agent.handoff.from`` via the start-time registry.

    This is the cross-batch regression: under ``BatchSpanProcessor`` the child
    tool span ends (and exports) before its ``invoke_agent`` parent, so the
    batch-local walk alone cannot see the caller.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    agent = _FakeSpan(span_id=110, name="invoke_agent coordinator")
    chat = _FakeSpan(span_id=120, name="chat gpt-4", parent_id=110)
    tool_attrs = {
        mapping.GEN_AI_OPERATION_NAME: "execute_tool",
        mapping.GEN_AI_TOOL_NAME: "handoff_to_specialist",
    }
    tool = _FakeSpan(
        span_id=130,
        name="execute_tool handoff_to_specialist",
        parent_id=120,
        attributes=tool_attrs,
    )
    # Populate the shared registry exactly as the dedup processor's on_start
    # would, for all three spans (parents start before children).
    for span in (agent, chat, tool):
        tr_mod._handoff_ancestry.record(span)

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner)
    # Export ONLY the tool span -> its invoke_agent parent is "in a prior batch".
    exporter.export([tool])

    out = captured_inner.get_finished_spans()
    assert len(out) == 1
    translated = out[0]
    assert translated.name == "ai.agent.handoff"
    assert translated.attributes[AIAttributes.AGENT_HANDOFF_TO] == "specialist"
    assert translated.attributes[AIAttributes.AGENT_HANDOFF_FROM] == "coordinator"


# ---------------------------------------------------------------------------
# Chat-output handoff synthesis (primary path for current MAF)
# ---------------------------------------------------------------------------


class _RichCtx:
    """SpanContext stand-in carrying the fields synthesis needs."""

    def __init__(self, trace_id: int, span_id: int, trace_flags=None) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_flags = trace_flags


class _FakeChatSpan:
    """A chat-span stand-in rich enough for handoff synthesis + translation."""

    def __init__(self, *, span_id, trace_id, parent_id=None, attributes=None, name="chat gpt-4"):
        self.context = _RichCtx(trace_id, span_id)
        self.parent = _RichCtx(trace_id, parent_id) if parent_id is not None else None
        self.name = name
        self.attributes = attributes or {}
        self.events = ()
        self.instrumentation_scope = _FakeScope()
        self.start_time = 1_000
        self.end_time = 2_000
        self.resource = None


def test_synthesize_handoff_spans_builds_directed_edge():
    """A chat span with a handoff target yields an ``ai.agent.handoff`` span."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    chat = _FakeChatSpan(span_id=520, trace_id=999, parent_id=510)
    spans = tr_mod.synthesize_handoff_spans(chat, "trip_coordinator", ["destination_finder"])

    assert len(spans) == 1
    handoff = spans[0]
    assert handoff.name == "ai.agent.handoff"
    assert handoff.attributes[AIAttributes.OPERATION_TYPE] == AIAttributes.OPERATION_AGENT_HANDOFF
    assert handoff.attributes[AIAttributes.AGENT_HANDOFF_FROM] == "trip_coordinator"
    assert handoff.attributes[AIAttributes.AGENT_HANDOFF_TO] == "destination_finder"
    # Shares the chat span's trace, gets a fresh span id, and is parented to the
    # chat span's parent (the enclosing invoke_agent), i.e. a sibling of chat.
    assert handoff.context.trace_id == 999
    assert handoff.context.span_id != 520
    assert handoff.parent is chat.parent


def test_synthesize_handoff_spans_omits_from_when_unknown():
    """Without a resolved caller we still emit the span with only ``to``."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    chat = _FakeChatSpan(span_id=521, trace_id=1000)
    spans = tr_mod.synthesize_handoff_spans(chat, None, ["specialist"])

    assert len(spans) == 1
    assert spans[0].attributes[AIAttributes.AGENT_HANDOFF_TO] == "specialist"
    assert AIAttributes.AGENT_HANDOFF_FROM not in spans[0].attributes


def test_synthesize_handoff_spans_empty_targets():
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    chat = _FakeChatSpan(span_id=522, trace_id=1001)
    assert tr_mod.synthesize_handoff_spans(chat, "a", []) == []


def test_exporter_synthesizes_handoff_from_chat_output_messages():
    """A chat span whose output carries a ``handoff_to_*`` tool call must
    cause the exporter to emit an extra ``ai.agent.handoff`` span with both
    ``from`` (resolved via the ancestry registry) and ``to`` populated.
    """
    import json as _json

    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    # Record the enclosing invoke_agent so from_agent resolves.
    agent = _FakeSpan(span_id=610, name="invoke_agent trip_coordinator")
    tr_mod._handoff_ancestry.record(agent)

    chat_attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "tool_call",
                            "id": "c1",
                            "name": "handoff_to_destination_finder",
                            "arguments": "{}",
                        }
                    ],
                }
            ]
        ),
    }
    chat = _FakeChatSpan(span_id=620, trace_id=4242, parent_id=610, attributes=chat_attrs)
    tr_mod._handoff_ancestry.record(chat)

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner)
    exporter.export([chat])

    out = captured_inner.get_finished_spans()
    names = [s.name for s in out]
    # The chat span itself (translated to ai.llm.invoke) plus the synthesized
    # handoff span.
    assert "ai.llm.invoke" in names
    handoffs = [s for s in out if s.name == "ai.agent.handoff"]
    assert len(handoffs) == 1
    assert handoffs[0].attributes[AIAttributes.AGENT_HANDOFF_TO] == "destination_finder"
    assert handoffs[0].attributes[AIAttributes.AGENT_HANDOFF_FROM] == "trip_coordinator"


def test_exporter_drops_low_value_workflow_spans_by_default():
    """edge_group / message.send routing spans are dropped unless verbose."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    edge = _FakeSpan(span_id=710, name="edge_group.process FanOutEdgeGroup")
    msg = _FakeSpan(span_id=711, name="message.send")
    keep = _FakeSpan(span_id=712, name="executor.process coordinator")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner, verbose_workflow_spans=False)
    exporter.export([edge, msg, keep])

    names = [s.name for s in captured_inner.get_finished_spans()]
    assert any(n.startswith("function.workflow.executor.process") for n in names)
    assert all("edge_group" not in n for n in names)
    assert all("message.send" not in n for n in names)


def test_exporter_keeps_low_value_workflow_spans_when_verbose():
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    edge = _FakeSpan(span_id=720, name="edge_group.process")
    msg = _FakeSpan(span_id=721, name="message.send")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner, verbose_workflow_spans=True)
    exporter.export([edge, msg])

    names = [s.name for s in captured_inner.get_finished_spans()]
    assert "function.workflow.edge_group.process" in names
    assert "function.workflow.message.send" in names


def test_verbose_workflow_spans_env_default(monkeypatch):
    """The exporter honors ``RHESIS_MAF_VERBOSE_WORKFLOW_SPANS`` by default."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    monkeypatch.delenv("RHESIS_MAF_VERBOSE_WORKFLOW_SPANS", raising=False)
    assert tr_mod.MAFTranslatingExporter(InMemorySpanExporter())._verbose_workflow_spans is False

    monkeypatch.setenv("RHESIS_MAF_VERBOSE_WORKFLOW_SPANS", "1")
    assert tr_mod.MAFTranslatingExporter(InMemorySpanExporter())._verbose_workflow_spans is True


def test_exporter_drops_workflow_build_keeps_workflow_run():
    """The build-time ``workflow.build`` span is dropped; ``workflow.run`` stays.

    ``workflow.build`` is emitted outside any run and would otherwise surface as
    its own standalone trace (one extra root per build). Dropping it keeps each
    workflow run a single trace.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    build = _FakeSpan(span_id=730, name="workflow.build")
    run = _FakeSpan(span_id=731, name="workflow.run")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner, verbose_workflow_spans=False)
    exporter.export([build, run])

    names = [s.name for s in captured_inner.get_finished_spans()]
    assert "function.workflow.run" in names
    assert all("build" not in n for n in names)


# ---------------------------------------------------------------------------
# Conversation turn-root stamping on the root workflow.run span
# ---------------------------------------------------------------------------


def test_extract_conversation_input_returns_first_user_text():
    import json as _json

    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_INPUT_MESSAGES: _json.dumps(
            [
                {"role": "system", "parts": [{"type": "text", "content": "be helpful"}]},
                {"role": "user", "parts": [{"type": "text", "content": "Plan a day trip"}]},
            ]
        ),
    }
    assert mapping.extract_conversation_input(attrs) == "Plan a day trip"


def test_extract_conversation_output_joins_text_and_skips_tool_calls():
    import json as _json

    text_attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(
            [{"role": "assistant", "parts": [{"type": "text", "content": "Here is your plan"}]}]
        ),
    }
    assert mapping.extract_conversation_output(text_attrs) == "Here is your plan"

    # A handoff (tool-call-only) turn carries no prose -> None.
    handoff_attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [{"type": "tool_call", "name": "handoff_to_x", "arguments": "{}"}],
                }
            ]
        ),
    }
    assert mapping.extract_conversation_output(handoff_attrs) is None


def test_extract_conversation_output_filters_non_assistant_roles():
    """Only ``role == "assistant"`` output text is stamped into conversation.output."""
    import json as _json

    attrs = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(
            [
                {"role": "tool", "parts": [{"type": "text", "content": "tool noise"}]},
                {"role": "user", "parts": [{"type": "text", "content": "echoed user text"}]},
                {"role": "assistant", "parts": [{"type": "text", "content": "Here is your plan"}]},
            ]
        ),
    }
    assert mapping.extract_conversation_output(attrs) == "Here is your plan"

    # Output array with no assistant message -> nothing to stamp.
    no_assistant = {
        mapping.GEN_AI_OPERATION_NAME: "chat",
        mapping.GEN_AI_OUTPUT_MESSAGES: _json.dumps(
            [{"role": "tool", "parts": [{"type": "text", "content": "tool noise"}]}]
        ),
    }
    assert mapping.extract_conversation_output(no_assistant) is None


def test_extract_conversation_input_output_ignore_non_chat_spans():
    attrs = {mapping.GEN_AI_OPERATION_NAME: "invoke_agent"}
    assert mapping.extract_conversation_input(attrs) is None
    assert mapping.extract_conversation_output(attrs) is None


def test_conversation_content_registry_first_input_wins_last_output_wins():
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry()
    reg.record_chat(7, input_text="first query", output_text="routing...")
    # Later turns echo the same query and produce newer output.
    reg.record_chat(7, input_text="first query", output_text="final plan")
    reg.record_chat(7, input_text="ignored second input", output_text=None)

    assert reg.get(7) == ("first query", "final plan")
    assert reg.get(999) == (None, None)


def test_conversation_content_registry_records_session_first_wins():
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry()
    reg.record_session(7, "session-a")
    # First session id wins; later turns / empty values do not overwrite it.
    reg.record_session(7, "session-b")
    reg.record_session(7, None)

    assert reg.get_session(7) == "session-a"
    assert reg.get_session(999) is None


def test_conversation_content_registry_read_is_repeatable():
    """Reading does not pop: every wrapped exporter has to see the same content."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry()
    reg.record_chat(7, input_text="first query", output_text="final plan")
    reg.record_session(7, "session-a")

    assert reg.read_for_root(7) == ("session-a", "first query", "final plan")
    assert reg.read_for_root(7) == ("session-a", "first query", "final plan")
    # Unknown trace ids yield an all-None triple.
    assert reg.read_for_root(999) == (None, None, None)


def test_conversation_content_registry_releases_what_falls_behind():
    """A read schedules the release; it happens once enough others have been read.

    Holding 10 KB of conversation text per trace until the entry cap evicts it
    would cost a long-running service far more memory than it needs to.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry(max_served=2)
    reg.record_chat(1, input_text="first", output_text="reply")
    reg.record_session(1, "sess-1")

    assert reg.read_for_root(1)[0] == "sess-1"
    for later in (2, 3):
        reg.record_session(later, f"sess-{later}")
        reg.read_for_root(later)

    assert reg.read_for_root(1) == (None, None, None), "should have fallen off the queue"
    assert reg.get(1) == (None, None)
    assert reg.get_session(1) is None


def test_conversation_content_registry_release_without_reading():
    """``release`` is for a run whose content nothing will stamp."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry(max_served=1)
    reg.record_session(1, "sess-1")
    reg.record_session(2, "sess-2")

    reg.release(1)
    reg.release(2)

    assert reg.get_session(1) is None
    assert reg.get_session(2) == "sess-2"


def test_conversation_content_registry_ignores_a_trace_with_nothing_recorded():
    """Otherwise a run of content-free traces evicts the ones with content.

    A single-turn run sets no conversation id, and content capture can be off
    entirely, so reads that find nothing are the common case in some processes.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry(max_served=1)
    reg.record_session(1, "sess-1")
    reg.read_for_root(1)

    for empty in range(2, 10):
        assert reg.read_for_root(empty) == (None, None, None)

    assert reg.read_for_root(1) == ("sess-1", None, None)


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(lambda reg, tid: reg.record_session(tid, f"sess-{tid}"), id="session-only"),
        pytest.param(lambda reg, tid: reg.record_chat(tid, input_text="query"), id="input-only"),
        pytest.param(lambda reg, tid: reg.record_chat(tid, output_text="answer"), id="output-only"),
    ],
)
def test_conversation_content_registry_releases_whichever_store_holds_the_content(record):
    """Content in any one store has to count as content.

    A store left out of the "is there anything here" check makes its entries
    invisible to the release queue, so they are never freed and the store grows
    until the entry cap evicts it -- which is the leak the queue exists to stop.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry(max_served=1)
    record(reg, 1)
    reg.read_for_root(1)
    assert reg.read_for_root(1) != (None, None, None), "precondition: trace 1 has content"

    record(reg, 2)
    reg.read_for_root(2)

    assert reg.read_for_root(1) == (None, None, None), "trace 1 should have been released"


def test_two_wrapped_exporters_both_stamp_the_conversation():
    """``enable()`` wraps every exporter on the provider, so a process with its
    own OTLP collector beside Rhesis has two translating exporters exporting the
    same spans. Both have to stamp the conversation, not just the faster one."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xBEEF01
    tr_mod._conversation_content.record_chat(
        trace_id, input_text="Plan a day trip", output_text="Here is your plan"
    )
    tr_mod._conversation_content.record_session(trace_id, "sess-two-exporters")
    run = _FakeChatSpan(span_id=760, trace_id=trace_id, parent_id=None, name="workflow.run")

    sa = ConversationContext.SpanAttributes
    for _ in range(2):
        inner = InMemorySpanExporter()
        tr_mod.MAFTranslatingExporter(inner).export([run])
        attrs = dict(inner.get_finished_spans()[0].attributes or {})
        assert attrs.get(sa.CONVERSATION_ID) == "sess-two-exporters"
        assert attrs.get(sa.CONVERSATION_INPUT) == "Plan a day trip"
        assert attrs.get(sa.CONVERSATION_OUTPUT) == "Here is your plan"


def test_exporter_stamps_turn_root_on_root_workflow_run():
    """A root ``workflow.run`` span with a recorded session id becomes a turn root.

    The conversation id is the agent-supplied session id (not the trace id), so
    multiple turns sharing a session group together.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xABCDEF
    tr_mod._conversation_content.record_chat(
        trace_id, input_text="Plan a day trip", output_text="Here is your plan"
    )
    tr_mod._conversation_content.record_session(trace_id, "sess-1")
    run = _FakeChatSpan(span_id=740, trace_id=trace_id, parent_id=None, name="workflow.run")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner)
    exporter.export([run])

    out = captured_inner.get_finished_spans()
    assert len(out) == 1
    attrs = dict(out[0].attributes or {})
    sa = ConversationContext.SpanAttributes
    assert out[0].name == "function.workflow.run"
    assert attrs.get(sa.IS_TURN_ROOT) is True
    assert attrs.get(sa.CONVERSATION_ID) == "sess-1"
    assert attrs.get(sa.CONVERSATION_INPUT) == "Plan a day trip"
    assert attrs.get(sa.CONVERSATION_OUTPUT) == "Here is your plan"


def test_exporter_stamps_io_but_not_turn_root_without_session_id():
    """A root ``workflow.run`` with no session id shows its conversation but stays single-turn.

    This is the single-turn ``run_traces`` path: spans are recorded but no
    conversation id was set, so input/output are stamped (the conversation is
    visible) while ``is_turn_root`` / ``conversation.id`` are NOT stamped (the
    run remains a plain single-turn trace, not grouped as a conversation).
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xFACADE
    tr_mod._conversation_content.record_chat(
        trace_id, input_text="Plan a day trip", output_text="Here is your plan"
    )
    # No record_session(...) call: this is a one-shot single-turn run.
    run = _FakeChatSpan(span_id=742, trace_id=trace_id, parent_id=None, name="workflow.run")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner)
    exporter.export([run])

    out = captured_inner.get_finished_spans()
    assert len(out) == 1
    attrs = dict(out[0].attributes or {})
    sa = ConversationContext.SpanAttributes
    assert out[0].name == "function.workflow.run"
    assert sa.IS_TURN_ROOT not in attrs
    assert sa.CONVERSATION_ID not in attrs
    assert attrs.get(sa.CONVERSATION_INPUT) == "Plan a day trip"
    assert attrs.get(sa.CONVERSATION_OUTPUT) == "Here is your plan"


def test_exporter_skips_root_without_session_or_content():
    """A root ``workflow.run`` with neither session id nor captured I/O is untouched."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xC0FFEE
    # No record_chat and no record_session for this trace.
    run = _FakeChatSpan(span_id=743, trace_id=trace_id, parent_id=None, name="workflow.run")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner)
    exporter.export([run])

    out = captured_inner.get_finished_spans()
    assert len(out) == 1
    attrs = dict(out[0].attributes or {})
    sa = ConversationContext.SpanAttributes
    assert out[0].name == "function.workflow.run"
    assert sa.IS_TURN_ROOT not in attrs
    assert sa.CONVERSATION_ID not in attrs
    assert sa.CONVERSATION_INPUT not in attrs
    assert sa.CONVERSATION_OUTPUT not in attrs


def test_exporter_skips_turn_root_on_nested_workflow_run():
    """A ``workflow.run`` nested under a parent (e.g. a Rhesis @endpoint span)
    must NOT be stamped as a turn root -- the enclosing span owns that role.

    The release of its per-trace entries is covered by the registry's own tests;
    here the point is that nothing is stamped.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0x123456
    tr_mod._conversation_content.record_chat(trace_id, input_text="hi", output_text="hello")
    tr_mod._conversation_content.record_session(trace_id, "sess-nested")
    run = _FakeChatSpan(span_id=741, trace_id=trace_id, parent_id=510, name="workflow.run")

    captured_inner = InMemorySpanExporter()
    exporter = tr_mod.MAFTranslatingExporter(captured_inner)
    exporter.export([run])

    out = captured_inner.get_finished_spans()
    assert len(out) == 1
    attrs = dict(out[0].attributes or {})
    sa = ConversationContext.SpanAttributes
    assert out[0].name == "function.workflow.run"
    assert sa.IS_TURN_ROOT not in attrs
    assert sa.CONVERSATION_ID not in attrs
    assert sa.CONVERSATION_INPUT not in attrs
    assert sa.CONVERSATION_OUTPUT not in attrs


def test_conversation_content_registry_truncates_io_at_record_time():
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    reg = tr_mod._ConversationContentRegistry()
    long_text = "x" * (ConversationContext.MAX_IO_LENGTH + 500)
    reg.record_chat(42, input_text=long_text, output_text=long_text)
    conv_input, conv_output = reg.get(42)
    assert conv_input is not None and len(conv_input) == ConversationContext.MAX_IO_LENGTH
    assert conv_output is not None and len(conv_output) == ConversationContext.MAX_IO_LENGTH


# ---------------------------------------------------------------------------
# Conversation trace join: every turn of a conversation in one trace
# ---------------------------------------------------------------------------


async def _run_turns(count: int, *, conversation_id: str | None) -> None:
    """Run ``count`` independent agent turns, optionally under one conversation."""
    if conversation_id is not None:
        set_conversation_id(conversation_id)
    for index in range(count):
        client = DeterministicChatClient([_text_response(f"Answer {index}.")])
        agent = Agent(client=client, instructions="Answer.", name="joiner")
        await agent.run(f"Question {index}?")


def _trace_ids(spans) -> set[int]:
    return {s.context.trace_id for s in spans}


@pytest.fixture
def drained_exporter(session_provider, captured_spans) -> InMemorySpanExporter:
    """The in-memory exporter, guaranteed empty before the test runs.

    ``captured_spans`` clears on teardown, but a test that never drains leaves
    its spans buffered in the ``BatchSpanProcessor``, and they arrive in the next
    test's flush. These tests count trace ids, so a stray turn from an earlier
    test reads as a turn that failed to join.
    """
    provider, _captured, _bsp = session_provider
    provider.force_flush()
    captured_spans.clear()
    return captured_spans


@pytest.mark.asyncio
async def test_turns_of_one_conversation_share_one_trace(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """MAF opens its own root span per turn, so OTEL mints a fresh trace id each
    time. Left alone, a ten-turn chat arrives as ten unrelated traces even though
    every turn carries the same conversation id."""
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    await _run_turns(3, conversation_id="conv-join")

    spans = _drain_spans(provider, drained_exporter)
    assert len(_trace_ids(spans)) == 1
    # One turn root per turn, all on that single trace, each carrying the id the
    # exporter propagates to every other span sharing the trace.
    sa = ConversationContext.SpanAttributes
    stamped = [s for s in spans if (s.attributes or {}).get(sa.IS_TURN_ROOT)]
    assert len(stamped) == 3
    assert all(s.parent is None for s in stamped)
    assert {s.attributes[sa.CONVERSATION_ID] for s in stamped} == {"conv-join"}


@pytest.mark.asyncio
async def test_the_first_turn_keeps_its_own_trace_id(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """The anchor is turn 1's real id, so turn 1 is never moved.

    Anything that observed a trace id for the first turn -- an endpoint result, a
    backend turn record, a link in the viewer -- still resolves.
    """
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    await _run_turns(1, conversation_id="conv-anchor")
    first = _trace_ids(_drain_spans(provider, drained_exporter))
    assert len(first) == 1
    drained_exporter.clear()

    await _run_turns(2, conversation_id="conv-anchor")
    assert _trace_ids(_drain_spans(provider, drained_exporter)) == first


@pytest.mark.asyncio
async def test_two_conversations_do_not_collide(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    await _run_turns(1, conversation_id="conv-a")
    first = _trace_ids(_drain_spans(provider, drained_exporter))
    drained_exporter.clear()
    await _run_turns(1, conversation_id="conv-b")
    second = _trace_ids(_drain_spans(provider, drained_exporter))

    assert len(first) == len(second) == 1
    assert first != second


@pytest.mark.asyncio
async def test_without_a_conversation_id_each_turn_keeps_its_own_trace(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """The documented limit of the join: the target trace has to be known when
    the run root is created, and only the Rhesis contextvar is readable then."""
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    await _run_turns(2, conversation_id=None)

    assert len(_trace_ids(_drain_spans(provider, drained_exporter))) == 2


@pytest.mark.asyncio
async def test_a_platform_owned_conversation_is_left_alone(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """``conversation_trace_id`` means the platform minted the trace itself.

    It is writing its own turn records -- the mapped input and the reply -- to
    that trace and joining the turns by its id. Moving spans anywhere would
    separate the agent's spans from the reply.
    """
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    set_conversation_trace_id("ab" * 16)
    await _run_turns(2, conversation_id="conv-platform")

    spans = _drain_spans(provider, drained_exporter)
    # Untouched: whatever OTEL assigned each turn, not an id of our choosing.
    assert int("ab" * 16, 16) not in _trace_ids(spans)
    assert len(_trace_ids(spans)) == 2


@pytest.mark.asyncio
async def test_an_enclosing_rhesis_span_keeps_ownership_of_the_trace_id(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """The served path: never move spans off the trace id the platform published.

    With an ``@endpoint``/``@observe`` span above the run, ``root_trace_id`` is
    the id the platform hands onwards -- the endpoint result, the next turn's
    conversation trace, the link the viewer opens. Rewriting under it strands all
    of those on a trace id with no spans.
    """
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    set_conversation_id("conv-served")
    tracer = provider.get_tracer("rhesis.sdk")
    with tracer.start_as_current_span("function.chat_endpoint") as endpoint_span:
        published = endpoint_span.get_span_context().trace_id
        set_root_trace_id(format(published, "032x"))
        await _run_turns(2, conversation_id=None)

    assert _trace_ids(_drain_spans(provider, drained_exporter)) == {published}


@pytest.mark.asyncio
async def test_a_conversation_turn_above_the_run_owns_the_turn(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """An app that owns its turn boundary must own it alone.

    ``conversation_turn`` exists for apps whose reply is not the model's last
    message. When one is open the MAF root must not claim turn-root too, and the
    rewrite must move nothing: that span already published the trace id.
    """
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    with conversation_turn("conv-owned", input="Question?") as turn:
        await _run_turns(1, conversation_id=None)
        published = turn.trace_id
        turn.output = "a reply the model never produced"

    spans = _drain_spans(provider, drained_exporter)
    stamped = [
        s
        for s in spans
        if (s.attributes or {}).get(ConversationContext.SpanAttributes.IS_TURN_ROOT)
    ]
    assert [s.name for s in stamped] == ["function.conversation_turn"]
    assert {format(t, "032x") for t in _trace_ids(spans)} == {published}


@pytest.mark.asyncio
async def test_child_parents_are_rebound_to_the_new_trace(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """A parent link still pointing at the abandoned trace is an inconsistency
    the next reader has to work out."""
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    await _run_turns(2, conversation_id="conv-parents")

    for span in _drain_spans(provider, drained_exporter):
        if span.parent is not None:
            assert span.parent.trace_id == span.context.trace_id


@pytest.mark.asyncio
async def test_translation_survives_the_join(
    drained_exporter, integration, reset_observability_settings, session_provider
):
    """Regression guard: the retrace wrapper must not shadow the translation.

    ``ReadableSpan`` serves ``name`` / ``attributes`` from private slots, so a
    wrapper forwarding by ``__getattr__`` alone resolves them on the innermost
    span and silently ships the raw MAF values.
    """
    enable_instrumentation()
    provider, _captured, _bsp = session_provider

    await _run_turns(2, conversation_id="conv-intact")

    spans = _drain_spans(provider, drained_exporter)
    names = [s.name for s in spans]
    assert "ai.llm.invoke" in names
    # ``AIOperationType`` subclasses ``str``, so this reads the value, not the repr.
    assert not any(name.startswith(("chat ", "invoke_agent ")) for name in names)
    llm = next(s for s in spans if s.name == "ai.llm.invoke")
    assert llm.attributes[AIAttributes.LLM_TOKENS_TOTAL] == 18


def test_exporter_stamps_turn_root_on_root_agent_span():
    """A plain ``agent.run()`` emits no ``workflow.run``, so its ``invoke_agent``
    span is the trace root and the only span that can carry the turn."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xA6E27
    tr_mod._conversation_content.record_chat(
        trace_id, input_text="Question?", output_text="Answer."
    )
    tr_mod._conversation_content.record_session(trace_id, "sess-agent")
    root = _FakeChatSpan(
        span_id=810, trace_id=trace_id, parent_id=None, name="invoke_agent researcher"
    )

    captured_inner = InMemorySpanExporter()
    tr_mod.MAFTranslatingExporter(captured_inner).export([root])

    out = captured_inner.get_finished_spans()
    attrs = dict(out[0].attributes or {})
    sa = ConversationContext.SpanAttributes
    assert out[0].name == "ai.agent.invoke"
    assert attrs.get(sa.IS_TURN_ROOT) is True
    assert attrs.get(sa.CONVERSATION_ID) == "sess-agent"
    assert attrs.get(sa.CONVERSATION_INPUT) == "Question?"
    assert attrs.get(sa.CONVERSATION_OUTPUT) == "Answer."


def test_exporter_skips_turn_root_on_nested_agent_span():
    """Inside a workflow, or under an ``@endpoint`` span, an agent span is not
    the trace root and that enclosing span owns turn-root semantics."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xA6E28
    tr_mod._conversation_content.record_session(trace_id, "sess-nested-agent")
    nested = _FakeChatSpan(
        span_id=811, trace_id=trace_id, parent_id=800, name="invoke_agent researcher"
    )

    captured_inner = InMemorySpanExporter()
    tr_mod.MAFTranslatingExporter(captured_inner).export([nested])

    attrs = dict(captured_inner.get_finished_spans()[0].attributes or {})
    assert ConversationContext.SpanAttributes.IS_TURN_ROOT not in attrs


def test_a_nested_agent_span_leaves_the_content_for_the_root():
    """Every agent in a workflow is a nested agent span. If one consumed the
    per-trace content, the ``workflow.run`` root would export with none of it."""
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    trace_id = 0xA6E29
    tr_mod._conversation_content.record_session(trace_id, "sess-order")
    nested = _FakeChatSpan(
        span_id=812, trace_id=trace_id, parent_id=801, name="invoke_agent researcher"
    )
    root = _FakeChatSpan(span_id=801, trace_id=trace_id, parent_id=None, name="workflow.run")

    captured_inner = InMemorySpanExporter()
    # Nested first, which is the order they end in.
    tr_mod.MAFTranslatingExporter(captured_inner).export([nested, root])

    workflow = next(
        s for s in captured_inner.get_finished_spans() if s.name == "function.workflow.run"
    )
    sa = ConversationContext.SpanAttributes
    assert workflow.attributes.get(sa.CONVERSATION_ID) == "sess-order"


# ---------------------------------------------------------------------------
# Lifecycle: enable / disable / idempotency / non-Rhesis provider
# ---------------------------------------------------------------------------


def test_integration_singleton_is_stable():
    assert get_integration() is get_integration()


@pytest.mark.parametrize(
    "env_value, expected",
    [
        (None, True),
        ("1", False),
        ("true", False),
        ("TRUE", False),
        ("yes", False),
        ("on", False),
        ("0", True),
        ("false", True),
        ("", True),
    ],
)
def test_content_capture_opt_out_env(monkeypatch, env_value, expected):
    """Content capture defaults on; only truthy opt-out values disable it."""
    from rhesis.sdk.telemetry.integrations.agent_framework import integration as integ_mod

    if env_value is None:
        monkeypatch.delenv(integ_mod._DISABLE_CONTENT_CAPTURE_ENV, raising=False)
    else:
        monkeypatch.setenv(integ_mod._DISABLE_CONTENT_CAPTURE_ENV, env_value)

    assert integ_mod._content_capture_enabled() is expected


def test_integration_enable_turns_on_sensitive_data(
    session_provider, reset_llm_observation_flag, reset_observability_settings, monkeypatch
):
    """``enable()`` opts MAF into content capture by default."""
    monkeypatch.delenv("RHESIS_DISABLE_CONTENT_CAPTURE", raising=False)
    OBSERVABILITY_SETTINGS.enable_sensitive_data = False

    integ = MAFIntegration()
    try:
        assert integ.enable() is True
        assert OBSERVABILITY_SETTINGS.enable_sensitive_data is True
    finally:
        integ.disable()


def test_integration_enable_idempotent_and_disable_neutralizes_dedup(
    session_provider, reset_llm_observation_flag, reset_observability_settings
):
    provider, _captured, _bsp = session_provider
    integ = MAFIntegration()

    assert integ.enable() is True
    assert integ.enabled is True
    assert integ._dedup_processor is not None
    assert integ._dedup_processor._active is True
    # The dedup processor is registered on the provider.
    procs = provider._active_span_processor._span_processors
    occurrences = sum(1 for p in procs if p is integ._dedup_processor)
    assert occurrences == 1

    # A second enable() must be idempotent: no double-wrapping, no second
    # dedup processor.
    assert integ.enable() is True
    procs = provider._active_span_processor._span_processors
    occurrences = sum(1 for p in procs if p is integ._dedup_processor)
    assert occurrences == 1

    # disable() neutralizes the dedup processor (OTEL has no removal API
    # so the processor stays attached but becomes a no-op).
    integ.disable()
    assert integ.enabled is False
    assert integ._dedup_processor._active is False
    procs = provider._active_span_processor._span_processors
    assert any(p is integ._dedup_processor for p in procs), (
        "dedup processor should remain attached after disable()"
    )

    # Re-enable: must re-activate the existing dedup processor instead of
    # adding a second one.
    assert integ.enable() is True
    assert integ._dedup_processor._active is True
    procs = provider._active_span_processor._span_processors
    occurrences = sum(1 for p in procs if p is integ._dedup_processor)
    assert occurrences == 1
    integ.disable()


def test_integration_disable_neutralizes_dedup_at_runtime(
    session_provider, reset_llm_observation_flag, reset_observability_settings
):
    """After disable(), the dedup processor's hooks must not toggle the flag."""
    integ = MAFIntegration()
    integ.enable()
    integ.disable()

    set_llm_observation_active(False)
    # Construct a real chat span via MAF's tracer so we exercise on_start/on_end
    # with a span that the processor would otherwise act on.
    enable_instrumentation()
    from agent_framework.observability import get_tracer

    tracer = get_tracer()
    with tracer.start_as_current_span("chat gpt-4") as span:
        span.set_attribute(mapping.GEN_AI_OPERATION_NAME, "chat")
    # The dedup processor is still attached but inactive; the flag must
    # therefore remain False.
    assert is_llm_observation_active() is False


def test_dedup_flag_restored_even_without_operation_attribute(
    session_provider, reset_llm_observation_flag, reset_observability_settings
):
    """Regression: on_end restores based on what on_start recorded, so a
    chat-named span missing gen_ai.operation.name cannot leave the flag
    stuck True."""
    provider, _captured, _bsp = session_provider
    proc = MAFLLMDedupSpanProcessor()
    proc.activate()

    tracer = provider.get_tracer("agent_framework.test")
    span = tracer.start_span("chat gpt-4")  # no operation attribute set
    proc.on_start(span)
    assert is_llm_observation_active() is True
    span.end()
    proc.on_end(span)
    assert is_llm_observation_active() is False


def test_enable_fails_without_wrappable_exporter(monkeypatch, reset_observability_settings):
    """Regression: enable() fails closed when translation cannot be installed,
    instead of turning on instrumentation whose spans the backend would
    reject. MAF has no off switch, so wrapping is checked before enabling."""
    bare_provider = TracerProvider()  # no span processors attached
    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: bare_provider)

    integ = MAFIntegration()
    assert integ.enable() is False
    assert integ.enabled is False
    assert integ._patched_processors == []


def test_integration_returns_false_when_provider_is_not_rhesis(
    monkeypatch, reset_observability_settings
):
    """A foreign tracer provider must yield ``enable() == False``.

    OTEL's :func:`set_tracer_provider` only honors the first call per
    process, so we patch :func:`opentelemetry.trace.get_tracer_provider`
    for the duration of this test. We patch *OTEL*, not ``agent_framework``;
    the real MAF package is still in play.
    """
    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: object())

    integ = MAFIntegration()
    assert integ.enable() is False
    assert integ.enabled is False


def test_integration_wraps_simple_span_processor_and_reverts_on_disable(
    monkeypatch, reset_observability_settings
):
    """SimpleSpanProcessor exporters must also be wrapped + reverted.

    Local/dev setups commonly attach a ``SimpleSpanProcessor`` (sync export,
    easier to debug). Without coverage here, MAF's raw GenAI span names like
    ``chat gpt-4`` would pass through untranslated and fail backend span-name
    validation. This test uses a fresh isolated ``TracerProvider`` (not the
    session one, which already has a BatchSpanProcessor attached) so we can
    assert exactly one wrap and a clean revert.
    """
    captured = InMemorySpanExporter()
    isolated_provider = TracerProvider()
    ssp = SimpleSpanProcessor(captured)
    isolated_provider.add_span_processor(ssp)

    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: isolated_provider)

    original_exporter = ssp.span_exporter
    assert original_exporter is captured

    integ = MAFIntegration()
    try:
        assert integ.enable() is True
        # The SimpleSpanProcessor's exporter is now the translating wrapper.
        assert isinstance(ssp.span_exporter, MAFTranslatingExporter)
        # The wrapper still delegates to the original in-memory exporter.
        assert ssp.span_exporter.wrapped is captured
        # The integration tracked the patch so disable() can revert it.
        assert any(p is ssp for p, _ in integ._patched_processors)
    finally:
        integ.disable()

    # After disable() the original exporter is restored.
    assert ssp.span_exporter is original_exporter
    assert not integ._patched_processors


# ---------------------------------------------------------------------------
# Translator failure path: function.maf.* fallback preserves the original name
# ---------------------------------------------------------------------------


def test_translation_failure_falls_back_to_function_maf(monkeypatch, session_provider):
    """When ``translate_span`` raises, the exporter must produce a
    ``function.maf.*`` name with ``gen_ai.original_span_name`` preserved.

    We deliberately patch the SDK's own translator function (not MAF), to
    force the exporter into its error branch.
    """
    from rhesis.sdk.telemetry.integrations.agent_framework import translator as tr_mod

    captured_inner = InMemorySpanExporter()
    wrapper = MAFTranslatingExporter(captured_inner)

    # Build a real MAF span via MAF's get_tracer.
    enable_instrumentation()
    from agent_framework.observability import get_tracer

    tracer = get_tracer()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("translation broken")

    monkeypatch.setattr(tr_mod, "translate_span", _boom)

    with tracer.start_as_current_span("chat gpt-4o") as span:
        span.set_attribute(mapping.GEN_AI_OPERATION_NAME, "chat")
        span.set_attribute(mapping.GEN_AI_REQUEST_MODEL, "gpt-4o")

    # Use the OTEL session provider's exporter to grab the span we just
    # emitted, then pipe that raw span through the wrapper directly to
    # simulate the BSP -> exporter step in isolation.
    provider, captured_session, _bsp = session_provider
    provider.force_flush()
    raw_chat_spans = [s for s in captured_session.get_finished_spans() if s.name == "chat gpt-4o"]
    captured_session.clear()
    assert raw_chat_spans, "expected to capture the raw chat span we just emitted"

    # Forward via the wrapper; with translate_span patched to raise, the
    # exporter must fall back to the function.maf.* name.
    wrapper.export(raw_chat_spans)

    out_spans = captured_inner.get_finished_spans()
    assert out_spans, "wrapper should have forwarded the fallback span"
    out = out_spans[0]
    assert out.name.startswith("function.maf."), (
        f"fallback span should land in function.maf.*; got {out.name!r}"
    )
    assert validate_span_name(out.name)
    assert out.attributes.get("gen_ai.original_span_name") == "chat gpt-4o"
    # The raw gen_ai.* attributes must still be carried for debuggability.
    assert out.attributes.get(mapping.GEN_AI_OPERATION_NAME) == "chat"


# ---------------------------------------------------------------------------
# Pure translate_span coverage on a real MAF-emitted span
# ---------------------------------------------------------------------------


def test_translate_span_on_real_maf_span(session_provider, reset_observability_settings):
    """``translate_span`` must rewrite a real MAF-tracer-emitted span.

    Builds a chat span via :func:`agent_framework.observability.get_tracer`
    (real MAF tracer wrapper) and translates it. Asserts the resulting
    name + key attributes match the Rhesis schema.
    """
    enable_instrumentation()
    from agent_framework.observability import get_tracer

    provider, captured, _bsp = session_provider
    captured.clear()
    tracer = get_tracer()
    with tracer.start_as_current_span("chat gpt-4o") as span:
        span.set_attribute(mapping.GEN_AI_OPERATION_NAME, "chat")
        span.set_attribute(mapping.GEN_AI_REQUEST_MODEL, "gpt-4o")
        span.set_attribute(mapping.GEN_AI_PROVIDER_NAME, "openai")
        span.set_attribute(mapping.GEN_AI_USAGE_INPUT_TOKENS, 7)
        span.set_attribute(mapping.GEN_AI_USAGE_OUTPUT_TOKENS, 11)
    provider.force_flush()
    real_spans = [s for s in captured.get_finished_spans() if s.name == "chat gpt-4o"]
    captured.clear()
    assert real_spans, "expected exactly one raw chat gpt-4o span"

    translated = translate_span(real_spans[0])
    assert translated.name == "ai.llm.invoke"
    a = translated.attributes
    assert a.get(AIAttributes.MODEL_NAME) == "gpt-4o"
    assert a.get(AIAttributes.MODEL_PROVIDER) == "openai"
    assert a.get(AIAttributes.LLM_TOKENS_INPUT) == 7
    assert a.get(AIAttributes.LLM_TOKENS_OUTPUT) == 11
    assert a.get(AIAttributes.LLM_TOKENS_TOTAL) == 18
    assert a.get(AIAttributes.OPERATION_TYPE) == AIAttributes.OPERATION_LLM_INVOKE


def test_dedup_processor_inactive_until_activated(reset_llm_observation_flag):
    """A freshly constructed dedup processor must do nothing until activated."""
    set_llm_observation_active(False)
    proc = MAFLLMDedupSpanProcessor()
    # Build a real MAF span, but do NOT activate the processor.
    enable_instrumentation()
    from agent_framework.observability import get_tracer

    tracer = get_tracer()
    with tracer.start_as_current_span("chat gpt-4") as span:
        span.set_attribute(mapping.GEN_AI_OPERATION_NAME, "chat")
        proc.on_start(span)
        # No activate() call means the hook must short-circuit.
        assert is_llm_observation_active() is False
    proc.on_end(span)
    assert is_llm_observation_active() is False
