"""
🔒 Behavior-Metric Security Testing

Security-focused tests for behavior-metric CRUD operations.
These tests ensure proper cross-tenant isolation and prevent unauthorized access
to resources across organizations.

Functions tested:
- add_behavior_to_metric: Cross-tenant prevention
- remove_behavior_from_metric: Cross-tenant prevention
- get_metric_behaviors: Cross-tenant prevention
- get_behavior_metrics: Cross-tenant prevention

Run with: python -m pytest tests/backend/crud/test_behavior_metric_security.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models


@pytest.mark.security
@pytest.mark.crud
class TestBehaviorMetricSecurity:
    """🔒 Security tests for behavior-metric operations"""

    def test_add_behavior_to_metric_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot add behaviors from other organizations to their metrics"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric in org1 and behavior in org2 using data factories
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data_org2 = BehaviorDataFactory.sample_data()
        behavior_data_org2.update(
            {"organization_id": uuid.UUID(org2_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric_org1 = models.Metric(**metric_data_org1)
        db_behavior_org2 = models.Behavior(**behavior_data_org2)
        test_db.add_all([db_metric_org1, db_behavior_org2])
        test_db.flush()

        # Try to add behavior from org2 to metric in org1 - should fail
        with pytest.raises(ValueError, match="Behavior with id .* not found or not accessible"):
            crud.add_behavior_to_metric(
                db=test_db,
                metric_id=db_metric_org1.id,
                behavior_id=db_behavior_org2.id,
                organization_id=uuid.UUID(org1_id),  # User is in org1
                user_id=authenticated_user_id,
            )

        # Verify no association was created
        association = test_db.execute(
            models.behavior_metric_association.select().where(
                models.behavior_metric_association.c.metric_id == db_metric_org1.id,
                models.behavior_metric_association.c.behavior_id == db_behavior_org2.id,
            )
        ).first()
        assert association is None

    def test_add_behavior_to_metric_cross_tenant_metric_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot add behaviors to metrics from other organizations"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric in org1 and behavior in org2 using data factories
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data_org2 = BehaviorDataFactory.sample_data()
        behavior_data_org2.update(
            {"organization_id": uuid.UUID(org2_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric_org1 = models.Metric(**metric_data_org1)
        db_behavior_org2 = models.Behavior(**behavior_data_org2)
        test_db.add_all([db_metric_org1, db_behavior_org2])
        test_db.flush()

        # Try to add behavior from org2 to metric in org1, but user is in org2 - should fail
        with pytest.raises(ValueError, match="Metric with id .* not found or not accessible"):
            crud.add_behavior_to_metric(
                db=test_db,
                metric_id=db_metric_org1.id,
                behavior_id=db_behavior_org2.id,
                organization_id=uuid.UUID(org2_id),  # User is in org2, metric is in org1
                user_id=authenticated_user_id,
            )

    def test_remove_behavior_from_metric_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot remove behaviors from metrics in other organizations"""
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            BehaviorDataFactory,
        )

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric and behavior in org1 using data factories
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        behavior_data_org1 = BehaviorDataFactory.sample_data()
        behavior_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric_org1 = models.Metric(**metric_data_org1)
        db_behavior_org1 = models.Behavior(**behavior_data_org1)
        test_db.add_all([db_metric_org1, db_behavior_org1])
        test_db.flush()

        # Create association in org1
        test_db.execute(
            models.behavior_metric_association.insert().values(
                metric_id=db_metric_org1.id,
                behavior_id=db_behavior_org1.id,
                organization_id=uuid.UUID(org1_id),
                user_id=uuid.UUID(authenticated_user_id),
            )
        )
        test_db.flush()

        # Try to remove association as user from org2 - should fail
        with pytest.raises(ValueError, match="Metric with id .* not found or not accessible"):
            crud.remove_behavior_from_metric(
                db=test_db,
                metric_id=db_metric_org1.id,
                behavior_id=db_behavior_org1.id,
                organization_id=uuid.UUID(
                    org2_id
                ),  # User is in org2, but metric/behavior are in org1
            )

        # Verify association still exists (wasn't removed)
        association = test_db.execute(
            models.behavior_metric_association.select().where(
                models.behavior_metric_association.c.metric_id == db_metric_org1.id,
                models.behavior_metric_association.c.behavior_id == db_behavior_org1.id,
            )
        ).first()
        assert association is not None

    def test_get_metric_behaviors_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot get behaviors for metrics from other organizations"""
        from tests.backend.routes.fixtures.data_factories import MetricDataFactory

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric in org1 using data factory
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )
        db_metric_org1 = models.Metric(**metric_data_org1)
        test_db.add(db_metric_org1)
        test_db.flush()

        # Try to get behaviors for metric from org1 as user from org2 - should fail
        with pytest.raises(ValueError, match="Metric with id .* not found or not accessible"):
            crud.get_metric_behaviors(
                db=test_db,
                metric_id=db_metric_org1.id,
                organization_id=org2_id,  # User is in org2, but metric is in org1
            )

    def test_get_behavior_metrics_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot get metrics for behaviors from other organizations"""
        from tests.backend.routes.fixtures.data_factories import BehaviorDataFactory

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create behavior in org1 using data factory
        behavior_data_org1 = BehaviorDataFactory.sample_data()
        behavior_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )
        db_behavior_org1 = models.Behavior(**behavior_data_org1)
        test_db.add(db_behavior_org1)
        test_db.flush()

        # Try to get metrics for behavior from org1 as user from org2 - should fail
        with pytest.raises(ValueError, match="Behavior with id .* not found or not accessible"):
            crud.get_behavior_metrics(
                db=test_db,
                behavior_id=db_behavior_org1.id,
                organization_id=org2_id,  # User is in org2, but behavior is in org1
            )
