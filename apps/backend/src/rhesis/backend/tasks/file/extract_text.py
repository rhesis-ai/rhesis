"""Celery task for asynchronous text extraction from uploaded files.

This task is dispatched immediately after a file is uploaded.  It fetches the
file bytes from object storage, runs the appropriate extractor, and persists the
result on the File row so the execution pipeline can read ``extracted_text``
without re-running OCR/vision per invocation.
"""

import logging

from rhesis.backend.celery.core import app

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="rhesis.backend.tasks.file.extract_text",
)
def extract_file_text(
    self,
    file_id: str,
    storage_path: str,
    filename: str,
    content_type: str,
    content_hash: str,
    organization_id: str,
) -> None:
    """Fetch file bytes from storage and persist extracted text on the File row.

    Idempotent: if a File row with the same content_hash already has
    ``extraction_status='done'``, the task exits early without re-running.
    """
    import uuid

    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.models.file import File
    from rhesis.backend.app.services.storage_service import StorageService

    try:
        storage = StorageService()

        with get_db_with_tenant_variables(organization_id, "") as db:
            file_row = db.query(File).filter(File.id == uuid.UUID(file_id)).first()
            if not file_row:
                logger.warning(f"[EXTRACT] File row not found: file_id={file_id}")
                return

            # Idempotency: skip if already done
            if file_row.extraction_status == "done":
                logger.debug(f"[EXTRACT] Already done for file_id={file_id}, skipping.")
                return

            # Non-extractable MIME types
            extractable_prefixes = ("image/", "application/pdf", "text/")
            if not any(content_type.startswith(p) for p in extractable_prefixes):
                file_row.extraction_status = "not_applicable"
                db.commit()
                logger.debug(
                    f"[EXTRACT] MIME type {content_type} not extractable — "
                    f"marked not_applicable for file_id={file_id}"
                )
                return

            # Read bytes from storage (synchronous fsspec read in worker context)
            full_path = storage._full_path(storage_path)
            with storage.fs.open(full_path, "rb") as f:
                content = f.read()

            from rhesis.sdk.services.extractor import extract_with_vision_fallback

            extracted = extract_with_vision_fallback(content, filename, content_type)

            file_row.extracted_text = extracted
            file_row.extraction_status = "done"
            db.commit()

            logger.info(
                f"[EXTRACT] Extracted {len(extracted or '')} chars "
                f"from file_id={file_id} ({filename})"
            )

    except Exception as exc:
        logger.error(
            f"[EXTRACT] Extraction failed for file_id={file_id}: {exc}", exc_info=True
        )
        try:
            with get_db_with_tenant_variables(organization_id, "") as db:
                file_row = db.query(File).filter(File.id == uuid.UUID(file_id)).first()
                if file_row:
                    file_row.extraction_status = "failed"
                    db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
