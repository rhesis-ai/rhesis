"""Exporting the audit log.

``start_export`` (the request) checks the filter, records ``audit_log.exported``
and queues the job. ``run_export`` (the job) reads the matching events in
batches, keyset on ``(occurred_at, id)``, and writes them straight to storage,
so memory stays flat however large the export. Each row has the shape
``GET /audit-events`` lists; content values are never exported.

The file lives at ``audit-exports/{org}/{celery task id}.{format}``. The
download route finds it from the ``job`` row, so a link never outlives the
caller's access: it is checked, and recorded as a read, on every download.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Iterator, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.crud.job import get_job, get_job_by_celery_task_id
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.models.audit_capture import audit_enabled
from rhesis.backend.app.models.enums import JobStatus
from rhesis.backend.app.services.audit_events import record_audit_event
from rhesis.backend.ee.audit import crud
from rhesis.backend.ee.audit.models import AuditEvent
from rhesis.backend.ee.audit.schemas import (
    AuditEventRead,
    AuditExportCreate,
    AuditExportCreated,
    event_payload,
)
from rhesis.backend.events.audit_actions import audit_action
from rhesis.backend.events.types import FieldChange

EXPORTED = audit_action(Permission.AuditLog.EXPORT.value)
VIEWED = audit_action(Permission.AuditLog.READ.value)
#: The ``job`` row's ``job_type``; the task's name is this under ``rhesis.backend.jobs.``.
JOB_TYPE = "audit_log.export"
BATCH_SIZE = 1000
#: How long a download's presigned link works. Each download signs a new one.
LINK_SECONDS = 300

CONTENT_TYPES = {"jsonl": "application/x-ndjson", "csv": "text/csv"}
CSV_COLUMNS = list(AuditEventRead.model_fields)
# A cell starting with one of these runs as a formula in a spreadsheet (OWASP CSV injection).
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


class ExportNotAvailable(Exception):
    """The org cannot export: it has no audit log (not licensed, or lapsed)."""


class ExportNotFound(LookupError):
    pass


class ExportNotReady(Exception):
    pass


@dataclass(frozen=True)
class ExportFile:
    path: str
    format: str
    filename: str

    @property
    def content_type(self) -> str:
        return CONTENT_TYPES[self.format]


def storage_path(organization_id, celery_task_id, fmt: str) -> str:
    # UUID() so nothing but a task id we minted can shape the path.
    return f"audit-exports/{uuid.UUID(str(organization_id))}/{uuid.UUID(str(celery_task_id))}.{fmt}"


def download_path(job_id) -> str:
    return f"/audit-events/exports/{job_id}/download"


# ---------------------------------------------------------------------------
# Starting an export (request)
# ---------------------------------------------------------------------------


def start_export(db: Session, current_user, request: AuditExportCreate) -> AuditExportCreated:
    """Check the filter, record the export, queue the job.

    The audit row is written first, in the request's transaction, which
    ``launch_job`` commits together with the job row before it dispatches: no
    export runs without its record. Raises ``HTTPException`` 400 on a bad filter.
    """
    from rhesis.backend.ee.audit.export.jobs import export_audit_log
    from rhesis.backend.jobs import launch_job

    organization_id = str(current_user.organization_id)
    until = datetime.now(timezone.utc)
    crud.export_page(
        db,
        organization_id,
        filter=request.filter,
        sort_order=request.sort_order,
        until=until,
        after=None,
        limit=1,
    )
    record_audit_event(EXPORTED, organization_id, db=db, changes=_request_changes(request))

    celery_task_id = str(uuid.uuid4())
    # Org-wide: no project on the job row or the notification.
    with temporary_project_scope(db, organization_id, str(current_user.id), ""):
        launch_job(
            export_audit_log,
            current_user=current_user,
            db=db,
            celery_task_id=celery_task_id,
            job_metadata={**request.model_dump(), "until": until.isoformat()},
            export_format=request.format,
            odata_filter=request.filter,
            sort_order=request.sort_order,
            until=until.isoformat(),
        )
    job = get_job_by_celery_task_id(db, celery_task_id, organization_id=organization_id)
    return AuditExportCreated(
        job_id=job.id if job is not None else None,
        task_id=celery_task_id,
        format=request.format,
        message=(
            "Audit log export started. It appears on the Jobs screen, and a "
            "notification with the download link follows when it is ready."
        ),
    )


def _request_changes(request: AuditExportCreate) -> list[FieldChange]:
    return [
        FieldChange(field=name, kind="value", after=value)
        for name, value in request.model_dump().items()
        if value is not None
    ]


# ---------------------------------------------------------------------------
# Writing the file (job)
# ---------------------------------------------------------------------------


def run_export(
    db: Session,
    storage,
    organization_id: str,
    *,
    fmt: str,
    filter: Optional[str],
    sort_order: str,
    until: datetime,
    path: str,
    progress: Callable[[int, int], None],
) -> dict:
    """Write every matching event that happened by ``until`` to ``path``."""
    if not audit_enabled(db, organization_id):
        raise ExportNotAvailable("The audit log is not available for this organization")
    total = crud.count_export_events(db, organization_id, filter, until)
    progress(0, total)
    written = 0

    def counted(batches: Iterable[list[AuditEvent]]) -> Iterator[list[AuditEvent]]:
        nonlocal written
        for rows in batches:
            yield rows
            written += len(rows)
            progress(written, max(total, written))

    batches = counted(_batches(db, organization_id, filter, sort_order, until))
    chunks = _jsonl_chunks(batches) if fmt == "jsonl" else _csv_chunks(batches)
    _, sha256, size = storage.put_object_chunks(chunks, path)
    return {"rows": written, "bytes": size, "sha256": sha256}


def _batches(
    db: Session, organization_id: str, filter: Optional[str], sort_order: str, until: datetime
) -> Iterator[list[AuditEvent]]:
    after = None
    while True:
        rows = crud.export_page(
            db,
            organization_id,
            filter=filter,
            sort_order=sort_order,
            until=until,
            after=after,
            limit=BATCH_SIZE,
        )
        if rows:
            yield rows
        if len(rows) < BATCH_SIZE:
            return
        after = (rows[-1].occurred_at, rows[-1].id)
        # One short read transaction per batch, so a large export holds back no vacuum.
        db.commit()


def _jsonl_chunks(batches: Iterable[list[AuditEvent]]) -> Iterator[bytes]:
    for rows in batches:
        lines = (json.dumps(event_payload(row), separators=(",", ":")) for row in rows)
        yield "".join(f"{line}\n" for line in lines).encode()


def _csv_chunks(batches: Iterable[list[AuditEvent]]) -> Iterator[bytes]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for rows in batches:
        for row in rows:
            payload = event_payload(row)
            writer.writerow([csv_cell(payload[column]) for column in CSV_COLUMNS])
        yield _drain(buffer)
    yield _drain(buffer)


def _drain(buffer: io.StringIO) -> bytes:
    data = buffer.getvalue().encode()
    buffer.seek(0)
    buffer.truncate()
    return data


def csv_cell(value) -> str:
    """One CSV cell: JSON for ``changes``, and text a spreadsheet will not run."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    text = str(value)
    if isinstance(value, str) and text.startswith(_FORMULA_START):
        return f"'{text}"
    return text


