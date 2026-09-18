"""Drop the JSONB review stores now that annotations hold every judgement

Three stores fed the annotation table and nothing reads them any more:

* ``test_result.test_reviews`` and ``trace.trace_reviews``, backfilled by
  eb2719043c01. Both columns go here.
* ``test.test_metadata->'reviews'`` on metric tuning cases, backfilled by
  b7d4e2f1a9c3, which deliberately left the array in place so the old code could
  still read it during a rolling deploy. That window is closed, so the key is
  stripped -- the column is shared with other writers, hence ``- 'reviews'``
  rather than rewriting the object.

The columns are dropped rather than left dormant because a nullable JSONB column
that nothing writes is an invitation to write to it again, and the reviews they
held are in ``annotation`` with their original ids (eb2719043c01 reused each
JSONB ``review_id`` as the annotation id, which is what keeps the ``override``
markers inside ``test_metrics`` valid).

``test`` runs under FORCE ROW LEVEL SECURITY, so the metadata strip runs with the
org GUC bound, one org at a time, as in b7d4e2f1a9c3. The two DROP COLUMNs are
DDL and need no binding.

**The downgrade cannot bring the data back.** It re-adds both columns as nullable
and leaves them empty, and it cannot restore the stripped metadata key either.
That is not an oversight: the annotations are the record now, and rebuilding the
JSONB from them would invent a shape no writer has produced since PR-1. Anyone
needing the old payloads should restore from a backup taken before this ran.

Revision ID: a3f6c81d05b2
Revises: b7d4e2f1a9c3
Create Date: 2026-09-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f6c81d05b2"
down_revision: Union[str, None] = "b7d4e2f1a9c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Read before any org is bound: the organization table's policy is the one that
# tolerates an unset tenant GUC.
_ORGANIZATIONS = sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")

_BIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', :org_id, true),
           set_config('app.current_project', '', true)
""")

_UNBIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', '', true),
           set_config('app.current_project', '', true)
""")

# Only rows that actually carry the key, so the rowcount reports what changed
# rather than the size of the table.
_STRIP_TUNING_REVIEWS = sa.text("""
    UPDATE test
       SET test_metadata = test_metadata - 'reviews'
     WHERE organization_id = CAST(:org_id AS uuid)
       AND test_metadata ? 'reviews'
""")


def _rowcount(result) -> int:
    return result.rowcount if result.rowcount is not None else 0


def upgrade() -> None:
    conn = op.get_bind()

    stripped = 0
    org_ids = [row[0] for row in conn.execute(_ORGANIZATIONS)]
    for org_id in org_ids:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)
        stripped += _rowcount(conn.execute(_STRIP_TUNING_REVIEWS, params))
    conn.execute(_UNBIND_ORG)

    print(
        f"[a3f6c81d05b2] Cleared the tuning reviews array from {stripped} test(s) "
        f"across {len(org_ids)} organization(s)."
    )

    op.drop_column("test_result", "test_reviews")
    op.drop_column("trace", "trace_reviews")


def downgrade() -> None:
    # Empty, and deliberately so -- see the module docstring. Re-added only so a
    # downgrade leaves a schema the older code can start against.
    op.add_column(
        "test_result",
        sa.Column("test_reviews", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "trace",
        sa.Column("trace_reviews", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
