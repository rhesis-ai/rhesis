"""Catch-up backfill for organization_member rows missed by SP8 migration

The original backfill (371c3c3cd787) ran once at deploy and only covered orgs
that already existed with ``owner_id`` set at that moment.  Orgs created
afterward depend on :func:`~rhesis.backend.ee.rbac.default_role.assign_default_org_role`
during onboarding; when that handler no-oped (RBAC dark at signup), owners were
left without an ``organization_member`` row and are denied every capability once
RBAC activates.

This migration re-runs the same idempotent owner and member inserts as
371c3c3cd787 steps 2–3.  Safe to run on every environment; existing rows are
skipped via ``ON CONFLICT DO NOTHING``.

Revision ID: f8e9a0b1c2d4
Revises: a7c3e9f10b24
Create Date: 2026-07-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8e9a0b1c2d4"
down_revision: Union[str, None] = "a7c3e9f10b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            -- 1. Ensure Owner and Admin built-in roles exist.
            INSERT INTO role (id, name, display_name, scope, level, is_built_in, organization_id)
            VALUES
                (gen_random_uuid(), 'Owner', 'Owner', 'organization', 100, true, NULL),
                (gen_random_uuid(), 'Admin', 'Admin', 'organization', 80,  true, NULL)
            ON CONFLICT DO NOTHING;

            -- 2. Backfill org owner → Owner role.
            INSERT INTO organization_member (id, organization_id, user_id, role_id)
            SELECT
                gen_random_uuid(),
                o.id,
                o.owner_id,
                r.id
            FROM organization o
            JOIN role r
              ON r.name = 'Owner'
             AND r.is_built_in = true
             AND r.organization_id IS NULL
            WHERE o.owner_id IS NOT NULL
            ON CONFLICT ON CONSTRAINT uq_organization_member_org_user DO NOTHING;

            -- 3. Backfill all other org users → Admin role.
            INSERT INTO organization_member (id, organization_id, user_id, role_id)
            SELECT
                gen_random_uuid(),
                u.organization_id,
                u.id,
                r.id
            FROM "user" u
            JOIN organization o ON o.id = u.organization_id
            JOIN role r
              ON r.name = 'Admin'
             AND r.is_built_in = true
             AND r.organization_id IS NULL
            WHERE u.organization_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1
                    FROM organization_member om2
                    WHERE om2.organization_id = u.organization_id
                      AND om2.user_id = u.id
              )
            ON CONFLICT ON CONSTRAINT uq_organization_member_org_user DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    # Data-only catch-up; rows are indistinguishable from API-created assignments.
    pass
