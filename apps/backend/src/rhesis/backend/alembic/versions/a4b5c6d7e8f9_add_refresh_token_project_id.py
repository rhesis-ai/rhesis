"""add project_id column to refresh_token

Token-exchange-issued refresh tokens now carry the project resolved
from the RFC 8693 ``resource`` parameter at exchange time, so that:

1. Rotation (``verify_and_rotate_refresh_token``) preserves the project
   binding on the successor row, the same way it already preserves
   ``client_id`` and ``scope`` (see ``d8a5e0f3c4b2``). Without this
   column the project claim on the access token would silently
   disappear on the first refresh -- a token that works, then stops,
   then works again only after a fresh exchange.
2. ``mint_for_client_bound_refresh`` reads it back to re-mint the
   access token's ``project`` claim on every rotation.

No FK to ``project.id``: this mirrors ``token.project_id``
(``a1b2c3d4e5f0``), which is also looked up before tenant context is
established and therefore left without a FK.

Nullable, no backfill. Existing rows -- all minted before this
migration ran -- keep ``project_id IS NULL``, which the refresh and
mint paths treat as "no project scope", the pre-existing behaviour.
The migration is strictly additive.

Revision ID: a4b5c6d7e8f9
Revises: 3f5954f6c374
Create Date: 2026-08-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.idempotency import column_exists, index_exists

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "3f5954f6c374"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    if not column_exists(conn, "refresh_token", "project_id"):
        op.add_column(
            "refresh_token",
            sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        )

    if not index_exists(conn, "ix_refresh_token_project_id"):
        op.create_index(
            "ix_refresh_token_project_id",
            "refresh_token",
            ["project_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_refresh_token_project_id", table_name="refresh_token")
    op.drop_column("refresh_token", "project_id")
