"""Add GIN index on test_result.test_metrics.

Metric-level filtering (e.g. querying test results where a specific metric's
``is_successful`` is false) currently requires a full scan of ``test_result``
with the JSONB column unpacked in Python. A ``jsonb_path_ops`` GIN index lets
Postgres use containment queries (``test_metrics @> '...'``) directly, which
is what the metric-level query endpoint needs as the table grows.

``CREATE INDEX CONCURRENTLY`` avoids holding a write lock on ``test_result``
while the index builds, so it must run outside the migration's transaction
via ``autocommit_block()``.

Revision ID: 598209e65e3c
Revises: b5c6d7e8f9a0
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "598209e65e3c"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_test_result_test_metrics_gin"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME}
            ON test_result USING gin (test_metrics jsonb_path_ops)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
