"""Add user.job_role and user.referral_source, asked during onboarding

Each comes with an ``_other`` text column for when the user picks "Other".
Existing users stay NULL; they are never asked.

Revision ID: c3d8e1f6a2b4
Revises: b5e2c8f41a93
Create Date: 2026-10-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d8e1f6a2b4"
down_revision: Union[str, None] = "b5e2c8f41a93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("job_role", sa.String(50), nullable=True))
    op.add_column("user", sa.Column("job_role_other", sa.String(255), nullable=True))
    op.add_column("user", sa.Column("referral_source", sa.String(50), nullable=True))
    op.add_column("user", sa.Column("referral_source_other", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "referral_source_other")
    op.drop_column("user", "referral_source")
    op.drop_column("user", "job_role_other")
    op.drop_column("user", "job_role")
