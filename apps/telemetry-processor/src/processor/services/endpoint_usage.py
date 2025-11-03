"""
Endpoint Usage Processor

Processes API endpoint usage events.
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from processor.models import EndpointUsage
from processor.services.base import SpanProcessor


class EndpointUsageProcessor(SpanProcessor):
    """
    Processes API endpoint usage events.

    Handles HTTP request tracking including performance and error metrics.
    """

    def can_process(self, attributes: Dict[str, Any]) -> bool:
        """Check if this is an endpoint usage event."""
        event_category = attributes.get("event.category")
        return event_category == "endpoint_usage"

    def process(
        self,
        attributes: Dict[str, Any],
        timestamp: datetime,
        session: Session,
    ) -> None:
        """
        Process endpoint usage span and insert into database.

        Args:
            attributes: Span attributes
            timestamp: Event timestamp
            session: Database session
        """
        try:
            common_fields = self.extract_common_fields(attributes)

            # Get endpoint (prefer route, fallback to URL)
            endpoint = attributes.get("http.route") or attributes.get("http.url", "unknown")
            method = attributes.get("http.method")

            self.logger.debug(f"Processing endpoint usage: {method} {endpoint}")

            # Create metadata excluding common fields
            metadata = self.filter_metadata(
                attributes,
                exclude_keys=[
                    "http.route",
                    "http.url",
                    "http.method",
                    "user.id",
                    "organization.id",
                    "http.status_code",
                    "duration_ms",
                    "deployment.type",
                    "event.category",
                ],
            )

            usage = EndpointUsage(
                endpoint=endpoint,
                method=method,
                user_id=common_fields["user_id"],
                organization_id=common_fields["organization_id"],
                status_code=attributes.get("http.status_code"),
                duration_ms=attributes.get("duration_ms"),
                timestamp=timestamp,
                deployment_type=common_fields["deployment_type"],
                event_metadata=metadata,
            )

            session.add(usage)
            self.logger.debug("Endpoint usage record added to session")

        except Exception as e:
            self.logger.error(f"Error processing endpoint usage: {e}", exc_info=True)
            raise
