"""
🔒 Requirement-Metric Security Testing

Security-focused tests for requirement-metric CRUD operations.
These tests ensure proper cross-tenant isolation and prevent unauthorized access
to resources across organizations.

Functions tested:
- add_requirement_to_metric: Cross-tenant prevention
- remove_requirement_from_metric: Cross-tenant prevention
- get_metric_requirements: Cross-tenant prevention
- get_requirement_metrics: Cross-tenant prevention

Run with: python -m pytest tests/backend/crud/test_requirement_metric_security.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.metric import (
    add_requirement_to_metric,
    get_requirement_metrics,
    get_metric_requirements,
    remove_requirement_from_metric,
)


@pytest.mark.security
@pytest.mark.crud
class TestRequirementMetricSecurity:
    """🔒 Security tests for requirement-metric operations"""

    def test_add_requirement_to_metric_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot add requirements from other organizations to their metrics"""
        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric in org1 and requirement in org2 using data factories
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        requirement_data_org2 = RequirementDataFactory.sample_data()
        requirement_data_org2.update(
            {"organization_id": uuid.UUID(org2_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric_org1 = models.Metric(**metric_data_org1)
        db_requirement_org2 = models.Requirement(**requirement_data_org2)
        test_db.add_all([db_metric_org1, db_requirement_org2])
        test_db.flush()

        # Try to add requirement from org2 to metric in org1 - should fail
        with pytest.raises(ValueError, match="Requirement with id .* not found or not accessible"):
            add_requirement_to_metric(
                db=test_db,
                metric_id=db_metric_org1.id,
                requirement_id=db_requirement_org2.id,
                organization_id=uuid.UUID(org1_id),  # User is in org1
                user_id=authenticated_user_id,
            )

        # Verify no association was created
        association = test_db.execute(
            models.requirement_metric_association.select().where(
                models.requirement_metric_association.c.metric_id == db_metric_org1.id,
                models.requirement_metric_association.c.requirement_id == db_requirement_org2.id,
            )
        ).first()
        assert association is None

    def test_add_requirement_to_metric_cross_tenant_metric_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot add requirements to metrics from other organizations"""
        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric in org1 and requirement in org2 using data factories
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        requirement_data_org2 = RequirementDataFactory.sample_data()
        requirement_data_org2.update(
            {"organization_id": uuid.UUID(org2_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric_org1 = models.Metric(**metric_data_org1)
        db_requirement_org2 = models.Requirement(**requirement_data_org2)
        test_db.add_all([db_metric_org1, db_requirement_org2])
        test_db.flush()

        # Try to add requirement from org2 to metric in org1, but user is in org2 - should fail
        with pytest.raises(ValueError, match="Metric with id .* not found or not accessible"):
            add_requirement_to_metric(
                db=test_db,
                metric_id=db_metric_org1.id,
                requirement_id=db_requirement_org2.id,
                organization_id=uuid.UUID(org2_id),  # User is in org2, metric is in org1
                user_id=authenticated_user_id,
            )

    def test_remove_requirement_from_metric_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot remove requirements from metrics in other organizations"""
        from tests.backend.routes.fixtures.data_factories import (
            RequirementDataFactory,
            MetricDataFactory,
        )

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create metric and requirement in org1 using data factories
        metric_data_org1 = MetricDataFactory.sample_data()
        metric_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        requirement_data_org1 = RequirementDataFactory.sample_data()
        requirement_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )

        db_metric_org1 = models.Metric(**metric_data_org1)
        db_requirement_org1 = models.Requirement(**requirement_data_org1)
        test_db.add_all([db_metric_org1, db_requirement_org1])
        test_db.flush()

        # Create association in org1
        test_db.execute(
            models.requirement_metric_association.insert().values(
                metric_id=db_metric_org1.id,
                requirement_id=db_requirement_org1.id,
                organization_id=uuid.UUID(org1_id),
                user_id=uuid.UUID(authenticated_user_id),
            )
        )
        test_db.flush()

        # Try to remove association as user from org2 - should fail
        with pytest.raises(ValueError, match="Metric with id .* not found or not accessible"):
            remove_requirement_from_metric(
                db=test_db,
                metric_id=db_metric_org1.id,
                requirement_id=db_requirement_org1.id,
                organization_id=uuid.UUID(
                    org2_id
                ),  # User is in org2, but metric/requirement are in org1
            )

        # Verify association still exists (wasn't removed)
        association = test_db.execute(
            models.requirement_metric_association.select().where(
                models.requirement_metric_association.c.metric_id == db_metric_org1.id,
                models.requirement_metric_association.c.requirement_id == db_requirement_org1.id,
            )
        ).first()
        assert association is not None

    def test_get_metric_requirements_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot get requirements for metrics from other organizations"""
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

        # Try to get requirements for metric from org1 as user from org2 - should fail
        with pytest.raises(ValueError, match="Metric with id .* not found or not accessible"):
            get_metric_requirements(
                db=test_db,
                metric_id=db_metric_org1.id,
                organization_id=org2_id,  # User is in org2, but metric is in org1
            )

    def test_get_requirement_metrics_cross_tenant_prevention(
        self, test_db: Session, authenticated_user_id: str
    ):
        """🔒 SECURITY: Test that users cannot get metrics for requirements from other organizations"""
        from tests.backend.routes.fixtures.data_factories import RequirementDataFactory

        # Create two separate organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())

        # Create actual organization records
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Test Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Test Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create requirement in org1 using data factory
        requirement_data_org1 = RequirementDataFactory.sample_data()
        requirement_data_org1.update(
            {"organization_id": uuid.UUID(org1_id), "user_id": uuid.UUID(authenticated_user_id)}
        )
        db_requirement_org1 = models.Requirement(**requirement_data_org1)
        test_db.add(db_requirement_org1)
        test_db.flush()

        # Try to get metrics for requirement from org1 as user from org2 - should fail
        with pytest.raises(ValueError, match="Requirement with id .* not found or not accessible"):
            get_requirement_metrics(
                db=test_db,
                requirement_id=db_requirement_org1.id,
                organization_id=org2_id,  # User is in org2, but requirement is in org1
            )
