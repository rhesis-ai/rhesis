"""The single primitive for creating an in-app notification.

Callable from anywhere a completed job needs to tell its recipient: a Celery
task's on_success/on_failure (see tasks/base.py's in_app_notification hook),
a live websocket handler, or a router. Takes project_id explicitly rather
than reading it from ambient scope, since not every caller has a request-
scoped session to read it from.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.notification import create_notification
from rhesis.backend.app.schemas.notification import NotificationRead
from rhesis.backend.app.schemas.websocket import EventType, UserTarget, WebSocketMessage
from rhesis.backend.app.services.notification.catalog import (
    NOTIFICATION_CATALOG,
    RenderedNotification,
)
from rhesis.backend.app.services.websocket.publisher import publish_event

logger = logging.getLogger(__name__)


def notify(
    db: Session,
    *,
    event_type: str,
    rendered: RenderedNotification,
    user_id: str,
    organization_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    """Persist *rendered* for its recipient and push it over their websocket.

    Publishing never raises -- a Redis failure must not fail the caller,
    matching how ``BaseTask._send_task_completion_email`` never breaks task
    completion on email failure.
    """
    kind = NOTIFICATION_CATALOG[event_type]
    payload = {"entity_ids": rendered.entity_ids} if rendered.entity_ids else None

    # .value if event_type is an enum member (the normal case), else already
    # a plain string -- NotificationEventType members don't override
    # __str__, so str(event_type) would return "TestSet.X" on Python <=3.11.
    event_type_value = getattr(event_type, "value", event_type)

    notification = create_notification(
        db,
        event_type=event_type_value,
        section=kind.section.value,
        title=rendered.title,
        body=rendered.body,
        is_failure=rendered.is_failure,
        entity_type=kind.entity_type,
        entity_id=rendered.entity_id,
        payload=payload,
        user_id=user_id,
        organization_id=organization_id,
        project_id=project_id,
    )

    try:
        notification_read = NotificationRead.model_validate(notification)
        publish_event(
            WebSocketMessage(
                type=EventType.NOTIFICATION,
                payload=notification_read.model_dump(mode="json"),
            ),
            UserTarget(user_id=str(user_id)),
        )
    except Exception:
        logger.exception("Failed to publish notification event for user %s", user_id)
