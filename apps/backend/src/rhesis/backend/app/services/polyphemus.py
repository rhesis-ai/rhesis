"""
Polyphemus Access Control Service

Handles access request workflow for the Polyphemus adversarial model,
including settings updates and admin email notifications.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models
from rhesis.backend.app.models.user import User
from rhesis.backend.notifications import email_service
from rhesis.backend.notifications.email.template_service import EmailTemplate

logger = logging.getLogger(__name__)


def request_access(
    db: Session, user: User, justification: str, expected_monthly_requests: int
) -> Tuple[bool, str]:
    """
    Process a Polyphemus access request for a user.

    Records the request timestamp in user settings and sends an email
    notification to admins for review.

    Args:
        db: Database session
        user: The requesting user (must have organization_id)
        justification: User's justification for access
        expected_monthly_requests: Expected monthly request volume

    Returns:
        Tuple of (success: bool, message: str)

    Raises:
        ValueError: If user has no organization
    """
    if not user.organization_id:
        raise ValueError(
            "Polyphemus access is only available to users belonging to an organization"
        )

    # Get fresh user from database
    db_user = db.query(models.User).filter(models.User.id == user.id).first()
    if db_user is None:
        raise ValueError("User not found")

    # Already verified
    if db_user.is_verified:
        return True, "You already have access to Polyphemus"

    # Already requested and pending
    settings_manager = db_user.settings
    polyphemus = settings_manager.raw.get("polyphemus_access", {})
    if polyphemus.get("requested_at") and not polyphemus.get("revoked_at"):
        return True, "Access request already submitted and pending review"

    # Record request timestamp
    now = datetime.now(timezone.utc)
    settings_manager.update({"polyphemus_access": {"requested_at": now.isoformat()}})
    db_user.user_settings = settings_manager.raw
    flag_modified(db_user, "user_settings")
    db.commit()

    # Send admin notification
    organization = _get_organization(db, db_user.organization_id)
    _send_admin_notification(db_user, organization, justification, expected_monthly_requests, now)

    return True, "Access request submitted successfully. We'll review it shortly."


def _get_organization(db: Session, organization_id: Optional[str]) -> Optional[models.Organization]:
    """Fetch organization by ID."""
    if not organization_id:
        return None
    return db.query(models.Organization).filter(models.Organization.id == organization_id).first()


def _send_admin_notification(
    user: User,
    organization: Optional[models.Organization],
    justification: str,
    expected_monthly_requests: int,
    request_time: datetime,
) -> None:
    """Send email notification to admins about a Polyphemus access request."""
    if not email_service.is_configured:
        return

    try:
        template_variables = {
            "user_name": user.name or user.email,
            "user_email": user.email,
            "user_id": str(user.id),
            "justification": justification,
            "expected_monthly_requests": expected_monthly_requests,
            "request_timestamp": request_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "organization_name": organization.name if organization else None,
            "organization_display_name": (organization.display_name if organization else None),
            "organization_email": organization.email if organization else None,
            "organization_website": organization.website if organization else None,
            "organization_is_active": organization.is_active if organization else False,
        }

        email_subject = f"Polyphemus Access Request - {user.name or user.email}"
        success = email_service.send_email(
            template=EmailTemplate.POLYPHEMUS_ACCESS_REQUEST,
            recipient_email=os.environ.get("FROM_EMAIL", "hello@rhesis.ai"),
            subject=email_subject,
            template_variables=template_variables,
            task_id=f"polyphemus_request_{user.id}",
        )

        if success:
            logger.info(f"Polyphemus access request email sent for user {user.email}")
        else:
            logger.warning(f"Failed to send Polyphemus access request email for user {user.email}")
    except Exception as e:
        logger.error(f"Failed to send Polyphemus access request email: {str(e)}")
