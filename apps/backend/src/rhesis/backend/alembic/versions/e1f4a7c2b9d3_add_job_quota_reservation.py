"""Add the quota reservation to job

- ``job.quota_reservation``: what the launching route reserved for the job, if anything.
- ``job.quota_settled_at``: when it was settled or given back. Settling sets it with a
  guarded update, so a redelivered, retried or revoked job settles at most once.

Revision ID: e1f4a7c2b9d3
Revises: c5e8a1d4f7b2
Create Date: 2026-11-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f4a7c2b9d3"
down_revision: Union[str, None] = "c5e8a1d4f7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job", sa.Column("quota_reservation", postgresql.JSONB(), nullable=True))
    op.add_column("job", sa.Column("quota_settled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "quota_settled_at")
    op.drop_column("job", "quota_reservation")
