"""
🧪 Test Run Entity Fixtures

Fixtures for creating test run entities and related relationships.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun

fake = Faker()


@pytest.fixture
def db_test_configuration(
    test_db: Session, test_organization, db_user, db_endpoint
) -> TestConfiguration:
    """
    🧪 Create a real test configuration entity in the test database

    This fixture creates an actual TestConfiguration record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_endpoint: Endpoint fixture (required for test configuration)

    Returns:
        TestConfiguration: Real test configuration record with valid database ID
    """
    test_config = TestConfiguration(
        endpoint_id=db_endpoint.id,
        user_id=db_user.id,
        organization_id=test_organization.id,
        attributes={"model": "gpt-3.5-turbo", "temperature": 0.7, "max_tokens": 1000},
    )
    test_db.add(test_config)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(test_config)
    return test_config


@pytest.fixture
def db_test_run(
    test_db: Session, test_organization, db_user, db_status, db_test_configuration
) -> TestRun:
    """
    🧪 Create a real test run entity in the test database

    This fixture creates an actual TestRun record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture
        db_test_configuration: Test configuration fixture

    Returns:
        TestRun: Real test run record with valid database ID
    """
    test_run = TestRun(
        name=fake.catch_phrase() + " Test Run",
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        test_configuration_id=db_test_configuration.id,
        attributes={"started_at": fake.date_time_this_year().isoformat(), "environment": "test"},
    )
    test_db.add(test_run)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(test_run)
    return test_run


@pytest.fixture
def db_test_run_running(
    test_db: Session, test_organization, db_user, db_test_configuration, db_status: Status
) -> TestRun:
    """
    🧪 Create a test run in RUNNING status

    This fixture creates a TestRun with RUNNING status for testing status updates.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_test_configuration: Test configuration fixture

    Returns:
        TestRun: Real test run record in RUNNING status
    """

    test_run = TestRun(
        name=fake.catch_phrase() + " Running Test Run",
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        test_configuration_id=db_test_configuration.id,
        attributes={"started_at": fake.date_time_this_year().isoformat(), "environment": "test"},
    )
    test_db.add(test_run)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(test_run)
    return test_run
