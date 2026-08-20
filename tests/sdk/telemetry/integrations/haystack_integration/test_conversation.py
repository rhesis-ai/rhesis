"""Tests for RhesisTracing: conversation grouping for apps that own their own loop."""

import pytest

pytest.importorskip("haystack")

from haystack import Pipeline, component  # noqa: E402
from rhesis.telemetry.constants import ConversationContext  # noqa: E402
from rhesis.telemetry.context import get_root_trace_id  # noqa: E402

from rhesis.sdk.telemetry.integrations.haystack.conversation import (  # noqa: E402
    DEFAULT_TURN_SPAN_NAME,
    ConversationTurn,
    RhesisTracing,
    _conversation_parent_context,
)
from rhesis.sdk.telemetry.integrations.haystack.integration import (  # noqa: E402
    HaystackIntegration,
)

CONV = ConversationContext.SpanAttributes


@component
class Echo:
    @component.output_types(out=str)
    def run(self, q: str) -> dict:
        return {"out": q}


def echo_pipeline():
    pipe = Pipeline()
    pipe.add_component("echo", Echo())
    return pipe


def turn_spans(exporter):
    return [s for s in exporter.get_finished_spans() if s.name == DEFAULT_TURN_SPAN_NAME]


class TestSetup:
    def test_disabled_by_the_caller_is_inert(self, sdk_provider):
        tracing = RhesisTracing("app", enabled=False)
        assert tracing.enabled is False

    def test_disabled_without_an_api_key(self, sdk_provider, monkeypatch):
        monkeypatch.delenv("RHESIS_API_KEY", raising=False)
        tracing = RhesisTracing("app")
        assert tracing.enabled is False

    def test_enabled_when_a_provider_and_key_exist(self, sdk_provider):
        tracing = RhesisTracing("app")
        assert tracing.enabled is True

    def test_never_raises_when_enabling_fails(self, sdk_provider, monkeypatch):
        """Tracing is not in the application's data path, so it must cost nothing when broken."""

        def boom(self):
            raise RuntimeError("boom")

        # Patched on the class object, not via a dotted string: the integrations package binds the
        # name ``haystack`` to the integration singleton, so a dotted path through it does not
        # resolve to this module.
        monkeypatch.setattr(HaystackIntegration, "enable", boom)
        tracing = RhesisTracing("app")
        assert tracing.enabled is False

    def test_the_trace_name_is_passed_through(self, sdk_provider):
        tracing = RhesisTracing("My Assistant")
        assert tracing.enabled is True
        assert tracing._tracer._name == "My Assistant"

    def test_turn_span_name_can_be_overridden(self, sdk_provider):
        tracing = RhesisTracing("app", turn_span_name="function.haystack.exchange")
        assert tracing.turn_span_name == "function.haystack.exchange"


class TestInertTurn:
    def test_turn_yields_a_handle_with_no_span(self, sdk_provider):
        tracing = RhesisTracing("app", enabled=False)
        with tracing.turn("hello") as turn:
            turn.output = "world"
        assert isinstance(turn, ConversationTurn)
        assert turn.span is None
        assert turn.output == "world"

    def test_flush_is_safe(self, sdk_provider):
        RhesisTracing("app", enabled=False).flush()

    def test_start_conversation_is_safe(self, sdk_provider):
        RhesisTracing("app", enabled=False).start_conversation("c-1")


