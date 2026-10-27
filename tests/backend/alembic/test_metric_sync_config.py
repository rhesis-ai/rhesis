"""Synced metrics keep their settings, and the sync works before metric.config exists."""

import uuid
from unittest.mock import patch

import pytest

from rhesis.backend.alembic.utils import metric_sync
from rhesis.backend.app import models


def definition(name):
    return {
        "name": name,
        "description": "Compares tool calls.",
        "evaluation_prompt": "Compare.",
        "score_type": "numeric",
        "min_score": 0,
        "max_score": 1,
        "threshold": 1,
        "class_name": "ToolCallTrajectory",
        "metric_type": "custom-code",
        "backend_type": "rhesis",
        "status": "New",
        "requirements": [],
        "metric_scope": ["Single-Turn"],
        "config": {"match": "exact"},
    }


def synced(db, name, org_id):
    return (
        db.query(models.Metric)
        .filter(models.Metric.name == name, models.Metric.organization_id == uuid.UUID(org_id))
        .one()
    )


@pytest.mark.integration
def test_a_synced_metric_keeps_its_settings(test_db, test_org_id):
    name = f"trajectory-{uuid.uuid4()}"

    metric_sync.sync_metrics_to_organizations(
        test_db, metric_definitions=[definition(name)], verbose=False
    )

    assert synced(test_db, name, test_org_id).config == {"match": "exact"}


@pytest.mark.integration
def test_settings_are_left_out_before_the_column_exists(test_db, test_org_id):
    """Older revisions sync the live initial_data.json, which has settings already."""
    name = f"trajectory-{uuid.uuid4()}"
    with patch.object(metric_sync, "sa_inspect") as inspect:
        inspect.return_value.get_columns.return_value = [{"name": "name"}]
        metric_sync.sync_metrics_to_organizations(
            test_db, metric_definitions=[definition(name)], verbose=False
        )

    assert synced(test_db, name, test_org_id).config is None
