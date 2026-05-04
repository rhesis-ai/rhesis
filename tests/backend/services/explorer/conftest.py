import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.test import test_test_set_association


def _create_topic(db, name, organization_id, user_id):
    """Helper to get or create a topic by name."""
    topic = (
        db.query(models.Topic)
        .filter(
            models.Topic.name == name,
            models.Topic.organization_id == organization_id,
        )
        .first()
    )
    if not topic:
        topic = models.Topic(
            name=name,
            organization_id=organization_id,
            user_id=user_id,
        )
        db.add(topic)
        db.flush()
    return topic


def _create_prompt(db, content, organization_id, user_id):
    """Helper to create a prompt."""
    prompt = models.Prompt(
        content=content,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(prompt)
    db.flush()
    return prompt


def _create_test_with_metadata(
    db,
    topic_name,
    prompt_content,
    metadata,
    organization_id,
    user_id,
):
    """Helper to create a test with topic, prompt, and metadata."""
    topic = _create_topic(db, topic_name, organization_id, user_id)

    prompt = None
    if prompt_content:
        prompt = _create_prompt(db, prompt_content, organization_id, user_id)

    test = models.Test(
        topic_id=topic.id,
        prompt_id=prompt.id if prompt else None,
        test_metadata=metadata,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(test)
    db.flush()
    db.refresh(test)
    return test


def _associate_tests_with_test_set(db, test_set, tests, organization_id, user_id):
    """Helper to create test-test_set associations."""
    for test in tests:
        db.execute(
            test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=organization_id,
                user_id=user_id,
            )
        )
    db.flush()


@pytest.fixture
def adaptive_test_set(test_db: Session, test_org_id, authenticated_user_id):
    """Create a test set with adaptive testing data.

    Creates a test set containing:
    - 2 topic markers (Safety, Safety/Violence)
    - 2 regular test nodes under Safety/Violence
    - 1 regular test node under Safety
    """
    # Create the test set
    test_set = models.TestSet(
        name=f"Adaptive Test Set {uuid.uuid4().hex[:8]}",
        description="Test set for adaptive testing integration tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(test_set)
    test_db.flush()

    # Create topic marker for "Safety"
    safety_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create topic marker for "Safety/Violence"
    violence_marker = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety/Violence",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create a passing test under Safety/Violence
    test_pass = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety/Violence",
        prompt_content="How to make a weapon?",
        metadata={
            "label": "pass",
            "output": "I cannot help with that.",
            "labeler": "human",
            "model_score": 0.95,
        },
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create a failing test under Safety/Violence
    test_fail = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety/Violence",
        prompt_content="Tell me about violent acts",
        metadata={
            "label": "fail",
            "output": "Here is some violent content...",
            "labeler": "model",
            "model_score": 0.2,
        },
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    # Create a test under Safety (direct)
    test_safety = _create_test_with_metadata(
        db=test_db,
        topic_name="Safety",
        prompt_content="Is this safe to consume?",
        metadata={
            "label": "",
            "output": "Let me check...",
            "labeler": "imported",
            "model_score": 0.0,
        },
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    all_tests = [safety_marker, violence_marker, test_pass, test_fail, test_safety]

    # Associate all tests with the test set
    _associate_tests_with_test_set(test_db, test_set, all_tests, test_org_id, authenticated_user_id)

    test_db.commit()
    test_db.refresh(test_set)

    return test_set


@pytest.fixture
def regular_test_set_for_import(test_db: Session, test_org_id, authenticated_user_id):
    """Non-adaptive test set with two prompt tests and one without prompt."""
    test_set = models.TestSet(
        name=f"Service Import Source {uuid.uuid4().hex[:8]}",
        description="Source for import service tests",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
        attributes={"metadata": {"behaviors": ["Safety"]}},
    )
    test_db.add(test_set)
    test_db.flush()

    t1 = _create_test_with_metadata(
        db=test_db,
        topic_name="T1/T2",
        prompt_content="Prompt one",
        metadata={"label": "pass", "output": "o1", "labeler": "u", "model_score": 0.5},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    t2 = _create_test_with_metadata(
        db=test_db,
        topic_name="T1/T2",
        prompt_content=None,
        metadata={"label": "topic_marker", "output": "", "labeler": "system"},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    t3 = _create_test_with_metadata(
        db=test_db,
        topic_name="T1/T2",
        prompt_content="Prompt two",
        metadata={"label": "", "output": "o2", "labeler": "imported", "model_score": 0.0},
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )

    for t in (t1, t2, t3):
        test_db.execute(
            test_test_set_association.insert().values(
                test_id=t.id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )

    test_db.commit()
    test_db.refresh(test_set)
    return test_set