# ---------------------------------------------------------------------------
# Finding a finished export (download)
# ---------------------------------------------------------------------------


def record_download(db: Session, organization_id: str, job_id, export: "ExportFile") -> None:
    """Every download is its own read of the log, never folded into the
    once-a-minute ``audit_log.viewed`` of browsing."""
    record_audit_event(
        VIEWED, organization_id, db=db, resource_id=job_id, resource_label=export.filename
    )


def finished_export(db: Session, job_id, organization_id: str, user_id: str) -> ExportFile:
    """The file of the org's export job ``job_id``.

    Raises ``ExportNotFound`` for another job type or org, ``ExportNotReady``
    until the job has completed.
    """
    job = get_job(db, job_id, organization_id=organization_id, user_id=user_id, with_related=False)
    if job is None or job.job_type != JOB_TYPE or not job.celery_task_id:
        raise ExportNotFound(job_id)
    if job.status != JobStatus.COMPLETED.value:
        raise ExportNotReady(job.status)
    fmt = (job.job_metadata or {}).get("format")
    if fmt not in CONTENT_TYPES:
        raise ExportNotFound(job_id)
    finished = job.finished_at or job.created_at
    return ExportFile(
        path=storage_path(organization_id, job.celery_task_id, fmt),
        format=fmt,
        filename=f"audit-log-{finished:%Y%m%d-%H%M%S}.{fmt}",
    )
