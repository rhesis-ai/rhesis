"""initial analytics tables

Revision ID: 001
Revises:
Create Date: 2025-10-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create analytics tables for telemetry data collection.

    These tables store anonymous usage data to help improve Rhesis:
    - user_activity: User login, logout, session events
    - endpoint_usage: API endpoint usage tracking
    - feature_usage: Feature-specific usage tracking
    """

    # Create user_activity table
    op.create_table(
        "user_activity",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("organization_id", sa.String(32), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # Create indexes for user_activity
    op.create_index("idx_user_activity_user_id", "user_activity", ["user_id"])
    op.create_index("idx_user_activity_org_id", "user_activity", ["organization_id"])
    op.create_index("idx_user_activity_timestamp", "user_activity", ["timestamp"])
    op.create_index("idx_user_activity_user_timestamp", "user_activity", ["user_id", "timestamp"])
    op.create_index(
        "idx_user_activity_deployment_timestamp",
        "user_activity",
        ["deployment_type", "timestamp"],
    )
    op.create_index("idx_user_activity_event_type", "user_activity", ["event_type"])

    # Create endpoint_usage table
    op.create_table(
        "endpoint_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("user_id", sa.String(32), nullable=True),
        sa.Column("organization_id", sa.String(32), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # Create indexes for endpoint_usage
    op.create_index("idx_endpoint_usage_endpoint", "endpoint_usage", ["endpoint"])
    op.create_index("idx_endpoint_usage_user_id", "endpoint_usage", ["user_id"])
    op.create_index("idx_endpoint_usage_org_id", "endpoint_usage", ["organization_id"])
    op.create_index("idx_endpoint_usage_timestamp", "endpoint_usage", ["timestamp"])
    op.create_index(
        "idx_endpoint_usage_endpoint_timestamp",
        "endpoint_usage",
        ["endpoint", "timestamp"],
    )
    op.create_index(
        "idx_endpoint_usage_deployment_timestamp",
        "endpoint_usage",
        ["deployment_type", "timestamp"],
    )
    op.create_index("idx_endpoint_usage_status", "endpoint_usage", ["status_code"])

    # Create feature_usage table
    op.create_table(
        "feature_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("feature_name", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=True),
        sa.Column("organization_id", sa.String(32), nullable=True),
        sa.Column("action", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # Create indexes for feature_usage
    op.create_index("idx_feature_usage_feature_name", "feature_usage", ["feature_name"])
    op.create_index("idx_feature_usage_user_id", "feature_usage", ["user_id"])
    op.create_index("idx_feature_usage_org_id", "feature_usage", ["organization_id"])
    op.create_index("idx_feature_usage_timestamp", "feature_usage", ["timestamp"])
    op.create_index(
        "idx_feature_usage_feature_timestamp",
        "feature_usage",
        ["feature_name", "timestamp"],
    )
    op.create_index(
        "idx_feature_usage_deployment_timestamp",
        "feature_usage",
        ["deployment_type", "timestamp"],
    )
    op.create_index("idx_feature_usage_action", "feature_usage", ["action"])


def downgrade() -> None:
    """Remove analytics tables and their indexes"""

    # Drop indexes first (in reverse order)
    op.drop_index("idx_feature_usage_action", "feature_usage")
    op.drop_index("idx_feature_usage_deployment_timestamp", "feature_usage")
    op.drop_index("idx_feature_usage_feature_timestamp", "feature_usage")
    op.drop_index("idx_feature_usage_timestamp", "feature_usage")
    op.drop_index("idx_feature_usage_org_id", "feature_usage")
    op.drop_index("idx_feature_usage_user_id", "feature_usage")
    op.drop_index("idx_feature_usage_feature_name", "feature_usage")

    op.drop_index("idx_endpoint_usage_status", "endpoint_usage")
    op.drop_index("idx_endpoint_usage_deployment_timestamp", "endpoint_usage")
    op.drop_index("idx_endpoint_usage_endpoint_timestamp", "endpoint_usage")
    op.drop_index("idx_endpoint_usage_timestamp", "endpoint_usage")
    op.drop_index("idx_endpoint_usage_org_id", "endpoint_usage")
    op.drop_index("idx_endpoint_usage_user_id", "endpoint_usage")
    op.drop_index("idx_endpoint_usage_endpoint", "endpoint_usage")

    op.drop_index("idx_user_activity_event_type", "user_activity")
    op.drop_index("idx_user_activity_deployment_timestamp", "user_activity")
    op.drop_index("idx_user_activity_user_timestamp", "user_activity")
    op.drop_index("idx_user_activity_timestamp", "user_activity")
    op.drop_index("idx_user_activity_org_id", "user_activity")
    op.drop_index("idx_user_activity_user_id", "user_activity")

    # Drop tables
    op.drop_table("feature_usage")
    op.drop_table("endpoint_usage")
    op.drop_table("user_activity")
