"""Add FK constraint from project_membership.role_id to role.id

The role_id column was added in SP6 (c8d9e0f1a2b3) as a nullable placeholder
before the role table existed.  Now that the role catalog is present (added in
SP7, d9e0f1a2b3c4), we can add the actual FK constraint.  Every existing
role_id is still NULL (SP6 shipped the column unused and SP8 assignment writes
have not reached production), so there are no orphan references to clean up
before adding the constraint.

ON DELETE SET NULL: if a custom role is deleted, project memberships lose their
role assignment rather than being cascade-deleted.  The member remains in the
project; the EE provider falls back to the org-level role (or denies if none).

The constraint name matches the Postgres default (``<table>_<col>_fkey``) used
by the sibling FKs on this table and by the SP7 catalog tables, so the model's
unnamed ``ForeignKey`` resolves to the same name and autogenerate stays quiet.

Revision ID: 4a5b6c7d8e9f
Revises: 382779ccfbd3
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4a5b6c7d8e9f"
down_revision: Union[str, None] = "382779ccfbd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    fk_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'project_membership_role_id_fkey' "
            "AND table_name = 'project_membership'"
        ),
    ).fetchone()
    if not fk_exists:
        op.create_foreign_key(
            "project_membership_role_id_fkey",
            "project_membership",
            "role",
            ["role_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_constraint(
        "project_membership_role_id_fkey",
        "project_membership",
        type_="foreignkey",
    )
