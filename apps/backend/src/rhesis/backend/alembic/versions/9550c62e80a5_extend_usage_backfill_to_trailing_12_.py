"""Extend usage backfill to trailing 12 months

91607f0dd412 only backfilled the *current* billing period, on the
assumption that "no usage yet this month" was the only gap worth
closing. That assumption was wrong for any org whose most recent
activity predates the current calendar month: an org with months of
real test executions, spans, and generated tests but nothing yet in the
few days since the new month rolled over shows a completely empty
Overview (0 used for everything) and an empty "Usage over Time" chart
across every one of its 3/6/12-month filter options -- because the
`usage` table never got a row for any of those earlier months, not
because nothing happened. Observed directly against a real org with
4,000+ historical test executions and its last activity dated three
weeks before this migration's authoring date.

This migration re-runs the same backfill for each of the trailing 12
calendar months (matching the "Usage over Time" chart's own maximum
lookback window, not further -- there's no filter option that would ever
read past it), not just the current one. Same resources, same sourcing,
same caveats as 91607f0dd412:

- TEST_EXECUTIONS / TRACING_SPANS: exact `test_result` / `trace` row
  counts.
- TEST_GENERATION: the same test_set.attributes.metadata.generation
  marker approximation.
- MODEL_TOKENS: still not backfillable, for the same reason (no prior
  table recorded Rhesis-hosted-model token counts at all).

Design carried over unchanged from 91607f0dd412 -- see that migration's
docstring for the full reasoning behind each of these:

- Per-organization loop of plain filtered SELECTs, never touching RLS on
  `test_result`/`trace` to avoid an ACCESS EXCLUSIVE lock on tables under
  live write load.
- Both an explicit `organization_id = :org_id` WHERE clause and a
  per-iteration `app.current_organization` GUC set, so this is correct
  whether or not the connecting role bypasses RLS.
- `used = GREATEST(usage.used, EXCLUDED.used)` merge, not addition --
  still correct here since each month's COUNT is a superset of whatever
  live accrual may already have written for that exact
  (org, resource, month) row, and still what makes re-running this
  migration a no-op.
- `organization.deleted_at IS NULL` filters the org list.
- `test_set.deleted_at` is deliberately not filtered in the
  TEST_GENERATION join, for the same live-accrual-parity reason.

What's different from 91607f0dd412, beyond the month range:

- Each month's window is now closed on both ends (`created_at >=
  month_start AND created_at < month_end`), not open-ended
  (`>= period_start`). The single-period version only needed a floor
  because "the current period" has no later boundary to worry about;
  backfilling 12 distinct months requires each one to have its own
  ceiling so July's rows don't also get counted into June's bucket.
  `month_end` is the first instant of the *next* month, computed by
  adding one day to the current month's last calendar day -- reliable
  across every month length without re-deriving it, and sidesteps any
  ambiguity about whether an inclusive upper bound should mean
  end-of-day or midnight.
- Cost is ~12x 91607f0dd412's: 12 months x 3 resource queries x every
  org, plus up to 12x the upserts. Still no schema-level locking of any
  kind (see above), so the added cost is wall-clock time on this
  migration's own connection, not contention with concurrent traffic --
  an acceptable trade for a one-time correction, accepted explicitly
  over leaving 11 months permanently unbackfilled.

Revision ID: 9550c62e80a5
Revises: 91607f0dd412
Create Date: 2026-08-04

"""

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9550c62e80a5"
down_revision: Union[str, None] = "91607f0dd412"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MONTHS_TO_BACKFILL = 12

_SET_ORG_GUC = sa.text("SELECT set_config('app.current_organization', :org_id, true)")

_COUNT_TEST_EXECUTIONS = sa.text("""
    SELECT count(*) FROM test_result
    WHERE organization_id = :org_id
      AND created_at >= :month_start
      AND created_at < :month_end
      AND deleted_at IS NULL
""")

_COUNT_TRACING_SPANS = sa.text("""
    SELECT count(*) FROM trace
    WHERE organization_id = :org_id
      AND created_at >= :month_start
      AND created_at < :month_end
      AND deleted_at IS NULL
""")

_COUNT_TEST_GENERATION = sa.text("""
    SELECT count(DISTINCT t.id) FROM test t
    JOIN test_test_set tts ON tts.test_id = t.id
    JOIN test_set ts ON ts.id = tts.test_set_id
    WHERE t.organization_id = :org_id
      AND t.created_at >= :month_start
      AND t.created_at < :month_end
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


def _trailing_months(months: int, today: date) -> list[tuple[date, date]]:
    """Return ``(period_start, period_end)`` for each of the trailing
    *months* calendar months, oldest first, ending with the month
    containing *today*. Mirrors app.services.usage's period math, kept
    local rather than imported so this migration stays self-contained
    (see 91607f0dd412's docstring for why).
    """
    year, month = today.year, today.month
    result = []
    for _ in range(months):
        period_start = date(year, month, 1)
        period_end = date(year, month, monthrange(year, month)[1])
        result.append((period_start, period_end))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return list(reversed(result))


def _month_bounds_utc(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    """UTC-aware (inclusive start, exclusive end) instants for one month.

    Timezone-aware `datetime`s, not the bare `date`s used for `usage`'s
    own DATE columns: binding a bare `date` against a `timestamptz`
    column lets Postgres cast it using the connecting session's timezone
    rather than UTC, silently shifting the boundary by that session's UTC
    offset. See 91607f0dd412's docstring for the concrete example.
    """
    month_start = datetime(
        period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc
    )
    next_month = period_end + timedelta(days=1)
    month_end = datetime(next_month.year, next_month.month, next_month.day, tzinfo=timezone.utc)
    return month_start, month_end


def upgrade() -> None:
    conn = op.get_bind()

    today = datetime.now(timezone.utc).date()
    months = _trailing_months(_MONTHS_TO_BACKFILL, today)

    org_ids = [
        str(row[0])
        for row in conn.execute(
            sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")
        ).fetchall()
    ]

    print(
        f"\nBackfilling usage for {len(org_ids)} organization(s) across "
        f"{len(months)} trailing month(s): {months[0][0]}..{months[-1][1]}"
    )

    backfilled = 0
    for org_id in org_ids:
        conn.execute(_SET_ORG_GUC, {"org_id": org_id})

        for period_start, period_end in months:
            month_start, month_end = _month_bounds_utc(period_start, period_end)
            params = {"org_id": org_id, "month_start": month_start, "month_end": month_end}

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

    print(f"Usage backfill complete: {backfilled} (org, resource, month) row(s) written.\n")


def downgrade() -> None:
    """No-op, for the same reason as 91607f0dd412: no schema to undo, and
    rows written here merge via GREATEST with whatever live accrual has
    since added, so there is no way to tell "what this migration
    contributed" apart from real accrued usage without a marker column
    this table doesn't have.
    """
