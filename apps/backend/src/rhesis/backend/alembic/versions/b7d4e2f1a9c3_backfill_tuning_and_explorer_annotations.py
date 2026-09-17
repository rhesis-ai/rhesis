"""Backfill annotations for metric tuning judgements and explorer human labels

Two JSONB stores move onto the ``annotation`` table here:

* ``test.test_metadata->'reviews'`` on a metric's tuning cases becomes one
  annotation per review, targeting the metric (``target_reference`` is the metric
  id). The verdict each review judged travels in ``attributes`` -- only tuning
  re-reads it, to ask whether the metric has moved since. The array itself is
  left in place; PR-5 clears it once nothing reads it.
* ``test.test_metadata`` label/labeler pairs written by a person become one
  entity-level annotation each, and only then is the pair stripped. A metric's
  own label stays exactly where it is: the whole point of the split is that
  "the metric said fail, a human said pass" is now expressible.

Neither source stored an id, so both take fresh ones and idempotency is by
natural key. For a tuning judgement that is the case, the author and the moment
it was made; for an explorer label it is only the case and the author, because
one person has one label on one test and re-running must not add a second.

**The author of a migrated explorer label is a best guess.** A tuning review
recorded its own ``reviewer_id``, but a label only ever recorded *that* a person
set it (``labeler = 'user'``), never which one, and nothing else kept the actor:
the activity feed derives who did what from the row's own ``user_id``, and
``activity_log`` is a job narrative with no actor column at all. So this takes
``test.user_id``, the test's creator, which is right whenever the person who
added a test is the one who labelled it -- the normal case, since both happen in
the same explorer session -- and wrong where someone labelled a colleague's
test, which the endpoint allowed because it scoped to the organization, not the
owner. The cost of a wrong guess is a name shown against the label and the real
labeller's next edit opening a second row instead of moving this one; their new
label still wins on read. A test with no creator at all is left alone, metadata
label and all, rather than attributed to nobody.

A judgement whose author or status no longer resolves is skipped rather than
aborting on a foreign key, as in eb2719043c01. A ``reviewer_id`` or
``reviewed_at`` that is not merely missing but malformed does abort, on the cast:
both are machine-written, so a bad one means the JSONB was edited by hand and
failing loudly beats guessing.

The label strip is guarded on an annotation carrying **the same verdict**, not
merely on one existing, which is what makes this safe to run while the new code
is already live -- see ``_STRIP_EXPLORER_LABELS``.

``annotation`` and ``test`` both run under FORCE ROW LEVEL SECURITY, so those
statements run with the org GUC bound, one org at a time (same approach as
eb2719043c01). The status and type_lookup seeds go through the shared templates,
which are org-wide and need no GUC.

Revision ID: b7d4e2f1a9c3
Revises: cb3558b77459
Create Date: 2026-09-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_status_template,
    load_cleanup_type_lookup_template,
    load_status_template,
    load_type_lookup_template,
)

revision: str = "b7d4e2f1a9c3"
down_revision: Union[str, None] = "cb3558b77459"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENTITY_TYPE_VALUES = "('EntityType', 'Annotation', 'Entity type for annotations')"

_STATUS_VALUES = (
    "('Accepted', 'The reviewer agreed with what the metric said'), "
    "('Rejected', 'The reviewer disagreed with what the metric said')"
)

_BIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', :org_id, true),
           set_config('app.current_project', '', true)
""")

# Read before any org is bound: the organization table's policy is the one that
# tolerates an unset tenant GUC.
_ORGANIZATIONS = sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")

