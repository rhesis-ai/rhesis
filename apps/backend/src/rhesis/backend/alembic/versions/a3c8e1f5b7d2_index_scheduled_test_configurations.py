"""index scheduled test configurations

The schedule dispatcher looks for due schedules every minute. A schedule lives in
``test_configuration.attributes['schedule']``, so a partial index over the rows that have one
keeps that scan to a handful of rows. ``next_run_at`` itself can't be indexed: Postgres'
text-to-timestamptz cast isn't immutable.

Revision ID: a3c8e1f5b7d2
Revises: e1f4a7c2b9d3
Create Date: 2026-11-25

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a3c8e1f5b7d2"
down_revision: Union[str, None] = "e1f4a7c2b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `?` is the JSONB key operator, not a bind parameter; no parameters are passed here.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_configuration_scheduled "
        "ON test_configuration (id) "
        "WHERE attributes ? 'schedule' AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_test_configuration_scheduled")
