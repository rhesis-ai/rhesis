"""Remove 'public' from test_set visibility CHECK constraint

The TestSet visibility CHECK constraint allowed 'public', 'organization', and
'user'.  The 'public' value was dead — nothing writes it, and cross-org sharing
is hard-blocked by RLS + ORM auto-filter.  Remove it so the schema honestly
reflects what is supported.  Any stale 'public' rows are migrated to
'organization' as a defensive measure.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-06-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE test_set SET visibility = 'organization' WHERE visibility = 'public'")
    op.execute("ALTER TABLE test_set DROP CONSTRAINT IF EXISTS test_set_visibility_check")
    op.create_check_constraint(
        "test_set_visibility_check",
        "test_set",
        "visibility IN ('organization', 'user')",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE test_set DROP CONSTRAINT IF EXISTS test_set_visibility_check")
    op.create_check_constraint(
        "test_set_visibility_check",
        "test_set",
        "visibility IN ('public', 'organization', 'user')",
    )
