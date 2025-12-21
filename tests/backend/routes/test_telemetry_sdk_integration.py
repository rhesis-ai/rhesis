"""Integration tests for backend using SDK telemetry schemas."""

from datetime import datetime, timezone

import pytest

from rhesis.backend.app.schemas.telemetry import (
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

# Verify that backend schemas are imported from SDK
from rhesis.sdk.telemetry.schemas import (
    OTELSpan as SDKOTELSpan,
)
from rhesis.sdk.telemetry.schemas import (
    OTELTraceBatch as SDKOTELTraceBatch,
)


class TestBackendSchemaImports:
    """Test that backend imports SDK schemas correctly."""

    def test_backend_uses_sdk_otelspan(self):
        """Test that backend OTELSpan is the SDK schema."""
        assert OTELSpan is SDKOTELSpan

    def test_backend_uses_sdk_oteltrace_batch(self):
        """Test that backend OTELTraceBatch is the SDK schema."""
        assert OTELTraceBatch is SDKOTELTraceBatch

    def test_backend_can_create_sdk_span(self):
        """Test that backend can create spans using SDK schema."""
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
        assert span.span_name == "ai.llm.invoke"

    def test_backend_can_validate_sdk_span_names(self):
        """Test that backend enforces SDK span name validation."""
        now = datetime.now(timezone.utc)

        # Valid span name should work
        valid_span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test",
            span_name="ai.llm.invoke",
            start_time=now,
            end_time=now,
        )
        assert valid_span.span_name == "ai.llm.invoke"

        # Invalid span name should be rejected
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="cannot use framework concept"):
            OTELSpan(
                trace_id="a" * 32,
                span_id="b" * 16,
                project_id="test",
                span_name="ai.agent.run",
                start_time=now,
                end_time=now,
            )

    def test_backend_can_create_trace_batch(self):
        """Test that backend can create trace batches."""
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

    def test_backend_enums_match_sdk(self):
        """Test that backend uses SDK enums."""
        assert SpanKind.INTERNAL == "INTERNAL"
        assert StatusCode.OK == "OK"
        assert AIOperationType.LLM_INVOKE == "ai.llm.invoke"

    def test_backend_can_use_ai_attributes(self):
        """Test that backend can use SDK AI attribute models."""
        llm_attrs = AILLMAttributes(
            model_provider="openai",
            model_name="gpt-4",
            tokens_input=100,
        )
        assert llm_attrs.model_provider == "openai"

        tool_attrs = AIToolAttributes(tool_name="weather", tool_type="http")
        assert tool_attrs.tool_name == "weather"

    def test_backend_can_use_span_events(self):
        """Test that backend can use SDK SpanEvent."""
        event = SpanEvent(name="ai.prompt", timestamp=datetime.now(timezone.utc), attributes={})
        assert event.name == "ai.prompt"

    def test_backend_can_use_span_links(self):
        """Test that backend can use SDK SpanLink."""
        link = SpanLink(trace_id="a" * 32, span_id="b" * 16, attributes={})
        assert link.trace_id == "a" * 32

    def test_trace_ingest_response_available(self):
        """Test that TraceIngestResponse is available in backend."""
        response = TraceIngestResponse(status="received", span_count=5, trace_id="a" * 32)
        assert response.status == "received"
        assert response.span_count == 5

    def test_backend_otelspan_validates_timing(self):
        """Test that backend enforces timing validation from SDK."""
        from pydantic import ValidationError

        now = datetime.now(timezone.utc)
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(ValidationError, match="end_time must be after start_time"):
            OTELSpan(
                trace_id="a" * 32,
                span_id="b" * 16,
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=past,
            )

    def test_backend_otelspan_validates_trace_id_format(self):
        """Test that backend enforces trace ID format from SDK."""
        from pydantic import ValidationError

        now = datetime.now(timezone.utc)

        with pytest.raises(ValidationError, match="32-character hex string"):
            OTELSpan(
                trace_id="invalid",
                span_id="b" * 16,
                project_id="test",
                span_name="ai.llm.invoke",
                start_time=now,
                end_time=now,
            )

    def test_backend_trace_batch_validates_size(self):
        """Test that backend enforces batch size limits from SDK."""
        from pydantic import ValidationError

        # Empty batch should fail
        with pytest.raises(ValidationError):
            OTELTraceBatch(spans=[])

    def test_backend_schemas_have_sdk_docstrings(self):
        """Test that backend schemas inherit SDK docstrings."""
        # Check that key fields have descriptions
        assert "32-char hex trace ID" in str(OTELSpan.model_fields["trace_id"].description)
        assert "Span kind" in str(OTELSpan.model_fields["span_kind"].description)

    def test_otelspan_json_serialization_with_datetime(self):
        """Test that OTELSpan with datetime can be JSON serialized."""
        import json

        now = datetime.now(timezone.utc)
        span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test-project",
            environment="development",
            span_name="function.test",
            start_time=now,
            end_time=now,
        )

        # This should not raise "Object of type datetime is not JSON serializable"
        json_dict = span.model_dump(mode="json")

        # Verify datetime was serialized to string
        assert isinstance(json_dict["start_time"], str)
        assert isinstance(json_dict["end_time"], str)

        # Verify it can be JSON stringified
        json_str = json.dumps(json_dict)
        assert isinstance(json_str, str)

    def test_oteltrace_batch_json_serialization(self):
        """Test that OTELTraceBatch can be JSON serialized."""
        import json

        now = datetime.now(timezone.utc)
        span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test",
            span_name="function.test",
            start_time=now,
            end_time=now,
        )

        batch = OTELTraceBatch(spans=[span])

        # This should not raise JSON serialization errors
        json_dict = batch.model_dump(mode="json")
        json_str = json.dumps(json_dict)

        assert isinstance(json_str, str)
        assert "start_time" in json_str
        assert "end_time" in json_str

    def test_span_with_events_json_serialization(self):
        """Test that spans with events (containing datetime) can be JSON serialized."""
        import json

        now = datetime.now(timezone.utc)
        event = SpanEvent(name="ai.prompt", timestamp=now, attributes={"text": "test prompt"})

        span = OTELSpan(
            trace_id="a" * 32,
            span_id="b" * 16,
            project_id="test",
            span_name="ai.llm.invoke",
            start_time=now,
            end_time=now,
            events=[event],
        )

        # This should not raise JSON serialization errors
        json_dict = span.model_dump(mode="json")
        json_str = json.dumps(json_dict)

        assert isinstance(json_str, str)
        # Verify event timestamp was serialized
        parsed = json.loads(json_str)
        assert isinstance(parsed["events"][0]["timestamp"], str)
