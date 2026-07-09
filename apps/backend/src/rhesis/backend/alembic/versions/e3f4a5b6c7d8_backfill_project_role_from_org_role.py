"""Backfill project_membership.role_id from organization_member.role_id

For every ``project_membership`` row where ``role_id IS NULL``, copies the
``role_id`` from the matching ``organization_member`` row (same ``user_id`` and
``organization_id``).

This is required for members who were added to projects before the RBAC
migration introduced ``project_membership.role_id``.  Without this backfill
those members show up with no explicit project role in the Member Access drawer
even though they were carrying their org role implicitly.

Revision ID: e3f4a5b6c7d8
Revises: 671d10bef526
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "671d10bef526"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Copy each user's org-level role_id into their project_membership rows
    # where no explicit project role has been set yet.
    #
    # Owner (level 100) IS propagated intentionally: the org owner becomes the
    # project-level owner too, reflecting that they created or are responsible
    # for those projects.  Only None (level 0) would be a meaningless project
    # role, but that cannot appear as an org role in practice.
    result = conn.execute(
        sa.text(
            """
            UPDATE project_membership pm
            SET    role_id = om.role_id
            FROM   organization_member om
            WHERE  pm.user_id         = om.user_id
              AND  pm.organization_id = om.organization_id
              AND  pm.role_id         IS NULL
              AND  om.role_id         IS NOT NULL
            """
        )
    )

    updated = result.rowcount if result.rowcount is not None else 0
    print(f"[e3f4a5b6c7d8] Backfilled role_id for {updated} project_membership row(s).")


def downgrade() -> None:
    # There is intentionally no downgrade: we cannot reliably distinguish
    # backfilled rows from rows that were explicitly set after the migration ran.
    pass
