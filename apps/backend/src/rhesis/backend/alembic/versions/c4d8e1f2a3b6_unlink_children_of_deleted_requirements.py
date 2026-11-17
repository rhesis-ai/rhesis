"""unlink_children_of_deleted_requirements

Requirement delete is a soft delete, so the parent_id FK's ON DELETE SET NULL
never ran and children kept pointing at deleted parents. The delete path now
unlinks them; this clears the links left behind before that.

Revision ID: c4d8e1f2a3b6
Revises: b7e2d4a9c31f
Create Date: 2026-11-17 10:00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e1f2a3b6"
down_revision: Union[str, None] = "b7e2d4a9c31f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE requirement AS child
        SET parent_id = NULL
        FROM requirement AS parent
        WHERE child.parent_id = parent.id
          AND parent.deleted_at IS NOT NULL
        """
    )


def downgrade() -> None:
    # The cleared links were dangling; there is nothing to restore.
    pass
