"""
Base Span Processor

Defines the interface for span processors following SOLID principles:
- Single Responsibility: Process one type of span
- Open/Closed: Open for extension, closed for modification
- Liskov Substitution: All processors can be used interchangeably
- Interface Segregation: Small, focused interface
- Dependency Inversion: Depends on abstraction (base class)
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SpanProcessor(ABC):
    """
    Abstract base class for span processors.

    Each processor handles a specific type of telemetry event
    (user activity, endpoint usage, or feature usage).
    """

    def __init__(self):
        """Initialize the processor."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def can_process(self, attributes: Dict[str, Any]) -> bool:
        """
        Determine if this processor can handle the given span.

        Args:
            attributes: Merged span and resource attributes

        Returns:
            bool: True if this processor should handle the span
        """
        pass

    @abstractmethod
    def process(
        self,
        attributes: Dict[str, Any],
        timestamp: datetime,
        session: Session,
    ) -> None:
        """
        Process the span and write to database.

        Args:
            attributes: Merged span and resource attributes
            timestamp: Event timestamp
            session: Database session
        """
        pass

    def extract_common_fields(self, attributes: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Extract common fields present in all event types.

        Args:
            attributes: Merged span and resource attributes

        Returns:
            Dict with user_id, org_id, and deployment_type
        """
        return {
            "user_id": attributes.get("user.id"),
            "organization_id": attributes.get("organization.id"),
            "deployment_type": attributes.get("deployment.type", "unknown"),
        }

    def filter_metadata(
        self,
        attributes: Dict[str, Any],
        exclude_keys: list[str],
    ) -> Dict[str, Any]:
        """
        Filter attributes to create metadata JSON.

        Args:
            attributes: All attributes
            exclude_keys: Keys to exclude from metadata

        Returns:
            Dict: Filtered metadata
        """
        return {k: v for k, v in attributes.items() if k not in exclude_keys}
