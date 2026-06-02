"""Add RESTRICTIVE project_isolation RLS policies to scoped tables

Phase 5 of the project-container feature:
- Enables RLS + FORCE ROW LEVEL SECURITY on all 36 scoped tables
- Creates a RESTRICTIVE project_isolation policy on each table
- The policy ANDs with the existing PERMISSIVE tenant_isolation policy
- NULL project_id rows remain visible inside any project (org-wide passthrough)
- Empty/unset app.current_project unblocks migration/background-job paths

Excluded: token (looked up before tenant context is bound).

Revision ID: c3d4e5f6a7b2
Revises: a1b2c3d4e5f0
Create Date: 2026-06-01

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b2"
down_revision: Union[str, None] = "a1b2c3d4e5f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Entity tables (project_id FK → project.id)
_ENTITY_TABLES = [
    "test_set",
    "test",
    "test_result",
    "test_run",
    "test_configuration",
    "test_context",
    "behavior",
    "category",
    "demographic",
    "dimension",
    "use_case",
    "risk",
    "topic",
    "metric",
    "prompt",
    "prompt_template",
    "response_pattern",
    "model",
    "source",
    "chunk",
    "file",
    "tool",
    "tag",
    "tagged_item",
    "status",
    "type_lookup",
    "task",
    "comment",
    "architect_session",
    "embedding",
    "subscription",
]

# Association tables (project_id FK)
_ASSOCIATION_TABLES = [
    "test_set_metric",
    "test_test_set",
    "behavior_metric",
    "prompt_test_set",
]

# Tables with project_id but no FK.
# token is deliberately excluded — looked up before tenant context is bound.
_TABLES_WITHOUT_FK = [
    "architect_message",
]

_ALL_SCOPED_TABLES = _ENTITY_TABLES + _ASSOCIATION_TABLES + _TABLES_WITHOUT_FK


def upgrade() -> None:
    for table in _ALL_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY project_isolation ON {table}
                AS RESTRICTIVE
                FOR ALL
                USING (
                    project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
                    OR project_id IS NULL
                    OR current_setting('app.current_project', true) = ''
                )
        """)


def downgrade() -> None:
    for table in reversed(_ALL_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        # Leave RLS enabled — the existing tenant_isolation policy remains active.
