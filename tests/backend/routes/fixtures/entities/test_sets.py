"""
🧪 Test Set Entity Fixtures

Fixtures for creating test set entities and related relationships.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_set import TestSet

fake = Faker()


@pytest.fixture
def db_test_set(test_db: Session, test_organization, db_user, db_status) -> TestSet:
    """
    🧪 Create a real test set entity in the test database

    This fixture creates an actual TestSet record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture

    Returns:
        TestSet: Real test set record with valid database ID
    """
    test_set = TestSet(
        name=fake.catch_phrase() + " Test Set",
        description=fake.text(max_nb_chars=200),
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        is_published=False,
        visibility="organization",
    )
    test_db.add(test_set)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(test_set)
    return test_set


@pytest.fixture
def db_test_set_with_tests(
    test_db: Session, test_organization, db_user, db_status, db_test
) -> TestSet:
    """
    🧪 Create a test set with associated tests

    This fixture creates a TestSet with associated Test records for testing
    relationships and bulk operations.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture
        db_test: Test fixture to associate

    Returns:
        TestSet: Real test set record with associated tests
    """
    test_set = TestSet(
        name=fake.catch_phrase() + " Test Set with Tests",
        description=fake.text(max_nb_chars=200),
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        is_published=False,
        visibility="organization",
    )
    test_db.add(test_set)
    test_db.flush()

    # Associate the test with the test set
    test_set.tests.append(db_test)
    test_db.flush()
    test_db.refresh(test_set)

    return test_set
