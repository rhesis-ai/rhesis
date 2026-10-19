"""Whether the active project has an endpoint of its own, and the nudge when it doesn't."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.endpoint import user_endpoint_exists
from rhesis.backend.app.crud.notification import user_notification_exists
from rhesis.backend.app.crud.project import project_is_example
from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.schemas.endpoint import EndpointSetupStatus
from rhesis.backend.app.services.notification import RenderedNotification, notify

logger = logging.getLogger(__name__)


def get_endpoint_setup_status(
    db: Session, organization_id: str, user_id: str, project_id: Optional[str]
) -> EndpointSetupStatus:
    """Check the session's project scope for a non-example endpoint.

    Sends the user a one-time "set up an endpoint" notification for this project when
    there is none, except in the onboarding example project: it is a demo, so the user
    isn't nudged to wire it up.
    """
    if not project_id:
        return EndpointSetupStatus(configured=None)
    configured = user_endpoint_exists(db, organization_id)
    if not configured and not project_is_example(db, project_id):
        _maybe_notify(db, organization_id, user_id, project_id)
    return EndpointSetupStatus(configured=configured)


def _maybe_notify(db: Session, organization_id: str, user_id: str, project_id: str) -> None:
    """Never raises: a failed nudge must not fail the status read."""
    event_type = NotificationEventType.Endpoint.SETUP_REQUIRED
    try:
        if user_notification_exists(db, user_id, event_type.value, project_id):
            return
        notify(
            db,
            event_type=event_type,
            rendered=RenderedNotification(
                title="Set up an endpoint",
                body="Connect your AI application to this project so you can test it.",
            ),
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
        )
    except Exception:
        logger.exception(
            "Failed to send endpoint-setup notification for user %s in project %s",
            user_id,
            project_id,
        )
        db.rollback()
