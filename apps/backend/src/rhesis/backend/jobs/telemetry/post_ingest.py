"""Celery task for post-ingestion linking and enrichment dispatch.

Runs after spans are stored in the database. Handles:
1. Test-result linking (traces <-> test results)
2. Conversation-id linking (first-turn patching)
3. Input file linking (SDK turns with file attachments)
4. Enrichment pipeline dispatch (enrich -> evaluate chain per trace)
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.database import SessionLocal, bind_scope_to_session
from rhesis.backend.app.services.telemetry.post_ingest import process_stored_spans
from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def post_ingest_link(
    self,
    stored_span_ids: List[str],
    unique_trace_ids: List[str],
    organization_id: str,
    project_id: str,
    test_run_id: Optional[str] = None,
    test_id: Optional[str] = None,
    test_configuration_id: Optional[str] = None,
) -> dict:
    """Link ingested spans and queue their evaluations.

    Batches stored by this release are processed inline by ``ingest_spans``; this
    task remains for messages the previous release queued.

    Args:
        stored_span_ids: Database primary keys of the stored spans.
        unique_trace_ids: Unique OTEL trace IDs in this batch.
        organization_id: Organization UUID string.
        project_id: Project UUID string.
        test_run_id: Test run UUID (if test execution trace).
        test_id: Test UUID (if test execution trace).
        test_configuration_id: Test configuration UUID (if test execution trace).
    """
    db: Session = SessionLocal()

    try:
        bind_scope_to_session(db, organization_id, "", project_id)

        stored_spans = db.query(models.Trace).filter(models.Trace.id.in_(stored_span_ids)).all()

        if not stored_spans:
            logger.warning(
                f"post_ingest_link: no spans found for ids (count={len(stored_span_ids)})"
            )
            return {"status": "no_spans", "trace_ids": unique_trace_ids}

        result = process_stored_spans(
            db, stored_spans, unique_trace_ids, organization_id, project_id
        )
        return {"status": "success", "trace_ids": unique_trace_ids, **result}

    except Exception as e:
        logger.error(
            f"post_ingest_link failed (traces={unique_trace_ids}): {e}",
            exc_info=True,
        )
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for post_ingest_link (traces={unique_trace_ids})")
            return {
                "status": "error",
                "trace_ids": unique_trace_ids,
                "message": str(e),
            }

    finally:
        db.close()
