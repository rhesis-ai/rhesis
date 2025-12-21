"""Custom OTLP exporter with Rhesis authentication."""

import logging
from datetime import datetime, timezone
from typing import Optional, Sequence

import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from rhesis.sdk.telemetry.schemas import OTELSpan, OTELTraceBatch, SpanEvent, SpanLink

logger = logging.getLogger(__name__)


class RhesisOTLPExporter(OTLPSpanExporter):
    """
    Custom OTLP exporter using SDK Pydantic schemas.

    Converts OTEL ReadableSpan → SDK OTELSpan → JSON
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        project_id: str,
        environment: str,
        timeout: int = 10,
    ):
        """
        Initialize exporter with Rhesis configuration.

        Args:
            api_key: Rhesis API key
            base_url: Backend base URL
            project_id: Project ID
            environment: Environment name
            timeout: Request timeout in seconds
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

        # Add authentication headers
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
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

            # Serialize via Pydantic (mode='json' ensures datetime serialization)
            response = self._session.post(
                self.endpoint,
                json=batch.model_dump(mode="json"),  # SDK schema serialization with JSON mode
                timeout=self._timeout,
            )

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
            self._failed_exports += 1
            self._consecutive_failures += 1
            logger.error(
                f"❌ Failed to connect to backend at {self.endpoint}. "
                f"Make sure the backend is running (docker compose up -d). Error: {e}"
            )
            self._log_persistent_failure_warning()
            return SpanExportResult.FAILURE

        except requests.exceptions.Timeout:
            self._failed_exports += 1
            self._consecutive_failures += 1
            logger.error(
                f"❌ Timeout exporting spans to {self.endpoint}. "
                f"Backend might be overloaded or unreachable."
            )
            self._log_persistent_failure_warning()
            return SpanExportResult.FAILURE

        except requests.exceptions.HTTPError as e:
            self._failed_exports += 1
            self._consecutive_failures += 1

            # Log validation errors from backend
            if e.response.status_code == 422:
                try:
                    error_detail = e.response.json()
                    logger.error(
                        f"❌ Backend rejected spans (validation error): {error_detail}. "
                        "Check span names follow pattern: ai.<domain>.<action>"
                    )
                except Exception:
                    logger.error(f"❌ Backend validation error (422): {e}")
            elif e.response.status_code == 401:
                logger.error(f"❌ Authentication failed. Check your RHESIS_API_KEY. Error: {e}")
            elif e.response.status_code == 403:
                logger.error(
                    f"❌ Authorization failed. Check your API key has access to "
                    f"project '{self.project_id}'. Error: {e}"
                )
            else:
                logger.error(f"❌ HTTP error exporting spans: {e}")

            self._log_persistent_failure_warning()
            return SpanExportResult.FAILURE

        except Exception as e:
            self._failed_exports += 1
            self._consecutive_failures += 1
            logger.error(
                f"❌ Unexpected error exporting spans: {e}. This is a bug - please report it.",
                exc_info=True,
            )
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

    def _convert_spans(self, spans: Sequence[ReadableSpan]) -> OTELTraceBatch:
        """
        Convert OTEL spans to SDK OTELSpan models.

        Args:
            spans: Sequence of OTEL spans

        Returns:
            OTELTraceBatch with validated SDK schemas
        """
        converted_spans = []

        for span in spans:
            # Convert trace/span IDs to hex strings
            trace_id = format(span.context.trace_id, "032x")
            span_id = format(span.context.span_id, "016x")
            parent_span_id = (
                format(span.parent.span_id, "016x") if span.parent and span.parent.span_id else None
            )

            # Convert events
            events = []
            if span.events:
                for event in span.events:
                    events.append(
                        SpanEvent(
                            name=event.name,
                            timestamp=self._timestamp_to_datetime(event.timestamp),
                            attributes=dict(event.attributes) if event.attributes else {},
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
                            attributes=dict(link.attributes) if link.attributes else {},
                        )
                    )

            # Create SDK OTELSpan model (validates automatically via Pydantic)
            otel_span = OTELSpan(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                project_id=self.project_id,
                environment=self.environment,
                span_name=span.name,
                span_kind=span.kind.name,
                start_time=self._timestamp_to_datetime(span.start_time),
                end_time=self._timestamp_to_datetime(span.end_time),
                status_code=span.status.status_code.name,
                status_message=span.status.description,
                attributes=dict(span.attributes) if span.attributes else {},
                events=events,
                links=links,
                resource=dict(span.resource.attributes) if span.resource else {},
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
