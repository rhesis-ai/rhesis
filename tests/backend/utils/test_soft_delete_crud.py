"""
Tests for soft deletion functionality in crud_utils.

These tests verify the soft deletion behavior including:
- Soft delete operations
- Automatic filtering of deleted records
- Restoration of deleted records
- Hard deletion
- Integration with existing CRUD operations
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils import crud_utils
from rhesis.backend.app.utils.model_utils import QueryBuilder
from rhesis.backend.app.database import without_soft_delete_filter

# Use existing data factories
from tests.backend.routes.fixtures.data_factories import (
    BehaviorDataFactory,
    TopicDataFactory,
    CategoryDataFactory,
)


@pytest.mark.unit
@pytest.mark.utils
class TestSoftDeletion:
    """Test soft deletion functionality in CRUD utilities."""

    def test_delete_item_performs_soft_delete(self, test_db: Session, test_org_id):
        """Test that delete_item performs soft deletion instead of hard deletion."""
        # Create a behavior for testing
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        # Soft delete the behavior
        deleted = crud_utils.delete_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id
        )

        # Verify item was returned
        assert deleted is not None
        assert deleted.id == behavior_id
        assert deleted.deleted_at is not None
        assert isinstance(deleted.deleted_at, datetime)

        # Verify item raises ItemDeletedException in normal queries
        from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

        with pytest.raises(ItemDeletedException):
            crud_utils.get_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Verify item still exists in database with deleted_at set
        with without_soft_delete_filter():
            found_with_deleted = crud_utils.get_item(
                test_db,
                models.Behavior,
                behavior_id,
                organization_id=test_org_id,
                include_deleted=True,
            )
            assert found_with_deleted is not None
            assert found_with_deleted.deleted_at is not None

    def test_delete_item_returns_none_if_not_found(self, test_db: Session, test_org_id):
        """Test that delete_item returns None if item doesn't exist."""
        non_existent_id = uuid.uuid4()

        result = crud_utils.delete_item(
            test_db, models.Behavior, non_existent_id, organization_id=test_org_id
        )

        assert result is None

    def test_get_item_excludes_deleted_by_default(self, test_db: Session, test_org_id):
        """Test that get_item raises exception for soft-deleted items by default."""
        from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

        # Create and delete a behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        crud_utils.delete_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Try to get the deleted item - should raise exception
        with pytest.raises(ItemDeletedException):
            crud_utils.get_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

    def test_get_item_includes_deleted_when_requested(self, test_db: Session, test_org_id):
        """Test that get_item can include soft-deleted items when requested."""
        # Create and delete a behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        crud_utils.delete_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Get the deleted item with include_deleted=True
        found = crud_utils.get_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id, include_deleted=True
        )

        assert found is not None
        assert found.id == behavior_id
        assert found.deleted_at is not None

    def test_get_deleted_items_returns_only_deleted(self, test_db: Session, test_org_id):
        """Test that get_deleted_items returns only soft-deleted items."""
        # Create multiple behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior1 = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior2 = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        # Delete some behaviors
        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior1.id, organization_id=test_org_id
        )
        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior2.id, organization_id=test_org_id
        )

        # Get deleted items
        deleted_items = crud_utils.get_deleted_items(
            test_db, models.Behavior, organization_id=test_org_id
        )

        deleted_ids = [item.id for item in deleted_items]

        # Verify only deleted items are returned
        assert len(deleted_items) >= 2  # At least our two deleted items
        assert deleted_behavior1.id in deleted_ids
        assert deleted_behavior2.id in deleted_ids
        assert active_behavior.id not in deleted_ids

        # Verify all returned items have deleted_at set
        for item in deleted_items:
            assert item.deleted_at is not None

    def test_restore_item_restores_deleted_record(self, test_db: Session, test_org_id):
        """Test that restore_item successfully restores a soft-deleted record."""
        # Create and delete a behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        crud_utils.delete_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Restore the behavior
        restored = crud_utils.restore_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id
        )

        # Verify restoration
        assert restored is not None
        assert restored.id == behavior_id
        assert restored.deleted_at is None

        # Verify item is now returned in normal queries
        found = crud_utils.get_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id
        )
        assert found is not None
        assert found.id == behavior_id
        assert found.deleted_at is None

    def test_restore_item_returns_none_if_not_found(self, test_db: Session, test_org_id):
        """Test that restore_item returns None if item doesn't exist."""
        non_existent_id = uuid.uuid4()

        result = crud_utils.restore_item(
            test_db, models.Behavior, non_existent_id, organization_id=test_org_id
        )

        assert result is None

    def test_restore_item_works_on_non_deleted_items(self, test_db: Session, test_org_id):
        """Test that restore_item works on items that aren't deleted (idempotent)."""
        # Create an active behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        # Try to restore (should be a no-op)
        restored = crud_utils.restore_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id
        )

        # Verify it returns the item
        assert restored is not None
        assert restored.id == behavior_id
        assert restored.deleted_at is None

    def test_hard_delete_item_permanently_deletes(self, test_db: Session, test_org_id):
        """Test that hard_delete_item permanently removes record from database."""
        # Create a behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        # Hard delete the behavior
        success = crud_utils.hard_delete_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id
        )

        assert success is True

        # Verify item is completely gone
        with without_soft_delete_filter():
            found = crud_utils.get_item(
                test_db,
                models.Behavior,
                behavior_id,
                organization_id=test_org_id,
                include_deleted=True,
            )
            assert found is None

    def test_hard_delete_soft_deleted_item(self, test_db: Session, test_org_id):
        """Test that hard_delete_item can delete already soft-deleted items."""
        # Create and soft delete a behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        crud_utils.delete_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Hard delete the soft-deleted behavior
        success = crud_utils.hard_delete_item(
            test_db, models.Behavior, behavior_id, organization_id=test_org_id
        )

        assert success is True

        # Verify item is completely gone
        with without_soft_delete_filter():
            found = crud_utils.get_item(
                test_db,
                models.Behavior,
                behavior_id,
                organization_id=test_org_id,
                include_deleted=True,
            )
            assert found is None

    def test_hard_delete_returns_false_if_not_found(self, test_db: Session, test_org_id):
        """Test that hard_delete_item returns False if item doesn't exist."""
        non_existent_id = uuid.uuid4()

        result = crud_utils.hard_delete_item(
            test_db, models.Behavior, non_existent_id, organization_id=test_org_id
        )

        assert result is False

    def test_soft_delete_multiple_records(self, test_db: Session, test_org_id):
        """Test soft deleting multiple records and querying them."""
        # Create multiple topics
        topics = []
        for _ in range(5):
            topic_data = TopicDataFactory.sample_data()
            topic = crud_utils.create_item(
                test_db, models.Topic, topic_data, organization_id=test_org_id
            )
            topics.append(topic)

        # Delete 3 of them
        for i in range(3):
            crud_utils.delete_item(test_db, models.Topic, topics[i].id, organization_id=test_org_id)

        # Get all topics (should exclude deleted)
        all_topics_query = (
            QueryBuilder(test_db, models.Topic).with_organization_filter(test_org_id).all()
        )

        # Should have 2 active topics
        active_ids = [t.id for t in all_topics_query]
        assert len([t for t in all_topics_query if t.deleted_at is None]) >= 2
        assert topics[3].id in active_ids
        assert topics[4].id in active_ids

        # Get deleted topics
        deleted_topics = crud_utils.get_deleted_items(
            test_db, models.Topic, organization_id=test_org_id
        )

        deleted_ids = [t.id for t in deleted_topics]
        assert len(deleted_ids) >= 3
        assert topics[0].id in deleted_ids
        assert topics[1].id in deleted_ids
        assert topics[2].id in deleted_ids


