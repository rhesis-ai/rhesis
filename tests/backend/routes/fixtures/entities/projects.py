"""
Project Fixtures

Fixtures for creating project entities and related relationships.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.project import Project

fake = Faker()


@pytest.fixture
def db_project(test_db: Session, test_organization, db_user, db_owner_user, db_status) -> Project:
    """
    Create a real project in the test database

    This fixture creates an actual Project record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_owner_user: User fixture for owner
        db_status: Status fixture

    Returns:
        Project: Real project record with valid database ID
    """
    project = Project(
        name=f"Test Project {fake.company()}",
        description=f"Test project for {fake.bs()}",
        icon="🚀",
        is_active=True,
        user_id=db_user.id,
        owner_id=db_owner_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(project)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(project)
    return project


@pytest.fixture
def db_inactive_project(
    test_db: Session, test_organization, db_user, db_owner_user, db_inactive_status
) -> Project:
    """
    Create an inactive project in the test database

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_owner_user: User fixture for owner
        db_inactive_status: Inactive status fixture

    Returns:
        Project: Real inactive project record
    """
    project = Project(
        name=f"Inactive Project {fake.company()}",
        description=f"Inactive test project for {fake.bs()}",
        icon="💤",
        is_active=False,
        user_id=db_user.id,
        owner_id=db_owner_user.id,
        organization_id=test_organization.id,
        status_id=db_inactive_status.id,
    )
    test_db.add(project)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(project)
    return project


@pytest.fixture
def db_draft_project(
    test_db: Session, test_organization, db_user, db_owner_user, db_draft_status
) -> Project:
    """
    Create a draft project in the test database

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_owner_user: User fixture for owner
        db_draft_status: Draft status fixture

    Returns:
        Project: Real draft project record
    """
    project = Project(
        name=f"Draft Project {fake.company()}",
        description=f"Draft test project for {fake.bs()}",
        icon="📝",
        is_active=True,
        user_id=db_user.id,
        owner_id=db_owner_user.id,
        organization_id=test_organization.id,
        status_id=db_draft_status.id,
    )
    test_db.add(project)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(project)
    return project
