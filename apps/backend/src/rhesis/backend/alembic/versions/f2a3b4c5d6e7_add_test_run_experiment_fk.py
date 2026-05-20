"""promote test_run experiment link to a proper FK

The previous parameter management migration left the experiment link buried
in ``test_run.attributes->>'parameter_experiment_id'``. That worked for
write-once snapshot data but does not give us:

- an enforced relational invariant (the JSON value can point at a
  non-existent experiment without the database complaining),
- a queryable join path (``TestRun.experiment``),
- an indexable column for the common "runs with experiment" filter.

This migration promotes the link to a real ``test_run.experiment_id``
column with a foreign key to ``experiment.id``:

- add the column as nullable (runs created before parameter management
  legitimately have no experiment),
- backfill from the JSONB snapshot only where the referenced experiment
  still exists, so the FK stays valid for soft-deleted or hard-deleted
  experiments,
- add a btree index on the new column,
- drop the old expression index, which the new column index supersedes.

The snapshot keys in ``attributes`` (parameter_experiment_name, version,
schema, etc.) are intentionally left in place -- they are an immutable
record of what was resolved for the run and are read by the API
``experiment_summary`` view and the connector wire protocol.

Revision ID: f2a3b4c5d6e7
Revises: e1a2b3c4d5e6
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def _index_exists(table: str, index_name: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i"),
        {"t": table, "i": index_name},
    ).fetchone()
    return row is not None


def _fk_exists(table: str, fk_name: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name AND contype = 'f'"),
        {"name": fk_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    # 1. add the FK column ------------------------------------------------ #
    if not _column_exists("test_run", "experiment_id"):
        op.add_column(
            "test_run",
            sa.Column(
                "experiment_id",
                postgresql.UUID(),
                nullable=True,
            ),
        )

    if not _fk_exists("test_run", "fk_test_run_experiment_id"):
        op.create_foreign_key(
            "fk_test_run_experiment_id",
            "test_run",
            "experiment",
            ["experiment_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 2. backfill from JSONB snapshot ------------------------------------- #
    # Only set the FK where the referenced experiment row still exists, so
    # we never violate the FK constraint on bad/stale snapshot data.
    op.execute(
        """
        UPDATE public.test_run AS tr
        SET experiment_id = (tr.attributes->>'parameter_experiment_id')::uuid
        FROM public.experiment AS e
        WHERE tr.attributes ? 'parameter_experiment_id'
          AND tr.experiment_id IS NULL
          AND (tr.attributes->>'parameter_experiment_id') ~
              '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
              '[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
          AND e.id = (tr.attributes->>'parameter_experiment_id')::uuid
        """
    )

    # 3. add btree index on the new column -------------------------------- #
    if not _index_exists("test_run", "ix_test_run_experiment_id"):
        op.create_index(
            "ix_test_run_experiment_id",
            "test_run",
            ["experiment_id"],
        )

    # 4. drop the now-superseded expression index ------------------------- #
    op.execute("DROP INDEX IF EXISTS ix_test_run_attr_parameter_experiment_id")


def downgrade() -> None:
    # Recreate the expression index first so reads that depend on it keep
    # working after the column goes away.
    if not _index_exists("test_run", "ix_test_run_attr_parameter_experiment_id"):
        op.execute(
            "CREATE INDEX ix_test_run_attr_parameter_experiment_id "
            "ON public.test_run "
            "((attributes->>'parameter_experiment_id')) "
            "WHERE attributes ? 'parameter_experiment_id'"
        )

    if _index_exists("test_run", "ix_test_run_experiment_id"):
        op.drop_index("ix_test_run_experiment_id", table_name="test_run")

    if _fk_exists("test_run", "fk_test_run_experiment_id"):
        op.drop_constraint("fk_test_run_experiment_id", "test_run", type_="foreignkey")

    if _column_exists("test_run", "experiment_id"):
        op.drop_column("test_run", "experiment_id")