@pytest.mark.unit
@pytest.mark.utils
class TestSoftDeleteContext:
    """Test the without_soft_delete_filter context manager."""

    def test_without_soft_delete_filter_includes_deleted(self, test_db: Session, test_org_id):
        """Test that context manager allows querying deleted records."""
        # Create and delete a category
        category_data = CategoryDataFactory.sample_data()
        category = crud_utils.create_item(
            test_db, models.Category, category_data, organization_id=test_org_id
        )
        category_id = category.id

        crud_utils.delete_item(test_db, models.Category, category_id, organization_id=test_org_id)

        # Normal query should not find it
        normal_query = (
            QueryBuilder(test_db, models.Category)
            .with_organization_filter(test_org_id)
            .filter_by_id(category_id)
        )
        assert normal_query is None

        # Query with context manager should find it
        with without_soft_delete_filter():
            with_deleted_query = (
                QueryBuilder(test_db, models.Category)
                .with_organization_filter(test_org_id)
                .with_deleted()
                .filter_by_id(category_id)
            )
            assert with_deleted_query is not None
            assert with_deleted_query.id == category_id
            assert with_deleted_query.deleted_at is not None

    def test_context_manager_is_reentrant(self, test_db: Session, test_org_id):
        """Test that context manager can be nested."""
        # Create and delete a behavior
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )
        behavior_id = behavior.id

        crud_utils.delete_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Nested context managers
        with without_soft_delete_filter():
            with without_soft_delete_filter():
                found = crud_utils.get_item(
                    test_db,
                    models.Behavior,
                    behavior_id,
                    organization_id=test_org_id,
                    include_deleted=True,
                )
                assert found is not None
                assert found.deleted_at is not None

        # Outside context, should raise exception for deleted item
        from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

        with pytest.raises(ItemDeletedException):
            crud_utils.get_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)


