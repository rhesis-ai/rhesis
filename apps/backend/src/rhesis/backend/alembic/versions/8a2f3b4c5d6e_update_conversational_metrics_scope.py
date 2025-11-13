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
from sqlalchemy.orm import Session

from rhesis.backend.app import models

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

    This operation is idempotent and will update metrics that match the names
    in METRICS_TO_UPDATE to have metric_scope = ["Multi-Turn"].
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\n🔄 Updating metrics to Multi-Turn scope...")
        print(f"   Metrics to update: {len(METRICS_TO_UPDATE)}\n")

        updated_count = 0
        not_found_count = 0

        for metric_name in METRICS_TO_UPDATE:
            # Find all metrics with this name across all organizations
            metrics = session.query(models.Metric).filter(models.Metric.name == metric_name).all()

            if metrics:
                for metric in metrics:
                    metric.metric_scope = ["Multi-Turn"]
                    updated_count += 1

                print(f"  ✓ Updated '{metric_name}' ({len(metrics)} org(s))")
            else:
                not_found_count += 1
                print(f"  ⚠ Metric '{metric_name}' not found in any organization")

        # Commit all changes
        session.commit()

        print("\n✅ Metric scope update complete!")
        print(f"   Updated: {updated_count} metric(s) across all organizations")
        if not_found_count > 0:
            print(f"   Not found: {not_found_count} metric name(s)")
        print()

    except Exception as e:
        print(f"\n❌ Migration failed: {e}\n")
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    """
    Revert the metrics back to Single-Turn scope.

    WARNING: This will set all specified metrics back to ["Single-Turn"] scope.
    Only use this if you need to roll back the migration.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\n🔄 Reverting metrics to Single-Turn scope...")
        print(f"   Metrics to revert: {len(METRICS_TO_UPDATE)}\n")

        reverted_count = 0

        for metric_name in METRICS_TO_UPDATE:
            # Find all metrics with this name across all organizations
            metrics = session.query(models.Metric).filter(models.Metric.name == metric_name).all()

            if metrics:
                for metric in metrics:
                    metric.metric_scope = ["Single-Turn"]
                    reverted_count += 1

                print(f"  ✓ Reverted '{metric_name}' ({len(metrics)} org(s))")

        # Commit all changes
        session.commit()

        print("\n✅ Metric scope revert complete!")
        print(f"   Reverted: {reverted_count} metric(s)")
        print()

    except Exception as e:
        print(f"\n❌ Downgrade failed: {e}\n")
        session.rollback()
        raise
    finally:
        session.close()
