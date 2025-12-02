"""
Tests for soft deletion functionality in QueryBuilder.

These tests verify the QueryBuilder's soft deletion capabilities including:
- with_deleted() method for including soft-deleted records
- only_deleted() method for querying only deleted records
- Integration with event listener
- Method chaining with other QueryBuilder methods
"""

import pytest
from datetime import datetime
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
class TestQueryBuilderSoftDelete:
    """Test QueryBuilder soft deletion methods."""

    def test_default_query_excludes_deleted(self, test_db: Session, test_org_id):
        """Test that default QueryBuilder queries exclude soft-deleted records."""
        # Create active and deleted behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Query without any soft delete method
        results = QueryBuilder(test_db, models.Behavior).with_organization_filter(test_org_id).all()

        result_ids = [b.id for b in results]

        # Should include active, not deleted
        assert active_behavior.id in result_ids
        assert deleted_behavior.id not in result_ids

    def test_with_deleted_includes_all_records(self, test_db: Session, test_org_id):
        """Test that with_deleted() includes both active and soft-deleted records."""
        # Create active and deleted behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Query with with_deleted()
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .all()
        )

        result_ids = [b.id for b in results]

        # Should include both active and deleted
        assert active_behavior.id in result_ids
        assert deleted_behavior.id in result_ids

    def test_only_deleted_returns_only_deleted_records(self, test_db: Session, test_org_id):
        """Test that only_deleted() returns only soft-deleted records."""
        # Create active and deleted behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Query with only_deleted()
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .only_deleted()
            .all()
        )

        result_ids = [b.id for b in results]

        # Should only include deleted, not active
        assert active_behavior.id not in result_ids
        assert deleted_behavior.id in result_ids

        # Verify all results have deleted_at set
        for behavior in results:
            assert behavior.deleted_at is not None

    def test_with_deleted_chains_with_filters(self, test_db: Session, test_org_id):
        """Test that with_deleted() chains properly with other filters."""
        # Create behaviors with specific names
        active_behavior = crud_utils.create_item(
            test_db,
            models.Behavior,
            {**BehaviorDataFactory.sample_data(), "name": "Active Behavior Test"},
            organization_id=test_org_id,
        )

        deleted_behavior = crud_utils.create_item(
            test_db,
            models.Behavior,
            {**BehaviorDataFactory.sample_data(), "name": "Deleted Behavior Test"},
            organization_id=test_org_id,
        )

        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Query with multiple filters including with_deleted()
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .with_custom_filter(lambda q: q.filter(models.Behavior.name.like("%Test%")))
            .all()
        )

        result_ids = [b.id for b in results]

        # Should include both because both match the filter
        assert len(result_ids) >= 2
        assert active_behavior.id in result_ids
        assert deleted_behavior.id in result_ids

    def test_only_deleted_chains_with_pagination(self, test_db: Session, test_org_id):
        """Test that only_deleted() chains with pagination methods."""
        # Create and delete multiple behaviors
        deleted_behaviors = []
        for i in range(5):
            behavior = crud_utils.create_item(
                test_db,
                models.Behavior,
                BehaviorDataFactory.sample_data(),
                organization_id=test_org_id,
            )
            crud_utils.delete_item(
                test_db, models.Behavior, behavior.id, organization_id=test_org_id
            )
            deleted_behaviors.append(behavior)

        # Query with pagination
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .only_deleted()
            .with_pagination(skip=1, limit=2)
            .all()
        )

        # Should have at most 2 results (limit)
        assert len(results) <= 2

        # All should be deleted
        for behavior in results:
            assert behavior.deleted_at is not None

    def test_only_deleted_chains_with_sorting(self, test_db: Session, test_org_id):
        """Test that only_deleted() chains with sorting methods."""
        # Create and delete multiple behaviors
        import time

        deleted_behaviors = []
        for i in range(3):
            behavior = crud_utils.create_item(
                test_db,
                models.Behavior,
                BehaviorDataFactory.sample_data(),
                organization_id=test_org_id,
            )
            crud_utils.delete_item(
                test_db, models.Behavior, behavior.id, organization_id=test_org_id
            )
            deleted_behaviors.append(behavior)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Query with sorting by deleted_at descending
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .only_deleted()
            .with_sorting("deleted_at", "desc")
            .all()
        )

        # Should have at least our 3 deleted behaviors
        result_ids = [b.id for b in results]
        assert len([b for b in deleted_behaviors if b.id in result_ids]) >= 3

        # Verify sorting (most recently deleted first)
        # Convert both to timestamps for comparison to avoid timezone issues
        if len(results) >= 2:
            for i in range(len(results) - 1):
                time1 = (
                    results[i].deleted_at.timestamp()
                    if hasattr(results[i].deleted_at, "timestamp")
                    else results[i].deleted_at
                )
                time2 = (
                    results[i + 1].deleted_at.timestamp()
                    if hasattr(results[i + 1].deleted_at, "timestamp")
                    else results[i + 1].deleted_at
                )
                assert time1 >= time2

    def test_filter_by_id_respects_soft_delete(self, test_db: Session, test_org_id):
        """Test that filter_by_id respects soft delete filtering."""
        # Create and delete a behavior
        behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        behavior_id = behavior.id

        crud_utils.delete_item(test_db, models.Behavior, behavior_id, organization_id=test_org_id)

        # Query by ID without with_deleted() should return None
        result = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .filter_by_id(behavior_id)
        )

        assert result is None

        # Query by ID with with_deleted() should find it
        result_with_deleted = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .filter_by_id(behavior_id)
        )

        assert result_with_deleted is not None
        assert result_with_deleted.id == behavior_id

    def test_count_respects_soft_delete_filtering(self, test_db: Session, test_org_id):
        """Test that count operations respect soft delete filtering."""
        # Create active and deleted topics
        active_count = 3
        deleted_count = 2

        # Create active topics
        for _ in range(active_count):
            crud_utils.create_item(
                test_db, models.Topic, TopicDataFactory.sample_data(), organization_id=test_org_id
            )

        # Create and delete topics
        for _ in range(deleted_count):
            topic = crud_utils.create_item(
                test_db, models.Topic, TopicDataFactory.sample_data(), organization_id=test_org_id
            )
            crud_utils.delete_item(test_db, models.Topic, topic.id, organization_id=test_org_id)

        # Default count should only include active
        default_results = (
            QueryBuilder(test_db, models.Topic).with_organization_filter(test_org_id).all()
        )
        default_count = len([t for t in default_results if t.deleted_at is None])
        assert default_count >= active_count

        # Count with with_deleted should include both
        with_deleted_results = (
            QueryBuilder(test_db, models.Topic)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .all()
        )
        total_count = len(with_deleted_results)
        assert total_count >= (active_count + deleted_count)

        # Count with only_deleted should only include deleted
        only_deleted_results = (
            QueryBuilder(test_db, models.Topic)
            .with_organization_filter(test_org_id)
            .only_deleted()
            .all()
        )
        deleted_only_count = len(only_deleted_results)
        assert deleted_only_count >= deleted_count


