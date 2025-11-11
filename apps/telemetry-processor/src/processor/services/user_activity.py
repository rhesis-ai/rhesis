"""
User Activity Processor

Processes user activity events (login, logout, sessions).
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from processor.models import UserActivity
from processor.services.base import SpanProcessor


class UserActivityProcessor(SpanProcessor):
    """
    Processes user activity events.

    Handles login, logout, and session tracking events.
    """

    def can_process(self, attributes: Dict[str, Any]) -> bool:
        """Check if this is a user activity event."""
        event_category = attributes.get("event.category")
        return event_category == "user_activity"

    def process(
        self,
        attributes: Dict[str, Any],
        timestamp: datetime,
        session: Session,
    ) -> None:
        """
        Process user activity span and insert into database.

        Args:
            attributes: Span attributes
            timestamp: Event timestamp
            session: Database session
        """
        try:
            common_fields = self.extract_common_fields(attributes)
            event_type = attributes.get("event.type", "unknown")

            self.logger.info(
                f"Processing user activity: event_type={event_type}, "
                f"user_id={common_fields['user_id']}"
            )

            # Create metadata excluding common fields
            metadata = self.filter_metadata(
                attributes,
                exclude_keys=[
                    "user.id",
                    "organization.id",
                    "event.type",
                    "event.category",
                    "session.id",
                    "deployment.type",
                ],
            )

            activity = UserActivity(
                user_id=common_fields["user_id"],
                organization_id=common_fields["organization_id"],
                event_type=event_type,
                timestamp=timestamp,
                session_id=attributes.get("session.id"),
                deployment_type=common_fields["deployment_type"],
                event_metadata=metadata,
            )

            session.add(activity)
            self.logger.debug("User activity record added to session")

        except Exception as e:
            self.logger.error(f"Error processing user activity: {e}", exc_info=True)
            raise
