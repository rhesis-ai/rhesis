"""Cover the per-run outcome counts on test_result

The test run list and detail pages count results per run by execution and verdict. With only
``ix_test_result_test_run_id``, Postgres reads the full rows for that, and ``test_result`` rows
are wide (JSONB output and metrics), so it chose a sequential scan of the whole table.

``ix_test_result_run_outcomes`` keeps ``test_run_id`` as its key and carries the columns the
count and the tenant filters read, so the query is an index-only scan. It replaces
``ix_test_result_test_run_id``, which it covers. The count itself now uses ``count(*)``
instead of ``count(id)``, so ``id`` is not needed in the index.

Measured on 30,420 results, the 50 runs on the first page of the list, as the query runs with
its tenant filters (warm cache):

    ix_test_result_test_run_id   Seq Scan, 6049 buffers, 15.7 ms
    ix_test_result_run_outcomes  Index Only Scan, 0 heap fetches, 320 buffers, 4.5 ms

Both build CONCURRENTLY, outside the migration transaction. The new index is built before the
old one is dropped.

Revision ID: c4d8e2f6a1b9
Revises: a7c3e9f1b5d2
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e2f6a1b9"
down_revision: Union[str, None] = "a7c3e9f1b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW = "ix_test_result_run_outcomes"
_OLD = "ix_test_result_test_run_id"
_INCLUDE = ["execution", "verdict", "organization_id", "project_id", "deleted_at"]


def _drop_if_invalid(name: str) -> None:
    # A failed CONCURRENTLY build leaves an INVALID index, which IF NOT EXISTS would keep.
    invalid = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE NOT i.indisvalid AND c.relname = :name"
            ),
            {"name": name},
        )
        .first()
    )
    if invalid:
        op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')


def upgrade() -> None:
    with op.get_context().autocommit_block():
        _drop_if_invalid(_NEW)
        op.create_index(
            _NEW,
            "test_result",
            ["test_run_id"],
            postgresql_include=_INCLUDE,
            if_not_exists=True,
            postgresql_concurrently=True,
        )
        op.drop_index(_OLD, table_name="test_result", if_exists=True, postgresql_concurrently=True)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        _drop_if_invalid(_OLD)
        op.create_index(
            _OLD,
            "test_result",
            ["test_run_id"],
            if_not_exists=True,
            postgresql_concurrently=True,
        )
        op.drop_index(_NEW, table_name="test_result", if_exists=True, postgresql_concurrently=True)
