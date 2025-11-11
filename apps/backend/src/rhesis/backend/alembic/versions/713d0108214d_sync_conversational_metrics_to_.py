"""sync_conversational_metrics_to_organizations

This migration syncs the 6 new DeepEval conversational metrics to all existing
organizations. It uses the reusable metric_sync utility which is fully idempotent
and only creates missing metrics.

New conversational metrics being added:
1. Turn Relevancy - Evaluates response relevance in multi-turn conversations
2. Role Adherence - Evaluates role maintenance throughout conversation
3. Knowledge Retention - Evaluates information recall from earlier turns
4. Conversation Completeness - Evaluates satisfactory conversation conclusion
5. Goal Accuracy - Evaluates goal achievement in conversations
6. Tool Use - Evaluates tool selection and usage in conversations

All metrics are scoped to Multi-Turn tests and use DeepEval 3.7.0.

For new organizations, these metrics are created during onboarding via load_initial_data.

Revision ID: 713d0108214d
Revises: 5806494f1668
Create Date: 2025-11-11
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

# Import reusable metric sync utility
from rhesis.backend.alembic.utils.metric_sync import (
    remove_metrics_from_organizations,
    sync_metrics_to_organizations,
)

# revision identifiers, used by Alembic.
revision: str = "713d0108214d"
down_revision: Union[str, None] = "5806494f1668"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Sync all metrics from initial_data.json to existing organizations.

    Uses the reusable sync_metrics_to_organizations utility which:
    - Is fully idempotent (safe to run multiple times)
    - Only creates missing metrics
    - Handles all the complexity of metric creation

    This will add the 6 new conversational metrics to all existing organizations.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Sync metrics using the reusable utility
        sync_metrics_to_organizations(
            session=session,
            verbose=True,
            commit=False,  # We'll commit here for better error handling
        )

        # Commit all changes
        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    """
    Remove the 6 conversational metrics from all organizations.

    WARNING: This will remove these specific metrics from all organizations:
    - Turn Relevancy
    - Role Adherence
    - Knowledge Retention
    - Conversation Completeness
    - Goal Accuracy
    - Tool Use

    Note: This is a destructive operation and should only be used in development or
    if you absolutely need to roll back the migration.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Define the conversational metric names to remove
        conversational_metric_names = [
            "Turn Relevancy",
            "Role Adherence",
            "Knowledge Retention",
            "Conversation Completeness",
            "Goal Accuracy",
            "Tool Use",
        ]

        # Use the reusable utility to remove metrics
        remove_metrics_from_organizations(
            session=session,
            metric_names=conversational_metric_names,
            verbose=True,
            commit=False,  # We'll commit here for better error handling
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
