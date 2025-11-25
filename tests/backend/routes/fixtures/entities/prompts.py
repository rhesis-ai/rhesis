"""
🤖 Prompt Fixtures

Fixtures for creating prompt entities and related relationships.
"""

import pytest
from faker import Faker
from sqlalchemy.orm import Session
from rhesis.backend.app.models.prompt import Prompt

fake = Faker()


@pytest.fixture
def db_prompt(test_db: Session, test_organization, db_user, db_status) -> Prompt:
    """
    🤖 Create a real prompt in the test database

    This fixture creates an actual Prompt record in the database that can be
    used for foreign key relationships in tests.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture

    Returns:
        Prompt: Real prompt record with valid database ID
    """
    prompt = Prompt(
        content=fake.paragraph(nb_sentences=3),
        language_code="en",
        expected_response=fake.paragraph(nb_sentences=2),
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(prompt)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(prompt)
    return prompt


@pytest.fixture
def db_multilingual_prompt(test_db: Session, test_organization, db_user, db_status) -> Prompt:
    """
    🤖 Create a multilingual prompt in the test database

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture

    Returns:
        Prompt: Real multilingual prompt record
    """
    prompt = Prompt(
        content="¿Cómo estás? Comment allez-vous? Wie geht es dir?",
        language_code="es",
        expected_response="I am doing well, thank you!",
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(prompt)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(prompt)
    return prompt


@pytest.fixture
def db_parent_prompt(test_db: Session, test_organization, db_user, db_status) -> Prompt:
    """
    🤖 Create a parent prompt for multiturn scenarios

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture

    Returns:
        Prompt: Real parent prompt record
    """
    prompt = Prompt(
        content="This is the first turn in a conversation.",
        language_code="en",
        expected_response="This is the expected response to the first turn.",
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(prompt)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(prompt)
    return prompt


@pytest.fixture
def db_child_prompt(
    test_db: Session, test_organization, db_user, db_status, db_parent_prompt
) -> Prompt:
    """
    🤖 Create a child prompt for multiturn scenarios

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture for creator
        db_status: Status fixture
        db_parent_prompt: Parent prompt fixture

    Returns:
        Prompt: Real child prompt record with parent relationship
    """
    prompt = Prompt(
        content="This is the second turn in the conversation.",
        language_code="en",
        expected_response="This is the expected response to the second turn.",
        parent_id=db_parent_prompt.id,
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(prompt)
    test_db.commit()  # Commit the transaction to make it visible to other transactions
    test_db.refresh(prompt)
    return prompt
