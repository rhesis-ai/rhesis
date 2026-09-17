"""add_organization_settings_to_organization

Add the organization_settings JSONB column: core-owned org preferences, the
organization-level mirror of user.user_settings. Branding (white-label colours,
product name, favicon, font) is its first section.

Existing rows get the same default as new ones, so the column is NOT NULL from
the start and readers never have to handle a missing blob.

Revision ID: cb3558b77459
Revises: 01926b6dd2b6
Create Date: 2026-09-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cb3558b77459"
down_revision: Union[str, None] = "01926b6dd2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_SETTINGS = '{"version": 1, "branding": {}}'


def upgrade() -> None:
    conn = op.get_bind()

    col_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='organization' AND column_name='organization_settings'"
        )
    ).fetchone()
    if col_exists:
        return

    op.add_column(
        "organization",
        sa.Column(
            "organization_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_SETTINGS}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("organization", "organization_settings")
