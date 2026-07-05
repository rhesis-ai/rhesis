"""Make ix_role_name_org partial (WHERE deleted_at IS NULL) for soft-deletes

Role deletion is now a soft delete: ``delete_role`` stamps ``deleted_at`` and
retains the row for auditability instead of hard-deleting it. The unique index
on ``(name, organization_id)`` must therefore ignore soft-deleted rows, so that
a deleted role's name can be reused when creating a new role. Rebuild the index
as a PostgreSQL partial unique index.

The separate ``uq_role_builtin_name`` index (built-in roles) is intentionally
left untouched — built-in roles are never deleted.

Revision ID: a7c3e9f10b24
Revises: e3f4a5b6c7d8
Create Date: 2026-07-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7c3e9f10b24"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rebuild ix_role_name_org as a partial unique index that excludes
    # soft-deleted rows, so a soft-deleted role no longer reserves its name.
    op.execute("DROP INDEX IF EXISTS ix_role_name_org")
    op.execute(
        "CREATE UNIQUE INDEX ix_role_name_org ON role (name, organization_id) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    # Restore the plain (non-partial) unique index.
    op.execute("DROP INDEX IF EXISTS ix_role_name_org")
    op.execute("CREATE UNIQUE INDEX ix_role_name_org ON role (name, organization_id)")
