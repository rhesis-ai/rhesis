"""
📊 Metric CRUD Operations Testing

Comprehensive test suite for metric-related CRUD operations.
Tests focus on metric operations and behavior associations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- get_metric: Retrieve single metric with relationships
- get_metrics: List metrics with pagination
- add_behavior_to_metric: Associate behaviors with metrics
- remove_behavior_from_metric: Remove behavior associations from metrics

Run with: python -m pytest tests/backend/crud/test_metric_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models


@pytest.mark.unit
@pytest.mark.crud
class TestMetricOperations:
    """📊 Test metric operations"""

    def test_get_metric_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful metric retrieval with relationships"""
        from tests.backend.routes.fixtures.data_factories import MetricDataFactory
        import uuid

        # Create metric using data factory
        metric_data = MetricDataFactory.sample_data()
        metric_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )
        db_metric = models.Metric(**metric_data)
        test_db.add(db_metric)
        test_db.flush()

        # Test metric retrieval
        result = crud.get_metric(db=test_db, metric_id=db_metric.id, organization_id=test_org_id)

        # Verify result
        assert result is not None
        assert result.id == db_metric.id
        assert result.name == metric_data["name"]
        assert result.organization_id == uuid.UUID(test_org_id)

    def test_get_metric_not_found(self, test_db: Session, test_org_id: str):
        """Test metric retrieval with non-existent ID"""
        fake_metric_id = uuid.uuid4()

        result = crud.get_metric(db=test_db, metric_id=fake_metric_id, organization_id=test_org_id)

        # Should return None for non-existent metric
        assert result is None

    def test_get_metrics_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful metrics listing"""
        from tests.backend.routes.fixtures.data_factories import MetricDataFactory
        import uuid

        # Create multiple metrics using data factory
        metric_data_1 = MetricDataFactory.sample_data()
        metric_data_1.update(
            {
                "name": f"{metric_data_1['name']} Alpha",
                "organization_id": uuid.UUID(test_org_id),
                "user_id": uuid.UUID(authenticated_user_id),
            }
        )

        metric_data_2 = MetricDataFactory.sample_data()
        metric_data_2.update(
            {
                "name": f"{metric_data_2['name']} Beta",
                "organization_id": uuid.UUID(test_org_id),
                "user_id": uuid.UUID(authenticated_user_id),
            }
        )

        db_metric_1 = models.Metric(**metric_data_1)
        db_metric_2 = models.Metric(**metric_data_2)
        test_db.add_all([db_metric_1, db_metric_2])
        test_db.flush()

        # Test metrics listing
        result = crud.get_metrics(db=test_db, skip=0, limit=10, organization_id=test_org_id)

        # Verify results
        assert len(result) >= 2  # May include other metrics from fixtures
        metric_names = [metric.name for metric in result]
        assert metric_data_1["name"] in metric_names
        assert metric_data_2["name"] in metric_names


@pytest.mark.unit
@pytest.mark.crud
class TestBehaviorMetricOperations:
    """📊🎯 Test behavior-metric association operations"""

    def test_add_behavior_to_metric_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful behavior addition to metric"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )
        import uuid

        # Create metric and behavior using data factories
        metric_data = MetricDataFactory.sample_data()
        metric_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data = BehaviorDataFactory.sample_data()
        behavior_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()

        # Test adding behavior to metric
        result = crud.add_behavior_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id,
        )

        # Verify association was created
        assert result is True

        # Verify association exists in database
        association = test_db.execute(
            models.behavior_metric_association.select().where(
                models.behavior_metric_association.c.metric_id == db_metric.id,
                models.behavior_metric_association.c.behavior_id == db_behavior.id,
            )
        ).first()

        assert association is not None
        assert association.organization_id == uuid.UUID(test_org_id)

    def test_add_behavior_to_metric_duplicate(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test adding duplicate behavior to metric"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )
        import uuid

        # Create metric and behavior using data factories
        metric_data = MetricDataFactory.sample_data()
        metric_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data = BehaviorDataFactory.sample_data()
        behavior_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()

        # Add behavior to metric first time
        first_result = crud.add_behavior_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id,
        )
        assert first_result is True

        # Try to add same behavior again
        second_result = crud.add_behavior_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id,
        )

        # Should return False for duplicate
        assert second_result is False

    def test_remove_behavior_from_metric_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful behavior removal from metric"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )
        import uuid

        # Create metric and behavior using data factories
        metric_data = MetricDataFactory.sample_data()
        metric_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data = BehaviorDataFactory.sample_data()
        behavior_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()

        # Add behavior to metric first
        test_db.execute(
            models.behavior_metric_association.insert().values(
                metric_id=db_metric.id,
                behavior_id=db_behavior.id,
                organization_id=uuid.UUID(test_org_id),
                user_id=uuid.UUID(authenticated_user_id),
            )
        )
        test_db.flush()

        # Test removing behavior from metric
        result = crud.remove_behavior_from_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
        )

        # Verify removal was successful
        assert result is True

        # Verify association is deleted
        association = test_db.execute(
            models.behavior_metric_association.select().where(
                models.behavior_metric_association.c.metric_id == db_metric.id,
                models.behavior_metric_association.c.behavior_id == db_behavior.id,
            )
        ).first()

        assert association is None

    def test_remove_behavior_from_metric_not_found(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test behavior removal with non-existent association"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )
        import uuid

        # Create metric and behavior but no association using data factories
        metric_data = MetricDataFactory.sample_data()
        metric_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data = BehaviorDataFactory.sample_data()
        behavior_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()

        # Test removing non-existent association
        result = crud.remove_behavior_from_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
        )

        # Should return False for non-existent association
        assert result is False

    def test_remove_behavior_from_metric_invalid_metric(self, test_db: Session, test_org_id: str):
        """Test behavior removal with non-existent metric"""
        fake_metric_id = uuid.uuid4()
        fake_behavior_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Metric with id .* not found"):
            crud.remove_behavior_from_metric(
                db=test_db,
                metric_id=fake_metric_id,
                behavior_id=fake_behavior_id,
                organization_id=uuid.UUID(test_org_id),
            )

    def test_remove_behavior_from_metric_invalid_behavior(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test behavior removal with non-existent behavior"""
        from tests.backend.routes.fixtures.data_factories import MetricDataFactory
        import uuid

        # Create metric using data factory
        metric_data = MetricDataFactory.sample_data()
        metric_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )
        db_metric = models.Metric(**metric_data)
        test_db.add(db_metric)
        test_db.flush()

        fake_behavior_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Behavior with id .* not found"):
            crud.remove_behavior_from_metric(
                db=test_db,
                metric_id=db_metric.id,
                behavior_id=fake_behavior_id,
                organization_id=uuid.UUID(test_org_id),
            )