# One annotation per stored tuning review. ``metric_id`` on the test is what makes
# a row a tuning case, and it is also the target the judgement is about.
_BACKFILL_TUNING = sa.text("""
    INSERT INTO annotation (
        organization_id, project_id, user_id,
        entity_type, entity_id, target_type, target_reference,
        status_id, comments, attributes, created_at, updated_at
    )
    SELECT
        t.organization_id,
        t.project_id,
        u.id,
        'Test',
        t.id,
        'metric',
        CAST(t.metric_id AS text),
        s.id,
        NULLIF(TRIM(COALESCE(r->>'comment', '')), ''),
        jsonb_strip_nulls(
            jsonb_build_object('verdict', r->>'verdict', 'score_type', r->>'score_type')
        ),
        -- ``created_at``, not ``updated_at``, as the fallback: it is part of the
        -- idempotency key below, and a test edited between two runs of this
        -- migration would otherwise re-insert every one of its judgements.
        COALESCE(CAST(r->>'reviewed_at' AS timestamp with time zone), t.created_at),
        COALESCE(CAST(r->>'reviewed_at' AS timestamp with time zone), t.created_at)
    FROM test t
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(t.test_metadata->'reviews') = 'array'
             THEN t.test_metadata->'reviews' ELSE '[]'::jsonb END
    ) AS r
    JOIN "user" u ON u.id = CAST(r->>'reviewer_id' AS uuid)
    JOIN type_lookup tl
      ON tl.organization_id = t.organization_id
     AND tl.type_name = 'EntityType'
     AND tl.type_value = 'Annotation'
    JOIN status s
      ON s.organization_id = t.organization_id
     AND s.entity_type_id = tl.id
     AND s.name = CASE WHEN r->>'decision' = 'rejected' THEN 'Rejected' ELSE 'Accepted' END
    WHERE t.organization_id = CAST(:org_id AS uuid)
      AND t.metric_id IS NOT NULL
      AND t.deleted_at IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM annotation a
          WHERE a.entity_type = 'Test'
            AND a.entity_id = t.id
            AND a.target_type = 'metric'
            AND a.target_reference = CAST(t.metric_id AS text)
            AND a.user_id = u.id
            AND a.created_at = COALESCE(
                CAST(r->>'reviewed_at' AS timestamp with time zone), t.created_at
            )
      )
""")

# One annotation per human-set explorer label. Topic markers carry the label
# ``topic_marker``, so the verdict filter already excludes them.
_BACKFILL_EXPLORER = sa.text("""
    INSERT INTO annotation (
        organization_id, project_id, user_id,
        entity_type, entity_id, target_type,
        status_id, created_at, updated_at
    )
    SELECT
        t.organization_id,
        t.project_id,
        -- The creator, standing in for the labeller nobody recorded. See the
        -- module docstring for what that costs when they are not the same person.
        t.user_id,
        'Test',
        t.id,
        'test',
        s.id,
        t.updated_at,
        t.updated_at
    FROM test t
    JOIN type_lookup tl
      ON tl.organization_id = t.organization_id
     AND tl.type_name = 'EntityType'
     AND tl.type_value = 'TestResult'
    JOIN status s
      ON s.organization_id = t.organization_id
     AND s.entity_type_id = tl.id
     AND s.name = CASE WHEN t.test_metadata->>'label' = 'fail' THEN 'Fail' ELSE 'Pass' END
    WHERE t.organization_id = CAST(:org_id AS uuid)
      AND t.deleted_at IS NULL
      AND t.user_id IS NOT NULL
      AND t.test_metadata->>'labeler' = 'user'
      AND t.test_metadata->>'label' IN ('pass', 'fail')
      AND NOT EXISTS (
          SELECT 1 FROM annotation a
          WHERE a.entity_type = 'Test'
            AND a.entity_id = t.id
            AND a.target_type = 'test'
            AND a.user_id = t.user_id
      )
""")

# Only for rows whose verdict is now represented by an annotation. Matching on
# the status name, not merely on a row existing, is what stops a label being
# dropped when it was never moved: during a rolling deploy the new code can have
# already written this user a *different* verdict, which makes the insert above
# skip the row as a duplicate. Stripping it then would delete the old verdict and
# silently flip the test to the new one.
_STRIP_EXPLORER_LABELS = sa.text("""
    UPDATE test
    SET test_metadata = test_metadata - 'label' - 'labeler'
    WHERE organization_id = CAST(:org_id AS uuid)
      AND test_metadata->>'labeler' = 'user'
      AND test_metadata->>'label' IN ('pass', 'fail')
      AND EXISTS (
          SELECT 1 FROM annotation a
          JOIN status s ON s.id = a.status_id
          WHERE a.entity_type = 'Test'
            AND a.entity_id = test.id
            AND a.target_type = 'test'
            AND a.user_id = test.user_id
            AND a.deleted_at IS NULL
            AND lower(s.name) = test.test_metadata->>'label'
      )
""")

