"""add_garak_v0_13_3_detector_metrics

This migration syncs the five new Garak detector metrics introduced in garak v0.13.3
to all existing organizations. It is fully idempotent and can be run multiple times —
only missing metrics will be added.

New metrics added in this migration:
- ANSI Escape Detection  (garak.detectors.ansiescape.ANSI)
- API Key Detection      (garak.detectors.apikey.APIKey)
- Repetitive Divergence Detection (garak.detectors.divergence.Repetitive)
- Exploit Code Detection (garak.detectors.exploitation.ExploitDetector)
- Malicious File Format Detection (garak.detectors.fileformats.FileFormatDetector)

Revision ID: c2d3e4f5a6b7
Revises: b3f7a9c2d1e4
Create Date: 2026-03-10
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from rhesis.backend.alembic.utils.metric_sync import (
    remove_metrics_from_organizations,
    sync_metrics_to_organizations,
)
from rhesis.sdk.metrics.providers.garak.registry import to_initial_data_metrics

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b3f7a9c2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GARAK_NEW_METRIC_NAMES = [
    "ANSI Escape Detection",
    "API Key Detection",
    "Repetitive Divergence Detection",
    "Exploit Code Detection",
    "Malicious File Format Detection",
]


def upgrade() -> None:
    """
    Sync new Garak v0.13.3 detector metrics to existing organizations.

    These metrics are defined in the SDK registry (detectors.yaml) rather than
    initial_data.json, so we source them directly from the SDK to avoid a no-op.
    Uses the reusable sync_metrics_to_organizations utility which:
    - Is fully idempotent (safe to run multiple times)
    - Only creates missing metrics
    - Handles all the complexity of metric creation including the 'garak' backend type
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\nAdding garak v0.13.3 detector metrics to existing organizations...")

        # Source from SDK registry — these metrics were removed from initial_data.json
        # in favour of runtime injection, so we can't rely on load_metrics_from_initial_data()
        sdk_metrics = to_initial_data_metrics()
        new_metric_defs = [m for m in sdk_metrics if m["name"] in GARAK_NEW_METRIC_NAMES]

        sync_metrics_to_organizations(
            session=session,
            metric_definitions=new_metric_defs,
            verbose=True,
            commit=False,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    """Remove the garak v0.13.3 detector metrics from all organizations."""
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\nRemoving garak v0.13.3 detector metrics from all organizations...")

        remove_metrics_from_organizations(
            session=session,
            metric_names=GARAK_NEW_METRIC_NAMES,
            verbose=True,
            commit=False,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
