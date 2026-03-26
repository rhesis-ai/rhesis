import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.adaptive_testing.settings import (
    get_adaptive_settings,
    update_adaptive_settings,
)
from rhesis.backend.app.services.adaptive_testing.tests import create_adaptive_test_set


def _create_adaptive_set(db: Session, organization_id: str, user_id: str) -> models.TestSet:
    test_set = create_adaptive_test_set(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        name=f"Adaptive Settings {uuid.uuid4().hex[:8]}",
    )
    db.flush()
    db.refresh(test_set)
    return test_set


def _create_project(db: Session, organization_id: str, user_id: str) -> models.Project:
    project = models.Project(
        name=f"Adaptive Settings Project {uuid.uuid4().hex[:8]}",
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(project)
    db.flush()
    return project


def _create_endpoint(
    db: Session, organization_id: str, user_id: str, project_id: uuid.UUID
) -> models.Endpoint:
    endpoint = models.Endpoint(
        name=f"Adaptive Endpoint {uuid.uuid4().hex[:8]}",
        connection_type="REST",
        organization_id=organization_id,
        user_id=user_id,
        project_id=project_id,
    )
    db.add(endpoint)
    db.flush()
    return endpoint


def _create_metric(db: Session, organization_id: str, user_id: str, name: str) -> models.Metric:
    metric = models.Metric(
        name=name,
        class_name="StubMetric",
        evaluation_prompt="stub prompt",
        score_type="binary",
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(metric)
    db.flush()
    return metric


@pytest.mark.integration
@pytest.mark.service
class TestAdaptiveSettings:
    def test_get_settings_empty(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)

        result = get_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result.default_endpoint is None
        assert result.metrics == []

    def test_update_default_endpoint(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)
        project = _create_project(test_db, test_org_id, authenticated_user_id)
        endpoint = _create_endpoint(test_db, test_org_id, authenticated_user_id, project.id)

        result = update_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            default_endpoint_id=endpoint.id,
        )

        assert result.default_endpoint is not None
        assert str(result.default_endpoint.id) == str(endpoint.id)
        assert result.default_endpoint.name == endpoint.name

    def test_update_metrics(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)
        metric = _create_metric(test_db, test_org_id, authenticated_user_id, "adaptive-metric-a")

        result = update_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            metric_ids=[metric.id],
        )

        assert len(result.metrics) == 1
        assert str(result.metrics[0].id) == str(metric.id)
        assert result.metrics[0].name == metric.name

    def test_update_both(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)
        project = _create_project(test_db, test_org_id, authenticated_user_id)
        endpoint = _create_endpoint(test_db, test_org_id, authenticated_user_id, project.id)
        metric = _create_metric(test_db, test_org_id, authenticated_user_id, "adaptive-metric-b")

        result = update_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            default_endpoint_id=endpoint.id,
            metric_ids=[metric.id],
        )

        assert result.default_endpoint is not None
        assert str(result.default_endpoint.id) == str(endpoint.id)
        assert len(result.metrics) == 1
        assert str(result.metrics[0].id) == str(metric.id)

    def test_update_endpoint_not_found(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)

        with pytest.raises(ValueError, match="Endpoint not found"):
            update_adaptive_settings(
                db=test_db,
                test_set=test_set,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                default_endpoint_id=uuid.uuid4(),
            )

    def test_update_metric_not_found(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)

        with pytest.raises(ValueError, match="Metric with id"):
            update_adaptive_settings(
                db=test_db,
                test_set=test_set,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                metric_ids=[uuid.uuid4()],
            )

    def test_update_replaces_metrics(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)
        metric_1 = _create_metric(test_db, test_org_id, authenticated_user_id, "adaptive-metric-c1")
        metric_2 = _create_metric(test_db, test_org_id, authenticated_user_id, "adaptive-metric-c2")

        update_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            metric_ids=[metric_1.id],
        )
        result = update_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            metric_ids=[metric_2.id],
        )

        assert len(result.metrics) == 1
        assert str(result.metrics[0].id) == str(metric_2.id)

    def test_get_settings_returns_updated(self, test_db: Session, test_org_id, authenticated_user_id):
        test_set = _create_adaptive_set(test_db, test_org_id, authenticated_user_id)
        project = _create_project(test_db, test_org_id, authenticated_user_id)
        endpoint = _create_endpoint(test_db, test_org_id, authenticated_user_id, project.id)
        metric = _create_metric(test_db, test_org_id, authenticated_user_id, "adaptive-metric-d")

        update_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            default_endpoint_id=endpoint.id,
            metric_ids=[metric.id],
        )
        result = get_adaptive_settings(
            db=test_db,
            test_set=test_set,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result.default_endpoint is not None
        assert str(result.default_endpoint.id) == str(endpoint.id)
        assert len(result.metrics) == 1
        assert str(result.metrics[0].id) == str(metric.id)
