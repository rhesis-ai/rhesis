"""Pushes job events to the ``job:{job_id}`` WebSocket channel.

Non-critical, same reasoning as ``ActivityLogSink``: a dropped live-update
push must never fail the work it describes -- the row in ``activity_log``
(and the next poll, if a client falls back to one) is still the record of
truth. This sink only shortens the time until a connected client sees it.

Opens its own read-only session to resolve ``job_id`` from
``celery_task_id``, for the same cross-connection-visibility reason
``ActivityLogSink`` does: the caller's row may only be flushed, not
committed, on the caller's own session.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.job import get_job_by_celery_task_id
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
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

# Lifecycle events that change the job row itself -- published as a separate
# JOB_STATUS_CHANGED message so a subscriber can update the header (e.g. a
# status chip) without waiting for the activity list to re-render.
#
# JobRetried maps to "running" rather than being omitted: tracking.mark_retrying
# deliberately leaves status at running and moves only the attempt counter, and
# that counter is on the same header. Without an entry here a retry would
# refresh the activity list while leaving the displayed attempt stale.
_STATUS_BY_EVENT = {
    JobStarted: "running",
    JobRetried: "running",
    JobCompleted: "completed",
    JobFailed: "failed",
    JobCancelled: "cancelled",
}


class WebSocketSink:
    name = "websocket"
    critical = False

    def handles(self, event: PlatformEvent) -> bool:
        return isinstance(event, _HANDLED)

    def deliver(self, event: PlatformEvent, db: Optional[Session]) -> None:
        """Ignores ``db``: this sink's channel resolution needs its own
        session for the same reason ``ActivityLogSink`` does. See the module
        docstring.
        """
        if isinstance(event, ActivityLogged):
            level, message = event.level, event.message
        else:
            level, message = render(event)

        if not event.celery_task_id:
            return

        with get_db_with_tenant_variables(
            str(event.organization_id),
            str(event.user_id) if event.user_id else "",
            str(event.project_id) if event.project_id else "",
        ) as own_db:
            job = get_job_by_celery_task_id(
                own_db, event.celery_task_id, organization_id=str(event.organization_id)
            )
            # Read the id inside the block: the instance is detached once the
            # session closes, and this must not depend on expire_on_commit
            # staying False.
            job_id = str(job.id) if job is not None else None

        if job_id is None:
            # No job row to key a channel on -- nobody can be subscribed to
            # "job:None". Matches ActivityLogSink's same fallback.
            return

        channel = ChannelTarget(channel=f"job:{job_id}")

        publish_event(
            WebSocketMessage(
                type=EventType.JOB_ACTIVITY_APPENDED,
                channel=channel.channel,
                payload={"level": level, "message": message},
            ),
            channel,
        )

        new_status = _STATUS_BY_EVENT.get(type(event))
        if new_status is not None:
            publish_event(
                WebSocketMessage(
                    type=EventType.JOB_STATUS_CHANGED,
                    channel=channel.channel,
                    payload={"status": new_status},
                ),
                channel,
            )
