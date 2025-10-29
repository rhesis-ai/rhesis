"""
Base Analytics Model

Defines common fields shared across all analytics tables.
Similar to backend's base model pattern.
"""

from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base, declared_attr

Base = declarative_base()


class AnalyticsBase(Base):
    """
    Abstract base class for all analytics models.

    Provides common fields that all analytics tables share:
    - id: Unique identifier
    - user_id: Hashed user identifier
    - organization_id: Hashed organization identifier
    - timestamp: Event timestamp
    - deployment_type: Deployment environment (cloud, self-hosted)
    - event_metadata: Additional event-specific data as JSON
    """

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(32), index=True)  # Hashed ID, nullable for some events
    organization_id = Column(String(32), index=True)  # Hashed ID, nullable
    timestamp = Column(DateTime, nullable=False, index=True)
    deployment_type = Column(String(50))  # cloud, self-hosted
    event_metadata = Column(JSON)  # Additional event-specific data

    @declared_attr
    def __tablename__(cls):
        """
        Auto-generate table name from class name.
        Converts CamelCase to snake_case.
        """
        # Convert CamelCase to snake_case
        import re

        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", cls.__name__)
        name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()
        return name