# Downgrade puts every entity-level Test annotation back where the old code read
# it from, including any the new code wrote after the upgrade -- the metadata pair
# is the pre-annotation representation, so that is where they belong.
#
# ``DISTINCT ON`` picks the newest per test, with the same ``updated_at`` then id
# tie-break the read path uses, because one metadata key cannot hold two people's
# labels and an arbitrary choice would differ between runs.
#
# ``label IS NULL`` is what protects a metric: a test the upgrade deliberately
# left alone still carries the metric's own verdict, and ``||`` overwrites keys,
# so without the guard a downgrade would destroy it and relabel it as a person's.
_RESTORE_EXPLORER_LABELS = sa.text("""
    UPDATE test
    SET test_metadata = test_metadata
        || jsonb_build_object('label', lower(latest.name), 'labeler', 'user')
    FROM (
        SELECT DISTINCT ON (a.entity_id) a.entity_id, s.name
        FROM annotation a
        JOIN status s ON s.id = a.status_id
        WHERE a.entity_type = 'Test'
          AND a.target_type = 'test'
          AND a.deleted_at IS NULL
          AND a.organization_id = CAST(:org_id AS uuid)
          AND s.name IN ('Pass', 'Fail')
        ORDER BY a.entity_id, a.updated_at DESC, a.id DESC
    ) AS latest
    WHERE test.id = latest.entity_id
      AND test.organization_id = CAST(:org_id AS uuid)
      AND test.test_metadata->>'label' IS NULL
""")

_DELETE_EXPLORER = sa.text("""
    DELETE FROM annotation
    WHERE organization_id = CAST(:org_id AS uuid)
      AND entity_type = 'Test'
      AND target_type = 'test'
""")

# Every tuning judgement in the org, not only those whose target still matches
# the case's current metric. Leaving one behind would strand it on an Accepted or
# Rejected status that the cleanup below then tries to delete, failing on the
# foreign key with the downgrade half applied.
_DELETE_TUNING = sa.text("""
    DELETE FROM annotation
    WHERE organization_id = CAST(:org_id AS uuid)
      AND entity_type = 'Test'
      AND target_type = 'metric'
""")

# The seeds and cleanups are org-wide, so the cleanups must not inherit the
# binding the loop above left behind: ``status`` and ``type_lookup`` both run
# FORCE ROW LEVEL SECURITY, so under a bound org they would clean only that one.
_UNBIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', '', true),
           set_config('app.current_project', '', true)
""")


def _rowcount(result) -> int:
    return result.rowcount if result.rowcount is not None else 0


def upgrade() -> None:
    op.execute(load_type_lookup_template(_ENTITY_TYPE_VALUES))
    op.execute(load_status_template("EntityType", "Annotation", _STATUS_VALUES))

    conn = op.get_bind()
    org_ids = [row[0] for row in conn.execute(_ORGANIZATIONS)]

    tuning = labels = 0
    for org_id in org_ids:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)

        from_tuning = _rowcount(conn.execute(_BACKFILL_TUNING, params))
        from_explorer = _rowcount(conn.execute(_BACKFILL_EXPLORER, params))
        stripped = _rowcount(conn.execute(_STRIP_EXPLORER_LABELS, params))
        if from_tuning or from_explorer:
            print(
                f"[b7d4e2f1a9c3] org {org_id}: {from_tuning} tuning judgement(s), "
                f"{from_explorer} explorer label(s), {stripped} metadata label(s) cleared."
            )
        tuning += from_tuning
        labels += from_explorer

    print(
        f"[b7d4e2f1a9c3] Backfilled {tuning} tuning judgement(s) and {labels} explorer "
        f"label(s) across {len(org_ids)} organization(s)."
    )


def downgrade() -> None:
    conn = op.get_bind()
    for org_id in [row[0] for row in conn.execute(_ORGANIZATIONS)]:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)
        conn.execute(_RESTORE_EXPLORER_LABELS, params)
        conn.execute(_DELETE_EXPLORER, params)
        conn.execute(_DELETE_TUNING, params)

    conn.execute(_UNBIND_ORG)
    op.execute(load_cleanup_status_template("EntityType", "Annotation", "'Accepted', 'Rejected'"))
    op.execute(load_cleanup_type_lookup_template("EntityType", "'Annotation'"))
