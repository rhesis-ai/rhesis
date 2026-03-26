"""Celery task for post-ingestion linking and enrichment dispatch.

Runs after spans are stored in the database. Handles:
1. Test-result linking (traces <-> test results)
2. Conversation-id linking (first-turn patching)
3. Input file linking (SDK turns with file attachments)
4. Enrichment pipeline dispatch (enrich -> evaluate chain per trace)
"""

import logging
from typing import List, Optional

from celery import shared_task
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.database import SessionLocal, set_session_variables

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
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
    """Link ingested spans and dispatch enrichment.

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
        set_session_variables(db, organization_id, "")

        stored_spans = db.query(models.Trace).filter(models.Trace.id.in_(stored_span_ids)).all()

        if not stored_spans:
            logger.warning(
                f"post_ingest_link: no spans found for ids (count={len(stored_span_ids)})"
            )
            return {"status": "no_spans", "trace_ids": unique_trace_ids}

        linked_count = 0
        conversation_linked = 0
        files_created = 0

        # 1. Test-result linking
        from rhesis.backend.app.services.telemetry.linking_service import (
            TraceLinkingService,
        )

        linking_service = TraceLinkingService(db)
        try:
            linked_count = linking_service.link_traces_for_incoming_batch(
                spans=stored_spans,
                organization_id=organization_id,
            )
            if linked_count > 0:
                logger.info(
                    f"Linked {linked_count} traces to test result (traces={unique_trace_ids})"
                )
        except Exception as link_error:
            logger.warning(f"Failed to link traces (traces={unique_trace_ids}): {link_error}")
            logger.debug("Trace linking traceback:", exc_info=True)

        # 2. Conversation-id linking
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            apply_pending_conversation_links,
            apply_pending_files,
        )

        try:
            conversation_linked = apply_pending_conversation_links(db, stored_spans)
            if conversation_linked > 0:
                logger.info(
                    f"Applied {conversation_linked} pending conversation "
                    f"links (traces={unique_trace_ids})"
                )
        except Exception as conversation_error:
            logger.warning(
                f"Failed to apply conversation links "
                f"(traces={unique_trace_ids}): {conversation_error}"
            )
            logger.debug("Conversation linking traceback:", exc_info=True)

        # 3. Input file linking
        try:
            files_created = apply_pending_files(db, stored_spans)
            if files_created > 0:
                logger.info(f"Created {files_created} pending file(s) (traces={unique_trace_ids})")
        except Exception as file_error:
            logger.warning(
                f"Failed to apply pending files (traces={unique_trace_ids}): {file_error}"
            )
            logger.debug("File linking traceback:", exc_info=True)

        # 4. Dispatch enrichment pipeline per root span so each turn in a
        #    multi-turn conversation gets its own evaluation task keyed by
        #    the root span's DB primary key.
        from rhesis.backend.app.services.telemetry.enrichment import (
            build_enrichment_chain,
        )
        from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async

        root_spans_in_batch = [s for s in stored_spans if s.parent_span_id is None]
        dispatched_traces: set[str] = set()

        for root_span in root_spans_in_batch:
            try:
                workflow = build_enrichment_chain(
                    root_span.trace_id,
                    project_id,
                    organization_id,
                    root_span_id=str(root_span.id),
                )
                workflow.apply_async()
                dispatched_traces.add(root_span.trace_id)
            except Exception as enrich_error:
                logger.warning(
                    f"Failed to enqueue enrichment for root span "
                    f"{root_span.id} (trace {root_span.trace_id}): {enrich_error}"
                )

        for trace_id in unique_trace_ids:
            if trace_id not in dispatched_traces:
                try:
                    enrich_trace_async.delay(trace_id, project_id, organization_id)
                except Exception as enrich_error:
                    logger.warning(
                        f"Failed to enqueue enrichment for trace {trace_id}: "
                        f"{enrich_error}"
                    )

        return {
            "status": "success",
            "trace_ids": unique_trace_ids,
            "linked": linked_count,
            "conversation_linked": conversation_linked,
            "files_created": files_created,
        }

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
