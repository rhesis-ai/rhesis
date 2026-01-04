"""Tests for telemetry Pydantic schemas."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from rhesis.sdk.telemetry.schemas import (
    FORBIDDEN_SPAN_DOMAINS,
    AILLMAttributes,
    AIOperationType,
    AIToolAttributes,
    OTELSpan,
    OTELTraceBatch,
    SpanEvent,
    SpanKind,
    SpanLink,
    StatusCode,
    TraceIngestResponse,
)


class TestSpanKind:
    """Tests for SpanKind enum."""

    def test_span_kind_values(self):
        """Test all span kind values are valid."""
        assert SpanKind.INTERNAL == "INTERNAL"
        assert SpanKind.CLIENT == "CLIENT"
        assert SpanKind.SERVER == "SERVER"
        assert SpanKind.PRODUCER == "PRODUCER"
        assert SpanKind.CONSUMER == "CONSUMER"


class TestStatusCode:
    """Tests for StatusCode enum."""

    def test_status_code_values(self):
        """Test all status code values are valid."""
        assert StatusCode.UNSET == "UNSET"
        assert StatusCode.OK == "OK"
        assert StatusCode.ERROR == "ERROR"


class TestAIOperationType:
    """Tests for AIOperationType enum."""

    def test_ai_operation_types(self):
        """Test primitive AI operation types."""
        assert AIOperationType.LLM_INVOKE == "ai.llm.invoke"
        assert AIOperationType.TOOL_INVOKE == "ai.tool.invoke"
        assert AIOperationType.RETRIEVAL == "ai.retrieval"
        assert AIOperationType.EMBEDDING_GENERATE == "ai.embedding.generate"


class TestSpanEvent:
    """Tests for SpanEvent model."""

    def test_span_event_creation(self):
        """Test creating a span event."""
        event = SpanEvent(
            name="ai.prompt",
            timestamp=datetime.now(timezone.utc),
            attributes={"prompt": "test"},
        )
        assert event.name == "ai.prompt"
        assert event.attributes["prompt"] == "test"

    def test_span_event_minimal(self):
        """Test span event with minimal fields."""
        event = SpanEvent(name="test", timestamp=datetime.now(timezone.utc))
        assert event.attributes == {}


class TestSpanLink:
    """Tests for SpanLink model."""

    def test_span_link_creation(self):
        """Test creating a span link."""
        link = SpanLink(trace_id="a" * 32, span_id="b" * 16, attributes={"type": "parent"})
        assert link.trace_id == "a" * 32
        assert link.span_id == "b" * 16


class TestOTELSpan:
    """Tests for OTELSpan model."""

    def test_valid_span(self):
        """Test creating a valid span."""
        now = datetime.now(timezone.utc)
        span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test-project",
            environment="development",
            span_name="ai.llm.invoke",
            start_time=now,
            end_time=now,
        )
        assert span.trace_id == "a" * 32
        assert span.span_id == "b" * 16
        assert span.span_name == "ai.llm.invoke"

    def test_trace_id_validation_invalid_length(self):
        """Test trace ID validation rejects invalid length."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="32-character hex string"):
            OTELSpan(
                trace_id="short",
                span_id="b" * 16,
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=now,
            )

    def test_trace_id_validation_invalid_chars(self):
        """Test trace ID validation rejects non-hex chars."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="32-character hex string"):
            OTELSpan(
                trace_id="z" * 32,
                span_id="b" * 16,
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=now,
            )

    def test_span_id_validation(self):
        """Test span ID validation."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="16-character hex string"):
            OTELSpan(
                trace_id="a" * 32,
                span_id="short",
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=now,
            )

    def test_span_name_validation_valid_ai_pattern(self):
        """Test span name accepts valid ai.* patterns."""
        now = datetime.now(timezone.utc)
        valid_names = [
            "ai.llm.invoke",
            "ai.tool.invoke",
            "ai.retrieval",
            "ai.embedding.generate",
        ]
        for name in valid_names:
            span = OTELSpan(
                trace_id="a" * 32,
                span_id="b" * 16,
                project_id="test",
                span_name=name,
                start_time=now,
                end_time=now,
            )
            assert span.span_name == name

    def test_span_name_validation_valid_function_pattern(self):
        """Test span name accepts function.* pattern."""
        now = datetime.now(timezone.utc)
        span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test",
            span_name="function.process_data",
            start_time=now,
            end_time=now,
        )
        assert span.span_name == "function.process_data"

    def test_span_name_validation_rejects_framework_concepts(self):
        """Test span name rejects framework concepts."""
        now = datetime.now(timezone.utc)
        # Generate test cases from the constant to ensure they stay in sync
        forbidden_names = [f"ai.{domain}.run" for domain in FORBIDDEN_SPAN_DOMAINS]
        for name in forbidden_names:
            with pytest.raises(ValidationError, match="cannot use framework concept"):
                OTELSpan(
                    trace_id="a" * 32,
                    span_id="b" * 16,
                    project_id="test",
                    span_name=name,
                    start_time=now,
                    end_time=now,
                )

    def test_span_name_validation_rejects_invalid_pattern(self):
        """Test span name rejects invalid patterns."""
        now = datetime.now(timezone.utc)
        invalid_names = ["invalid", "test.name", "llm.invoke"]
        for name in invalid_names:
            with pytest.raises(ValidationError, match="must follow"):
                OTELSpan(
                    trace_id="a" * 32,
                    span_id="b" * 16,
                    project_id="test",
                    span_name=name,
                    start_time=now,
                    end_time=now,
                )

    def test_timing_validation(self):
        """Test end_time must be after start_time."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="end_time must be after start_time"):
            OTELSpan(
                trace_id="a" * 32,
                span_id="b" * 16,
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )


class TestOTELTraceBatch:
    """Tests for OTELTraceBatch model."""

    def test_valid_batch(self):
        """Test creating a valid trace batch."""
        now = datetime.now(timezone.utc)
        span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test",
            span_name="ai.llm.invoke",
            start_time=now,
            end_time=now,
        )
        batch = OTELTraceBatch(spans=[span])
        assert len(batch.spans) == 1

    def test_batch_validation_min_length(self):
        """Test batch must contain at least one span."""
        with pytest.raises(ValidationError):
            OTELTraceBatch(spans=[])

    def test_batch_validation_max_length(self):
        """Test batch cannot exceed 1000 spans."""
        now = datetime.now(timezone.utc)
        spans = [
            OTELSpan(
                trace_id="a" * 32,
                span_id=f"{i:016x}",
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=now,
            )
            for i in range(1001)
        ]
        with pytest.raises(ValidationError):
            OTELTraceBatch(spans=spans)


class TestTraceIngestResponse:
    """Tests for TraceIngestResponse model."""

    def test_trace_response_creation(self):
        """Test creating a trace response."""
        response = TraceIngestResponse(status="received", span_count=5, trace_id="a" * 32)
        assert response.status == "received"
        assert response.span_count == 5


class TestAILLMAttributes:
    """Tests for AILLMAttributes model."""

    def test_llm_attributes_creation(self):
        """Test creating LLM attributes."""
        attrs = AILLMAttributes(
            model_provider="openai",
            model_name="gpt-4",
            tokens_input=100,
            tokens_output=50,
        )
        assert attrs.model_provider == "openai"
        assert attrs.model_name == "gpt-4"
        assert attrs.tokens_input == 100


class TestAIToolAttributes:
    """Tests for AIToolAttributes model."""

    def test_tool_attributes_creation(self):
        """Test creating tool attributes."""
        attrs = AIToolAttributes(tool_name="weather_api", tool_type="http")
        assert attrs.tool_name == "weather_api"
        assert attrs.tool_type == "http"
