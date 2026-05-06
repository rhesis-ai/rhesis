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
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from rhesis.sdk.telemetry.attributes import AIAttributes, validate_span_name  # noqa: E402
from rhesis.sdk.telemetry.context import (  # noqa: E402
    is_llm_observation_active,
    set_llm_observation_active,
)
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
# Lifecycle: enable / disable / idempotency / non-Rhesis provider
# ---------------------------------------------------------------------------


def test_integration_singleton_is_stable():
    assert get_integration() is get_integration()


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
