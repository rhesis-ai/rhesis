"""Catch-up backfill for project_membership.role_id missed by e3f4a5b6c7d8

Migration ``e3f4a5b6c7d8`` copied ``organization_member.role_id`` into
``project_membership.role_id`` where the project role was still NULL.  That
one-shot ran before some orgs had ``organization_member`` rows (RBAC-dark
onboarding), so their project memberships stayed NULL even after the org
catch-up (``f8e9a0b1c2d4``) repaired ``organization_member``.

Members with NULL project roles still inherit their org role for authorization
(see ``PermissionAuthorizationProvider._resolve_role``), but
``GET /rbac/projects/{id}/members`` reads the stored column and the Members tab
shows "—".

This migration re-runs the same idempotent UPDATE as e3f4a5b6c7d8.  Rows that
already have an explicit project role are untouched.

Revision ID: f9e8d7c6b5a4
Revises: f8e9a0b1c2d4
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f9e8d7c6b5a4"
down_revision: Union[str, None] = "f8e9a0b1c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
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
    print(f"[f9e8d7c6b5a4] Backfilled role_id for {updated} project_membership row(s).")


def downgrade() -> None:
    # Data-only catch-up; cannot distinguish backfilled rows from explicit assignments.
    pass
