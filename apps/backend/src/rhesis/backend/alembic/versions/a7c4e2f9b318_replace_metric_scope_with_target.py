"""Replace metric_scope with the metric's target

A metric's target (``config["target"]``) now says what it judges, and so which tests it
runs on, in place of ``metric_scope``. Every metric without a target gets one from its
scope and class:

- a conversational class, or a metric scoped to Multi-Turn alone, judges the conversation;
- Tool Call Trajectory, and a code metric reading only the trace, judge the whole run;
- every other metric judges each turn.

A metric scoped to Multi-Turn alone whose class can't judge a conversation judges each turn.
A conversation has no reference answer, so a metric judging one no longer requires it; it was
scored against an empty one before. The MetricScope type lookups go too. The downgrade restores scopes from the targets, not the
scopes this revision dropped, and not the type lookups.

Revision ID: a7c4e2f9b318
Revises: f2c8d4e6a913
Create Date: 2026-10-27
"""

import json
from typing import Any, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from rhesis.backend.alembic.utils.tenant_scope import iter_tenant_scopes

revision: str = "a7c4e2f9b318"
down_revision: Union[str, None] = "f2c8d4e6a913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Snapshots of the SDK's classes at this revision, so later changes there don't change it.
CONVERSATIONAL = frozenset(
    {
        "ConversationalJudge",
        "GoalAchievementJudge",
        "DeepEvalConversationCompleteness",
        "DeepEvalGoalAccuracy",
        "DeepEvalKnowledgeRetention",
        "DeepEvalRoleAdherence",
        "DeepEvalToolUse",
        "DeepEvalTurnRelevancy",
    }
)
WHOLE_RUN = frozenset({"ToolCallTrajectory"})
# Classes that can't judge a conversation: they read only a turn's input and output, or
# always compare with a reference answer.
TURN_ONLY = frozenset(
    {
        "DeepEvalAnswerRelevancy",
        "DeepEvalBias",
        "DeepEvalContextualPrecision",
        "DeepEvalContextualRecall",
        "DeepEvalMisuse",
        "DeepEvalNonAdvice",
        "DeepEvalPIILeakage",
        "DeepEvalRoleViolation",
        "DeepEvalToxicity",
        "DeepTeamIllegal",
        "DeepTeamSafety",
        "GarakDetectorMetric",
    }
)

_SELECT = sa.text("""
    SELECT id, class_name, metric_scope, config, evaluation_examples, ground_truth_required
    FROM metric
    WHERE organization_id = CAST(:org_id AS uuid)
      AND project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
""")
_UPDATE = sa.text("""
    UPDATE metric
    SET config = CAST(:config AS jsonb),
        ground_truth_required = ground_truth_required AND NOT CAST(:conversation AS boolean)
    WHERE id = CAST(:id AS uuid)
""")
_DROP_SCOPE_TYPES = sa.text("""
    DELETE FROM type_lookup
    WHERE organization_id = CAST(:org_id AS uuid)
      AND project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
      AND type_name = 'MetricScope'
""")
_RESTORE = sa.text("""
    UPDATE metric
    SET metric_scope = CASE
        WHEN config -> 'target' ->> 'on' = 'conversation' THEN '["Multi-Turn"]'::jsonb
        WHEN config -> 'target' ->> 'on' = 'run' THEN '["Single-Turn", "Multi-Turn"]'::jsonb
        ELSE '["Single-Turn"]'::jsonb
    END
    WHERE organization_id = CAST(:org_id AS uuid)
      AND project_id IS NOT DISTINCT FROM CAST(:project_id AS uuid)
""")


def _accepted_params(evaluation_examples: Optional[str]) -> Optional[list]:
    """The parameters an SDK code metric's function declares, recorded by metric sync."""
    try:
        data = json.loads(evaluation_examples or "")
    except (json.JSONDecodeError, TypeError):
        return None
    connection = data.get("sdk_connection") if isinstance(data, dict) else None
    accepted = connection.get("accepted_params") if isinstance(connection, dict) else None
    return accepted if isinstance(accepted, list) else None


def target_for(class_name: Optional[str], scope: Any, evaluation_examples: Optional[str]) -> str:
    """The target of a metric with this class and scope."""
    accepted = _accepted_params(evaluation_examples)
    reads_turns = accepted is None or bool({"input", "output"} & set(accepted))
    reads_trace = accepted is None or "trace" in accepted
    if class_name in CONVERSATIONAL:
        return "conversation"
    if class_name in WHOLE_RUN or not reads_turns:
        return "run"
    if scope == ["Multi-Turn"] and class_name not in TURN_ONLY and reads_trace:
        return "conversation"
    return "turn"


def upgrade() -> None:
    conn = op.get_bind()
    for org_id, project_id in iter_tenant_scopes(conn):
        conn.execute(_DROP_SCOPE_TYPES, {"org_id": org_id, "project_id": project_id})
        rows = conn.execute(_SELECT, {"org_id": org_id, "project_id": project_id}).all()
        for metric_id, class_name, scope, config, examples, reference in rows:
            config = dict(config or {})
            if not config.get("target"):
                config["target"] = {"on": target_for(class_name, scope, examples)}
            elif not (reference and config["target"].get("on") == "conversation"):
                continue
            conversation = config["target"].get("on") == "conversation"
            conn.execute(
                _UPDATE,
                {"id": str(metric_id), "config": json.dumps(config), "conversation": conversation},
            )

    op.drop_constraint("ck_metric_metric_scope_non_empty", "metric", type_="check")
    op.drop_column("metric", "metric_scope")


def downgrade() -> None:
    op.add_column("metric", sa.Column("metric_scope", postgresql.JSONB(), nullable=True))
    conn = op.get_bind()
    for org_id, project_id in iter_tenant_scopes(conn):
        conn.execute(_RESTORE, {"org_id": org_id, "project_id": project_id})
    # Rows in no organization, which the walk above doesn't reach.
    conn.execute(
        sa.text(
            """UPDATE metric SET metric_scope = '["Single-Turn"]'::jsonb WHERE metric_scope IS NULL"""
        )
    )
    op.alter_column("metric", "metric_scope", nullable=False)
    op.create_check_constraint(
        "ck_metric_metric_scope_non_empty",
        "metric",
        "jsonb_typeof(metric_scope) = 'array' AND jsonb_array_length(metric_scope) > 0",
    )