@pytest.mark.unit
@pytest.mark.utils
class TestBaseModelSoftDeleteMethods:
    """Test soft delete methods on the Base model."""

    def test_is_deleted_property_false_for_active(self, test_db: Session, test_org_id):
        """Test that is_deleted returns False for active records."""
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )

        assert behavior.is_deleted is False
        assert behavior.deleted_at is None

    def test_is_deleted_property_true_for_deleted(self, test_db: Session, test_org_id):
        """Test that is_deleted returns True for soft-deleted records."""
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )

        # Soft delete
        behavior.soft_delete()
        test_db.commit()

        assert behavior.is_deleted is True
        assert behavior.deleted_at is not None
        assert isinstance(behavior.deleted_at, datetime)

    def test_soft_delete_method_sets_timestamp(self, test_db: Session, test_org_id):
        """Test that soft_delete() method sets deleted_at timestamp."""
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )

        before_delete = datetime.now(timezone.utc)
        behavior.soft_delete()
        after_delete = datetime.now(timezone.utc)
        test_db.commit()

        assert behavior.deleted_at is not None
        assert before_delete <= behavior.deleted_at <= after_delete

    def test_restore_method_clears_timestamp(self, test_db: Session, test_org_id):
        """Test that restore() method clears deleted_at timestamp."""
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )

        # Soft delete
        behavior.soft_delete()
        test_db.commit()
        assert behavior.deleted_at is not None

        # Restore
        behavior.restore()
        test_db.commit()

        assert behavior.deleted_at is None
        assert behavior.is_deleted is False

    def test_multiple_soft_delete_calls_update_timestamp(self, test_db: Session, test_org_id):
        """Test that calling soft_delete multiple times updates the timestamp."""
        behavior_data = BehaviorDataFactory.sample_data()
        behavior = crud_utils.create_item(
            test_db, models.Behavior, behavior_data, organization_id=test_org_id
        )

        # First soft delete
        behavior.soft_delete()
        test_db.commit()
        first_deleted_at = behavior.deleted_at

        # Restore
        behavior.restore()
        test_db.commit()

        # Second soft delete (after a brief moment)
        import time

        time.sleep(0.01)  # Small delay to ensure different timestamp
        behavior.soft_delete()
        test_db.commit()
        second_deleted_at = behavior.deleted_at

        assert first_deleted_at is not None
        assert second_deleted_at is not None
        assert second_deleted_at >= first_deleted_at
