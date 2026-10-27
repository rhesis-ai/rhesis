"""Add metric.config and the Tool Call Trajectory metric

``metric.config`` holds settings of a metric's class, passed to it when it is built: the
trajectory metric's match and argument modes, and later a metric's target. The Tool Call
Trajectory metric compares the tools an endpoint called with a test's expected tool calls,
and is added to every existing organization.

Revision ID: f2c8d4e6a913
Revises: c3e5cfa15f16
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from rhesis.backend.alembic.utils.metric_sync import (
    remove_metrics_from_organizations,
    sync_metrics_to_organizations,
)

revision: str = "f2c8d4e6a913"
down_revision: Union[str, None] = "c3e5cfa15f16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

METRIC_NAME = "Tool Call Trajectory"

# Snapshot of the initial_data.json entry, so later edits there don't change this migration.
METRIC_DEFINITION = {
    "name": METRIC_NAME,
    "description": (
        "Checks that the endpoint called the tools the test expects, in order. Compares the "
        "tool calls in the trace with the test's expected tool calls, without a model. Tests "
        "without expected tool calls are not judged by it."
    ),
    "evaluation_prompt": "Compare the trace's tool calls with the test's expected tool calls.",
    "score_type": "numeric",
    "min_score": 0.0,
    "max_score": 1.0,
    "threshold": 1.0,
    "threshold_operator": ">=",
    "explanation": (
        "Scores 1 and passes when the tool calls match; the reason names the first difference."
    ),
    "ground_truth_required": False,
    "context_required": False,
    "class_name": "ToolCallTrajectory",
    "metric_type": "custom-code",
    "backend_type": "rhesis",
    "status": "New",
    "requirements": [],
    "metric_scope": ["Single-Turn", "Multi-Turn"],
    "config": {"match": "in_order", "arguments": "partial"},
}


def upgrade() -> None:
    op.add_column("metric", sa.Column("config", postgresql.JSONB(), nullable=True))

    session = Session(bind=op.get_bind())
    try:
        sync_metrics_to_organizations(
            session=session, metric_definitions=[METRIC_DEFINITION], commit=False
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        remove_metrics_from_organizations(session=session, metric_names=[METRIC_NAME])
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    op.drop_column("metric", "config")
