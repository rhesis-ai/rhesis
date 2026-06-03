"""Backfill project_membership for all existing org users

When the project_membership table was created (a1b2c3d4e5f0) it started empty.
Auto-enrolment only fires for new project creations and new user invitations,
so every user and project that existed before that migration has no membership
rows.  This migration inserts one row per (user, project) pair that share the
same organization_id, skipping duplicates if any partial enrolment already ran.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c3
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Temporarily disable the auto_apply_rls_policies event trigger so that the
    # INSERT into project_membership (which already has its RLS policies) does
    # not cause the trigger to fire and attempt to re-create existing policies.
    conn.execute(sa.text("SET session_replication_role = replica"))

    conn.execute(
        sa.text(
            """
            INSERT INTO project_membership (id, project_id, user_id, organization_id, created_at, updated_at)
            SELECT
                gen_random_uuid(),
                p.id       AS project_id,
                u.id       AS user_id,
                u.organization_id,
                now(),
                now()
            FROM "user" u
            CROSS JOIN project p
            WHERE u.organization_id = p.organization_id
              AND u.organization_id IS NOT NULL
              AND p.organization_id IS NOT NULL
              AND (u.deleted_at IS NULL OR u.deleted_at > now())
              AND (p.deleted_at IS NULL OR p.deleted_at > now())
            ON CONFLICT (project_id, user_id) DO NOTHING
            """
        )
    )

    conn.execute(sa.text("SET session_replication_role = DEFAULT"))


def downgrade() -> None:
    # Removing backfilled memberships is destructive and cannot be done safely
    # (we cannot distinguish backfilled rows from rows created by normal usage).
    # The downgrade is intentionally a no-op.
    pass
