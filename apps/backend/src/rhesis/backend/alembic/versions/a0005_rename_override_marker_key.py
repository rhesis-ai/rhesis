"""Rename the override marker key review_id -> annotation_id

The marker an annotation writes into ``test_metrics`` / ``trace_metrics`` /
``test_output`` pointed at the annotation under the key ``review_id``, left over
from when annotations were JSONB reviews. Its value already *is* an annotation
id (a0004bkflanno reused each JSONB ``review_id`` as the annotation's primary
key), so this renames the key and touches nothing else.

``v_metric_stats.has_override`` only tests that ``override`` exists and is
non-empty, and reads ``{override,original_value}``; it never reads this key, so
the view needs no change.

Five places carry the marker:

- ``test_result.test_metrics -> metrics -> <metric> -> override``
- ``test_result.test_output -> conversation_summary[] -> override``
- ``trace.trace_metrics -> turn_metrics -> metrics -> <metric> -> override``
- ``trace.trace_metrics -> conversation_metrics -> metrics -> <metric> -> override``
- ``trace.trace_metrics -> turn_overrides -> <turn> -> override``

All but the second are an object of entries, so one template covers four of
them. Renaming subtracts the old key and adds the new one, which preserves
``original_value``, ``original_error``, ``overridden_by`` and ``overridden_at``.

``test_result`` and ``trace`` run under FORCE ROW LEVEL SECURITY, so every
statement runs with the org GUC bound, one org at a time (same approach as
a0004bkflanno).

Revision ID: a0005ovrdkey
Revises: a0004bkflanno
Create Date: 2026-09-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a0005ovrdkey"
down_revision: Union[str, None] = "a0004bkflanno"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', :org_id, true),
           set_config('app.current_project', '', true)
""")

# Read before any org is bound: the organization table's policy tolerates an
# unset tenant GUC, the two tables below do not.
_ORGANIZATIONS = sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")

# An object whose values each hold an `override`: the metrics maps and
# `turn_overrides`.
_RENAME_IN_OBJECT = """
    UPDATE {table} t
    SET {column} = jsonb_set(t.{column}, '{path}', (
        SELECT jsonb_object_agg(
            e.key,
            CASE WHEN e.value #> '{{override,{old}}}' IS NOT NULL
                 THEN jsonb_set(
                          e.value,
                          '{{override}}',
                          ((e.value -> 'override') - '{old}')
                          || jsonb_build_object('{new}', e.value #> '{{override,{old}}}')
                      )
                 ELSE e.value
            END
        )
        FROM jsonb_each(t.{column} #> '{path}') AS e
    ))
    WHERE t.organization_id = CAST(:org_id AS uuid)
      AND jsonb_typeof(t.{column} #> '{path}') = 'object'
      AND EXISTS (
          SELECT 1 FROM jsonb_each(t.{column} #> '{path}') AS g
          WHERE g.value #> '{{override,{old}}}' IS NOT NULL
      )
"""

# An array whose elements each hold an `override`: the conversation turns. Turn
# order is the array order, so the rebuild has to preserve it.
_RENAME_IN_ARRAY = """
    UPDATE {table} t
    SET {column} = jsonb_set(t.{column}, '{path}', (
        SELECT jsonb_agg(
            CASE WHEN e.value #> '{{override,{old}}}' IS NOT NULL
                 THEN jsonb_set(
                          e.value,
                          '{{override}}',
                          ((e.value -> 'override') - '{old}')
                          || jsonb_build_object('{new}', e.value #> '{{override,{old}}}')
                      )
                 ELSE e.value
            END
            ORDER BY e.ord
        )
        FROM jsonb_array_elements(t.{column} #> '{path}')
             WITH ORDINALITY AS e(value, ord)
    ))
    WHERE t.organization_id = CAST(:org_id AS uuid)
      AND jsonb_typeof(t.{column} #> '{path}') = 'array'
      AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(t.{column} #> '{path}') AS g
          WHERE g.value #> '{{override,{old}}}' IS NOT NULL
      )
"""

_OBJECT_TARGETS = (
    {"table": "test_result", "column": "test_metrics", "path": "{metrics}"},
    {"table": "trace", "column": "trace_metrics", "path": "{turn_metrics,metrics}"},
    {
        "table": "trace",
        "column": "trace_metrics",
        "path": "{conversation_metrics,metrics}",
    },
    {"table": "trace", "column": "trace_metrics", "path": "{turn_overrides}"},
)

_ARRAY_TARGETS = (
    {"table": "test_result", "column": "test_output", "path": "{conversation_summary}"},
)


def _rename(old: str, new: str) -> None:
    conn = op.get_bind()
    org_ids = [row[0] for row in conn.execute(_ORGANIZATIONS)]

    renamed = 0
    for org_id in org_ids:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)

        for template, targets in (
            (_RENAME_IN_OBJECT, _OBJECT_TARGETS),
            (_RENAME_IN_ARRAY, _ARRAY_TARGETS),
        ):
            for target in targets:
                result = conn.execute(sa.text(template.format(old=old, new=new, **target)), params)
                renamed += result.rowcount if result.rowcount is not None else 0

    print(
        f"[a0005ovrdkey] Renamed '{old}' -> '{new}' in override markers on "
        f"{renamed} row(s) across {len(org_ids)} organization(s)."
    )


def upgrade() -> None:
    _rename("review_id", "annotation_id")


def downgrade() -> None:
    _rename("annotation_id", "review_id")
