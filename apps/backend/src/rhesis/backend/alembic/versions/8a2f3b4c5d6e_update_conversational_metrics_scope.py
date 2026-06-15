"""update_conversational_metrics_scope_to_multiturn

This migration updates specific conversational metrics to have Multi-Turn scope
for all organizations. These metrics were either missing the scope or had incorrect
scope values.

Metrics being updated:
1. Turn Relevancy
2. Role Adherence
3. Knowledge Retention
4. Conversation Completeness
5. Goal Accuracy
6. Tool Use
7. Conversation Completeness (Task Success)
8. Contextual Coherence
9. Conversational Relevance
10. Knowledge Retention (Memory Consistency)
11. Role Adherence (Instruction Compliance)

All these metrics will be set to ["Multi-Turn"] scope.

Revision ID: 8a2f3b4c5d6e
Revises: 713d0108214d
Create Date: 2025-11-13
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "8a2f3b4c5d6e"
down_revision: Union[str, None] = "713d0108214d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Metrics to update with Multi-Turn scope
METRICS_TO_UPDATE = [
    "Turn Relevancy",
    "Role Adherence",
    "Knowledge Retention",
    "Conversation Completeness",
    "Goal Accuracy",
    "Tool Use",
    "Conversation Completeness (Task Success)",
    "Contextual Coherence",
    "Conversational Relevance",
    "Knowledge Retention (Memory Consistency)",
    "Role Adherence (Instruction Compliance)",
]


def upgrade() -> None:
    """
    Update specified metrics to have Multi-Turn scope across all organizations.

    Uses raw SQL so this migration remains correct even when the ORM model
    has columns (e.g. project_id) that do not yet exist in the database at
    the point in the migration chain where this revision runs.
    """
    for metric_name in METRICS_TO_UPDATE:
        op.execute(
            text(
                "UPDATE metric SET metric_scope = CAST(:scope AS JSON) "
                "WHERE name = :name AND deleted_at IS NULL"
            ).bindparams(scope='["Multi-Turn"]', name=metric_name)
        )
    print(f"Updated {len(METRICS_TO_UPDATE)} metric name(s) to Multi-Turn scope")


def downgrade() -> None:
    """
    Revert the metrics back to Single-Turn scope.

    WARNING: This will set all specified metrics back to ["Single-Turn"] scope.
    Only use this if you need to roll back the migration.
    """
    for metric_name in METRICS_TO_UPDATE:
        op.execute(
            text(
                "UPDATE metric SET metric_scope = CAST(:scope AS JSON) "
                "WHERE name = :name AND deleted_at IS NULL"
            ).bindparams(scope='["Single-Turn"]', name=metric_name)
        )
    print(f"Reverted {len(METRICS_TO_UPDATE)} metric name(s) to Single-Turn scope")
