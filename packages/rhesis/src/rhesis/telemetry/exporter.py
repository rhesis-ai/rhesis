"""Custom OTLP exporter with Rhesis authentication."""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from tenacity import (
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from rhesis.telemetry.constants import ConversationContext as ConvContextConstants
from rhesis.telemetry.schemas import OTELSpan, OTELTraceBatch, SpanEvent, SpanLink

logger = logging.getLogger(__name__)


class RhesisOTLPExporter(OTLPSpanExporter):
    """
    Custom OTLP exporter using SDK Pydantic schemas.

    Converts OTEL ReadableSpan → SDK OTELSpan → JSON
    """

    # 408, 429, and all 5xx — mirrors upstream OTLP _is_retryable() and adds
    # 429 (which upstream skips). Connection/Timeout errors retried separately.
    _RETRYABLE_STATUSES = frozenset({408, 429}) | frozenset(range(500, 600))

    def __init__(
        self,
        api_key: str,
        base_url: str,
        project_id: str,
        environment: str,
        timeout: int = 10,
        max_attempts: int = 3,
    ):
        """
        Initialize exporter with Rhesis configuration.

        Args:
            api_key: Rhesis API key
            base_url: Backend base URL
            project_id: Project ID
            environment: Environment name
            timeout: Total wall-time budget per export() call in seconds,
                including retries and backoff. Defaults to 10.
            max_attempts: Hard cap on attempts (backstop; deadline usually
                fires first). Defaults to 3.
        """
        # Convert ws:// → http://, wss:// → https://
        if base_url.startswith("ws://"):
            http_url = base_url.replace("ws://", "http://")
        elif base_url.startswith("wss://"):
            http_url = base_url.replace("wss://", "https://")
        else:
            http_url = base_url

        # Construct trace endpoint
        self.endpoint = f"{http_url.rstrip('/')}/telemetry/traces"

        # Initialize parent with custom headers
        super().__init__(
            endpoint=self.endpoint,
            timeout=timeout,
        )

        self.api_key = api_key
        self.project_id = project_id
        self.environment = environment
        self._max_attempts = max_attempts
        self._timeout = timeout

        # Set by shutdown() to abort in-flight retries (checked by stop predicate + sleep).
        self._shutdown_event = threading.Event()

        # Add authentication headers
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

        # Tenacity config matched to upstream OTLP semantics: deadline-bounded,
        # shutdown-cooperative, exhaustion unwraps for the existing except branches.
        self._retryer = Retrying(
            wait=wait_exponential_jitter(initial=1, exp_base=2, jitter=2, max=10),
            stop=(
                stop_after_attempt(max_attempts)  # hard backstop
                | stop_after_delay(timeout)  # total wall-time budget
                | self._stop_on_shutdown  # cooperative shutdown
            ),
            retry=(
                retry_if_exception_type(
                    (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
                )
                | retry_if_result(lambda r: r.status_code in self._RETRYABLE_STATUSES)
            ),
            before_sleep=self._log_retry,
            sleep=self._interruptible_sleep,  # Event.wait so shutdown unblocks mid-backoff
            # Unwrap last attempt via Future.result() instead of raising RetryError.
            retry_error_callback=lambda state: state.outcome.result(),
        )

        # Failure tracking to alert users of persistent issues
        self._consecutive_failures = 0
        self._total_exports = 0
        self._failed_exports = 0

        logger.debug(f"OTLP exporter initialized: {self.endpoint}")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """
        Export spans to Rhesis backend using SDK schemas.

        The backend validates span names according to semantic conventions:
        - Valid: ai.llm.invoke, ai.tool.invoke, ai.retrieval
        - Invalid: ai.agent.run, ai.chain.execute (HTTP 422 rejection)

        Args:
            spans: Sequence of spans to export

        Returns:
            SpanExportResult indicating success or failure
        """
        if not spans:
            return SpanExportResult.SUCCESS

        self._total_exports += 1

        try:
            # Convert OTEL spans to SDK schema models
            batch = self._convert_spans(spans)

            logger.debug(
                f"Exporting {len(spans)} span(s) for trace "
                f"{spans[0].context.trace_id if spans else 'unknown'}"
            )

            # Per-attempt timeout shrinks with the remaining budget so a slow
            # first attempt can't let a second attempt overshoot the deadline.
            payload = batch.model_dump(mode="json")
            deadline = time.monotonic() + self._timeout

            def _post_with_remaining_budget(p: dict) -> requests.Response:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise requests.exceptions.Timeout("export wall-time budget exhausted")
                return self._session.post(self.endpoint, json=p, timeout=remaining)

            # Serialize via Pydantic and send with retry on transient failures
            response = self._retryer(_post_with_remaining_budget, payload)
            response.raise_for_status()

            logger.debug(f"Successfully exported {len(spans)} span(s)")

            # Reset failure counter on success
            if self._consecutive_failures > 0:
                logger.info(
                    f"✅ Telemetry export recovered after {self._consecutive_failures} failures"
                )
            self._consecutive_failures = 0

            return SpanExportResult.SUCCESS

        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"❌ Failed to connect to backend at {self.endpoint}. "
                f"Make sure the backend is running (docker compose up -d). Error: {e}"
            )
            return self._record_failure()

        except requests.exceptions.Timeout:
            logger.error(
                f"❌ Timeout exporting spans to {self.endpoint}. "
                f"Backend might be overloaded or unreachable."
            )
            return self._record_failure()

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None

            if status_code == 422:
                try:
                    error_detail = e.response.json()
                    logger.error(
                        f"❌ Backend rejected spans (validation error): {error_detail}. "
                        "Check span names follow pattern: ai.<domain>.<action>"
                    )
                except Exception:
                    logger.error(f"❌ Backend validation error (422): {e}")
            elif status_code == 401:
                logger.error(f"❌ Authentication failed. Check your RHESIS_API_KEY. Error: {e}")
            elif status_code == 403:
                logger.error(
                    f"❌ Authorization failed. Check your API key has access to "
                    f"project '{self.project_id}'. Error: {e}"
                )
            else:
                logger.error(f"❌ HTTP error exporting spans: {e}")

            return self._record_failure()

        except Exception as e:
            logger.error(
                f"❌ Unexpected error exporting spans: {e}. This is a bug - please report it.",
                exc_info=True,
            )
            return self._record_failure()

    def _record_failure(self) -> SpanExportResult:
        """Increment failure counters and emit a warning if persistent."""
        self._failed_exports += 1
        self._consecutive_failures += 1
        self._log_persistent_failure_warning()
        return SpanExportResult.FAILURE

    def _log_persistent_failure_warning(self) -> None:
        """Log warning if exports are repeatedly failing."""
        if self._consecutive_failures == 5:
            success_rate = (
                ((self._total_exports - self._failed_exports) / self._total_exports * 100)
                if self._total_exports > 0
                else 0
            )
            logger.warning(
                f"⚠️  TELEMETRY ALERT: 5 consecutive export failures detected!\n"
                f"   Endpoint: {self.endpoint}\n"
                f"   Total exports: {self._total_exports}\n"
                f"   Failed exports: {self._failed_exports}\n"
                f"   Success rate: {success_rate:.1f}%\n"
                f"   → Check backend logs: docker logs rhesis-backend-1 --tail 50\n"
                f"   → Verify backend is running: docker compose ps\n"
                f"   → Check API key and project ID are correct"
            )
        elif self._consecutive_failures % 10 == 0:
            logger.warning(
                f"⚠️  TELEMETRY ALERT: {self._consecutive_failures} consecutive failures! "
                f"Traces are NOT being sent to backend."
            )

    def _stop_on_shutdown(self, retry_state) -> bool:
        """Tenacity stop predicate: bail when shutdown() has been called."""
        return self._shutdown_event.is_set()

    def _interruptible_sleep(self, seconds: float) -> None:
        """Tenacity sleep callback: Event.wait so shutdown unblocks mid-backoff."""
        self._shutdown_event.wait(seconds)

    def shutdown(self) -> None:
        """Signal in-flight retries to abort, then delegate to parent."""
        self._shutdown_event.set()
        super().shutdown()

    def _log_retry(self, retry_state) -> None:
        """Log retry attempts for transient export failures."""
        # next_action.sleep is the upcoming sleep duration; idle_for is
        # cumulative across attempts and would over-report on retry 2+.
        next_sleep = retry_state.next_action.sleep if retry_state.next_action else 0.0
        logger.warning(
            f"Transient export failure, "
            f"retry {retry_state.attempt_number}/{self._max_attempts} "
            f"in {next_sleep:.1f}s"
        )

    def _convert_spans(self, spans: Sequence[ReadableSpan]) -> OTELTraceBatch:
        """
        Convert OTEL spans to SDK OTELSpan models.

        Handles conversation turn-root spans by stripping synthetic
        parent_span_id and propagating conversation_id.

        Args:
            spans: Sequence of OTEL spans

        Returns:
            OTELTraceBatch with validated SDK schemas
        """
        converted_spans = []

        # First pass: identify turn-root trace_ids for conversation_id
        # propagation to child spans
        turn_root_conversations: dict[str, str] = {}
        for span in spans:
            attrs = dict(span.attributes) if span.attributes else {}
            is_turn_root = attrs.get(ConvContextConstants.SpanAttributes.IS_TURN_ROOT)
            if is_turn_root:
                tid = format(span.context.trace_id, "032x")
                cid = attrs.get(ConvContextConstants.SpanAttributes.CONVERSATION_ID)
                if cid:
                    turn_root_conversations[tid] = cid

        for span in spans:
            # Convert trace/span IDs to hex strings
            trace_id = format(span.context.trace_id, "032x")
            span_id = format(span.context.span_id, "016x")
            parent_span_id = (
                format(span.parent.span_id, "016x") if span.parent and span.parent.span_id else None
            )

            attrs = dict(span.attributes) if span.attributes else {}

            # Check if this is a conversation turn-root span
            is_turn_root = attrs.get(ConvContextConstants.SpanAttributes.IS_TURN_ROOT)
            conversation_id = None

            if is_turn_root:
                # Strip synthetic parent_span_id (from
                # _build_conversation_parent_context)
                parent_span_id = None
                conversation_id = attrs.get(ConvContextConstants.SpanAttributes.CONVERSATION_ID)
            elif trace_id in turn_root_conversations:
                # Child span of a conversation turn: inherit
                # conversation_id
                conversation_id = turn_root_conversations[trace_id]

            # Convert events
            events = []
            if span.events:
                for event in span.events:
                    events.append(
                        SpanEvent(
                            name=event.name,
                            timestamp=self._timestamp_to_datetime(event.timestamp),
                            attributes=(dict(event.attributes) if event.attributes else {}),
                        )
                    )

            # Convert links
            links = []
            if span.links:
                for link in span.links:
                    links.append(
                        SpanLink(
                            trace_id=format(link.context.trace_id, "032x"),
                            span_id=format(link.context.span_id, "016x"),
                            attributes=(dict(link.attributes) if link.attributes else {}),
                        )
                    )

            # Create SDK OTELSpan model
            otel_span = OTELSpan(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                project_id=self.project_id,
                environment=self.environment,
                conversation_id=conversation_id,
                span_name=span.name,
                span_kind=span.kind.name,
                start_time=self._timestamp_to_datetime(span.start_time),
                end_time=self._timestamp_to_datetime(span.end_time),
                status_code=span.status.status_code.name,
                status_message=span.status.description,
                attributes=attrs,
                events=events,
                links=links,
                resource=(dict(span.resource.attributes) if span.resource else {}),
            )

            converted_spans.append(otel_span)

        return OTELTraceBatch(spans=converted_spans)

    @staticmethod
    def _timestamp_to_datetime(timestamp_ns: Optional[int]) -> Optional[datetime]:
        """Convert nanosecond timestamp to datetime."""
        if timestamp_ns is None:
            return None
        dt = datetime.fromtimestamp(timestamp_ns / 1e9, tz=timezone.utc)
        return dt
