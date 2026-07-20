"""Detach garak metrics from behaviors.

Garak detectors were auto-attached to behaviors (Robustness, Compliance,
Reliability) during org onboarding.  This caused hand-authored test sets
to inherit the full Garak detector battery via the behavior-level metric
fallback, producing inconclusive or errored results for detectors that
require probe-specific context (triggers, repeat_word) and noise from
detectors that are only meaningful with their paired Garak probe.

This migration removes all behavior_metric rows that link a Garak metric
to any behavior.  Going forward, detectors.yaml no longer declares a
behavior for any detector, so new orgs won't create these associations.
Garak detectors remain in the metric catalog and continue to be attached
at the test-set level during Garak probe import.

Revision ID: d4e7f2a9c1b8
Revises: e6f7a8b9c0d4
Create Date: 2026-07-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4e7f2a9c1b8"
down_revision: Union[str, None] = "e6f7a8b9c0d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM behavior_metric
        WHERE metric_id IN (
            SELECT id FROM metric
            WHERE evaluation_prompt LIKE 'garak.detectors.%%'
        )
    """)


def downgrade() -> None:
    pass
