"""
Status Fixtures

Fixtures for creating status entities and related type lookups.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session
from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.type_lookup import TypeLookup

fake = Faker()


@pytest.fixture
def test_type_lookup(test_db: Session, test_organization) -> TypeLookup:
    """
    Create a test type lookup in the database

    This fixture creates a real TypeLookup record that can be used
    as a foreign key reference for statuses.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture

    Returns:
        TypeLookup: Real type lookup record
    """
    type_lookup = TypeLookup(
        type_name="EntityType",
        type_value="ENDPOINT",
        description="Entity type for endpoints",
        organization_id=test_organization.id,
        user_id=None  # Can be None for system types
    )
    test_db.add(type_lookup)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(type_lookup)
    return type_lookup


@pytest.fixture
def db_status(test_db: Session, test_organization, test_type_lookup, db_user) -> Status:
    """
    Create a real status in the test database

    This fixture creates an actual Status record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        test_type_lookup: General EntityType TypeLookup fixture
        db_user: User fixture

    Returns:
        Status: Real status record with valid database ID
    """
    status = Status(
        name="Active",
        description="Active status for testing",
        entity_type_id=test_type_lookup.id,  # Use General entity type like production
        organization_id=test_organization.id,
        user_id=db_user.id
    )
    test_db.add(status)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(status)
    return status


@pytest.fixture
def db_inactive_status(test_db: Session, test_organization, test_type_lookup, db_user) -> Status:
    """
    Create an inactive status in the test database

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        test_type_lookup: General EntityType TypeLookup fixture
        db_user: User fixture

    Returns:
        Status: Real inactive status record
    """
    status = Status(
        name="Inactive",
        description="Inactive status for testing",
        entity_type_id=test_type_lookup.id,  # Use General entity type like production
        organization_id=test_organization.id,
        user_id=db_user.id
    )
    test_db.add(status)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(status)
    return status


@pytest.fixture
def db_draft_status(test_db: Session, test_organization, test_type_lookup, db_user) -> Status:
    """
    Create a draft status in the test database

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        test_type_lookup: General EntityType TypeLookup fixture
        db_user: User fixture

    Returns:
        Status: Real draft status record
    """
    status = Status(
        name="Draft",
        description="Draft status for testing",
        entity_type_id=test_type_lookup.id,  # Use General entity type like production
        organization_id=test_organization.id,
        user_id=db_user.id
    )
    test_db.add(status)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(status)
    return status


@pytest.fixture
def db_project_status(test_db: Session, test_organization, test_type_lookup, db_user) -> Status:
    """
    Create a project status in the test database

    This fixture creates an actual Status record specifically for projects
    using the General entity type (as used in production).

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        test_type_lookup: General EntityType TypeLookup fixture
        db_user: User fixture

    Returns:
        Status: Real project status record with valid database ID
    """
    status = Status(
        name="Active",
        description="Active status for project testing",
        entity_type_id=test_type_lookup.id,  # Use General entity type like production
        organization_id=test_organization.id,
        user_id=db_user.id
    )
    test_db.add(status)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(status)
    return status
