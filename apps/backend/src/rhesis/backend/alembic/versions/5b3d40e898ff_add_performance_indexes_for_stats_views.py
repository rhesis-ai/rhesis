"""add performance indexes for stats views

Revision ID: 5b3d40e898ff
Revises: cb4b107b5daf
Create Date: 2026-03-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "5b3d40e898ff"
down_revision: Union[str, None] = "cb4b107b5daf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    # -- Tier 1: View JOIN conditions (highest impact) --
    ("ix_test_run_status_id", "test_run", ["status_id"]),
    ("ix_test_run_test_configuration_id", "test_run", ["test_configuration_id"]),
    ("ix_test_result_test_id", "test_result", ["test_id"]),
    ("ix_test_result_status_id", "test_result", ["status_id"]),
    ("ix_test_result_test_run_id", "test_result", ["test_run_id"]),
    ("ix_test_configuration_test_set_id", "test_configuration", ["test_set_id"]),
    ("ix_test_behavior_id", "test", ["behavior_id"]),
    ("ix_test_category_id", "test", ["category_id"]),
    ("ix_test_topic_id", "test", ["topic_id"]),
    # -- Tier 2: WHERE / filter columns --
    ("ix_test_run_organization_id", "test_run", ["organization_id"]),
    ("ix_test_result_organization_id", "test_result", ["organization_id"]),
    ("ix_test_organization_id", "test", ["organization_id"]),
    ("ix_test_configuration_organization_id", "test_configuration", ["organization_id"]),
    ("ix_test_configuration_endpoint_id", "test_configuration", ["endpoint_id"]),
    ("ix_test_run_user_id", "test_run", ["user_id"]),
    ("ix_test_set_organization_id", "test_set", ["organization_id"]),
    # -- Tier 3: Composite indexes for common query patterns --
    ("ix_test_run_org_created", "test_run", ["organization_id", "created_at"]),
    ("ix_test_result_org_created", "test_result", ["organization_id", "created_at"]),
    ("ix_test_result_run_org", "test_result", ["test_run_id", "organization_id"]),
    # -- Tier 4: Association table indexes --
    ("ix_test_test_set_test_set_id", "test_test_set", ["test_set_id"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
