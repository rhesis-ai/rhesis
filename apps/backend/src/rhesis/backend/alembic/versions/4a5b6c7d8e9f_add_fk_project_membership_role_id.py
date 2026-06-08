"""Add FK constraint from project_membership.role_id to role.id

The role_id column was added in SP6 (c8d9e0f1a2b3) as a nullable placeholder
before the role table existed.  Now that the role catalog is present (added in
SP7, d9e0f1a2b3c4), we can add the actual FK constraint.

ON DELETE SET NULL: if a custom role is deleted, project memberships lose their
role assignment rather than being cascade-deleted.  The member remains in the
project; the EE provider falls back to the org-level role (or denies if none).

Revision ID: 4a5b6c7d8e9f
Revises: 382779ccfbd3
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "4a5b6c7d8e9f"
down_revision: Union[str, None] = "382779ccfbd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_project_membership_role_id",
        "project_membership",
        "role",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_project_membership_role_id",
        "project_membership",
        type_="foreignkey",
    )
