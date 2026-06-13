"""Backfill missing RLS policies

Several tables added after the original RLS migration (fcac5b8b5eb0) never
received a tenant_isolation policy. The Phase 5 project_isolation migration
(c3d4e5f6a7b2) covered the 36 tables with ProjectMixin but missed endpoint,
experiment, trace, and project_membership which had pre-existing project_id
columns.

Revision ID: d4e5f6a7b8c3
Revises: c3d4e5f6a7b2
Create Date: 2026-06-01

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c3"
down_revision: Union[str, None] = "c3d4e5f6a7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that need tenant_isolation added (have organization_id, no policy).
# RLS is already enabled on most via Phase 5; auth_client, project_membership,
# and trace also need ENABLE + FORCE.
_NEED_TENANT_ISOLATION = [
    "architect_session",
    "auth_client",
    "behavior_metric",
    "chunk",
    "comment",
    "embedding",
    "file",
    "metric",
    "model",
    "project_membership",
    "task",
    "test_set_metric",
    "tool",
    "trace",
]

# Tables that need project_isolation added (have project_id, no policy).
# endpoint and experiment had pre-existing project_id columns that Phase 5
# did not cover. project_membership and trace need both policies.
_NEED_PROJECT_ISOLATION = [
    "endpoint",
    "experiment",
    "project_membership",
    "trace",
]

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
        USING (organization_id = current_setting('app.current_organization')::uuid)
"""

_PROJECT_POLICY = """
    CREATE POLICY project_isolation ON {table}
        AS RESTRICTIVE
        FOR ALL
        USING (
            project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
            OR project_id IS NULL
            OR current_setting('app.current_project', true) = ''
        )
"""


def upgrade() -> None:
    for table in _NEED_TENANT_ISOLATION:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(_TENANT_POLICY.format(table=table))

    for table in _NEED_PROJECT_ISOLATION:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(_PROJECT_POLICY.format(table=table))


def downgrade() -> None:
    for table in reversed(_NEED_PROJECT_ISOLATION):
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")

    for table in reversed(_NEED_TENANT_ISOLATION):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
