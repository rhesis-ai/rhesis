"""Backfill usage from pre-launch activity

The usage-accounting feature (77df3dbea77d) only starts counting from the
moment its accrual code runs. Without this migration, an org that has
already run tests, ingested traces, or generated tests earlier in the
current billing period would see 0 on the dashboard despite real activity,
until fresh activity happens to accrue after deploy.

This backfills the *current* UTC billing period only (not all-time history)
for the three flow resources that have a reliable source, using the exact
row shapes the live accrual code counts:

- TEST_EXECUTIONS: COUNT(*) of `test_result` rows, matching
  `get_test_statistics()`'s `COUNT(test_result.id)` in
  tasks/execution/result_processor.py (there run per test_run; here
  aggregated per org across the whole period).
- TRACING_SPANS: COUNT(*) of `trace` rows, matching `post_ingest_link`'s
  `len(stored_spans)` in tasks/telemetry/post_ingest.py.
- TEST_GENERATION: an approximation, not an exact match. There is no column
  marking a `test` row as "produced by generation" versus "manually
  authored or imported" -- both paths call the same `bulk_create_tests()`.
  A `test_set` gets a `generation` key stamped into
  `attributes.metadata.generation` only when it went through the
  generation pipeline (tasks/test_set.py's
  `_attach_tests_to_existing_test_set` / `_save_test_set_to_database`), so
  tests linked to such a test_set are counted instead of every test row in
  the period. Known imprecision: a test manually added later to an
  already-generated test_set is indistinguishable from this query and gets
  counted too.

MODEL_TOKENS is deliberately NOT backfilled: no table anywhere recorded
Rhesis-hosted-model token counts before this feature's `on_usage` callback
started emitting them. `trace.attributes` carries token counts for
OTel-instrumented spans generally (any customer app's LLM calls it happens
to trace), not scoped to "was this a Rhesis-hosted-model call that should
count toward this org's quota" -- using it would frequently count the
wrong thing. It starts at zero for this period, the same as any
newly-introduced counter with no prior instrumentation.

Design notes:

- Per-organization loop issuing plain indexed SELECTs, not one set-based
  `INSERT ... SELECT ... GROUP BY organization_id` across all orgs. Every
  source table here (`test_result`, `trace`, `test`, `test_set`,
  `test_test_set`) has FORCE'd row-level security, and a single query
  spanning multiple orgs cannot satisfy each row's own
  `organization_id = current_setting('app.current_organization')` check --
  only disabling RLS for the query would work, which requires an
  `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` taking an ACCESS EXCLUSIVE
  lock. `test_result` and `trace` are continuously written in production
  (test executions, telemetry ingestion); briefly serializing every
  concurrent writer behind that lock is not an acceptable trade for a
  one-time cosmetic backfill. A per-org loop of ordinary filtered SELECTs
  never needs that lock.
- Every query also carries an explicit `organization_id = :org_id` WHERE
  clause in addition to setting the `app.current_organization` GUC per
  iteration: the WHERE clause keeps this correct even when the connecting
  role happens to bypass RLS entirely (true for local dev's default
  superuser role), while the GUC satisfies the `usage` table's WITH CHECK
  on the INSERT below in any environment where RLS is actually enforced.
  Neither mechanism alone is guaranteed to hold in every environment this
  runs in, so both are applied together.
- The upsert uses `used = GREATEST(usage.used, EXCLUDED.used)`, not
  addition. Live accrual may already have written to the exact same
  (organization_id, resource, current period) row between deploy and this
  migration running -- the historical COUNT computed here already spans
  the whole period including that post-deploy window (the same rows get
  counted by both the live accrual path and this backfill's SELECT), so
  adding would double-count that overlap. GREATEST only ever raises `used`
  to the historical floor and never lowers a higher, already-accrued
  value, which also makes re-running this migration a no-op the second
  time.
- `organization.deleted_at IS NULL` filters the org list, unlike a few
  older org-loop migrations in this file (e.g. 41a9355b3991) that don't
  filter it -- there is no dashboard for a deleted org's members to see a
  backfilled number on, so there is nothing to gain from writing one.
- Accepted, unaddressed edge case: a test execution (or span, or generated
  test) that lands in the narrow window between this migration's SELECT
  for an org and its own upsert landing could, if the live Celery accrual
  task for that same event happens to run in between, be counted once by
  each mechanism -- a one-off overcount of at most a handful of units.
  Not worth a distributed lock for a one-time, non-billing-enforced
  dashboard number.

Revision ID: 91607f0dd412
Revises: 77df3dbea77d
Create Date: 2026-08-04

"""

