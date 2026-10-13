"""Deleting export files a week after their job finished.

An export is a hand-off, not an archive: the log itself stays the record, and
a file of it left in storage is a second copy outside retention, the role
checks and the purge. So each file goes ``FILE_LIFETIME`` after its job
finished, whatever the org's retention. Run per org by the daily audit purge
(core ``jobs/audit_retention.py``), which ``register_audit`` hooks this into.

The files are found from the ``job`` rows, never by listing storage. Once a
file is gone (deleted here, or already missing) its job gets
``job_metadata["file_deleted_at"]``, so it is not looked at again and the
download says the file no longer exists.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.job import get_finished_jobs_without_marker, mark_jobs
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.storage_service import StorageService
from rhesis.backend.ee.audit.export.service import (
    CONTENT_TYPES,
    FILE_DELETED_KEY,
    JOB_TYPE,
    storage_path,
)

logger = logging.getLogger(__name__)

FILE_LIFETIME = timedelta(days=7)
#: Jobs handled per org per run; any beyond wait for the next day.
BATCH_SIZE = 500


def delete_expired_exports(
    db: Session, org: Organization, now: datetime, storage: StorageService | None = None
) -> int:
    """Delete ``org``'s export files older than ``FILE_LIFETIME``; returns how many
    jobs no longer have a file. A file storage fails on is left for the next run."""
    jobs = get_finished_jobs_without_marker(
        db, org.id, JOB_TYPE, now - FILE_LIFETIME, FILE_DELETED_KEY, BATCH_SIZE
    )
    if not jobs:
        return 0
    storage = storage or StorageService()
    gone = []
    for job in jobs:
        fmt = (job.job_metadata or {}).get("format")
        try:
            if fmt in CONTENT_TYPES and job.celery_task_id:
                storage.remove_object(storage_path(org.id, job.celery_task_id, fmt))
        except Exception:
            logger.exception("Could not delete the file of audit export job %s", job.id)
            continue
        gone.append(job.id)
    mark_jobs(db, org.id, gone, FILE_DELETED_KEY, now.isoformat())
    return len(gone)
