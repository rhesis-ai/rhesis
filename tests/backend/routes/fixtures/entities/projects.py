"""
Project Fixtures

Fixtures for creating project entities and related relationships.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.project_membership import ProjectMembership

fake = Faker()


@pytest.fixture
def db_project(
    test_db: Session,
    test_organization,
    db_user,
    db_owner_user,
    db_status,
    authenticated_user_id,
) -> Project:
    """
    Create a real project in the test database

    This fixture creates an actual Project record in the database that can be
    used for foreign key relationships in tests.  It also enrolls the session
    user (``authenticated_user_id``) as a project member so that
    ``crud.get_project`` — which enforces project_membership presence — returns
    the row rather than None when the authenticated client accesses it.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_owner_user: User fixture for owner
        db_status: Status fixture
        authenticated_user_id: Session user ID making HTTP requests

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
    test_db.flush()

    # Enroll the session user so crud.get_project sees a membership row.
    membership = ProjectMembership(
        project_id=project.id,
        user_id=authenticated_user_id,
        organization_id=test_organization.id,
    )
    test_db.add(membership)
    test_db.flush()

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
