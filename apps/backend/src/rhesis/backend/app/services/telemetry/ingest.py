"""Queued span ingest, shared by every trace ingest route.

A route authenticates, checks limits, decodes and resolves the project, then
queues an :class:`IngestJob`. A worker runs :func:`process_ingest_job`, which
stores the spans. Nothing on the request path writes to the database, so a
burst of exports cannot tie up API threads or connections.
"""

import base64
import gzip
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from rhesis.telemetry.schemas import OTELSpan
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import TraceIngestSettings
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.services.telemetry.span_storage import store_spans
from rhesis.backend.app.utils.crud_utils import clean_strings_recursive

logger = logging.getLogger(__name__)

# Lists the attributes cut to the size limit, so a reader knows the value is partial.
TRUNCATED_ATTRIBUTES = "rhesis.truncated_attributes"
DROPPED_ATTRIBUTES = "rhesis.dropped_attributes_count"
DROPPED_EVENTS = "rhesis.dropped_events_count"

_MESSAGE_VERSION = 1

_OWN_PREFIXES = ("ai.", "rhesis.")


class SpanStorageError(RuntimeError):
    """Spans could not be stored; nothing from this batch was committed."""


class UnstorableSpans(SpanStorageError):
    """The database refused the spans' values; retrying cannot help."""


class TooManySpans(ValueError):
    """The request carries more spans than one request may (413)."""


# ---------------------------------------------------------------------------
# Pre-store hooks
# ---------------------------------------------------------------------------

# Runs in the worker, inside the project scope, before the spans are stored and
# before the job locks their traces. May rewrite the spans in place (an EE hook
# joins conversation turns this way); it must lock every trace it writes.
PreStoreHook = Callable[[Session, List[OTELSpan], str, str], None]

_PRE_STORE_HOOKS: Dict[str, PreStoreHook] = {}


def register_pre_store_hook(name: str, hook: PreStoreHook) -> None:
    """Make ``hook`` available to jobs that name it. Idempotent."""
    _PRE_STORE_HOOKS[name] = hook


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@dataclass
class IngestJob:
    """Spans for one project, as queued for a worker."""

    spans: List[OTELSpan]
    organization_id: str
    user_id: Optional[str]
    project_id: str
    pre_store_hooks: List[str] = field(default_factory=list)

    def to_message(self) -> Dict[str, Any]:
        """A Celery-safe (JSON) message: the spans gzip-compressed, base64-encoded."""
        raw = json.dumps([s.model_dump(mode="json") for s in self.spans]).encode()
        return {
            "v": _MESSAGE_VERSION,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "pre_store_hooks": list(self.pre_store_hooks),
            "spans_gz": base64.b64encode(gzip.compress(raw, compresslevel=5)).decode("ascii"),
        }

    @classmethod
    def from_message(cls, message: Dict[str, Any]) -> "IngestJob":
        raw = gzip.decompress(base64.b64decode(message["spans_gz"]))
        return cls(
            spans=[OTELSpan.model_validate(s) for s in json.loads(raw)],
            organization_id=message["organization_id"],
            user_id=message.get("user_id"),
            project_id=message["project_id"],
            pre_store_hooks=list(message.get("pre_store_hooks") or []),
        )

    def messages(self, max_message_bytes: int) -> List[Dict[str, Any]]:
        """This job as messages whose spans take at most ``max_message_bytes`` on the broker.

        The size counted is the compressed, base64-encoded spans, which is what
        the message carries. Split by span.

        A single span bigger than the limit still travels on its own: it already
        passed the per-attribute and request size caps.
        """
        message = self.to_message()
        if len(message["spans_gz"]) <= max_message_bytes or len(self.spans) <= 1:
            return [message]
        middle = len(self.spans) // 2
        return [
            part
            for half in (self.spans[:middle], self.spans[middle:])
            for part in IngestJob(
                half, self.organization_id, self.user_id, self.project_id, self.pre_store_hooks
            ).messages(max_message_bytes)
        ]


# ---------------------------------------------------------------------------
# Span limits
# ---------------------------------------------------------------------------


def _truncate(value: Any, max_chars: int) -> tuple[Any, bool]:
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars], True
    if isinstance(value, list) and any(isinstance(v, str) and len(v) > max_chars for v in value):
        return [v[:max_chars] if isinstance(v, str) else v for v in value], True
    return value, False


