"""Tests for telemetry RhesisOTLPExporter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.exporter import RhesisOTLPExporter


class TestRhesisOTLPExporter:
    """Tests for RhesisOTLPExporter."""

    def test_exporter_initialization(self):
        """Test exporter initialization."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        assert exporter.api_key == "test-key"
        assert exporter.project_id == "test-project"
        assert exporter.environment == "test"
        assert "Bearer test-key" in exporter._session.headers["Authorization"]

    def test_exporter_converts_ws_to_http(self):
        """Test exporter converts WebSocket URL to HTTP."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="ws://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Verify endpoint is publicly accessible
        assert exporter.endpoint == "http://localhost:8080/telemetry/traces"
        assert hasattr(exporter, "endpoint")  # Confirm it's a public attribute

    def test_exporter_converts_wss_to_https(self):
        """Test exporter converts WSS URL to HTTPS."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="wss://api.rhesis.ai",
            project_id="test-project",
            environment="production",
        )

        assert exporter.endpoint == "https://api.rhesis.ai/telemetry/traces"

    @patch("rhesis.sdk.telemetry.exporter.requests.Session.post")
    def test_export_success(self, mock_post):
        """Test successful span export."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Create a mock span
        span_context = SpanContext(
            trace_id=int("a" * 32, 16),
            span_id=int("b" * 16, 16),
            is_remote=False,
        )

        mock_span = MagicMock(spec=ReadableSpan)
        mock_span.context = span_context
        mock_span.parent = None
        mock_span.name = "ai.llm.invoke"
        mock_span.kind = SpanKind.INTERNAL
        mock_span.start_time = int(datetime.now(timezone.utc).timestamp() * 1e9)
        mock_span.end_time = int(datetime.now(timezone.utc).timestamp() * 1e9)
        mock_span.status = Status(StatusCode.OK)
        mock_span.attributes = {"test": "value"}
        mock_span.events = []
        mock_span.links = []
        mock_span.resource = None

        result = exporter.export([mock_span])

        assert result == SpanExportResult.SUCCESS
        assert mock_post.called

    @patch("rhesis.sdk.telemetry.exporter.requests.Session.post")
    def test_export_empty_spans(self, mock_post):
        """Test export with empty span list returns success."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        result = exporter.export([])

        assert result == SpanExportResult.SUCCESS
        assert not mock_post.called

    @patch("rhesis.sdk.telemetry.exporter.requests.Session.post")
    def test_export_timeout(self, mock_post):
        """Test export handles timeout."""
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout()

        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Create mock span
        span_context = SpanContext(
            trace_id=int("a" * 32, 16),
            span_id=int("b" * 16, 16),
            is_remote=False,
        )

        mock_span = MagicMock(spec=ReadableSpan)
        mock_span.context = span_context
        mock_span.parent = None
        mock_span.name = "ai.llm.invoke"
        mock_span.kind = SpanKind.INTERNAL
        mock_span.start_time = int(datetime.now(timezone.utc).timestamp() * 1e9)
        mock_span.end_time = int(datetime.now(timezone.utc).timestamp() * 1e9)
        mock_span.status = Status(StatusCode.OK)
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []
        mock_span.resource = None

        result = exporter.export([mock_span])

        assert result == SpanExportResult.FAILURE

    @patch("rhesis.sdk.telemetry.exporter.requests.Session.post")
    def test_export_validation_error(self, mock_post):
        """Test export handles validation errors (422)."""
        from requests.exceptions import HTTPError

        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"detail": "Invalid span name"}

        mock_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)

        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Create mock span
        span_context = SpanContext(
            trace_id=int("a" * 32, 16),
            span_id=int("b" * 16, 16),
            is_remote=False,
        )

        mock_span = MagicMock(spec=ReadableSpan)
        mock_span.context = span_context
        mock_span.parent = None
        mock_span.name = "invalid.span.name"
        mock_span.kind = SpanKind.INTERNAL
        mock_span.start_time = int(datetime.now(timezone.utc).timestamp() * 1e9)
        mock_span.end_time = int(datetime.now(timezone.utc).timestamp() * 1e9)
        mock_span.status = Status(StatusCode.OK)
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []
        mock_span.resource = None

        result = exporter.export([mock_span])

        assert result == SpanExportResult.FAILURE

    def test_timestamp_conversion(self):
        """Test timestamp conversion from nanoseconds to datetime."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Test with known timestamp
        timestamp_ns = 1704067200000000000  # 2024-01-01 00:00:00 UTC
        dt = exporter._timestamp_to_datetime(timestamp_ns)

        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

    def test_timestamp_conversion_none(self):
        """Test timestamp conversion with None."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        dt = exporter._timestamp_to_datetime(None)
        assert dt is None

    def test_exporter_endpoint_is_accessible(self):
        """Test that endpoint is accessible as a public attribute."""
        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # This should not raise AttributeError
        assert hasattr(exporter, "endpoint")
        assert exporter.endpoint == "http://localhost:8080/telemetry/traces"
        assert isinstance(exporter.endpoint, str)

    @patch("rhesis.sdk.telemetry.exporter.requests.Session.post")
    def test_export_spans_with_datetime_serialization(self, mock_post):
        """Test that datetime objects are properly serialized during export."""
        from datetime import datetime, timezone

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        exporter = RhesisOTLPExporter(
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

        # Create a mock span with real datetime objects
        now = datetime.now(timezone.utc)
        span_context = SpanContext(
            trace_id=int("a" * 32, 16),
            span_id=int("b" * 16, 16),
            is_remote=False,
        )

        mock_span = MagicMock(spec=ReadableSpan)
        mock_span.context = span_context
        mock_span.parent = None
        mock_span.name = "function.test"
        mock_span.kind = SpanKind.INTERNAL
        mock_span.start_time = int(now.timestamp() * 1e9)
        mock_span.end_time = int((now.timestamp() + 1) * 1e9)
        mock_span.status = Status(StatusCode.OK)
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []
        mock_span.resource = None

        # This should not raise "Object of type datetime is not JSON serializable"
        result = exporter.export([mock_span])

        assert result == SpanExportResult.SUCCESS
        assert mock_post.called

        # Verify the json parameter was passed (not data)
        call_kwargs = mock_post.call_args[1]
        assert "json" in call_kwargs

        # Verify datetime was serialized to string
        json_data = call_kwargs["json"]
        assert isinstance(json_data, dict)
        assert "spans" in json_data
        # The datetime should have been serialized to ISO format string
        assert isinstance(json_data["spans"][0]["start_time"], str)
