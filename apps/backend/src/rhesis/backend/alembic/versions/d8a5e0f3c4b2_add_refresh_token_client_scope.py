"""add client_id and scope columns to refresh_token

Token-exchange-issued refresh tokens carry the calling
``AuthClient.client_id`` and the resolved scope so that:

1. ``POST /auth/refresh`` can require HTTP Basic client credentials
   when the looked-up row's ``client_id`` is set (S2/S3). UI / SSO
   refresh tokens leave the column NULL and behave unchanged.
2. The new access token minted on rotation preserves the same ``azp``
   and ``scope`` as the original; without this, a ``scope=read``
   token-exchange refresh would silently escalate to full-user on its
   first rotation.

Both columns are nullable. Existing rows -- all of which were minted
before this migration ran -- keep ``client_id IS NULL``, which the
refresh handler treats as "UI/SSO token, no Basic auth needed". The
migration is therefore strictly additive: no backfill, no behaviour
change for the legacy path.

Revision ID: d8a5e0f3c4b2
Revises: c7f4d9b2e1a3
Create Date: 2026-05-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8a5e0f3c4b2"
down_revision: Union[str, None] = "c7f4d9b2e1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    client_id_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='refresh_token' AND column_name='client_id'"
        )
    ).fetchone()
    if not client_id_exists:
        op.add_column(
            "refresh_token",
            sa.Column("client_id", sa.String(64), nullable=True),
        )

    scope_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='refresh_token' AND column_name='scope'"
        )
    ).fetchone()
    if not scope_exists:
        op.add_column(
            "refresh_token",
            sa.Column("scope", sa.String(255), nullable=True),
        )

    index_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename='refresh_token' "
            "AND indexname='ix_refresh_token_client_id'"
        )
    ).fetchone()
    if not index_exists:
        op.create_index(
            "ix_refresh_token_client_id",
            "refresh_token",
            ["client_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_refresh_token_client_id", table_name="refresh_token")
    op.drop_column("refresh_token", "scope")
    op.drop_column("refresh_token", "client_id")
