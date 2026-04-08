"""Tests for telemetry RhesisOTLPExporter."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_connection_error_then_succeed(self, mock_post):
        """Retry on ConnectionError, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [requests.exceptions.ConnectionError(), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_timeout_then_succeed(self, mock_post):
        """Retry on Timeout, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [requests.exceptions.Timeout(), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_429_then_succeed(self, mock_post):
        """Retry on 429 Too Many Requests, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=429), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_503_then_succeed(self, mock_post):
        """Retry on 503 Service Unavailable, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=503), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_408_then_succeed(self, mock_post):
        """Retry on 408 Request Timeout, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=408), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_502_then_succeed(self, mock_post):
        """Retry on 502 Bad Gateway, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=502), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_504_then_succeed(self, mock_post):
        """Retry on 504 Gateway Timeout, succeed on 2nd attempt."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=504), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_500_then_succeed(self, mock_post):
        """Retry on 500 Internal Server Error, succeed on 2nd attempt.

        500 is part of the broadened 5xx retryable set that mirrors upstream
        OTLPSpanExporter's _is_retryable() (408 + every 5xx). Servers commonly
        return 500 during deploys, restarts, and transient backend pressure
        — all cases where a retry is the right call.
        """
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=500), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_retry_on_501_then_succeed(self, mock_post):
        """Retry on 501 — covers a 5xx that the previous narrow set missed."""
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [MagicMock(status_code=501), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_no_retry_on_400(self, mock_post):
        """400 Bad Request is not transient — fail immediately, no retry."""
        resp = MagicMock(status_code=400)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_no_retry_on_missing_schema(self, mock_post):
        """MissingSchema is a RequestException not in our retryable types.

        It's a code/config bug (URL has no scheme like 'http://'), not a
        transient network failure. The retry= predicate only matches
        ConnectionError + Timeout exceptions and our retryable status set,
        so MissingSchema falls through to the catch-all "unexpected error"
        branch and is not retried.

        Note: SSLError, despite intuitively being a "permanent" failure,
        IS retried because requests.exceptions.SSLError is a subclass of
        ConnectionError. That matches upstream OTLPSpanExporter behavior
        and is intentional — a brief TLS handshake glitch can be transient.
        """
        mock_post.side_effect = requests.exceptions.MissingSchema("Invalid URL: no scheme")

        assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_ssl_error_is_retried_as_connection_error(self, mock_post):
        """Document that SSLError is retried via the ConnectionError predicate.

        Regression guard: if someone narrows the retry types and SSLError
        stops being retried, this test will fail and force a deliberate
        decision rather than a silent behavior change.
        """
        ok = MagicMock(status_code=200)
        mock_post.side_effect = [requests.exceptions.SSLError("transient"), ok]

        assert self.exporter.export([self.span]) == SpanExportResult.SUCCESS
        assert mock_post.call_count == 2

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_exhaust_retries_on_persistent_connection_error(self, mock_post, caplog):
        """Give up after max_attempts on persistent ConnectionError."""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        with caplog.at_level("ERROR", logger="rhesis.telemetry.exporter"):
            assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 3
        # Must hit the ConnectionError branch (not the generic "This is a bug" path)
        assert any("Failed to connect to backend" in r.message for r in caplog.records)
        assert not any("This is a bug" in r.message for r in caplog.records)

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_exhaust_retries_on_persistent_timeout(self, mock_post, caplog):
        """Give up after max_attempts on persistent Timeout."""
        mock_post.side_effect = requests.exceptions.Timeout()

        with caplog.at_level("ERROR", logger="rhesis.telemetry.exporter"):
            assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 3
        # Must hit the Timeout branch (not the generic "This is a bug" path)
        assert any("Timeout exporting spans" in r.message for r in caplog.records)
        assert not any("This is a bug" in r.message for r in caplog.records)

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_exhaust_retries_on_persistent_503(self, mock_post, caplog):
        """Give up after max_attempts on persistent 503 Service Unavailable."""
        resp = MagicMock(status_code=503)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        with caplog.at_level("ERROR", logger="rhesis.telemetry.exporter"):
            assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 3
        # Must hit the HTTPError branch (not the generic "This is a bug" path)
        assert any("HTTP error exporting spans" in r.message for r in caplog.records)
        assert not any("This is a bug" in r.message for r in caplog.records)

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_exhaust_retries_on_persistent_429(self, mock_post, caplog):
        """Give up after max_attempts on persistent 429 Too Many Requests."""
        resp = MagicMock(status_code=429)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        with caplog.at_level("ERROR", logger="rhesis.telemetry.exporter"):
            assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 3
        # Must hit the HTTPError branch (not the generic "This is a bug" path)
        assert any("HTTP error exporting spans" in r.message for r in caplog.records)
        assert not any("This is a bug" in r.message for r in caplog.records)

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_no_retry_on_422(self, mock_post):
        """Do not retry on 422 validation error — fail immediately."""
        resp = MagicMock(status_code=422)
        resp.json.return_value = {"detail": "Invalid span"}
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_no_retry_on_401(self, mock_post):
        """Do not retry on 401 auth error — fail immediately."""
        resp = MagicMock(status_code=401)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        mock_post.return_value = resp

        assert self.exporter.export([self.span]) == SpanExportResult.FAILURE
        assert mock_post.call_count == 1

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_recovery_resets_consecutive_failures(self, mock_post):
        """A successful retry after failures clears the consecutive counter.

        Covers the recovery log line in export() which was previously
        uncovered by the test suite.
        """
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
        """stop_after_delay fires before stop_after_attempt when budget runs out.

        With a 0.1s total budget and instant-failing posts, the deadline
        predicate should terminate the loop after the first wait pushes
        elapsed time past the budget — well before the 3-attempt cap.
        """
        # Tight budget; do NOT skip the wait so the deadline check fires.
        exporter = RhesisOTLPExporter(
            api_key="k",
            base_url="http://localhost",
            project_id="p",
            environment="t",
            timeout=0,  # zero budget — stop_after_delay fires after first attempt
        )
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = exporter.export([self._make_span()])
        assert result == SpanExportResult.FAILURE
        # stop_after_delay(0) means no time budget, so we should bail after
        # the first attempt completes — well below max_attempts=3.
        assert mock_post.call_count < 3

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_shutdown_aborts_in_flight_retry(self, mock_post):
        """shutdown() pre-set should bail out at the next stop check.

        Pre-setting the shutdown event before calling export() simulates a
        BatchSpanProcessor.shutdown() that races with an in-flight retry.
        The _stop_on_shutdown predicate should fire on the next stop check
        and terminate the loop after the current attempt finishes.
        """
        exporter = RhesisOTLPExporter(
            api_key="k", base_url="http://localhost", project_id="p", environment="t"
        )
        # Skip waits to keep test fast — the shutdown predicate is what we
        # want to verify, not the wait interruption mechanism (which is
        # covered separately by test_interruptible_sleep_unblocks_on_shutdown).
        exporter._retryer.wait = lambda *a, **kw: 0
        mock_post.side_effect = requests.exceptions.ConnectionError()

        # Pre-signal shutdown before export starts
        exporter._shutdown_event.set()

        result = exporter.export([self._make_span()])
        assert result == SpanExportResult.FAILURE
        # First attempt runs, then _stop_on_shutdown fires on the stop check
        # (between attempts), so call_count should be exactly 1.
        assert mock_post.call_count == 1

    def test_shutdown_method_sets_event(self):
        """shutdown() override sets the event before delegating to parent."""
        exporter = RhesisOTLPExporter(
            api_key="k", base_url="http://localhost", project_id="p", environment="t"
        )
        assert not exporter._shutdown_event.is_set()

        exporter.shutdown()
        assert exporter._shutdown_event.is_set()

    def test_interruptible_sleep_unblocks_on_shutdown(self):
        """_interruptible_sleep returns immediately when event is set.

        This is the mechanism by which a shutdown() called mid-backoff
        unblocks the worker thread instead of letting it sleep for the
        full backoff duration.
        """
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

    def test_stop_on_shutdown_predicate(self):
        """_stop_on_shutdown returns True iff the event is set."""
        exporter = RhesisOTLPExporter(
            api_key="k", base_url="http://localhost", project_id="p", environment="t"
        )
        assert exporter._stop_on_shutdown(None) is False
        exporter._shutdown_event.set()
        assert exporter._stop_on_shutdown(None) is True

    @patch("rhesis.telemetry.exporter.requests.Session.post")
    def test_per_attempt_timeout_shrinks_with_remaining_budget(self, mock_post):
        """Each attempt's request timeout reflects the remaining wall-time budget.

        The closure in export() computes `remaining = deadline - time.monotonic()`
        and passes that to `Session.post(timeout=...)`, so a slow first attempt
        cannot allow a second attempt to overshoot the total budget.
        """
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
