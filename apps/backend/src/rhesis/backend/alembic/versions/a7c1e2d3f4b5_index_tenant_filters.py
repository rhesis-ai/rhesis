"""Index the tenant filter on the hot list tables

Every query on a tenant table carries ``organization_id = :org`` twice (the
scope listener and the RLS policy), and every list endpoint sorts by
``created_at``. Only a handful of tables had an index on organization_id, so
``GET /prompts?limit=25`` was a sequential scan plus a top-N sort over every
org's rows. A ``(organization_id, created_at)`` btree serves both the filter
and the sort.

Measured on Postgres 16 with 50,000 prompt rows across 3 organizations, page
41 of a 25-row list, as a non-BYPASSRLS role with the tenant GUCs set the way
``get_db_with_tenant_variables`` sets them (median of 25 runs):

    no index    Seq Scan + top-N heapsort, 1045 buffers, 7.01 ms
    this index  Index Scan Backward, no sort, 144 buffers, 0.78 ms

Two shapes were measured and rejected:

* ``(organization_id, created_at DESC)`` is indistinguishable from the
  ascending index (0.84 ms / 133 buffers vs 0.86 ms / 144 buffers): Postgres
  reads the ascending index backwards for ``ORDER BY created_at DESC``. The
  ascending form is used because a plain column list is something Alembic
  autogenerate can compare against the model; a ``DESC`` index has to be
  declared as a SQL expression, which autogenerate cannot.
* ``(organization_id, project_id, created_at)`` is worse than no index at all
  (8.26 ms). The project scope filter is ``project_id = :pid OR project_id IS
  NULL``, so project_id cannot act as an index prefix; the planner falls back
  to a bitmap scan and still has to sort.

``OrganizationMixin.organization_id`` now declares ``index=True`` so new tables
get a single-column index by default. That makes the model metadata expect
``ix_<table>_organization_id`` on the 19 mixin tables that lack one, so this
migration backfills them too (18 built here, ``architect_session`` renamed) -
without that, ``alembic revision --autogenerate`` would propose them on every
run. Six of those tables also get
the composite index above; the single-column index is redundant for reads
there and is kept only so models and migrations agree.

``architect_session`` already had the index under a non-default name and is
renamed rather than duplicated.

Everything builds CONCURRENTLY, outside the migration transaction.

Revision ID: a7c1e2d3f4b5
Revises: b7e1c9d4a2f3
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c1e2d3f4b5"
down_revision: Union[str, None] = "b7e1c9d4a2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# test_run is not listed: it already has ix_test_run_org_created.
_COMPOSITE_TABLES = [
    "prompt",
    "metric",
    "requirement",
    "topic",
    "category",
    "endpoint",
    "tag",
    "test",
    "test_set",
    "comment",
    "task",
]

# OrganizationMixin tables with no index on organization_id as of this revision.
_SINGLE_COLUMN_TABLES = [
    "category",
    "chunk",
    "embedding",
    "file",
    "metric",
    "model",
    "prompt",
    "prompt_template",
    "requirement",
    "source",
    "status",
    "subscription",
    "tag",
    "tagged_item",
    "token",
    "tool",
    "topic",
    "type_lookup",
]


def _indexes() -> list[tuple[str, str, list[str]]]:
    return [
        (f"ix_{t}_org_created", t, ["organization_id", "created_at"]) for t in _COMPOSITE_TABLES
    ] + [(f"ix_{t}_organization_id", t, ["organization_id"]) for t in _SINGLE_COLUMN_TABLES]


def _drop_invalid_indexes() -> None:
    # A failed CONCURRENTLY build leaves an INVALID index behind, and IF NOT EXISTS
    # would then keep it forever. Drop those so the rerun rebuilds them.
    conn = op.get_bind()
    names = [name for name, _, _ in _indexes()]
    invalid = conn.execute(
        sa.text(
            "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "WHERE NOT i.indisvalid AND c.relname = ANY(:names)"
        ),
        {"names": names},
    ).scalars()
    for name in invalid:
        op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')


def upgrade() -> None:
    # architect_session already has this index under a non-default name; rename it
    # so it matches what index=True on the mixin declares instead of building a twin.
    op.execute(
        "ALTER INDEX IF EXISTS ix_architect_session_org_id "
        "RENAME TO ix_architect_session_organization_id"
    )
    with op.get_context().autocommit_block():
        _drop_invalid_indexes()
        for name, table, columns in _indexes():
            op.create_index(name, table, columns, if_not_exists=True, postgresql_concurrently=True)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, _columns in reversed(_indexes()):
            op.drop_index(name, table_name=table, if_exists=True, postgresql_concurrently=True)
    op.execute(
        "ALTER INDEX IF EXISTS ix_architect_session_organization_id "
        "RENAME TO ix_architect_session_org_id"
    )
