"""
🧪 Test Entity Fixtures

Fixtures for creating test entities and related relationships.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test

fake = Faker()


@pytest.fixture
def db_test(test_db: Session, test_organization, db_user, db_status) -> Test:
    """
    🧪 Create a real test entity in the test database

    This fixture creates an actual Test record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture

    Returns:
        Test: Real test record with valid database ID
    """
    test = Test(
        priority=fake.random_int(min=1, max=5),
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        test_metadata={"source": "fixture", "created_for": "test_purposes"},
    )
    test_db.add(test)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(test)
    return test


@pytest.fixture
def db_test_with_prompt(test_db: Session, test_organization, db_user, db_status, db_prompt) -> Test:
    """
    🧪 Create a test entity with a prompt relationship

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture
        db_prompt: Prompt fixture

    Returns:
        Test: Real test record with prompt relationship
    """
    test = Test(
        prompt_id=db_prompt.id,
        priority=fake.random_int(min=1, max=5),
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
        test_metadata={"source": "fixture", "has_prompt": True},
    )
    test_db.add(test)
    test_db.flush()
    test_db.refresh(test)
    return test


@pytest.fixture
def db_test_minimal(test_db: Session, test_organization, db_user) -> Test:
    """
    🧪 Create a minimal test entity with only required fields

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator

    Returns:
        Test: Minimal test record
    """
    test = Test(user_id=db_user.id, organization_id=test_organization.id)
    test_db.add(test)
    test_db.flush()
    test_db.refresh(test)
    return test
