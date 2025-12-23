"""Celery task for async trace enrichment."""

import logging

from celery import shared_task
from sqlalchemy.orm import Session

from rhesis.backend.app.database import SessionLocal
from rhesis.backend.app.services.telemetry.enricher import TraceEnricher

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enrich_trace_async(self, trace_id: str, project_id: str) -> dict:
    """
    Enrich trace asynchronously in background.

    This reuses the same enrichment logic as sync enrichment.
    The only difference is it runs in a Celery worker.

    Args:
        trace_id: Trace ID to enrich
        project_id: Project ID for access control

    Returns:
        Enrichment result
    """
    db: Session = SessionLocal()

    try:
        logger.info(f"Starting async enrichment for trace {trace_id}")

        # Use same enricher as sync path (code reuse!)
        enricher = TraceEnricher(db)
        enriched_data = enricher.enrich_trace(trace_id, project_id)

        if enriched_data:
            # Get field names from Pydantic model
            enriched_fields = [
                field for field, value in enriched_data.model_dump().items() if value is not None
            ]
            logger.info(f"Completed async enrichment for trace {trace_id}: {enriched_fields}")

            return {
                "status": "success",
                "trace_id": trace_id,
                "enriched_fields": enriched_fields,
            }
        else:
            logger.warning(f"No spans found for trace {trace_id}")
            return {
                "status": "no_spans",
                "trace_id": trace_id,
            }

    except Exception as e:
        logger.error(f"Async enrichment failed for trace {trace_id}: {e}", exc_info=True)

        # Retry with exponential backoff
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for trace {trace_id}")
            return {"status": "error", "trace_id": trace_id, "message": str(e)}

    finally:
        db.close()
