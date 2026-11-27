"""Add rules: the rule metric type, its presets, and Tool Call Trajectory as a rule

A rule checks a field of the trace, or an expectation, against a fixed value, with no model.
Every organization gets the ``rule`` MetricType lookup and four preset rules (Response Time,
No Failed Tool Calls, Token Budget, Exact Match), and its Tool Call Trajectory metrics move
from ``custom-code`` to ``rule``.

Revision ID: b6f1d3a8c9e2
Revises: a7c4e2f9b318
Create Date: 2026-11-27
"""

from typing import Any, Dict, List, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from rhesis.backend.alembic.utils.metric_sync import (
    remove_metrics_from_organizations,
    sync_metrics_to_organizations,
)
from rhesis.backend.alembic.utils.tenant_scope import iter_tenant_scopes

revision: str = "b6f1d3a8c9e2"
down_revision: Union[str, None] = "a7c4e2f9b318"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RULE = "rule"
CUSTOM_CODE = "custom-code"
RULE_DESCRIPTION = (
    "Rule with no model: a field of the trace or an expectation, checked against a fixed value"
)
CUSTOM_CODE_DESCRIPTION = "Metric calculated using custom Python logic"


def _rule(name: str, description: str, prompt: str, explanation: str, **item: Any) -> Dict:
    return {
        "name": name,
        "description": description,
        "evaluation_prompt": prompt,
        "score_type": "numeric",
        "min_score": 0.0,
        "max_score": 1.0,
        "threshold": 1.0,
        "threshold_operator": ">=",
        "explanation": explanation,
        "ground_truth_required": False,
        "context_required": False,
        "metric_type": RULE,
        "backend_type": "rhesis",
        "status": "New",
        "requirements": [],
        **item,
    }


# Snapshot of the initial_data.json entries, so later edits there don't change this migration.
PRESETS: List[Dict[str, Any]] = [
    _rule(
        "Response Time",
        "Checks that each turn answered within 5 seconds. Reads the turn's timing from the "
        "trace, without a model. A turn with no timing, such as one built from a stored "
        "response, is not applicable.",
        "duration_ms <= 5000",
        "Scores 1 and passes when the turn took 5,000 ms or less; the reason gives the time "
        "it took.",
        class_name="FieldRule",
        config={"field": "duration_ms", "op": "<=", "value": 5000, "target": {"on": "turn"}},
    ),
    _rule(
        "No Failed Tool Calls",
        "Checks that no tool call ended in an error. Reads each tool call's status from the "
        "trace, without a model. Not applicable when the endpoint reports no tool calls.",
        "error_count == 0",
        "Scores 1 and passes when every tool call succeeded; the reason names the ones that "
        "failed.",
        class_name="FieldRule",
        config={"field": "error_count", "op": "==", "value": 0, "target": {"on": "tool_call"}},
    ),
    _rule(
        "Token Budget",
        "Checks that a whole run used at most 20,000 tokens. Sums the token counts of the "
        "model calls in the trace, without a model. Not applicable when no model call reports "
        "tokens.",
        "tokens.total <= 20000",
        "Scores 1 and passes when the run used 20,000 tokens or fewer; the reason gives the count.",
        class_name="FieldRule",
        config={"field": "tokens.total", "op": "<=", "value": 20000, "target": {"on": "run"}},
    ),
    _rule(
        "Exact Match",
        "Checks that each answer is exactly the test's expected response, without a model. "
        "Not applicable when the test has no expected response.",
        "output == expected response",
        "Scores 1 and passes when the answer equals the expected response.",
        class_name="ResponseRule",
        ground_truth_required=True,
        config={"match": "exact", "target": {"on": "turn"}},
    ),
]
PRESET_NAMES = [preset["name"] for preset in PRESETS]

_FIND_TYPE = sa.text("""
    SELECT id FROM type_lookup
    WHERE type_name = 'MetricType' AND type_value = :value
      AND organization_id = CAST(:org_id AS uuid)
    ORDER BY created_at
    LIMIT 1
""")

_ADD_TYPE = sa.text("""
    INSERT INTO type_lookup (type_name, type_value, description, organization_id)
    VALUES ('MetricType', :value, :description, CAST(:org_id AS uuid))
    RETURNING id
""")

_DESCRIBE_TYPE = sa.text("""
    UPDATE type_lookup SET description = :description
    WHERE id = CAST(:type_id AS uuid) AND description IS NULL
""")

_MOVE_TRAJECTORY = sa.text("""
    UPDATE metric SET metric_type_id = CAST(:type_id AS uuid)
    WHERE class_name = 'ToolCallTrajectory'
      AND organization_id = CAST(:org_id AS uuid)
      AND project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
""")

_MOVE_TYPE = sa.text("""
    UPDATE metric SET metric_type_id = CAST(:to_id AS uuid)
    WHERE metric_type_id = CAST(:from_id AS uuid)
      AND organization_id = CAST(:org_id AS uuid)
      AND project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
""")


def _type_id(conn, org_id: str, value: str, description: str) -> str:
    """The org's MetricType lookup for ``value``, added when it has none."""
    found = conn.execute(_FIND_TYPE, {"value": value, "org_id": org_id}).scalar()
    if found is None:
        return str(
            conn.execute(
                _ADD_TYPE, {"value": value, "description": description, "org_id": org_id}
            ).scalar()
        )
    conn.execute(_DESCRIBE_TYPE, {"description": description, "type_id": str(found)})
    return str(found)


def _sync(callback) -> None:
    session = Session(bind=op.get_bind())
    try:
        callback(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upgrade() -> None:
    # Before any tenant is bound: the sync walks every organization itself.
    _sync(
        lambda session: sync_metrics_to_organizations(
            session=session, metric_definitions=PRESETS, commit=False
        )
    )

    conn = op.get_bind()
    rule_ids: Dict[str, str] = {}
    for org_id, project_id in iter_tenant_scopes(conn):
        if project_id is None:
            rule_ids[org_id] = _type_id(conn, org_id, RULE, RULE_DESCRIPTION)
        conn.execute(
            _MOVE_TRAJECTORY,
            {"type_id": rule_ids[org_id], "org_id": org_id, "project_id": project_id},
        )


def downgrade() -> None:
    _sync(
        lambda session: remove_metrics_from_organizations(
            session=session, metric_names=PRESET_NAMES
        )
    )

    conn = op.get_bind()
    ids: Dict[str, Optional[tuple]] = {}
    for org_id, project_id in iter_tenant_scopes(conn):
        if project_id is None:
            rule_id = conn.execute(_FIND_TYPE, {"value": RULE, "org_id": org_id}).scalar()
            ids[org_id] = (
                (str(rule_id), _type_id(conn, org_id, CUSTOM_CODE, CUSTOM_CODE_DESCRIPTION))
                if rule_id is not None
                else None
            )
        if ids[org_id] is None:
            continue
        rule_id, custom_code_id = ids[org_id]
        conn.execute(
            _MOVE_TYPE,
            {
                "from_id": rule_id,
                "to_id": custom_code_id,
                "org_id": org_id,
                "project_id": project_id,
            },
        )
    # The rule lookups stay: older code ignores them, and deleting them would need each
    # org bound again.
