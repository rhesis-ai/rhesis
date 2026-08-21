"""Tests for ``rhesis.telemetry.conversation_turn``.

The primitive exists for one reason: an app whose reply is composed from a tool
result or from its own code holds that text only *after* the agent framework's run
span has ended, so nothing downstream can recover it. These tests pin the contract
that makes it usable — one turn root per exchange, the reply recorded, the turns of
a conversation on one trace, and complete silence when something above already owns
the turn.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rhesis.telemetry.attributes import validate_span_name
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import (
    get_conversation_id,
    get_conversation_trace_id,
    get_root_trace_id,
    set_conversation_id,
    set_conversation_trace_id,
    set_root_trace_id,
    set_tracing_disabled,
)
from rhesis.telemetry.conversation import (
    DEFAULT_TURN_SPAN_NAME,
    build_conversation_parent_context,
    conversation_turn,
)

ATTRS = ConversationContext.SpanAttributes


@pytest.fixture(scope="module")
def provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Ride on the global provider; OTEL honours only the first ``set_tracer_provider``."""
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
def reset_context():
    """Keep the conversation contextvars from leaking between tests."""
    yield
    set_conversation_id(None)
    set_conversation_trace_id(None)
    set_root_trace_id(None)
    set_tracing_disabled(False)


def turn_roots(exported):
    return [s for s in exported if (s.attributes or {}).get(ATTRS.IS_TURN_ROOT)]


class TestTurnRoot:
    def test_records_the_conversation_and_both_sides_of_the_turn(self, spans):
        with conversation_turn("conv-1", input="what is the weather?") as turn:
            turn.output = "It is 20C."

        roots = turn_roots(spans())
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert roots[0].name == DEFAULT_TURN_SPAN_NAME
        assert attributes[ATTRS.CONVERSATION_ID] == "conv-1"
        assert attributes[ATTRS.CONVERSATION_INPUT] == "what is the weather?"
        assert attributes[ATTRS.CONVERSATION_OUTPUT] == "It is 20C."

    def test_the_reply_may_be_set_at_the_very_end_of_the_block(self, spans):
        """The whole point: the span outlives whatever produced the reply."""
        with conversation_turn("conv-1", input="hi") as turn:
            # Stands in for an agent run that has already finished and closed its
            # own spans by the time the app knows what to say.
            turn.output = "composed after the run"

        assert turn_roots(spans())[0].attributes[ATTRS.CONVERSATION_OUTPUT] == (
            "composed after the run"
        )

    def test_a_turn_with_no_reply_still_records_the_input(self, spans):
        with conversation_turn("conv-1", input="hi"):
            pass

        attributes = turn_roots(spans())[0].attributes
        assert attributes[ATTRS.CONVERSATION_INPUT] == "hi"
        assert ATTRS.CONVERSATION_OUTPUT not in attributes

    def test_the_span_name_is_accepted_by_the_backend(self, spans):
        """A name outside ai.*/function.* is rejected with HTTP 422 and dropped."""
        with conversation_turn("conv-1", input="hi", name="function.my_agent_turn") as turn:
            turn.output = "ok"

        exported = spans()
        assert [s.name for s in exported] == ["function.my_agent_turn"]
        assert validate_span_name(DEFAULT_TURN_SPAN_NAME)
        assert all(validate_span_name(s.name) for s in exported)

    def test_long_text_is_truncated(self, spans):
        limit = ConversationContext.MAX_IO_LENGTH
        with conversation_turn("conv-1", input="a" * (limit + 500)) as turn:
            turn.output = "b" * (limit + 500)

        attributes = turn_roots(spans())[0].attributes
        assert len(attributes[ATTRS.CONVERSATION_INPUT]) == limit
        assert len(attributes[ATTRS.CONVERSATION_OUTPUT]) == limit

    def test_the_conversation_id_is_bound_inside_and_restored_after(self, spans):
        set_conversation_id("outer")
        with conversation_turn("conv-1", input="hi"):
            assert get_conversation_id() == "conv-1"
        assert get_conversation_id() == "outer"

    def test_an_exception_still_closes_the_turn(self, spans):
        with pytest.raises(RuntimeError):
            with conversation_turn("conv-1", input="hi") as turn:
                turn.output = "partial"
                raise RuntimeError("agent blew up")

        # The span is still exported, with whatever was recorded before the failure.
        assert turn_roots(spans())[0].attributes[ATTRS.CONVERSATION_OUTPUT] == "partial"
        assert get_conversation_id() is None
        assert get_root_trace_id() is None


