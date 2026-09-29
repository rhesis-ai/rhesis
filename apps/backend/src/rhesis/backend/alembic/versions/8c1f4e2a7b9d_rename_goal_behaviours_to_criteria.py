"""Rename Goal Achievement behaviour keys to criteria

Contract-scored Goal Achievement results stored their breakdown as ``behavior_verdicts``
(``behavior`` / ``complied``) with ``behaviors_*`` counts, next to the goal-scored
``criteria_evaluations`` (``criterion`` / ``met``). Both now use the criteria shape, and the
contract's ``required_behavior`` / ``prohibited_behavior`` lists are ``required_criteria`` /
``prohibited_criteria``.

The keys sit at several depths: ``test_result.test_output -> goal_evaluation``,
``test_result.test_metrics -> metrics -> <metric>``, the metric maps in ``trace.trace_metrics``,
the contract copy inside each of those, and ``test.test_metadata -> evaluation_contract``. So
rows are rewritten in Python by walking the whole JSON value rather than by one SQL template per
path.

The downgrade turns criteria back into behaviour verdicts only on contract-scored entries
(those carrying ``contract`` or ``adversarial``); goal-scored entries always used criteria.

``test``, ``test_result`` and ``trace`` run under FORCE ROW LEVEL SECURITY, so every statement
runs with the org GUC bound, one org at a time (same approach as 01926b6dd2b6).

Revision ID: 8c1f4e2a7b9d
Revises: 7c3e9a1b5d20
Create Date: 2026-09-29
"""

import json
from typing import Any, Callable, Dict, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8c1f4e2a7b9d"
down_revision: Union[str, None] = "7c3e9a1b5d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', :org_id, true),
           set_config('app.current_project', '', true)
""")

# Read before any org is bound: the organization table's policy tolerates an unset tenant GUC.
_ORGANIZATIONS = sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")

# (table, JSONB columns). A cheap text match narrows the rows before the Python walk; it also
# matches ordinary conversation text, so only rows the walk actually changed are written.
_TARGETS = (
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


def _downgrade_node(node: Dict[str, Any]) -> None:
    _rename_keys(node, {new: old for old, new in _CONTRACT_KEYS.items()})
    if "contract" not in node and "adversarial" not in node:
        return
    if isinstance(node.get("criteria_evaluations"), list):
        node["behavior_verdicts"] = [
            {
                "behavior": c.get("criterion", ""),
                "kind": c.get("kind", "required"),
                "complied": bool(c.get("met", False)),
                "evidence": c.get("evidence", ""),
                "relevant_turns": c.get("relevant_turns") or [],
            }
            for c in node.pop("criteria_evaluations")
            if isinstance(c, dict)
        ]
    _rename_keys(node, {new: old for old, new in _COUNT_KEYS.items()})
    node.pop("all_criteria_met", None)


def _walk(value: Any, visit: Callable[[Dict[str, Any]], None]) -> Any:
    if isinstance(value, dict):
        for child in value.values():
            _walk(child, visit)
        visit(value)
    elif isinstance(value, list):
        for child in value:
            _walk(child, visit)
    return value


def _rewrite(visit: Callable[[Dict[str, Any]], None], marker: str) -> None:
    conn = op.get_bind()
    org_ids = [row[0] for row in conn.execute(_ORGANIZATIONS)]

    rewritten = 0
    for org_id in org_ids:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)

        for table, columns in _TARGETS:
            match = " OR ".join(f"CAST({c} AS text) LIKE :marker" for c in columns)
            rows = conn.execute(
                sa.text(
                    f"SELECT id, {', '.join(columns)} FROM {table} "
                    f"WHERE organization_id = CAST(:org_id AS uuid) AND ({match})"
                ),
                {**params, "marker": f"%{marker}%"},
            ).fetchall()

            for row in rows:
                before = [json.dumps(row[i + 1]) for i in range(len(columns))]
                values = {c: _walk(row[i + 1], visit) for i, c in enumerate(columns)}
                if [json.dumps(v) for v in values.values()] == before:
                    continue
                assignments = ", ".join(f"{c} = CAST(:{c} AS jsonb)" for c in columns)
                conn.execute(
                    sa.text(f"UPDATE {table} SET {assignments} WHERE id = :id"),
                    {
                        "id": row[0],
                        **{c: json.dumps(v) if v is not None else None for c, v in values.items()},
                    },
                )
                rewritten += 1

    print(f"[8c1f4e2a7b9d] Rewrote {rewritten} row(s) across {len(org_ids)} organization(s).")


def upgrade() -> None:
    _rewrite(_upgrade_node, "behavior")


def downgrade() -> None:
    _rewrite(_downgrade_node, "criteri")