@pytest.mark.unit
@pytest.mark.utils
class TestQueryBuilderWithEventListener:
    """Test QueryBuilder interaction with soft delete event listener."""

    def test_event_listener_applies_automatic_filtering(self, test_db: Session, test_org_id):
        """Test that event listener automatically filters soft-deleted records."""
        # Create and delete a category
        category = crud_utils.create_item(
            test_db, models.Category, CategoryDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(test_db, models.Category, category.id, organization_id=test_org_id)

        # Raw query without QueryBuilder should still filter
        raw_query = (
            test_db.query(models.Category)
            .filter(models.Category.organization_id == test_org_id)
            .all()
        )

        raw_ids = [c.id for c in raw_query]
        assert category.id not in raw_ids

    def test_with_deleted_overrides_event_listener(self, test_db: Session, test_org_id):
        """Test that with_deleted() properly overrides event listener filtering."""
        # Create and delete a category
        category = crud_utils.create_item(
            test_db, models.Category, CategoryDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(test_db, models.Category, category.id, organization_id=test_org_id)

        # Query with with_deleted() should find it despite event listener
        results = (
            QueryBuilder(test_db, models.Category)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .all()
        )

        result_ids = [c.id for c in results]
        assert category.id in result_ids

    def test_context_manager_overrides_event_listener(self, test_db: Session, test_org_id):
        """Test that without_soft_delete_filter context manager overrides event listener."""
        # Create and delete a behavior
        behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(test_db, models.Behavior, behavior.id, organization_id=test_org_id)

        # Within context, even regular queries should see deleted records
        with without_soft_delete_filter():
            results = (
                test_db.query(models.Behavior)
                .filter(models.Behavior.organization_id == test_org_id)
                .all()
            )

            result_ids = [b.id for b in results]
            assert behavior.id in result_ids

    def test_multiple_entities_in_query_all_filtered(self, test_db: Session, test_org_id):
        """Test that queries with multiple entities filter soft-deleted records."""
        # Create multiple behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        # Delete one behavior
        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Direct query should filter out deleted records
        results = (
            test_db.query(models.Behavior)
            .filter(models.Behavior.organization_id == test_org_id)
            .all()
        )

        result_ids = [b.id for b in results]
        # Should only include active behavior
        assert active_behavior.id in result_ids
        assert deleted_behavior.id not in result_ids


@pytest.mark.unit
@pytest.mark.utils
class TestQueryBuilderEdgeCases:
    """Test edge cases and error conditions for QueryBuilder soft deletion."""

    def test_with_deleted_on_empty_table(self, test_db: Session, test_org_id):
        """Test with_deleted() on a table with no records."""
        # Query topics with with_deleted() when there are none
        results = (
            QueryBuilder(test_db, models.Topic)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .all()
        )

        # Should return empty list, not error
        assert isinstance(results, list)

    def test_only_deleted_on_empty_table(self, test_db: Session, test_org_id):
        """Test only_deleted() on a table with no records."""
        # Query categories with only_deleted() when there are none
        results = (
            QueryBuilder(test_db, models.Category)
            .with_organization_filter(test_org_id)
            .only_deleted()
            .all()
        )

        # Should return empty list, not error
        assert isinstance(results, list)

    def test_chain_with_deleted_and_only_deleted(self, test_db: Session, test_org_id):
        """Test that chaining with_deleted and only_deleted uses the last one."""
        # Create active and deleted behaviors
        active_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        deleted_behavior = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )

        crud_utils.delete_item(
            test_db, models.Behavior, deleted_behavior.id, organization_id=test_org_id
        )

        # Chain with_deleted() then only_deleted()
        # Last call should take precedence
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_deleted()
            .only_deleted()
            .all()
        )

        result_ids = [b.id for b in results]

        # Should only show deleted (last method wins)
        assert active_behavior.id not in result_ids
        assert deleted_behavior.id in result_ids

    def test_first_with_soft_delete_filtering(self, test_db: Session, test_org_id):
        """Test that first() method respects soft delete filtering."""
        # Create multiple behaviors and delete one
        behaviors = []
        for i in range(3):
            behavior = crud_utils.create_item(
                test_db,
                models.Behavior,
                {**BehaviorDataFactory.sample_data(), "name": f"Behavior {i}"},
                organization_id=test_org_id,
            )
            behaviors.append(behavior)

        # Delete the first one
        crud_utils.delete_item(
            test_db, models.Behavior, behaviors[0].id, organization_id=test_org_id
        )

        # first() should skip the deleted one
        first_result = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_sorting("name", "asc")
            .first()
        )

        # Should not be the deleted behavior
        if first_result:
            assert first_result.id != behaviors[0].id
            assert first_result.deleted_at is None
