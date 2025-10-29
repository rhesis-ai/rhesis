"""add_sdk_metrics_to_existing_orgs

This migration intelligently syncs metrics from initial_data.json to all existing organizations.
It's fully idempotent and can be run multiple times - only missing metrics will be added.

The migration uses the reusable metric_sync utility which:
1. Reads metrics from initial_data.json (single source of truth)
2. For each organization, checks which metrics are missing
3. Creates only the missing metrics
4. Can handle continuous additions of new metrics to initial_data.json

For new organizations, metrics are created during onboarding via load_initial_data.

Future migrations can reuse the sync_metrics_to_organizations function from:
    rhesis.backend.alembic.utils.metric_sync

Revision ID: 7e5b79f596ce
Revises: a6a7196f4949
Create Date: 2025-10-30 00:35:46
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

# Import reusable metric sync utility
from rhesis.backend.alembic.utils.metric_sync import (
    load_metrics_from_initial_data,
    remove_metrics_from_organizations,
    sync_metrics_to_organizations,
)

# revision identifiers, used by Alembic.
revision: str = "7e5b79f596ce"
down_revision: Union[str, None] = "a6a7196f4949"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Sync all metrics from initial_data.json to existing organizations.

    Uses the reusable sync_metrics_to_organizations utility which:
    - Is fully idempotent (safe to run multiple times)
    - Only creates missing metrics
    - Handles all the complexity of metric creation
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
    Remove all metrics defined in initial_data.json from all organizations.

    WARNING: This uses initial_data.json as reference and will remove ALL metrics
    defined there from all organizations. Use with extreme caution on production systems.

    Note: This is a destructive operation and should only be used in development or
    if you absolutely need to roll back the migration.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Load metrics from initial_data.json to get the names
        all_metrics = load_metrics_from_initial_data()
        metric_names = [m["name"] for m in all_metrics]

        # Use the reusable utility to remove metrics
        remove_metrics_from_organizations(
            session=session,
            metric_names=metric_names,
            verbose=True,
            commit=False,  # We'll commit here for better error handling
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
