"""Tests for telemetry RhesisOTLPExporter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode
from rhesis.telemetry.exporter import RhesisOTLPExporter


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

    @patch("rhesis.telemetry.exporter.requests.Session.post")
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

    @patch("rhesis.telemetry.exporter.requests.Session.post")
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

    @patch("rhesis.telemetry.exporter.requests.Session.post")
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
        # Skip retry backoff sleeps so the test stays fast.
        exporter._retryer.wait = lambda *a, **kw: 0

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

    @patch("rhesis.telemetry.exporter.requests.Session.post")
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

    @patch("rhesis.telemetry.exporter.requests.Session.post")
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


class TestExporterRetryLogic:
    """Tests for the retry logic in RhesisOTLPExporter."""

    def setup_method(self):
        """Create a shared exporter and span for each test."""
        self.exporter = RhesisOTLPExporter(
            api_key="k", base_url="http://localhost", project_id="p", environment="t"
        )
        self.exporter._retryer.wait = lambda *a, **kw: 0

        tracer = TracerProvider().get_tracer("test")
        with tracer.start_as_current_span("ai.llm.invoke") as span:
            pass  # span ends when context exits
        self.span = span._readable_span()

    @pytest.mark.parametrize(
        "exc",
        [requests.exceptions.ConnectionError(), requests.exceptions.Timeout()],
        ids=["connection_error", "timeout"],
    )
    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_transient_exception_then_succeed(self, mock_post, exc):
        """Retry on ConnectionError/Timeout, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [exc, ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @pytest.mark.parametrize("status", [408, 429, 500, 501, 502, 503, 504])
    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_retryable_status_then_succeed(self, mock_post, status):
        """Retry on each retryable status (408, 429, all 5xx), succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=status), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @pytest.mark.parametrize("status", [400, 401, 422])
    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_no_retry_on_non_retryable_status(self, mock_post, status):
        """Non-retryable 4xx (400/401/422) — fail fast, no retry."""
        resp = MagicMock(status_code=status)
        resp.json.return_value = {"detail": "x"}  # 422 branch tries to parse
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_no_retry_on_missing_schema(self, mock_post):
        """MissingSchema (URL config bug) isn't in the retry predicate — fail fast."""
        mock_post.side_effect = requests.exceptions.MissingSchema("Invalid URL: no scheme")

        assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_ssl_error_is_retried_as_connection_error(self, mock_post):
        """SSLError subclasses ConnectionError, so it gets retried (regression guard)."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [requests.exceptions.SSLError("transient"), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @pytest.mark.parametrize(
        "exc, expected_log",
        [
            (requests.exceptions.ConnectionError(), "Failed to connect to backend"),
            (requests.exceptions.Timeout(), "Timeout exporting spans"),
        ],
        ids=["connection_error", "timeout"],
    )
    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_exhaust_retries_on_persistent_exception(self, mock_post, caplog, exc, expected_log):
        """Persistent transport exception exhausts retries via the matching except branch."""
        mock_post.side_effect = exc

        with caplog.at_level("ERROR", logger="rhesis.telemetry.exporter"):
            assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 3
        assert any(expected_log in r.message for r in caplog.records)
        assert not any("This is a bug" in r.message for r in caplog.records)

    @pytest.mark.parametrize("status", [503, 429], ids=["503", "429"])
    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_exhaust_retries_on_persistent_status(self, mock_post, caplog, status):
        """Persistent retryable status exhausts retries via the HTTPError branch."""
        resp = MagicMock(status_code=status)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        with caplog.at_level("ERROR", logger="rhesis.telemetry.exporter"):
            assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 3
        assert any("HTTP error exporting spans" in r.message for r in caplog.records)
        assert not any("This is a bug" in r.message for r in caplog.records)

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_recovery_resets_consecutive_failures(self, mock_post):
        """A successful export after failures clears _consecutive_failures."""
        # Two failed exports first to bump _consecutive_failures
        mock_post.side_effect = requests.exceptions.ConnectionError()
        self.exporter.export([self.span])
        self.exporter.export([self.span])
        assert self.exporter._consecutive_failures == 2

        # Now a clean export — counter should reset to 0
        ok = MagicMock(status_code=200)
        mock_post.side_effect = None
        mock_post.return_value = ok

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert self.exporter._consecutive_failures == 0


class TestExporterDeadlineAndShutdown:
    """Tests for deadline-bounded retries and cooperative shutdown."""

    def _make_span(self):
        tracer = TracerProvider().get_tracer("test")
        with tracer.start_as_current_span("ai.llm.invoke") as span:
            pass
        return span._readable_span()

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_deadline_stops_loop_before_attempt_cap(self, mock_post):
        """timeout=0 budget halts retries before any post happens."""
        exporter = RhesisOTLPExporter(
            api_key="k",
            base_url="http://localhost",
            project_id="p",
            environment="t",
            timeout=0,
        )
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = exporter.export([self._make_span()])
        assert result == SpanExportResult.FAILURE
        # Closure deadline guard preempts the first post (remaining <= 0),
        # so call_count is 0 — well below max_attempts=3.
        assert mock_post.call_count == 0

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_shutdown_aborts_in_flight_retry(self, mock_post):
        """Pre-set shutdown event aborts retries after the current attempt."""
        exporter = RhesisOTLPExporter(
            api_key="k", base_url="http://localhost", project_id="p", environment="t"
        )
        # Skip waits — sleep interruption is covered by test_interruptible_sleep_*.
        exporter._retryer.wait = lambda *a, **kw: 0
        mock_post.side_effect = requests.exceptions.ConnectionError()

        # Pre-signal shutdown before export starts
        exporter._shutdown_event.set()

        result = exporter.export([self._make_span()])
        assert result == SpanExportResult.FAILURE
        # First attempt runs, then _stop_on_shutdown fires on the stop check
        # (between attempts), so call_count should be exactly 1.
        assert mock_post.call_count == 1

    def test_interruptible_sleep_unblocks_on_shutdown(self):
        """_interruptible_sleep returns immediately once shutdown is set."""
        import time as _time

        exporter = RhesisOTLPExporter(
            api_key="k", base_url="http://localhost", project_id="p", environment="t"
        )

        # First: confirm sleep without shutdown actually waits a small amount
        start = _time.monotonic()
        exporter._interruptible_sleep(0.05)
        elapsed = _time.monotonic() - start
        assert elapsed >= 0.04  # roughly the requested duration

        # Now: with shutdown set, the same sleep should return ~immediately
        exporter._shutdown_event.set()
        start = _time.monotonic()
        exporter._interruptible_sleep(5.0)  # would normally wait 5 seconds
        elapsed = _time.monotonic() - start
        assert elapsed < 0.1  # should be near-instant

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_per_attempt_timeout_shrinks_with_remaining_budget(self, mock_post):
        """Per-attempt Session.post timeout shrinks with the remaining budget."""
        exporter = RhesisOTLPExporter(
            api_key="k",
            base_url="http://localhost",
            project_id="p",
            environment="t",
            timeout=10,
        )
        exporter._retryer.wait = lambda *a, **kw: 0

        # Capture the timeout passed to each Session.post call
        timeouts_seen = []

        def _capture(*args, **kwargs):
            timeouts_seen.append(kwargs.get("timeout"))
            raise requests.exceptions.ConnectionError()

        mock_post.side_effect = _capture
        exporter.export([self._make_span()])

        # First attempt should get ~10s (full budget); subsequent attempts
        # should see strictly less than the previous (budget shrinking).
        assert len(timeouts_seen) >= 2
        assert timeouts_seen[0] <= 10
        for prev, curr in zip(timeouts_seen, timeouts_seen[1:]):
            assert curr < prev, f"timeout did not shrink: {timeouts_seen}"


class TestExporterBatchChunking:
    """Tests for batch chunking in RhesisOTLPExporter."""

    def _make_exporter(self, max_chunk_size=100, **kwargs):
        defaults = dict(
            api_key="k",
            base_url="http://localhost",
            project_id="p",
            environment="t",
        )
        defaults.update(kwargs)
        exp = RhesisOTLPExporter(max_chunk_size=max_chunk_size, **defaults)
        exp._retryer.wait = lambda *a, **kw: 0
        return exp

    def _make_spans(self, n, n_roots=1):
        """Create n ReadableSpans; the first n_roots have no parent.

        Children are created inside a root span's context so OTEL
        assigns them a proper parent_span_id.
        """
        tracer = TracerProvider().get_tracer("test")
        spans = []
        n_children = n - n_roots

        for i in range(n_roots):
            if i < n_roots - 1:
                batch = n_children // n_roots
            else:
                batch = n_children - (n_children // n_roots) * (n_roots - 1)

            child_readable = []
            with tracer.start_as_current_span("ai.llm.invoke") as root:
                for _ in range(batch):
                    with tracer.start_as_current_span("ai.tool.invoke") as child:
                        pass
                    child_readable.append(child._readable_span())

            spans.append(root._readable_span())
            spans.extend(child_readable)

        return spans

    def test_default_max_chunk_size(self):
        """Default max_chunk_size is 100."""
        exporter = RhesisOTLPExporter(
            api_key="k",
            base_url="http://localhost",
            project_id="p",
            environment="t",
        )
        assert exporter._max_chunk_size == 100

    def test_custom_max_chunk_size(self):
        """Constructor parameter overrides default."""
        exporter = self._make_exporter(max_chunk_size=50)
        assert exporter._max_chunk_size == 50

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_small_batch_no_chunking(self, mock_post):
        """A batch under max_chunk_size results in a single POST."""
        mock_post.return_value = MagicMock(status_code=200)
        exporter = self._make_exporter(max_chunk_size=100)

        spans = self._make_spans(10, n_roots=1)
        result = exporter.export(spans)

        assert result == SpanExportResult.SUCCESS
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_large_batch_chunks_into_multiple_posts(self, mock_post):
        """A batch of 250 spans with max_chunk_size=100 results in 3 POSTs."""
        mock_post.return_value = MagicMock(status_code=200)
        exporter = self._make_exporter(max_chunk_size=100)

        spans = self._make_spans(250, n_roots=2)
        result = exporter.export(spans)

        assert result == SpanExportResult.SUCCESS
        assert mock_post.call_count == 3

        total_spans_sent = 0
        for call in mock_post.call_args_list:
            payload = call[1]["json"]
            total_spans_sent += len(payload["spans"])
        assert total_spans_sent == 250

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_root_spans_in_first_chunk(self, mock_post):
        """Root spans (parent_span_id=None) always appear in the first chunk."""
        payloads = []

        def _capture(*args, **kwargs):
            payloads.append(kwargs["json"])
            return MagicMock(status_code=200)

        mock_post.side_effect = _capture
        exporter = self._make_exporter(max_chunk_size=5)

        spans = self._make_spans(15, n_roots=3)
        result = exporter.export(spans)

        assert result == SpanExportResult.SUCCESS
        assert len(payloads) >= 2

        first_chunk_spans = payloads[0]["spans"]
        root_spans_in_first = [s for s in first_chunk_spans if s["parent_span_id"] is None]
        assert len(root_spans_in_first) == 3

        for later_payload in payloads[1:]:
            for s in later_payload["spans"]:
                assert s["parent_span_id"] is not None

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_chunk_failure_returns_failure(self, mock_post):
        """If chunk 2 POST fails, export returns FAILURE (chunk 1 already sent)."""
        ok = MagicMock(status_code=200)
        fail = MagicMock(status_code=422)
        fail.json.return_value = {"detail": "rejected"}
        fail.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=fail,
        )
        mock_post.side_effect = [ok, fail]

        exporter = self._make_exporter(max_chunk_size=5)
        spans = self._make_spans(10, n_roots=1)
        result = exporter.export(spans)

        assert result == SpanExportResult.FAILURE
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_per_chunk_deadline(self, mock_post):
        """Each chunk gets its own fresh deadline, not a shared one."""
        deadlines_seen = []

        def _capture(*args, **kwargs):
            deadlines_seen.append(kwargs.get("timeout"))
            return MagicMock(status_code=200)

        mock_post.side_effect = _capture
        exporter = self._make_exporter(max_chunk_size=5, timeout=10)

        spans = self._make_spans(12, n_roots=1)
        result = exporter.export(spans)

        assert result == SpanExportResult.SUCCESS
        assert mock_post.call_count >= 2

        for t in deadlines_seen:
            assert t > 9.0, f"Chunk deadline should be ~10s (fresh budget), got {t}"