class TestTurnRecording:
    def test_turn_records_input_output_and_conversation_id(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        with tracing.turn("what is the weather?") as turn:
            turn.output = "sunny"

        span = turn_spans(exporter)[0]
        assert span.attributes[CONV.IS_TURN_ROOT] is True
        assert span.attributes[CONV.CONVERSATION_ID] == "conv-1"
        assert span.attributes[CONV.CONVERSATION_INPUT] == "what is the weather?"
        assert span.attributes[CONV.CONVERSATION_OUTPUT] == "sunny"

    def test_turn_without_output_records_no_output(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        with tracing.turn("hello"):
            pass
        assert CONV.CONVERSATION_OUTPUT not in turn_spans(exporter)[0].attributes

    def test_input_and_output_are_truncated(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        limit = ConversationContext.MAX_IO_LENGTH
        with tracing.turn("i" * (limit + 500)) as turn:
            turn.output = "o" * (limit + 500)
        span = turn_spans(exporter)[0]
        assert len(span.attributes[CONV.CONVERSATION_INPUT]) == limit
        assert len(span.attributes[CONV.CONVERSATION_OUTPUT]) == limit

    def test_extra_invocation_context_reaches_the_turn(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1", test_run_id="run-9")
        with tracing.turn("hello"):
            echo_pipeline().run({"echo": {"q": "hello"}})

        # The pipeline's own spans pick the metadata up from the ContextVar.
        pipeline_spans = [
            s for s in exporter.get_finished_spans() if s.name.startswith("function.haystack.p")
        ]
        assert pipeline_spans
        assert pipeline_spans[0].attributes["rhesis.test.run_id"] == "run-9"


class TestTurnOwnership:
    def test_the_turn_owns_the_root_and_restores_it(self, sdk_provider):
        tracing = RhesisTracing("app")
        assert get_root_trace_id() is None
        with tracing.turn("hello"):
            assert get_root_trace_id() is not None
        assert get_root_trace_id() is None

    def test_the_pipeline_root_nests_under_the_turn(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        with tracing.turn("hello") as turn:
            echo_pipeline().run({"echo": {"q": "hello"}})
            turn.output = "hello"

        spans = {s.name: s for s in exporter.get_finished_spans()}
        turn_span = spans[DEFAULT_TURN_SPAN_NAME]
        pipeline_span = spans["function.haystack.pipeline.run"]
        assert pipeline_span.parent.span_id == turn_span.context.span_id
        # Exactly one span per turn may claim it, and here that is the turn, not the pipeline.
        assert CONV.IS_TURN_ROOT not in pipeline_span.attributes

    def test_the_pipeline_does_not_restate_the_turn_text(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        with tracing.turn("hello") as turn:
            echo_pipeline().run({"echo": {"q": "hello"}})
            turn.output = "hello"
        pipeline_span = next(
            s for s in exporter.get_finished_spans() if s.name == "function.haystack.pipeline.run"
        )
        assert CONV.CONVERSATION_INPUT not in pipeline_span.attributes
        assert CONV.CONVERSATION_OUTPUT not in pipeline_span.attributes


class TestConversationContinuity:
    def test_turns_in_one_conversation_share_a_trace(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        for message in ("first", "second", "third"):
            with tracing.turn(message) as turn:
                turn.output = f"reply to {message}"

        spans = turn_spans(exporter)
        assert len(spans) == 3
        assert len({s.context.trace_id for s in spans}) == 1

    def test_later_turns_hang_off_the_synthetic_parent(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        with tracing.turn("first"):
            pass
        with tracing.turn("second"):
            pass

        first, second = turn_spans(exporter)
        assert first.parent is None
        # The exporter strips this placeholder, so the turn is still stored as a root span.
        assert second.parent.span_id == ConversationContext.SYNTHETIC_PARENT_SPAN_ID

    def test_a_new_conversation_starts_a_new_trace(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        with tracing.turn("hello"):
            pass
        tracing.start_conversation("conv-2")
        with tracing.turn("hello again"):
            pass

        spans = turn_spans(exporter)
        assert len({s.context.trace_id for s in spans}) == 2

    def test_inner_spans_join_the_turn_trace(self, sdk_provider):
        exporter, _ = sdk_provider
        tracing = RhesisTracing("app")
        tracing.start_conversation("conv-1")
        with tracing.turn("first"):
            echo_pipeline().run({"echo": {"q": "a"}})
        with tracing.turn("second"):
            echo_pipeline().run({"echo": {"q": "b"}})

        trace_ids = {s.context.trace_id for s in exporter.get_finished_spans()}
        assert len(trace_ids) == 1


class TestConversationParentContext:
    def test_bad_trace_id_is_rejected_without_raising(self, caplog):
        with caplog.at_level("WARNING"):
            assert _conversation_parent_context("not-hex") is None
        assert "Invalid conversation trace id" in caplog.text

    def test_valid_trace_id_builds_a_context(self):
        assert _conversation_parent_context("a" * 32) is not None
