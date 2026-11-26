"""Celery task for asynchronous text extraction from uploaded files.

This task is dispatched immediately after a file is uploaded.  It fetches the
file bytes from object storage, runs the appropriate extractor, and persists the
result on the File row so the execution pipeline can read ``extracted_text``
without re-running OCR/vision per invocation.
"""

import logging

from celery.exceptions import SoftTimeLimitExceeded

from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="rhesis.backend.jobs.file.extract_text",
)
def extract_file_text(
    self,
    file_id: str,
    storage_path: str,
    filename: str,
    content_type: str,
    content_hash: str,
    organization_id: str,
    project_id: str = "",
) -> None:
    """Fetch file bytes from storage and persist extracted text on the File row.

    Idempotent: if a File row with the same content_hash already has
    ``extraction_status='done'``, the task exits early without re-running.

    ``project_id`` is the file's own project (empty for org-level files). It must
    be passed so the session's ``app.current_project`` GUC matches the row: under
    the fail-closed project_isolation RLS policy, a session with the org set but
    no project can only see ``project_id IS NULL`` rows, so a project-scoped file
    would otherwise be invisible here and extraction would silently no-op.
    """
    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.services import file_extraction
    from rhesis.backend.app.services.storage_service import StorageService

    def session():
        return get_db_with_tenant_variables(organization_id, "", project_id)

    try:
        with session() as db:
            if not file_extraction.needs_extraction(db, file_id, content_type):
                logger.debug(f"[EXTRACT] Nothing to extract for file_id={file_id}")
                return

        # No session is open from here: extraction can take minutes.
        storage = StorageService()
        with storage.fs.open(storage._full_path(storage_path), "rb") as f:
            content = f.read()

        from rhesis.sdk.services.extractor import extract_with_vision_fallback

        extracted = extract_with_vision_fallback(content, filename, content_type)

        with session() as db:
            saved = file_extraction.record_extraction(db, file_id, "done", extracted)
        if not saved:
            logger.warning(f"[EXTRACT] Result not saved, file gone or already done: {file_id}")
            return

        logger.info(
            f"[EXTRACT] Extracted {len(extracted or '')} chars from file_id={file_id} ({filename})"
        )

    except Exception as exc:
        logger.error(f"[EXTRACT] Extraction failed for file_id={file_id}: {exc}", exc_info=True)
        try:
            with session() as db:
                file_extraction.record_extraction(db, file_id, "failed")
        except Exception:
            pass
        if isinstance(exc, SoftTimeLimitExceeded):
            raise  # The same file would hit the limit again.
        raise self.retry(exc=exc)
