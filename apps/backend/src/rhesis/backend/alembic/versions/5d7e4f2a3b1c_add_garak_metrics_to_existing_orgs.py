"""add_garak_metrics_to_existing_orgs

This migration syncs newly added Garak detector metrics from initial_data.json to all
existing organizations. It's fully idempotent and can be run multiple times - only
missing metrics will be added.

The Garak metrics use the new 'garak' backend type and 'GarakDetectorMetric' class name
to integrate with Garak's vulnerability detection framework.

Added metrics:
- Garak: Mitigation Bypass
- Garak: Continuation Detection
- Garak: Misleading Claims
- Garak: LMRC Risk
- Garak: Toxicity Detection
- Garak: Malware Generation
- Garak: Package Hallucination
- Garak: Known Bad Signatures
- Garak: XSS Detection
- Garak: Snowball Detection
- Garak: Do Not Answer Detection
- Garak: Leak Replay Detection

Revision ID: 5d7e4f2a3b1c
Revises: 3f8a2b9c1d4e
Create Date: 2026-01-23
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
revision: str = "5d7e4f2a3b1c"
down_revision: Union[str, None] = "3f8a2b9c1d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# List of Garak metric names added in this migration
GARAK_METRIC_NAMES = [
    "Garak: Mitigation Bypass",
    "Garak: Continuation Detection",
    "Garak: Misleading Claims",
    "Garak: LMRC Risk",
    "Garak: Toxicity Detection",
    "Garak: Malware Generation",
    "Garak: Package Hallucination",
    "Garak: Known Bad Signatures",
    "Garak: XSS Detection",
    "Garak: Snowball Detection",
    "Garak: Do Not Answer Detection",
    "Garak: Leak Replay Detection",
]


def upgrade() -> None:
    """
    Sync Garak metrics from initial_data.json to existing organizations.

    Uses the reusable sync_metrics_to_organizations utility which:
    - Is fully idempotent (safe to run multiple times)
    - Only creates missing metrics
    - Handles all the complexity of metric creation including the new 'garak' backend type
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\n🔧 Adding Garak detector metrics to existing organizations...")

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
    Remove Garak metrics from all organizations.

    Only removes the specific Garak metrics added in this migration,
    not all metrics from initial_data.json.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\n🗑 Removing Garak metrics from all organizations...")

        # Use the reusable utility to remove only Garak metrics
        remove_metrics_from_organizations(
            session=session,
            metric_names=GARAK_METRIC_NAMES,
            verbose=True,
            commit=False,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
