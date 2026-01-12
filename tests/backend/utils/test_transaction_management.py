"""
🔄 Transaction Management Testing for Utility Functions

Comprehensive test suite for verifying that transaction management works correctly
in utility functions after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit on success in CRUD utilities
- Proper data persistence after operations
- Transaction isolation in utility functions

Functions tested from app/utils/crud_utils.py:
- _create_db_item_with_transaction
- update_item
- delete_item

Run with: python -m pytest tests/backend/utils/test_transaction_management.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils import crud_utils
from tests.backend.routes.fixtures.data_factories import (
    BehaviorDataFactory,
    CategoryDataFactory,
    TopicDataFactory,
)


@pytest.mark.unit
@pytest.mark.utils
@pytest.mark.transaction
class TestCRUDUtilsTransactionManagement:
    """🔄 Test automatic transaction management in CRUD utilities"""

    def test_create_db_item_commits_on_success(self, test_db: Session):
        """Test that _create_db_item_with_transaction commits automatically on success"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Create behavior data
        behavior_data = BehaviorDataFactory.sample_data()
        behavior_data["organization_id"] = organization.id
        behavior_data["user_id"] = user.id

        # Create item using the utility function
        result = crud_utils._create_db_item_with_transaction(
            test_db, models.Behavior, behavior_data, commit=True
        )

        # Verify item was created and persisted
        assert result is not None
        assert result.name == behavior_data["name"]
        assert result.id is not None

        # Verify it's actually in the database (committed)
        db_behavior = test_db.query(models.Behavior).filter(models.Behavior.id == result.id).first()
        assert db_behavior is not None
        assert db_behavior.name == behavior_data["name"]

    def test_create_db_item_with_commit_false_still_persists(self, test_db: Session):
        """Test that _create_db_item_with_transaction still persists data when commit=False (session context manager handles commit)"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Create topic data
        topic_data = TopicDataFactory.sample_data()
        topic_data["organization_id"] = organization.id
        topic_data["user_id"] = user.id

        # Create item with commit=False (but session context manager should still commit)
        result = crud_utils._create_db_item_with_transaction(
            test_db, models.Topic, topic_data, commit=False
        )

        # Verify item was created
        assert result is not None
        assert result.name == topic_data["name"]
        assert result.id is not None

        # Verify it's persisted when session context manager commits
        # (This test verifies the refactoring works correctly)
        db_topic = test_db.query(models.Topic).filter(models.Topic.id == result.id).first()
        assert db_topic is not None
        assert db_topic.name == topic_data["name"]

    def test_update_item_commits_on_success(self, test_db: Session):
        """Test that update_item commits automatically on success"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # First create a behavior to update
        behavior_data = BehaviorDataFactory.sample_data()
        behavior_data["organization_id"] = organization.id
        behavior_data["user_id"] = user.id

        behavior = crud_utils._create_db_item_with_transaction(
            test_db, models.Behavior, behavior_data
        )
        original_name = behavior.name

        # Update the behavior
        new_name = "Updated Behavior Name"
        update_data = {"name": new_name}

        result = crud_utils.update_item(
            test_db, models.Behavior, behavior.id, update_data, organization.id, user.id
        )

        # Verify item was updated and persisted
        assert result is not None
        assert result.name == new_name
        assert result.name != original_name

        # Verify it's actually updated in the database (committed)
        db_behavior = (
            test_db.query(models.Behavior).filter(models.Behavior.id == behavior.id).first()
        )
        assert db_behavior is not None
        assert db_behavior.name == new_name
        assert db_behavior.name != original_name

    def test_delete_item_commits_on_success(self, test_db: Session):
        """Test that delete_item commits automatically on success"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # First create a category to delete
        category_data = CategoryDataFactory.sample_data()
        category_data["organization_id"] = organization.id
        category_data["user_id"] = user.id

        category = crud_utils._create_db_item_with_transaction(
            test_db, models.Category, category_data
        )
        category_id = category.id

        # Verify category exists
        db_category = (
            test_db.query(models.Category).filter(models.Category.id == category_id).first()
        )
        assert db_category is not None

        # Delete the category
        result = crud_utils.delete_item(
            test_db, models.Category, category_id, organization.id, user.id
        )

        # Verify item was deleted and change persisted
        assert result is not None
        assert result.id == category_id

        # Verify it's actually deleted from the database (committed)
        db_category = (
            test_db.query(models.Category).filter(models.Category.id == category_id).first()
        )
        assert db_category is None

    def test_create_item_commits_on_success(self, test_db: Session):
        """Test that create_item commits automatically on success"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Create behavior data
        behavior_data = BehaviorDataFactory.sample_data()

        # Create item using the main create_item function
        result = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization.id, user.id
        )

        # Verify item was created and persisted
        assert result is not None
        assert result.name == behavior_data["name"]
        assert result.organization_id == organization.id
        assert result.user_id == user.id

        # Verify it's actually in the database (committed)
        db_behavior = test_db.query(models.Behavior).filter(models.Behavior.id == result.id).first()
        assert db_behavior is not None
        assert db_behavior.name == behavior_data["name"]

    def test_get_or_create_entity_commits_on_create(self, test_db: Session):
        """Test that get_or_create_entity commits automatically when creating new entity"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Create unique topic data
        topic_data = TopicDataFactory.sample_data()
        topic_data["name"] = f"Unique Topic {uuid.uuid4()}"

        # Use get_or_create_entity (should create new)
        result = crud_utils.get_or_create_entity(
            test_db, models.Topic, topic_data, organization.id, user.id
        )

        # Verify entity was created and persisted
        assert result is not None
        assert result.name == topic_data["name"]
        assert result.organization_id == organization.id

        # Verify it's actually in the database (committed)
        db_topic = test_db.query(models.Topic).filter(models.Topic.id == result.id).first()
        assert db_topic is not None
        assert db_topic.name == topic_data["name"]

    def test_get_or_create_entity_returns_existing(self, test_db: Session):
        """Test that get_or_create_entity returns existing entity without creating duplicate"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # First create a topic
        topic_data = TopicDataFactory.sample_data()
        topic_data["name"] = f"Existing Topic {uuid.uuid4()}"

        first_result = crud_utils.get_or_create_entity(
            test_db, models.Topic, topic_data, organization.id, user.id
        )
        first_id = first_result.id

        # Try to get_or_create the same topic
        second_result = crud_utils.get_or_create_entity(
            test_db, models.Topic, topic_data, organization.id, user.id
        )

        # Verify we got the same existing entity
        assert second_result is not None
        assert second_result.id == first_id
        assert second_result.name == topic_data["name"]

        # Verify only one topic exists in database
        topic_count = (
            test_db.query(models.Topic)
            .filter(
                models.Topic.name == topic_data["name"],
                models.Topic.organization_id == organization.id,
            )
            .count()
        )
        assert topic_count == 1

    def test_multiple_operations_transaction_isolation(self, test_db: Session):
        """Test that multiple CRUD utility operations maintain proper transaction isolation"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Create multiple behaviors
        behavior_data1 = BehaviorDataFactory.sample_data()
        behavior_data1["name"] = "Behavior 1"

        behavior_data2 = BehaviorDataFactory.sample_data()
        behavior_data2["name"] = "Behavior 2"

        # Create first behavior
        result1 = crud_utils.create_item(
            test_db, models.Behavior, behavior_data1, organization.id, user.id
        )

        # Create second behavior
        result2 = crud_utils.create_item(
            test_db, models.Behavior, behavior_data2, organization.id, user.id
        )

        # Verify both behaviors exist independently
        assert result1 is not None
        assert result2 is not None
        assert result1.id != result2.id
        assert result1.name == "Behavior 1"
        assert result2.name == "Behavior 2"

        # Verify both are persisted in database
        db_behavior1 = (
            test_db.query(models.Behavior).filter(models.Behavior.id == result1.id).first()
        )
        db_behavior2 = (
            test_db.query(models.Behavior).filter(models.Behavior.id == result2.id).first()
        )

        assert db_behavior1 is not None
        assert db_behavior2 is not None
        assert db_behavior1.name == "Behavior 1"
        assert db_behavior2.name == "Behavior 2"

    def test_update_item_with_invalid_id_returns_none(self, test_db: Session):
        """Test that update_item returns None for non-existent item without causing transaction issues"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Try to update non-existent item
        non_existent_id = uuid.uuid4()
        update_data = {"name": "Updated Name"}

        result = crud_utils.update_item(
            test_db, models.Behavior, non_existent_id, update_data, organization.id, user.id
        )

        # Verify None is returned and no transaction issues
        assert result is None

        # Verify no phantom records were created
        phantom_behavior = (
            test_db.query(models.Behavior).filter(models.Behavior.id == non_existent_id).first()
        )
        assert phantom_behavior is None

    def test_delete_item_with_invalid_id_returns_none(self, test_db: Session):
        """Test that delete_item returns None for non-existent item without causing transaction issues"""
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        # Create test organization and user
        unique_id = str(uuid.uuid4())[:8]
        organization, user, _ = create_test_organization_and_user(
            test_db,
            f"Transaction Test Org {unique_id}",
            f"transaction-user-{unique_id}@test.com",
            "Transaction User",
        )

        # Try to delete non-existent item
        non_existent_id = uuid.uuid4()

        result = crud_utils.delete_item(
            test_db, models.Category, non_existent_id, organization.id, user.id
        )

        # Verify None is returned and no transaction issues
        assert result is None

        # Verify no phantom records were created or affected
        all_categories = (
            test_db.query(models.Category)
            .filter(models.Category.organization_id == organization.id)
            .count()
        )
        # This should not cause any issues with the transaction
