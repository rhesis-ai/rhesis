"""Add the built-in Auditor role

Org-wide read plus the audit log (read and export), no writes. Its permissions
are computed in code (``permissions_for_built_in_role`` in
``ee/rbac/models.py``), so this only seeds the row. Level and description must
match ``BUILT_IN_ROLE_LEVELS`` and ``BUILT_IN_ROLE_DESCRIPTIONS`` there.

Revision ID: c5e1a8f3b902
Revises: a7c3e9d2f410
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5e1a8f3b902"
down_revision: Union[str, None] = "a7c3e9d2f410"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NAME = "Auditor"
_LEVEL = 70
_DESCRIPTION = (
    "Read-only access to every project, and to the audit log: view and export it. "
    "Cannot make changes."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO role (
                id, name, display_name, description, scope, level,
                is_built_in, organization_id, created_at, updated_at
            )
            SELECT gen_random_uuid(), CAST(:name AS varchar), CAST(:name AS varchar),
                   CAST(:description AS text), 'organization', CAST(:level AS integer),
                   true, NULL, now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM role
                WHERE name = CAST(:name AS varchar)
                  AND organization_id IS NULL AND deleted_at IS NULL
            )
            """
        ),
        {"name": _NAME, "level": _LEVEL, "description": _DESCRIPTION},
    )


def downgrade() -> None:
    # Members holding the role block the delete (ON DELETE RESTRICT): reassign them first.
    op.get_bind().execute(
        sa.text("DELETE FROM role WHERE name = :name AND is_built_in = true"),
        {"name": _NAME},
    )