def _limit_attributes(
    attributes: Dict[str, Any], settings: TraceIngestSettings
) -> tuple[Dict[str, Any], List[str], int]:
    kept: Dict[str, Any] = {}
    truncated: List[str] = []
    # Rhesis's own keys first: the trace views, metrics and token counts read them.
    keys = sorted(attributes, key=lambda key: not key.startswith(_OWN_PREFIXES))
    for index, key in enumerate(keys):
        if index >= settings.max_attributes_per_span:
            return kept, truncated, len(attributes) - index
        kept[key], cut = _truncate(attributes[key], settings.max_attribute_chars)
        if cut:
            truncated.append(key)
    return kept, truncated, 0


def apply_span_limits(spans: Sequence[OTELSpan], settings: TraceIngestSettings) -> None:
    """Bound each span's size in place. Raises :class:`TooManySpans`.

    Values are cut rather than the span refused, and the cut is recorded on the
    span, so a large tool result still shows, marked as partial.
    """
    if len(spans) > settings.max_spans_per_request:
        raise TooManySpans(
            f"{len(spans)} spans in one request; the limit is {settings.max_spans_per_request}"
        )
    for span in spans:
        # Both are written to columns and used in lookups; PostgreSQL rejects NUL.
        span.conversation_id = clean_strings_recursive(span.conversation_id)
        span.environment = clean_strings_recursive(span.environment)
        attributes, truncated, dropped = _limit_attributes(span.attributes, settings)
        if len(span.events) > settings.max_events_per_span:
            attributes[DROPPED_EVENTS] = len(span.events) - settings.max_events_per_span
            span.events = span.events[: settings.max_events_per_span]
        for event in span.events:
            event.attributes, cut, _ = _limit_attributes(event.attributes, settings)
            truncated.extend(f"event:{event.name}:{key}" for key in cut)
        if truncated:
            attributes[TRUNCATED_ATTRIBUTES] = sorted(set(truncated))
        if dropped:
            attributes[DROPPED_ATTRIBUTES] = dropped
        span.attributes = attributes
        if span.status_message:
            span.status_message, _ = _truncate(span.status_message, settings.max_attribute_chars)


# ---------------------------------------------------------------------------
# Storage (worker side)
# ---------------------------------------------------------------------------


@dataclass
class StoredBatch:
    """What one call to :func:`process_ingest_job` stored: the new rows, as inserted
    (still readable after the commit)."""

    spans: List[Any] = field(default_factory=list)
    trace_ids: List[str] = field(default_factory=list)

    @property
    def span_count(self) -> int:
        return len(self.spans)


def _inject_pending_output(spans: List[OTELSpan], organization_id: str, project_id: str) -> None:
    # Mutates span attributes, so it has to run before storage.
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        inject_pending_output,
    )

    try:
        injected = inject_pending_output(spans, organization_id, project_id)
        if injected:
            logger.info(f"Injected mapped output into {injected} span(s)")
    except Exception as exc:
        logger.warning(f"Failed to inject pending output: {exc}")
        logger.debug("Pending output injection traceback:", exc_info=True)


def _run_pre_store_hooks(db: Session, job: IngestJob) -> None:
    for name in job.pre_store_hooks:
        hook = _PRE_STORE_HOOKS.get(name)
        if hook is None:
            # Store anyway: losing the spans is worse than skipping an enrichment.
            logger.error(f"Ingest pre-store hook {name!r} is not registered in this worker")
            continue
        hook(db, job.spans, job.organization_id, job.project_id)


def process_ingest_job(db: Session, job: IngestJob) -> StoredBatch:
    """Store a queued job's spans, enriched, and commit. Does not run post-processing.

    Spans already stored (same ``trace_id`` and ``span_id``) are skipped, so a
    retried export is safe. Raises :class:`SpanStorageError` when the write fails.
    """
    spans, organization_id, project_id = job.spans, job.organization_id, job.project_id
    for span in spans:
        span.project_id = project_id
    _inject_pending_output(spans, organization_id, project_id)

    try:
        with temporary_project_scope(db, organization_id, job.user_id or "", project_id):
            # Hooks run first and take their own locks, in an order of their
            # choosing; a hook that re-files spans locks the traces it writes.
            # store_spans locks the traces it stores.
            _run_pre_store_hooks(db, job)
            stored = store_spans(db, spans, organization_id)
        db.commit()
    except DataError as exc:
        db.rollback()
        logger.error(
            f"Trace ingestion refused by the database, dropping | org={organization_id} | "
            f"project={project_id} | spans={len(spans)} | error={exc}",
            exc_info=True,
        )
        raise UnstorableSpans(str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.error(
            f"Trace ingestion failed | org={organization_id} | project={project_id} | "
            f"spans={len(spans)} | error_type={type(exc).__name__} | error={exc}",
            exc_info=True,
        )
        raise SpanStorageError(str(exc)) from exc

    if not stored:
        return StoredBatch()
    return StoredBatch(spans=stored, trace_ids=list({s.trace_id for s in stored}))
