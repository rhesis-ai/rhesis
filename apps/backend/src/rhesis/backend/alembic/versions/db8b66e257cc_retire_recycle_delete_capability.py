"""Retire the recycle:delete capability in favour of recycle:purge

The two permanent-delete recycle routes (``DELETE /recycle/{model}/{id}`` and
``DELETE /recycle/empty/{model}``) used to derive ``recycle:delete`` from the
router's resource and HTTP verb. They now declare ``recycle:purge``, which was
already in the catalog, so no route maps to ``recycle:delete`` any more.

EE custom roles that granted ``recycle:delete`` get a matching
``recycle:purge`` grant, so they keep the ability to permanently delete.
Built-in roles are computed from code and need no rows.

``recycle:delete`` is retired rather than deleted, per the catalog's
append-only contract: its ``role_permission`` rows stay auditable.

Revision ID: db8b66e257cc
Revises: a9d3e7c1b2f4
Create Date: 2026-11-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "db8b66e257cc"
down_revision: Union[str, None] = "a9d3e7c1b2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD = "recycle:delete"
_NEW = "recycle:purge"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permission (id, role_id, permission_id, created_at, updated_at)
            SELECT gen_random_uuid(), rp.role_id, new_perm.id, now(), now()
            FROM role_permission rp
            JOIN permission old_perm ON old_perm.id = rp.permission_id
                                    AND old_perm.name = :old
            JOIN permission new_perm ON new_perm.name = :new
            JOIN role r ON r.id = rp.role_id AND r.is_built_in = false
            ON CONFLICT ON CONSTRAINT uq_role_permission DO NOTHING
            """
        ),
        {"old": _OLD, "new": _NEW},
    )
    conn.execute(
        sa.text("UPDATE permission SET is_retired = true WHERE name = :name"),
        {"name": _OLD},
    )


def downgrade() -> None:
    """Un-retire only. Copied ``recycle:purge`` grants are kept: they cannot be
    told apart from grants an admin made directly, and keeping them never
    widens access beyond what the role held before the upgrade."""
    op.get_bind().execute(
        sa.text("UPDATE permission SET is_retired = false WHERE name = :name"),
        {"name": _OLD},
    )
