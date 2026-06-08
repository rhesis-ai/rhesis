"""Backfill organization_member: owner→Owner, all other members→Admin (SP8)

Derives org-level role assignments from the existing data:
- ``organization.owner_id`` → Owner built-in role
- Every other org user (``user.organization_id``)         → Admin built-in role

The Owner and Admin built-in roles are created inline if they do not yet
exist (idempotent: the EE startup sync may have seeded them earlier).  All
inserts use ON CONFLICT DO NOTHING so the migration is safe to re-run.

This migration must run *before* the ``is_superuser`` column drop
(382779ccfbd3) so the seeded initial admin retains authority as Owner.

Revision ID: 371c3c3cd787
Revises: d9e0f1a2b3c4
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "371c3c3cd787"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
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
            --    Exclude rows already inserted in step 2 (owner_id users) to avoid
            --    assigning both Owner and Admin to the same person.
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
    # Removes ALL rows in organization_member — the backfill is not separable from
    # rows created by later API writes, so downgrade is a full wipe.
    # The table itself was created in d9e0f1a2b3c4; only the data is removed here.
    op.execute(
        sa.text(
            """
            DELETE FROM organization_member;
            """
        )
    )
