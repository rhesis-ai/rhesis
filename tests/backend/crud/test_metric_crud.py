"""
📊 Metric CRUD Operations Testing

Comprehensive test suite for metric-related CRUD operations.
Tests focus on metric operations and requirement associations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- get_metric: Retrieve single metric with relationships
- get_metrics: List metrics with pagination
- add_requirement_to_metric: Associate requirements with metrics
- remove_requirement_from_metric: Remove requirement associations from metrics

Run with: python -m pytest tests/backend/crud/test_metric_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.metric import (
    add_requirement_to_metric,
    get_metric,
    get_metrics,
    remove_requirement_from_metric,
)


@pytest.mark.unit
@pytest.mark.crud
class TestMetricOperations:
    """📊 Test metric operations"""

    def test_get_metric_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful metric retrieval with relationships"""
        import uuid

        from tests.backend.routes.fixtures.data_factories import MetricDataFactory

        # Create metric using data factory
        metric_data = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )
        db_metric = models.Metric(**metric_data)
        test_db.add(db_metric)
        test_db.flush()

        # Test metric retrieval
        result = get_metric(db=test_db, metric_id=db_metric.id, organization_id=test_org_id)

        # Verify result
        assert result is not None
        assert result.id == db_metric.id
        assert result.name == metric_data["name"]
        assert result.organization_id == uuid.UUID(test_org_id)

    def test_get_metric_not_found(self, test_db: Session, test_org_id: str):
        """Test metric retrieval with non-existent ID"""
        fake_metric_id = uuid.uuid4()

        result = get_metric(db=test_db, metric_id=fake_metric_id, organization_id=test_org_id)

        # Should return None for non-existent metric
        assert result is None

    def test_get_metrics_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful metrics listing"""
        from tests.backend.routes.fixtures.data_factories import MetricDataFactory

        # Create multiple metrics using data factory
        metric_data_1 = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )
        metric_data_1["name"] = f"{metric_data_1['name']} Alpha"

        metric_data_2 = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )
        metric_data_2["name"] = f"{metric_data_2['name']} Beta"

        db_metric_1 = models.Metric(**metric_data_1)
        db_metric_2 = models.Metric(**metric_data_2)
        test_db.add_all([db_metric_1, db_metric_2])
        test_db.flush()

        # Test metrics listing
        result = get_metrics(db=test_db, skip=0, limit=10, organization_id=test_org_id)

        # Verify results
        assert len(result) >= 2  # May include other metrics from fixtures
        metric_names = [metric.name for metric in result]
        assert metric_data_1["name"] in metric_names
        assert metric_data_2["name"] in metric_names


@pytest.mark.unit
@pytest.mark.crud
class TestRequirementMetricOperations:
    """📊🎯 Test requirement-metric association operations"""

    def test_add_requirement_to_metric_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful requirement addition to metric"""
        import uuid

        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create metric and requirement using data factories
        metric_data = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )

        requirement_data = RequirementDataFactory.sample_data()
        requirement_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_requirement = models.Requirement(**requirement_data)
        test_db.add_all([db_metric, db_requirement])
        test_db.flush()

        # Test adding requirement to metric
        result = add_requirement_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            requirement_id=db_requirement.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id,
        )

        # Verify association was created
        assert result is True

        # Verify association exists in database
        association = test_db.execute(
            models.requirement_metric_association.select().where(
                models.requirement_metric_association.c.metric_id == db_metric.id,
                models.requirement_metric_association.c.requirement_id == db_requirement.id,
            )
        ).first()

        assert association is not None
        assert association.organization_id == uuid.UUID(test_org_id)

    def test_add_requirement_to_metric_twice(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test adding duplicate requirement to metric"""
        import uuid

        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create metric and requirement using data factories
        metric_data = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )

        requirement_data = RequirementDataFactory.sample_data()
        requirement_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_requirement = models.Requirement(**requirement_data)
        test_db.add_all([db_metric, db_requirement])
        test_db.flush()

        # Add requirement to metric first time
        first_result = add_requirement_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            requirement_id=db_requirement.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id,
        )
        assert first_result is True

        # Try to add same requirement again
        second_result = add_requirement_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            requirement_id=db_requirement.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id,
        )

        # Should return False for duplicate
        assert second_result is False

    def test_remove_requirement_from_metric_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful requirement removal from metric"""
        import uuid

        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create metric and requirement using data factories
        metric_data = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )

        requirement_data = RequirementDataFactory.sample_data()
        requirement_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_requirement = models.Requirement(**requirement_data)
        test_db.add_all([db_metric, db_requirement])
        test_db.flush()

        # Add requirement to metric first
        test_db.execute(
            models.requirement_metric_association.insert().values(
                metric_id=db_metric.id,
                requirement_id=db_requirement.id,
                organization_id=uuid.UUID(test_org_id),
                user_id=uuid.UUID(authenticated_user_id),
            )
        )
        test_db.flush()

        # Test removing requirement from metric
        result = remove_requirement_from_metric(
            db=test_db,
            metric_id=db_metric.id,
            requirement_id=db_requirement.id,
            organization_id=uuid.UUID(test_org_id),
        )

        # Verify removal was successful
        assert result is True

        # Verify association is deleted
        association = test_db.execute(
            models.requirement_metric_association.select().where(
                models.requirement_metric_association.c.metric_id == db_metric.id,
                models.requirement_metric_association.c.requirement_id == db_requirement.id,
            )
        ).first()

        assert association is None

    def test_remove_requirement_from_metric_not_found(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test requirement removal with non-existent association"""
        import uuid

        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create metric and requirement but no association using data factories
        metric_data = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )

        requirement_data = RequirementDataFactory.sample_data()
        requirement_data.update(
            {"organization_id": uuid.UUID(test_org_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric = models.Metric(**metric_data)
        db_requirement = models.Requirement(**requirement_data)
        test_db.add_all([db_metric, db_requirement])
        test_db.flush()

        # Test removing non-existent association
        result = remove_requirement_from_metric(
            db=test_db,
            metric_id=db_metric.id,
            requirement_id=db_requirement.id,
            organization_id=uuid.UUID(test_org_id),
        )

        # Should return False for non-existent association
        assert result is False

    def test_remove_requirement_from_metric_invalid_metric(self, test_db: Session, test_org_id: str):
        """Test requirement removal with non-existent metric"""
        fake_metric_id = uuid.uuid4()
        fake_requirement_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Metric with id .* not found"):
            remove_requirement_from_metric(
                db=test_db,
                metric_id=fake_metric_id,
                requirement_id=fake_requirement_id,
                organization_id=uuid.UUID(test_org_id),
            )

    def test_remove_requirement_from_metric_invalid_requirement(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test requirement removal with non-existent requirement"""
        import uuid

        from tests.backend.routes.fixtures.data_factories import MetricDataFactory

        # Create metric using data factory
        metric_data = MetricDataFactory.orm_data(
            test_db, test_org_id, authenticated_user_id
        )
        db_metric = models.Metric(**metric_data)
        test_db.add(db_metric)
        test_db.flush()

        fake_requirement_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Requirement with id .* not found"):
            remove_requirement_from_metric(
                db=test_db,
                metric_id=db_metric.id,
                requirement_id=fake_requirement_id,
                organization_id=uuid.UUID(test_org_id),
            )
