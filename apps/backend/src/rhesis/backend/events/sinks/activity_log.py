"""Writes user-facing job logs to the ``activity_log`` table.

Opens its own session and commits immediately, so a log line survives the
task transaction rolling back -- you want the failure narrative precisely
when the transaction dies. Non-critical: a dropped log line must never fail
the work it describes.
"""

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
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
        """Ignores ``db``: this sink owns its durability, not the caller's
        transaction. See the module docstring.
        """
        if isinstance(event, ActivityLogged):
            level, message = event.level, event.message
        else:
            level, message = render(event)

        with get_db_with_tenant_variables(
            str(event.organization_id),
            str(event.user_id) if event.user_id else "",
            str(event.project_id) if event.project_id else "",
        ) as own_db:
            # Every job-lifecycle event carries celery_task_id, not job_id
            # directly (see types.py) -- resolved here via the same indexed
            # lookup crud.job.get_job_by_celery_task_id uses. A miss (job row
            # not found, e.g. an untracked job type) still writes the entry,
            # just with no job to attach it to.
            job_id = None
            if event.celery_task_id:
                job_id = (
                    own_db.query(Job.id).filter(Job.celery_task_id == event.celery_task_id).scalar()
                )

            # Monotonic per job via MAX+1, not a DB sequence: Postgres has no
            # native per-FK-value sequence, and at this platform's job volume
            # a rare race producing a duplicate ordinal (two concurrent log
            # lines for the same job landing in the same instant) costs a
            # cosmetic ordering wobble, not correctness.
            sequence = None
            if job_id is not None:
                max_sequence = (
                    own_db.query(func.max(ActivityLog.sequence))
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

            own_db.add(entry)
            own_db.commit()
