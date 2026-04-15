"""add_sso_config_to_organization

Add sso_config JSON column to the organization table for per-org SSO configuration.
Includes a CHECK constraint to validate required keys when config is present.

Revision ID: a3b4c5d6e7f8
Revises: e1cbd5f10580
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "e1cbd5f10580"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organization", sa.Column("sso_config", sa.JSON(), nullable=True))

    op.create_check_constraint(
        "ck_organization_sso_config_valid",
        "organization",
        """
        sso_config IS NULL
        OR (
            sso_config->>'issuer_url' IS NOT NULL
            AND sso_config->>'client_id' IS NOT NULL
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint("ck_organization_sso_config_valid", "organization", type_="check")
    op.drop_column("organization", "sso_config")
