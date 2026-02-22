"""Tests for conversation-based tracing across the SDK telemetry stack.

Tests cover:
- Context variables (set/get conversation_id, conversation_trace_id)
- Tracer: synthetic parent context, turn-root attributes, trace_id reuse
- Exporter: parent_span_id stripping, conversation_id propagation
- Executor: extraction of _rhesis_conversation_context from inputs
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags

from rhesis.sdk.telemetry.constants import ConversationContext as ConvCtx
from rhesis.sdk.telemetry.context import (
    get_conversation_id,
    get_conversation_trace_id,
    set_conversation_id,
    set_conversation_trace_id,
)
from rhesis.sdk.telemetry.exporter import RhesisOTLPExporter
from rhesis.sdk.telemetry.tracer import Tracer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_span(
    trace_id: int,
    span_id: int,
    parent_span_id: int | None = None,
    name: str = "function.chat",
    attributes: dict | None = None,
) -> MagicMock:
    """Create a mock ReadableSpan with the given IDs and attributes."""
    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    mock = MagicMock(spec=ReadableSpan)
    mock.context = span_context
    if parent_span_id is not None:
        parent_ctx = SpanContext(
            trace_id=trace_id,
            span_id=parent_span_id,
            is_remote=True,
        )
        mock.parent = parent_ctx
    else:
        mock.parent = None
    mock.name = name
    mock.kind = SpanKind.INTERNAL
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
    mock.start_time = now_ns
    mock.end_time = now_ns + 100_000_000  # +100ms
    mock.status = Status(StatusCode.OK)
    mock.attributes = attributes or {}
    mock.events = []
    mock.links = []
    mock.resource = None
    return mock


def _make_exporter() -> RhesisOTLPExporter:
    return RhesisOTLPExporter(
        api_key="test-key",
        base_url="http://localhost:8080",
        project_id="test-project",
        environment="test",
    )


# ---------------------------------------------------------------------------
# Context variable tests
# ---------------------------------------------------------------------------


class TestConversationContextVars:
    """Test conversation context variable get/set."""

    def test_conversation_id_default_none(self):
        set_conversation_id(None)
        assert get_conversation_id() is None

    def test_set_get_conversation_id(self):
        set_conversation_id("conv-abc-123")
        assert get_conversation_id() == "conv-abc-123"
        set_conversation_id(None)

    def test_conversation_trace_id_default_none(self):
        set_conversation_trace_id(None)
        assert get_conversation_trace_id() is None

    def test_set_get_conversation_trace_id(self):
        tid = "a" * 32
        set_conversation_trace_id(tid)
        assert get_conversation_trace_id() == tid
        set_conversation_trace_id(None)


# ---------------------------------------------------------------------------
# Exporter tests
# ---------------------------------------------------------------------------


class TestExporterConversation:
    """Test exporter conversation span handling."""

    def test_turn_root_parent_stripped(self):
        """Turn-root span should have parent_span_id set to None."""
        exporter = _make_exporter()
        trace_id = int("aa" * 16, 16)
        synthetic_parent_id = 0xDEADBEEF

        span = _make_mock_span(
            trace_id=trace_id,
            span_id=0x1234,
            parent_span_id=synthetic_parent_id,
            attributes={
                ConvCtx.SpanAttributes.IS_TURN_ROOT: True,
                ConvCtx.SpanAttributes.CONVERSATION_ID: "session-xyz",
            },
        )

        batch = exporter._convert_spans([span])
        assert len(batch.spans) == 1
        converted = batch.spans[0]
        assert converted.parent_span_id is None
        assert converted.conversation_id == "session-xyz"

    def test_child_span_inherits_conversation_id(self):
        """Child span sharing trace_id with a turn root inherits conversation_id."""
        exporter = _make_exporter()
        trace_id = int("bb" * 16, 16)

        root = _make_mock_span(
            trace_id=trace_id,
            span_id=0x1111,
            parent_span_id=0xDEADBEEF,
            name="function.chat",
            attributes={
                ConvCtx.SpanAttributes.IS_TURN_ROOT: True,
                ConvCtx.SpanAttributes.CONVERSATION_ID: "conv-42",
            },
        )
        child = _make_mock_span(
            trace_id=trace_id,
            span_id=0x2222,
            parent_span_id=0x1111,
            name="ai.llm.invoke",
            attributes={"ai.operation.type": "llm.invoke"},
        )

        batch = exporter._convert_spans([root, child])
        assert batch.spans[0].conversation_id == "conv-42"
        assert batch.spans[1].conversation_id == "conv-42"

    def test_non_conversation_span_has_no_conversation_id(self):
        """Span without conversation attributes should have conversation_id=None."""
        exporter = _make_exporter()
        span = _make_mock_span(
            trace_id=int("cc" * 16, 16),
            span_id=0x3333,
            attributes={"some.attr": "value"},
        )

        batch = exporter._convert_spans([span])
        assert batch.spans[0].conversation_id is None

    @patch("rhesis.sdk.telemetry.exporter.requests.Session.post")
    def test_conversation_span_export_roundtrip(self, mock_post):
        """Conversation span exports successfully with conversation_id in payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        exporter = _make_exporter()
        trace_id = int("dd" * 16, 16)

        span = _make_mock_span(
            trace_id=trace_id,
            span_id=0x4444,
            parent_span_id=0xDEADBEEF,
            attributes={
                ConvCtx.SpanAttributes.IS_TURN_ROOT: True,
                ConvCtx.SpanAttributes.CONVERSATION_ID: "session-export-test",
            },
        )

        result = exporter.export([span])
        assert result == SpanExportResult.SUCCESS

        call_kwargs = mock_post.call_args[1]
        json_data = call_kwargs["json"]
        exported_span = json_data["spans"][0]
        assert exported_span["conversation_id"] == "session-export-test"
        assert exported_span["parent_span_id"] is None


