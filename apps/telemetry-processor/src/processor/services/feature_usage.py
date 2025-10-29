"""
Feature Usage Processor

Processes feature-specific usage events.
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from processor.models import FeatureUsage
from processor.services.base import SpanProcessor


class FeatureUsageProcessor(SpanProcessor):
    """
    Processes feature usage events.

    Handles feature interaction tracking for adoption analysis.
    """

    def can_process(self, attributes: Dict[str, Any]) -> bool:
        """Check if this is a feature usage event."""
        event_category = attributes.get("event.category")
        return event_category == "feature_usage"

    def process(
        self,
        attributes: Dict[str, Any],
        timestamp: datetime,
        session: Session,
    ) -> None:
        """
        Process feature usage span and insert into database.

        Args:
            attributes: Span attributes
            timestamp: Event timestamp
            session: Database session
        """
        try:
            common_fields = self.extract_common_fields(attributes)
            feature_name = attributes.get("feature.name", "unknown")
            action = attributes.get("feature.action")

            self.logger.debug(f"Processing feature usage: {feature_name}.{action}")

            # Create metadata excluding common fields
            metadata = self.filter_metadata(
                attributes,
                exclude_keys=[
                    "feature.name",
                    "feature.action",
                    "user.id",
                    "organization.id",
                    "deployment.type",
                    "event.category",
                ],
            )

            usage = FeatureUsage(
                feature_name=feature_name,
                user_id=common_fields["user_id"],
                organization_id=common_fields["organization_id"],
                action=action,
                timestamp=timestamp,
                deployment_type=common_fields["deployment_type"],
                event_metadata=metadata,
            )

            session.add(usage)
            self.logger.debug("Feature usage record added to session")

        except Exception as e:
            self.logger.error(f"Error processing feature usage: {e}", exc_info=True)
            raise
