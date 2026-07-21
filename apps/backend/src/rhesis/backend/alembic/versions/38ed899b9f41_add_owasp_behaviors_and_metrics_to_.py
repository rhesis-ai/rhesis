"""add_owasp_behaviors_and_metrics_to_existing_orgs

This migration syncs the two new OWASP behaviors ("OWASP LLM Top 10" and
"OWASP Agentic Top 10") and their twenty associated metrics
("OWASP LLM01: Prompt Injection" ... "OWASP LLM10: Unbounded Consumption" and
"OWASP ASI01: Agent Goal Hijack" ... "OWASP ASI10: Rogue Agents") from
initial_data.json to all existing organizations. It's fully idempotent and can
be run multiple times - only missing behaviors/metrics will be added.

Behaviors must be created before metrics are synced, because
sync_metrics_to_organizations() looks up the target behavior by name per
organization and silently skips the behavior association if it doesn't exist
yet in that organization - it does not create behaviors itself.

For new organizations, both behaviors and metrics are created during
onboarding via load_initial_data(), which already processes the full
initial_data.json behavior/metric lists - no changes were needed there.

Future migrations can reuse sync_behaviors_to_organizations /
remove_behaviors_from_organizations and sync_metrics_to_organizations /
remove_metrics_from_organizations from:
    rhesis.backend.alembic.utils.metric_sync

Revision ID: 38ed899b9f41
Revises: b1c2d3e4f5a6
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

# Import reusable behavior/metric sync utilities
from rhesis.backend.alembic.utils.metric_sync import (
    load_behaviors_from_initial_data,
    load_metrics_from_initial_data,
    remove_behaviors_from_organizations,
    remove_metrics_from_organizations,
    sync_behaviors_to_organizations,
    sync_metrics_to_organizations,
)

# revision identifiers, used by Alembic.
revision: str = "38ed899b9f41"
down_revision: Union[str, None] = "e6f7a8b9c0d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The new OWASP behaviors/metrics are identified by their "OWASP" name prefix
# so the names are sourced from initial_data.json (the single source of
# truth) rather than duplicated as literal strings here.
_OWASP_PREFIX = "OWASP"


def _owasp_behavior_names() -> list[str]:
    return [
        b["name"] for b in load_behaviors_from_initial_data() if b["name"].startswith(_OWASP_PREFIX)
    ]


def _owasp_metric_names() -> list[str]:
    return [
        m["name"] for m in load_metrics_from_initial_data() if m["name"].startswith(_OWASP_PREFIX)
    ]


def upgrade() -> None:
    """
    Sync the OWASP behaviors and metrics from initial_data.json to existing organizations.

    Order matters: behaviors are created first so that the metric sync's
    per-organization behavior lookup succeeds and associations are created.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        behavior_names = _owasp_behavior_names()
        metric_names = _owasp_metric_names()

        # Step 1: get-or-create the two new behaviors in every existing organization
        sync_behaviors_to_organizations(
            session=session,
            behavior_names=behavior_names,
            verbose=True,
            commit=False,
        )

        # Step 2: sync the twenty new metrics (and their behavior associations)
        sync_metrics_to_organizations(
            session=session,
            metric_names=metric_names,
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
    """
    Remove the OWASP metrics and behaviors from all organizations.

    Metrics are removed first since deleting a metric also cleans up its
    behavior_metric association rows; behaviors are removed afterward so no
    dangling associations are left pointing at them.

    WARNING: This is a destructive operation. It removes these metrics and
    behaviors from ALL organizations, including any user edits made to them
    after creation. Use with caution on production systems.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        behavior_names = _owasp_behavior_names()
        metric_names = _owasp_metric_names()

        remove_metrics_from_organizations(
            session=session,
            metric_names=metric_names,
            verbose=True,
            commit=False,
        )

        remove_behaviors_from_organizations(
            session=session,
            behavior_names=behavior_names,
            verbose=True,
            commit=False,
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
