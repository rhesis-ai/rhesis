"""Add metric_id to test_set and test

Marks a test set (and its tests) as owned by a single metric, for metric tuning:
the metric's own golden test set, hidden from the normal /test_sets and /tests
lists the same way explorer_row hides Explorer's rows.

Nullable with no server default, so this adds no DML at all -- unlike
7dd69fe35db5 (explorer_row), which needed the FORCE ROW LEVEL SECURITY
disable/restore dance purely so its backfill UPDATE could see rows. Nothing to
backfill here means nothing to work around.

test is a hot table, so the foreign keys go on as NOT VALID first and are
validated in a second statement: ADD CONSTRAINT ... NOT VALID takes a brief
ACCESS EXCLUSIVE lock without scanning, and VALIDATE CONSTRAINT then scans under
a weaker SHARE UPDATE EXCLUSIVE lock that does not block reads or writes. All
existing rows have metric_id IS NULL, so validation cannot fail.

Revision ID: c7e2f4a91b83
Revises: 3f5954f6c374
Create Date: 2026-08-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.idempotency import column_exists, fk_exists, index_exists
from rhesis.backend.app.models.guid import GUID

# revision identifiers, used by Alembic.
revision: str = "c7e2f4a91b83"
down_revision: Union[str, None] = "3f5954f6c374"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, index name, fk constraint name)
# (table, index name, fk constraint name, one row per metric)
# test_set is unique: a metric owns at most one tuning test set, and without the
# constraint two concurrent first POSTs each create one, after which half the
# cases live in a set nothing reads. test is not: a metric owns many cases.
_TARGETS = (
    ("test_set", "ix_test_set_metric_id", "fk_test_set_metric_id", True),
    ("test", "ix_test_metric_id", "fk_test_metric_id", False),
)


def upgrade() -> None:
    conn = op.get_bind()

    for table, index_name, fk_name, unique in _TARGETS:
        if not column_exists(conn, table, "metric_id"):
            op.add_column(
                table,
                sa.Column("metric_id", GUID(), nullable=True),
            )

        if not index_exists(conn, index_name):
            # Partial: rows with no metric_id are the overwhelming majority and
            # must not be forced unique against each other.
            op.create_index(
                index_name,
                table,
                ["metric_id"],
                unique=unique,
                postgresql_where=sa.text("metric_id IS NOT NULL"),
            )

        if not fk_exists(conn, fk_name, table):
            op.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} "
                f"FOREIGN KEY (metric_id) REFERENCES metric (id) NOT VALID"
            )
            op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {fk_name}")


def downgrade() -> None:
    conn = op.get_bind()

    for table, index_name, fk_name, _unique in _TARGETS:
        if fk_exists(conn, fk_name, table):
            op.drop_constraint(fk_name, table, type_="foreignkey")

        if index_exists(conn, index_name):
            op.drop_index(index_name, table_name=table)

        if column_exists(conn, table, "metric_id"):
            op.drop_column(table, "metric_id")
