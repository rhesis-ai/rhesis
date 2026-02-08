"""Add refresh_token table for access/refresh token rotation

Like ``token`` and ``user``, this table is intentionally excluded from
Row-Level Security because it is used during authentication *before*
the organization context is established.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("refresh_token"):
        return

    # Explicitly disable RLS — refresh tokens are auth-layer data,
    # queried before organization context is known (same as token/user).
    op.create_table(
        "refresh_token",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            index=True,
            unique=True,
        ),
        sa.Column(
            "nano_id",
            sa.String(),
            unique=True,
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "token_hash",
            sa.String(64),
            nullable=False,
            unique=True,
            index=True,
            comment="SHA-256 hex digest of the raw opaque token",
        ),
        sa.Column(
            "family_id",
            sa.dialects.postgresql.UUID(),
            nullable=False,
            index=True,
            comment=("Groups tokens in a rotation chain for reuse detection"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Set when the token is explicitly revoked",
        ),
    )

    # Ensure RLS is NOT enabled on this table.
    # If a blanket RLS migration ran after table creation, undo it.
    op.execute("ALTER TABLE public.refresh_token DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.refresh_token")


def downgrade() -> None:
    op.drop_table("refresh_token")