class TestTraceJoining:
    def test_turns_of_one_conversation_share_a_trace(self, spans):
        for index in range(3):
            with conversation_turn("conv-join", input=f"turn {index}") as turn:
                turn.output = f"reply {index}"

        exported = spans()
        assert len({s.context.trace_id for s in exported}) == 1
        assert len(turn_roots(exported)) == 3

    def test_the_first_turn_keeps_its_own_trace_id(self, spans):
        """So anything that already published an id for turn 1 still resolves."""
        with conversation_turn("conv-anchor", input="one") as turn:
            first = turn.trace_id
        with conversation_turn("conv-anchor", input="two") as turn:
            assert turn.trace_id == first

    def test_two_conversations_do_not_collide(self, spans):
        with conversation_turn("conv-a", input="hi") as turn:
            first = turn.trace_id
        with conversation_turn("conv-b", input="hi") as turn:
            assert turn.trace_id != first

    def test_later_turns_hang_off_the_strippable_placeholder(self, spans):
        """The exporter turns that parent back into a root span."""
        with conversation_turn("conv-parent", input="one"):
            pass
        captured_first = spans()
        assert captured_first[0].parent is None

        with conversation_turn("conv-parent", input="two"):
            pass
        second = [s for s in spans() if s.name == DEFAULT_TURN_SPAN_NAME][-1]
        assert second.parent is not None
        assert second.parent.span_id == ConversationContext.SYNTHETIC_PARENT_SPAN_ID

    def test_a_platform_supplied_trace_id_is_adopted(self, spans):
        """An unseen conversation resumed from a persisted trace id joins it."""
        set_conversation_trace_id("ab" * 16)
        with conversation_turn("conv-resumed", input="hi") as turn:
            assert turn.trace_id == "ab" * 16

    def test_the_conversation_trace_id_is_published_for_nested_integrations(self, spans):
        with conversation_turn("conv-publish", input="hi") as turn:
            assert get_conversation_trace_id() == turn.trace_id
            assert get_root_trace_id() == turn.trace_id
        assert get_conversation_trace_id() is None
        assert get_root_trace_id() is None


class TestStandsDown:
    def test_no_span_when_a_rhesis_root_already_owns_the_turn(self, spans, provider_and_exporter):
        """Two spans claiming is_turn_root detaches one subtree into a phantom turn."""
        provider, _captured = provider_and_exporter
        tracer = provider.get_tracer("rhesis.sdk")

        with tracer.start_as_current_span("function.my_endpoint") as endpoint_span:
            set_root_trace_id(format(endpoint_span.get_span_context().trace_id, "032x"))
            endpoint_span.set_attribute(ATTRS.IS_TURN_ROOT, True)
            endpoint_span.set_attribute(ATTRS.CONVERSATION_ID, "conv-served")
            with conversation_turn("conv-served", input="hi") as turn:
                assert turn.trace_id is None
                turn.output = "reply"

        exported = spans()
        assert not any(s.name == DEFAULT_TURN_SPAN_NAME for s in exported)
        assert len(turn_roots(exported)) == 1
        assert turn_roots(exported)[0].name == "function.my_endpoint"

    def test_the_conversation_id_is_still_bound_when_standing_down(self, spans):
        set_root_trace_id("cd" * 16)
        with conversation_turn("conv-served", input="hi"):
            assert get_conversation_id() == "conv-served"
        assert not spans()

    def test_no_span_when_tracing_is_disabled(self, spans):
        set_tracing_disabled(True)
        with conversation_turn("conv-off", input="hi") as turn:
            assert turn.trace_id is None
            turn.output = "reply"
        assert not spans()

    def test_the_turn_object_is_always_usable(self, spans):
        """App code must never have to branch on whether tracing is configured."""
        set_tracing_disabled(True)
        with conversation_turn("conv-off", input="hi") as turn:
            turn.output = "reply"
            assert turn.conversation_id == "conv-off"
            assert turn.input == "hi"


class TestParentContextBuilder:
    def test_builds_a_context_carrying_the_conversation_trace(self):
        context = build_conversation_parent_context("ab" * 16)
        span_context = otel_trace.get_current_span(context).get_span_context()
        assert span_context.trace_id == int("ab" * 16, 16)
        assert span_context.span_id == ConversationContext.SYNTHETIC_PARENT_SPAN_ID
        assert span_context.trace_flags.sampled

    @pytest.mark.parametrize("value", ["", "not-hex", "00" * 16, None])
    def test_an_unusable_id_yields_no_context(self, value):
        """Better a fresh trace than a span on trace id zero, which OTEL rejects."""
        assert build_conversation_parent_context(value) is None