# ---------------------------------------------------------------------------
# Tracer tests
# ---------------------------------------------------------------------------


class TestTracerConversation:
    """Test tracer conversation context handling."""

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_build_conversation_parent_context(self, mock_get_provider):
        """_build_conversation_parent_context creates valid OTEL context."""
        mock_provider = MagicMock()
        mock_provider.get_tracer.return_value = MagicMock()
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        conv_trace_id = "a" * 32
        ctx = tracer._build_conversation_parent_context(conv_trace_id)
        assert ctx is not None

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_build_conversation_parent_context_invalid_id(self, mock_get_provider):
        """Invalid trace_id returns None."""
        mock_provider = MagicMock()
        mock_provider.get_tracer.return_value = MagicMock()
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        ctx = tracer._build_conversation_parent_context("not-hex")
        assert ctx is None

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_conversation_turn_root_attributes_set(self, mock_get_provider):
        """When conversation context is active, turn-root attributes are set on root span."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        # Set conversation context
        set_conversation_id("conv-turn-root")
        set_conversation_trace_id("a" * 32)

        try:
            result = tracer.trace_execution("chat", lambda: "hello", (), {})
            assert result == "hello"

            # Verify IS_TURN_ROOT and CONVERSATION_ID attributes were set
            set_attr_calls = {
                call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list
            }
            assert set_attr_calls.get(ConvCtx.SpanAttributes.IS_TURN_ROOT) is True
            assert set_attr_calls.get(ConvCtx.SpanAttributes.CONVERSATION_ID) == "conv-turn-root"
        finally:
            set_conversation_id(None)
            set_conversation_trace_id(None)

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_no_conversation_context_no_attributes(self, mock_get_provider):
        """Without conversation context, no turn-root attributes are set."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        # Ensure no conversation context
        set_conversation_id(None)
        set_conversation_trace_id(None)

        tracer.trace_execution("func", lambda: "ok", (), {})

        attr_names = [call[0][0] for call in mock_span.set_attribute.call_args_list]
        assert ConvCtx.SpanAttributes.IS_TURN_ROOT not in attr_names
        assert ConvCtx.SpanAttributes.CONVERSATION_ID not in attr_names


# ---------------------------------------------------------------------------
# Executor tests
# ---------------------------------------------------------------------------


class TestExecutorConversation:
    """Test executor conversation context extraction."""

    def test_conversation_context_extracted_and_cleared(self):
        """Executor extracts conversation context and clears it after execution."""
        from rhesis.sdk.connector.executor import TestExecutor

        executor = TestExecutor()

        # Track what context vars were set during execution
        captured_conv_id = None
        captured_trace_id = None

        def mock_func(prompt="hello"):
            nonlocal captured_conv_id, captured_trace_id
            captured_conv_id = get_conversation_id()
            captured_trace_id = get_conversation_trace_id()
            return "response"

        inputs = {
            "prompt": "hello",
            ConvCtx.CONTEXT_KEY: {
                ConvCtx.Fields.CONVERSATION_ID: "session-exec-test",
                ConvCtx.Fields.TRACE_ID: "b" * 32,
            },
        }

        result = asyncio.get_event_loop().run_until_complete(
            executor.execute(mock_func, "mock_func", inputs)
        )

        assert result["status"] == "success"
        assert captured_conv_id == "session-exec-test"
        assert captured_trace_id == "b" * 32
        # Context should be cleared after execution
        assert get_conversation_id() is None
        assert get_conversation_trace_id() is None

    def test_conversation_context_not_passed_to_function(self):
        """The _rhesis_conversation_context key should be popped from inputs."""
        from rhesis.sdk.connector.executor import TestExecutor

        executor = TestExecutor()

        received_kwargs = {}

        def mock_func(**kwargs):
            received_kwargs.update(kwargs)
            return "ok"

        inputs = {
            "prompt": "hello",
            ConvCtx.CONTEXT_KEY: {
                ConvCtx.Fields.CONVERSATION_ID: "abc",
                ConvCtx.Fields.TRACE_ID: None,
            },
        }

        asyncio.get_event_loop().run_until_complete(
            executor.execute(mock_func, "mock_func", inputs)
        )

        assert ConvCtx.CONTEXT_KEY not in received_kwargs
        assert "prompt" in received_kwargs

    def test_no_conversation_context_no_error(self):
        """Executor works fine without conversation context."""
        from rhesis.sdk.connector.executor import TestExecutor

        executor = TestExecutor()

        result = asyncio.get_event_loop().run_until_complete(
            executor.execute(lambda: "ok", "simple", {})
        )
        assert result["status"] == "success"
        assert result["output"] == "ok"

    def test_conversation_context_cleared_on_error(self):
        """Conversation context is cleared even when function raises."""
        from rhesis.sdk.connector.executor import TestExecutor

        executor = TestExecutor()

        def failing_func():
            raise RuntimeError("boom")

        inputs = {
            ConvCtx.CONTEXT_KEY: {
                ConvCtx.Fields.CONVERSATION_ID: "err-conv",
                ConvCtx.Fields.TRACE_ID: "c" * 32,
            },
        }

        result = asyncio.get_event_loop().run_until_complete(
            executor.execute(failing_func, "failing", inputs)
        )

        assert result["status"] == "error"
        assert get_conversation_id() is None
        assert get_conversation_trace_id() is None
