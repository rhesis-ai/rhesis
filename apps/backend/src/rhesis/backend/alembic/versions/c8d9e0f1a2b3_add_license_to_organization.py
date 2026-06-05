"""add_license_to_organization

Add license Text column to the organization table for per-org signed
license tokens. The column is consumed exclusively by the EE
SignedTokenLicenseProvider; core stores it as an opaque value.

Modeled on a3b4c5d6e7f8_add_sso_config_to_organization.py.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    col_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='organization' AND column_name='license'"
        )
    ).fetchone()
    if not col_exists:
        op.add_column("organization", sa.Column("license", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("organization", "license")
