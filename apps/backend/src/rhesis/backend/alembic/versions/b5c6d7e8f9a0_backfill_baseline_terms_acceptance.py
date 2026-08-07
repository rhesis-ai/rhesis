"""Backfill baseline T&C acceptance for onboarded users.

Server-side terms tracking (#2144) stores acceptance in
``user_settings.terms``. Accounts that completed onboarding before that
shipped (or before this release deployed to a given environment) have no
record and would be blocked by the post-login gate even though T&Cs are
still at baseline version ``1.0``.

This one-shot backfill runs at deploy time per environment, so the
effective "tracking started" moment is when the migration applies — not a
hardcoded merge date. It stamps baseline acceptance for every onboarded
user that does not already have a terms record. New users after deploy
must accept explicitly via onboarding / ``POST /auth/accept-terms``.

Revision ID: b5c6d7e8f9a0
Revises: d4e7f2a9c1b8
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "d4e7f2a9c1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASELINE_TERMS_VERSION = "1.0"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET user_settings = jsonb_set(
                    COALESCE(user_settings, '{}'::jsonb),
                    '{terms}',
                    jsonb_build_object(
                        'version', :version,
                        'accepted_at', COALESCE(joined_at, created_at, now())
                    ),
                    true
                )
            WHERE organization_id IS NOT NULL
              AND deleted_at IS NULL
              AND (
                    user_settings -> 'terms' IS NULL
                 OR COALESCE(user_settings -> 'terms' ->> 'accepted_at', '') = ''
              )
            """
        ).bindparams(version=_BASELINE_TERMS_VERSION)
    )


def downgrade() -> None:
    # Best-effort: cannot distinguish backfill from an explicit 1.0 accept.
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET user_settings = user_settings #- '{terms}'
            WHERE user_settings -> 'terms' ->> 'version' = :version
            """
        ).bindparams(version=_BASELINE_TERMS_VERSION)
    )
