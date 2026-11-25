"""Celery task that stores queued trace spans, then links and queues their evaluation."""

import logging
from typing import Any, Dict

from sqlalchemy.exc import InterfaceError, OperationalError

from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.services.telemetry.ingest import (
    IngestJob,
    SpanStorageError,
    StoredBatch,
    UnstorableSpans,
    process_ingest_job,
)
from rhesis.backend.app.services.telemetry.post_ingest import process_stored_spans
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


def finish_stored_batch(db, batch: StoredBatch, job: IngestJob) -> None:
    """Link, queue evaluations for, and meter the batch just stored, on this session.

    The spans are committed, so a failure here is logged, not retried: retrying the
    ingest would re-run storage for nothing.
    """
    if not batch.spans:
        return
    try:
        process_stored_spans(db, batch.spans, batch.trace_ids, job.organization_id, job.project_id)
    except Exception as exc:
        db.rollback()
        logger.warning(
            f"Post-ingest processing failed | traces={batch.trace_ids} | "
            f"error_type={type(exc).__name__} | error={exc}",
            exc_info=True,
        )


# Exporters already retried before the request was accepted; these retries cover
# a database blip between acceptance and storage. acks_late (global) means a
# worker lost mid-task redelivers the message, and duplicate spans are skipped.
@app.task(bind=True, max_retries=5, default_retry_delay=10, acks_late=True)
def ingest_spans(self, message: Dict[str, Any]) -> Dict[str, Any]:
    """Store the spans of one queued :class:`IngestJob` message."""
    job = IngestJob.from_message(message)
    db = SessionLocal()
    try:
        bind_scope_to_session(db, job.organization_id, job.user_id or "", job.project_id)
        try:
            batch = process_ingest_job(db, job)
        except UnstorableSpans:
            # Logged by process_ingest_job; the same values would fail every retry.
            return {"stored": 0, "received": len(job.spans), "trace_ids": []}
        except (SpanStorageError, OperationalError, InterfaceError) as exc:
            # InterfaceError/OperationalError: the database was unreachable before storage.
            raise self.retry(exc=exc, countdown=min(10 * 2**self.request.retries, 300))

        logger.info(
            f"Ingested {batch.span_count} of {len(job.spans)} span(s) | "
            f"traces={batch.trace_ids} | org={job.organization_id} | project={job.project_id}"
        )
        finish_stored_batch(db, batch, job)
    finally:
        db.close()
    return {"stored": batch.span_count, "received": len(job.spans), "trace_ids": batch.trace_ids}


def enqueue_ingest(job: IngestJob, max_message_bytes: int) -> int:
    """Queue ``job`` on the trace-ingest queue, split by message size. Returns messages."""
    messages = job.messages(max_message_bytes)
    for message in messages:
        ingest_spans.apply_async(kwargs={"message": message})
    return len(messages)
