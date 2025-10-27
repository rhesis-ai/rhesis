"""
Analytics Database Models

Defines the database schema for telemetry analytics tables.
Each model represents a specific type of analytics data.
"""

from sqlalchemy import Column, Float, Integer, String

from processor.models.base import AnalyticsBase


class UserActivity(AnalyticsBase):
    """
    User activity events (login, logout, session tracking).

    Tracks user engagement and session information for retention analysis.

    Inherits from AnalyticsBase:
    - id, user_id, organization_id, timestamp, deployment_type, event_metadata
    """

    __tablename__ = "analytics_user_activity"

    # Override to make user_id required for this table
    user_id = Column(String(32), nullable=False, index=True)  # Hashed ID

    # Table-specific fields
    event_type = Column(String(50), nullable=False)  # login, logout, etc.
    session_id = Column(String(255))


class EndpointUsage(AnalyticsBase):
    """
    API endpoint usage tracking.

    Tracks API calls, performance metrics, and error rates.

    Inherits from AnalyticsBase:
    - id, user_id, organization_id, timestamp, deployment_type, event_metadata
    """

    __tablename__ = "analytics_endpoint_usage"

    # Table-specific fields
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10))  # GET, POST, PUT, DELETE
    status_code = Column(Integer)
    duration_ms = Column(Float)


class FeatureUsage(AnalyticsBase):
    """
    Feature-specific usage tracking.

    Tracks which features users interact with and how frequently.

    Inherits from AnalyticsBase:
    - id, user_id, organization_id, timestamp, deployment_type, event_metadata
    """

    __tablename__ = "analytics_feature_usage"

    # Table-specific fields
    feature_name = Column(String(100), nullable=False, index=True)
    action = Column(String(100))  # created, viewed, updated, deleted