from calendar import monthrange
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91607f0dd412"
down_revision: Union[str, None] = "77df3dbea77d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SET_ORG_GUC = sa.text("SELECT set_config('app.current_organization', :org_id, true)")

_COUNT_TEST_EXECUTIONS = sa.text("""
    SELECT count(*) FROM test_result
    WHERE organization_id = :org_id
      AND created_at >= :period_start
      AND deleted_at IS NULL
""")

_COUNT_TRACING_SPANS = sa.text("""
    SELECT count(*) FROM trace
    WHERE organization_id = :org_id
      AND created_at >= :period_start
      AND deleted_at IS NULL
""")

_COUNT_TEST_GENERATION = sa.text("""
    SELECT count(DISTINCT t.id) FROM test t
    JOIN test_test_set tts ON tts.test_id = t.id
    JOIN test_set ts ON ts.id = tts.test_set_id
    WHERE t.organization_id = :org_id
      AND t.created_at >= :period_start
      AND t.deleted_at IS NULL
      AND ts.attributes #> '{metadata,generation}' IS NOT NULL
""")

_UPSERT_USAGE = sa.text("""
    INSERT INTO usage (organization_id, resource, period_start, period_end, used)
    VALUES (:org_id, :resource, :period_start, :period_end, :used)
    ON CONFLICT (organization_id, resource, period_start)
    DO UPDATE SET
        used = GREATEST(usage.used, EXCLUDED.used),
        updated_at = now()
""")


def upgrade() -> None:
    conn = op.get_bind()

    # Computed once here rather than imported from
    # app.services.usage._current_period: this migration stays self-contained
    # (no dependency on application code that could change shape later), but
    # the semantics must match exactly -- first day of the current UTC month
    # through its last day.
    today = datetime.now(timezone.utc).date()
    period_start = today.replace(day=1)
    period_end = today.replace(day=monthrange(today.year, today.month)[1])

    org_ids = [
        str(row[0])
        for row in conn.execute(
            sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")
        ).fetchall()
    ]

    print(
        f"\nBackfilling usage for {len(org_ids)} organization(s), "
        f"period {period_start}..{period_end}"
    )

    backfilled = 0
    for org_id in org_ids:
        conn.execute(_SET_ORG_GUC, {"org_id": org_id})

        params = {"org_id": org_id, "period_start": period_start}
        test_executions = conn.execute(_COUNT_TEST_EXECUTIONS, params).scalar() or 0
        tracing_spans = conn.execute(_COUNT_TRACING_SPANS, params).scalar() or 0
        test_generation = conn.execute(_COUNT_TEST_GENERATION, params).scalar() or 0

        for resource, used in (
            ("test_executions", test_executions),
            ("tracing_spans", tracing_spans),
            ("test_generation", test_generation),
        ):
            if not used:
                continue
            conn.execute(
                _UPSERT_USAGE,
                {
                    "org_id": org_id,
                    "resource": resource,
                    "period_start": period_start,
                    "period_end": period_end,
                    "used": used,
                },
            )
            backfilled += 1

    print(f"Usage backfill complete: {backfilled} (org, resource) row(s) written.\n")


def downgrade() -> None:
    """No-op.

    This migration makes no schema changes to undo. It also cannot safely
    reverse its data: rows it wrote merge via GREATEST with whatever the
    live accrual path has added since, so there is no way to tell "what
    this migration contributed" apart from "what real usage has since
    accrued" without a marker column this table doesn't have. Deleting the
    affected rows on downgrade would destroy real, live-accrued usage
    along with the backfilled baseline.
    """
