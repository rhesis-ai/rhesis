"""Re-run the JSON key renames on project-scoped rows

01926b6dd2b6 (override marker ``review_id`` -> ``annotation_id``) and 8c1f4e2a7b9d
(Goal Achievement behaviour keys -> criteria) bound the org GUC and left
``app.current_project`` blank. Under the restrictive ``project_isolation`` policy
that hides every row with a ``project_id``, so on a migration role without
BYPASSRLS they only rewrote NULL-project rows. ``trace.project_id`` is NOT NULL,
so no trace was rewritten at all.

This walks every org and every project in it and applies the same rewrites. Both
are key renames that skip rows already on the new keys, so running them where the
originals did reach every row changes nothing.

Revision ID: 17eb2c93d8e0
Revises: 8c1f4e2a7b9d
Create Date: 2026-09-30
"""

import json
from typing import Any, Callable, Dict, Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.tenant_scope import iter_tenant_scopes

revision: str = "17eb2c93d8e0"
down_revision: Union[str, None] = "8c1f4e2a7b9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IN_SCOPE = """
    t.organization_id = CAST(:org_id AS uuid)
    AND t.project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
"""

# --- 01926b6dd2b6: override marker key -----------------------------------------

_RENAME_IN_OBJECT = (
    """
    UPDATE {table} t
    SET {column} = jsonb_set(t.{column}, '{path}', (
        SELECT jsonb_object_agg(
            e.key,
            CASE WHEN e.value #> '{{override,review_id}}' IS NOT NULL
                 THEN jsonb_set(
                          e.value,
                          '{{override}}',
                          ((e.value -> 'override') - 'review_id')
                          || jsonb_build_object('annotation_id', e.value #> '{{override,review_id}}')
                      )
                 ELSE e.value
            END
        )
        FROM jsonb_each(t.{column} #> '{path}') AS e
    ))
    WHERE """
    + _IN_SCOPE
    + """
      AND jsonb_typeof(t.{column} #> '{path}') = 'object'
      AND EXISTS (
          SELECT 1 FROM jsonb_each(t.{column} #> '{path}') AS g
          WHERE g.value #> '{{override,review_id}}' IS NOT NULL
      )
"""
)

_RENAME_IN_ARRAY = (
    """
    UPDATE {table} t
    SET {column} = jsonb_set(t.{column}, '{path}', (
        SELECT jsonb_agg(
            CASE WHEN e.value #> '{{override,review_id}}' IS NOT NULL
                 THEN jsonb_set(
                          e.value,
                          '{{override}}',
                          ((e.value -> 'override') - 'review_id')
                          || jsonb_build_object('annotation_id', e.value #> '{{override,review_id}}')
                      )
                 ELSE e.value
            END
            ORDER BY e.ord
        )
        FROM jsonb_array_elements(t.{column} #> '{path}')
             WITH ORDINALITY AS e(value, ord)
    ))
    WHERE """
    + _IN_SCOPE
    + """
      AND jsonb_typeof(t.{column} #> '{path}') = 'array'
      AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(t.{column} #> '{path}') AS g
          WHERE g.value #> '{{override,review_id}}' IS NOT NULL
      )
"""
)

_MARKER_TARGETS = (
    (_RENAME_IN_OBJECT, {"table": "test_result", "column": "test_metrics", "path": "{metrics}"}),
    (
        _RENAME_IN_OBJECT,
        {"table": "trace", "column": "trace_metrics", "path": "{turn_metrics,metrics}"},
    ),
    (
        _RENAME_IN_OBJECT,
        {"table": "trace", "column": "trace_metrics", "path": "{conversation_metrics,metrics}"},
    ),
    (_RENAME_IN_OBJECT, {"table": "trace", "column": "trace_metrics", "path": "{turn_overrides}"}),
    (
        _RENAME_IN_ARRAY,
        {"table": "test_result", "column": "test_output", "path": "{conversation_summary}"},
    ),
)

# --- 8c1f4e2a7b9d: Goal Achievement behaviour keys ------------------------------

_CRITERIA_TARGETS = (
    ("test_result", ("test_output", "test_metrics")),
    ("trace", ("trace_metrics",)),
    ("test", ("test_metadata",)),
)

_CONTRACT_KEYS = {
    "required_behavior": "required_criteria",
    "prohibited_behavior": "prohibited_criteria",
}
_COUNT_KEYS = {
    "behaviors_total": "criteria_total",
    "behaviors_complied": "criteria_met",
    "behaviors_violated": "criteria_failed",
    "violated_behaviors": "failed_criteria",
}
_CRITERIA_MATCH_KEYS = ["behavior_verdicts", *_CONTRACT_KEYS, *_COUNT_KEYS]


def _rename_keys(node: Dict[str, Any], mapping: Dict[str, str]) -> None:
    for old, new in mapping.items():
        if old in node:
            node[new] = node.pop(old)


def _upgrade_node(node: Dict[str, Any]) -> None:
    _rename_keys(node, _CONTRACT_KEYS)
    if isinstance(node.get("behavior_verdicts"), list):
        node["criteria_evaluations"] = [
            {
                "criterion": v.get("behavior", ""),
                "kind": v.get("kind", "required"),
                "met": bool(v.get("complied", False)),
                "evidence": v.get("evidence", ""),
                "relevant_turns": v.get("relevant_turns") or [],
            }
            for v in node.pop("behavior_verdicts")
            if isinstance(v, dict)
        ]
        node.setdefault("all_criteria_met", all(c["met"] for c in node["criteria_evaluations"]))
    _rename_keys(node, _COUNT_KEYS)


def _walk(value: Any, visit: Callable[[Dict[str, Any]], None]) -> Any:
    if isinstance(value, dict):
        for child in value.values():
            _walk(child, visit)
        visit(value)
    elif isinstance(value, list):
        for child in value:
            _walk(child, visit)
    return value


def _rewrite_criteria(conn, params: Dict[str, Any], table: str, columns: Sequence[str]) -> int:
    match = " OR ".join(
        f"CAST(t.{c} AS text) LIKE :key{i}"
        for c in columns
        for i in range(len(_CRITERIA_MATCH_KEYS))
    )
    rows = conn.execute(
        sa.text(
            f"SELECT t.id, {', '.join(f't.{c}' for c in columns)} FROM {table} t "  # noqa: S608
            f"WHERE {_IN_SCOPE} AND ({match})"
        ),
        {**params, **{f"key{i}": f'%"{k}"%' for i, k in enumerate(_CRITERIA_MATCH_KEYS)}},
    ).fetchall()

    rewritten = 0
    for row in rows:
        before = [json.dumps(row[i + 1]) for i in range(len(columns))]
        values = {c: _walk(row[i + 1], _upgrade_node) for i, c in enumerate(columns)}
        if [json.dumps(v) for v in values.values()] == before:
            continue
        assignments = ", ".join(f"{c} = CAST(:{c} AS jsonb)" for c in columns)
        conn.execute(
            sa.text(f"UPDATE {table} SET {assignments} WHERE id = :id"),  # noqa: S608
            {
                "id": row[0],
                **{c: json.dumps(v) if v is not None else None for c, v in values.items()},
            },
        )
        rewritten += 1
    return rewritten


def upgrade() -> None:
    conn = op.get_bind()
    counts = {"test_result": 0, "trace": 0, "test": 0}
    orgs = set()

    for org_id, project_id in iter_tenant_scopes(conn):
        orgs.add(org_id)
        params = {"org_id": org_id, "project_id": project_id}
        for template, target in _MARKER_TARGETS:
            result = conn.execute(sa.text(template.format(**target)), params)
            counts[target["table"]] += result.rowcount or 0
        for table, columns in _CRITERIA_TARGETS:
            counts[table] += _rewrite_criteria(conn, params, table, columns)

    print(
        f"[17eb2c93d8e0] Rewrote {counts['test_result']} test_result, {counts['trace']} trace "
        f"and {counts['test']} test row update(s) across {len(orgs)} organization(s)."
    )


def downgrade() -> None:
    # 01926b6dd2b6 and 8c1f4e2a7b9d own the reverse renames.
    pass
