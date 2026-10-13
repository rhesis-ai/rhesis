"""Celery job for audit log exports, listed in ``ee/celery_jobs.py``."""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.services.storage_service import StorageService
from rhesis.backend.celery.core import app
from rhesis.backend.ee.audit.export import service
from rhesis.backend.jobs.base import BaseJob, in_app_notification


@in_app_notification(NotificationEventType.AuditLog.EXPORT_COMPLETED)
@app.task(
    base=BaseJob,
    # Under rhesis.backend.jobs so the Jobs screen shows the type as audit_log.export.
    name=f"rhesis.backend.jobs.{service.JOB_TYPE}",
    bind=True,
    display_name="Audit Log Export",
    # A lapsed licence or a bad filter fails the same way on every attempt.
    dont_autoretry_for=BaseJob.dont_autoretry_for + (service.ExportNotAvailable, HTTPException),
)
def export_audit_log(
    self,
    export_format: str,
    odata_filter: Optional[str],
    sort_order: str,
    until: str,
) -> dict:
    organization_id, _, _ = self.get_tenant_context()
    path = service.storage_path(organization_id, self.request.id, export_format)
    with self.get_db_session() as db:
        result = service.run_export(
            db,
            StorageService(),
            organization_id,
            fmt=export_format,
            filter=odata_filter,
            sort_order=sort_order,
            until=datetime.fromisoformat(until),
            path=path,
            progress=self.set_progress,
        )
    self.emit(f"Exported {result['rows']} audit events ({result['bytes']} bytes)")
    job_id = self._resolve_job_id()
    # No link here: a Celery result is readable by anyone who can poll the job.
    return {
        **result,
        "format": export_format,
        "download_path": service.download_path(job_id) if job_id else None,
    }
