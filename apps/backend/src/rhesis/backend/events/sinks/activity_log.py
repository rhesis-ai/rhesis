"""Writes user-facing job logs to the ``activity_log`` table.

Without a caller session it opens its own and commits immediately, so a log
line survives the task transaction rolling back -- you want the failure
narrative precisely when the transaction dies. With ``emit(..., db=...)`` it
joins the caller's transaction instead (flush, not commit -- the dispatcher
promises "join", and committing would also commit the caller's unrelated
pending work), so the line lands or rolls back with the work it describes.
Non-critical: a dropped log line must never fail the work it describes.
"""

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app.crud.job import get_job_by_celery_task_id
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.events.rendering import render
from rhesis.backend.events.types import (
    ActivityLogged,
    JobCancelled,
    JobCompleted,
    JobFailed,
    JobQueued,
    JobRetried,
    JobStarted,
    PlatformEvent,
)

logger = logging.getLogger(__name__)

_HANDLED = (
    JobQueued,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobRetried,
    JobCancelled,
    ActivityLogged,
)


class ActivityLogSink:
    name = "activity_log"
    critical = False

    def handles(self, event: PlatformEvent) -> bool:
        return isinstance(event, _HANDLED)

    def deliver(self, event: PlatformEvent, db: Optional[Session]) -> None:
        """Write one row, on ``db`` when given, else on a session of its own.
        See the module docstring for what each choice promises.
        """
        if isinstance(event, ActivityLogged):
            level, message = event.level, event.message
        else:
            level, message = render(event)

        if db is not None:
            self._write(db, event, level, message)
            db.flush()
            return

        with get_db_with_tenant_variables(
            str(event.organization_id),
            str(event.user_id) if event.user_id else "",
            str(event.project_id) if event.project_id else "",
        ) as own_db:
            self._write(own_db, event, level, message)
            own_db.commit()

    @staticmethod
    def _write(db: Session, event: PlatformEvent, level: str, message: str) -> None:
        # Prefer the id the emitter stamped (see types.py); the indexed lookup
        # by celery_task_id is the fallback for callers that never learned it.
        # A miss either way (e.g. an untracked job type) still writes the
        # entry, just with no job to attach it to.
        job_id = event.job_id
        if job_id is None and event.celery_task_id:
            job = get_job_by_celery_task_id(
                db, event.celery_task_id, organization_id=str(event.organization_id)
            )
            job_id = job.id if job is not None else None

        # Monotonic per job via MAX+1, not a DB sequence: Postgres has no
        # native per-FK-value sequence, and at this platform's job volume
        # a rare race producing a duplicate ordinal (two concurrent log
        # lines for the same job landing in the same instant) costs a
        # cosmetic ordering wobble, not correctness.
        sequence = None
        if job_id is not None:
            max_sequence = (
                db.query(func.max(ActivityLog.sequence))
                .filter(ActivityLog.job_id == job_id)
                .scalar()
            )
            sequence = (max_sequence or 0) + 1

        entry = ActivityLog(
            job_id=job_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            source=event.source,
            sequence=sequence,
            level=level,
            message=message,
            context=event.context,
        )
        # Set explicitly rather than relying on auto_stamp, matching
        # tracking.create_job: the event has already resolved these, and
        # relying on ambient scope would be one more thing that could
        # silently disagree with what the event itself says.
        entry.organization_id = event.organization_id
        if event.project_id:
            entry.project_id = event.project_id

        db.add(entry)
