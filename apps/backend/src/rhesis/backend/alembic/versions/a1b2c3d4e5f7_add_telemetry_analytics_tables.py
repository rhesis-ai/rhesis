"""add_telemetry_analytics_tables

Revision ID: a1b2c3d4e5f7
Revises: 5ac5d119bda1
Create Date: 2025-10-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "5ac5d119bda1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create analytics tables for telemetry data collection.

    These tables store anonymous usage data to help improve Rhesis:
    - analytics_user_activity: User login, logout, session events
    - analytics_endpoint_usage: API endpoint usage tracking
    - analytics_feature_usage: Feature-specific usage tracking
    """

    # Create analytics_user_activity table
    op.create_table(
        "analytics_user_activity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # Create indexes for analytics_user_activity
    op.create_index(
        "idx_user_activity_user_timestamp",
        "analytics_user_activity",
        ["user_id", "timestamp"],
    )
    op.create_index(
        "idx_user_activity_deployment_timestamp",
        "analytics_user_activity",
        ["deployment_type", "timestamp"],
    )

    # Create analytics_endpoint_usage table
    op.create_table(
        "analytics_endpoint_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("endpoint", sa.String(255), nullable=False, index=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # Create indexes for analytics_endpoint_usage
    op.create_index(
        "idx_endpoint_usage_endpoint_timestamp",
        "analytics_endpoint_usage",
        ["endpoint", "timestamp"],
    )
    op.create_index(
        "idx_endpoint_usage_deployment_timestamp",
        "analytics_endpoint_usage",
        ["deployment_type", "timestamp"],
    )

    # Create analytics_feature_usage table
    op.create_table(
        "analytics_feature_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("feature_name", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # Create indexes for analytics_feature_usage
    op.create_index(
        "idx_feature_usage_feature_timestamp",
        "analytics_feature_usage",
        ["feature_name", "timestamp"],
    )
    op.create_index(
        "idx_feature_usage_deployment_timestamp",
        "analytics_feature_usage",
        ["deployment_type", "timestamp"],
    )


def downgrade() -> None:
    """Remove analytics tables and their indexes"""

    # Drop indexes first
    op.drop_index("idx_feature_usage_deployment_timestamp", "analytics_feature_usage")
    op.drop_index("idx_feature_usage_feature_timestamp", "analytics_feature_usage")
    op.drop_index("idx_endpoint_usage_deployment_timestamp", "analytics_endpoint_usage")
    op.drop_index("idx_endpoint_usage_endpoint_timestamp", "analytics_endpoint_usage")
    op.drop_index("idx_user_activity_deployment_timestamp", "analytics_user_activity")
    op.drop_index("idx_user_activity_user_timestamp", "analytics_user_activity")

    # Drop tables
    op.drop_table("analytics_feature_usage")
    op.drop_table("analytics_endpoint_usage")
    op.drop_table("analytics_user_activity")
