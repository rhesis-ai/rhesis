"""Add test_set_metric association table

Revision ID: 3f8a2b9c1d4e
Revises: 1dc33ff4b0a2
Create Date: 2026-01-23 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f8a2b9c1d4e"
down_revision: Union[str, None] = "1dc33ff4b0a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the test_set_metric association table
    op.create_table(
        "test_set_metric",
        sa.Column(
            "test_set_id",
            sa.UUID(),
            sa.ForeignKey("test_set.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "metric_id",
            sa.UUID(),
            sa.ForeignKey("metric.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("user.id"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organization.id"),
            nullable=False,
        ),
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_test_set_metric_test_set_id",
        "test_set_metric",
        ["test_set_id"],
    )
    op.create_index(
        "ix_test_set_metric_metric_id",
        "test_set_metric",
        ["metric_id"],
    )
    op.create_index(
        "ix_test_set_metric_organization_id",
        "test_set_metric",
        ["organization_id"],
    )

    # Enable RLS on the new table
    op.execute("ALTER TABLE test_set_metric ENABLE ROW LEVEL SECURITY")

    # Create RLS policy for organization-based access
    op.execute(
        """
        CREATE POLICY test_set_metric_organization_isolation ON test_set_metric
        FOR ALL
        USING (
            organization_id::text = current_setting('app.organization_id', true)
            OR current_setting('app.organization_id', true) IS NULL
            OR current_setting('app.organization_id', true) = ''
        )
        """
    )


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS test_set_metric_organization_isolation ON test_set_metric")

    # Drop indexes
    op.drop_index("ix_test_set_metric_organization_id", table_name="test_set_metric")
    op.drop_index("ix_test_set_metric_metric_id", table_name="test_set_metric")
    op.drop_index("ix_test_set_metric_test_set_id", table_name="test_set_metric")

    # Drop the table
    op.drop_table("test_set_metric")
