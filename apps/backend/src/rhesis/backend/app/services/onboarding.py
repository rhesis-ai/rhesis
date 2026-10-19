"""Seeded example rows never count. Project-scoped rows are checked per visible project under
``temporary_project_scope``."""

import logging

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.endpoint import user_endpoint_exists
from rhesis.backend.app.crud.notification import user_notification_exists
from rhesis.backend.app.crud.project import list_visible_project_example_flags
from rhesis.backend.app.crud.test import user_test_exists
from rhesis.backend.app.crud.test_set import user_test_set_exists
from rhesis.backend.app.crud.user import other_org_member_exists
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.app.schemas.user import OnboardingStatus
from rhesis.backend.app.services.notification import RenderedNotification, notify

logger = logging.getLogger(__name__)

# Empty project id means the org-level scope, where project_id IS NULL rows live.
_ORG_LEVEL_SCOPE = ""


def get_onboarding_status(db: Session, organization_id: str, user_id: str) -> OnboardingStatus:
    """Return which onboarding steps the caller's organization has really done."""
    projects = list_visible_project_example_flags(db, organization_id, user_id)
    endpoint_setup, test_cases_created = _scan_project_data(
        db, organization_id, user_id, [str(project_id) for project_id, _ in projects]
    )
    if not endpoint_setup:
        _maybe_notify_endpoint_setup(db, organization_id, user_id)
    return OnboardingStatus(
        project_created=any(not is_example for _, is_example in projects),
        endpoint_setup=endpoint_setup,
        users_invited=other_org_member_exists(db, organization_id, user_id),
        test_cases_created=test_cases_created,
    )


def _scan_project_data(
    db: Session, organization_id: str, user_id: str, project_ids: list[str]
) -> tuple[bool, bool]:
    """Check each scope for a user-made endpoint and test, stopping once both are found."""
    endpoint_found = False
    tests_found = False
    for project_id in [_ORG_LEVEL_SCOPE, *project_ids]:
        with temporary_project_scope(db, organization_id, user_id, project_id):
            endpoint_found = endpoint_found or user_endpoint_exists(db, organization_id)
            tests_found = (
                tests_found
                or user_test_exists(db, organization_id)
                or user_test_set_exists(db, organization_id)
            )
        if endpoint_found and tests_found:
            break
    return endpoint_found, tests_found


def _maybe_notify_endpoint_setup(db: Session, organization_id: str, user_id: str) -> None:
    """Tell the user, once, that they need an endpoint. Never raises: it must not fail the read."""
    # Org-level scope so the row has no project_id and shows in every project.
    with temporary_project_scope(db, organization_id, user_id, _ORG_LEVEL_SCOPE):
        try:
            event_type = NotificationEventType.Endpoint.SETUP_REQUIRED
            if user_notification_exists(db, user_id, event_type.value):
                return
            notify(
                db,
                event_type=event_type,
                rendered=RenderedNotification(
                    title="Set up an endpoint",
                    body="Connect your AI application as an endpoint so you can test it.",
                ),
                user_id=user_id,
                organization_id=organization_id,
                project_id=None,
            )
        except Exception:
            logger.exception("Failed to send endpoint-setup notification for user %s", user_id)
            db.rollback()
