"""
Tests for model_utils functions.

These tests verify the current behavior of functions before they are refactored
to use the new direct parameter passing approach.
"""

from unittest.mock import ANY, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.query_utils import QueryBuilder


@pytest.mark.unit
@pytest.mark.utils
class TestQueryBuilder:
    """Test QueryBuilder class."""

    def test_query_builder_init_success(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test successful QueryBuilder initialization."""
        # Call the QueryBuilder constructor
        query_builder = QueryBuilder(test_db, models.Test)

        # Verify the query builder was created successfully
        assert query_builder.db == test_db
        assert query_builder.model == models.Test
        assert query_builder.query is not None
        assert query_builder._skip == 0
        assert query_builder._limit is None
        assert query_builder._sort_by is None
        assert query_builder._sort_order == "asc"

    def test_query_builder_init_with_error(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test QueryBuilder initialization raises exception when query creation fails."""

        # Mock db.query to fail
        def mock_query_side_effect(model):
            raise Exception("Query creation failed")

        with patch.object(test_db, "query", side_effect=mock_query_side_effect):
            # Call the QueryBuilder constructor - should raise exception
            with pytest.raises(Exception, match="Query creation failed"):
                QueryBuilder(test_db, models.Test)

    def test_with_joined_applies_joinedload_per_relationship(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """with_joined should call query.options(joinedload(...)) once per name."""
        query_builder = QueryBuilder(test_db, models.Test)
        original_query = MagicMock()
        query_builder.query = original_query
        # Each .options() returns the next stage of the query so the builder
        # picks it up on subsequent calls.
        stage1 = MagicMock()
        stage2 = MagicMock()
        original_query.options.return_value = stage1
        stage1.options.return_value = stage2

        result = query_builder.with_joined("prompt", "topic")

        assert result is query_builder
        assert original_query.options.call_count == 1
        assert stage1.options.call_count == 1
        assert query_builder.query is stage2
        assert query_builder._joined_count == 2

    def test_with_joined_rejects_unknown_relationship(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Unknown relationship names should fail loudly, not silently."""
        query_builder = QueryBuilder(test_db, models.Test)
        with pytest.raises(ValueError, match="not_a_real_relationship"):
            query_builder.with_joined("prompt", "not_a_real_relationship")

    def test_with_selectin_applies_selectinload_per_relationship(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """with_selectin should call query.options(selectinload(...)) once per name."""
        query_builder = QueryBuilder(test_db, models.Metric)
        original_query = MagicMock()
        query_builder.query = original_query
        stage1 = MagicMock()
        stage2 = MagicMock()
        original_query.options.return_value = stage1
        stage1.options.return_value = stage2

        result = query_builder.with_selectin("behaviors", "test_sets")

        assert result is query_builder
        assert query_builder.query is stage2
        assert query_builder._selectin_count == 2

    def test_with_selectin_rejects_unknown_relationship(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        query_builder = QueryBuilder(test_db, models.Metric)
        with pytest.raises(ValueError, match="not_a_real_m2m"):
            query_builder.with_selectin("behaviors", "not_a_real_m2m")

    def test_with_joined_and_selectin_empty_call_is_noop(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Calling with no relationship names should be a safe no-op."""
        query_builder = QueryBuilder(test_db, models.Test)
        original_query = MagicMock()
        query_builder.query = original_query

        query_builder.with_joined().with_selectin()

        original_query.options.assert_not_called()
        assert query_builder._joined_count == 0
        assert query_builder._selectin_count == 0

    def test_with_joined_warns_when_load_count_exceeds_threshold(
        self, test_db: Session, authenticated_user_id, test_org_id, caplog
    ):
        """Crossing the eager-load threshold should emit a warning."""
        import logging

        query_builder = QueryBuilder(test_db, models.Test)
        query_builder.query = MagicMock()
        # Make .options() return a fresh mock each time so chaining works.
        query_builder.query.options.return_value = query_builder.query

        # Test has 12 M2O relationships — exactly the threshold for the warning.
        with caplog.at_level(logging.WARNING):
            query_builder.with_joined(
                "prompt",
                "test_type",
                "user",
                "assignee",
                "owner",
                "parent",
                "topic",
                "behavior",
                "category",
                "status",
                "source",
                "organization",
            )

        assert any(
            "accumulated 12 eager loads" in record.message
            for record in caplog.records
        )

    def test_query_builder_with_optimized_loads(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test QueryBuilder with_optimized_loads method."""
        # Create QueryBuilder instance
        query_builder = QueryBuilder(test_db, models.Test)

        # Mock the apply_optimized_loads function
        with patch(
            "rhesis.backend.app.utils.query_utils.apply_optimized_loads"
        ) as mock_apply_optimized_loads:
            mock_modified_query = MagicMock()
            mock_apply_optimized_loads.return_value = mock_modified_query

            nested_relationships = {"test_set": {"prompts": None}}

            # Call with_optimized_loads
            result = query_builder.with_optimized_loads(
                skip_many_to_many=False,
                skip_one_to_many=True,
                nested_relationships=nested_relationships,
            )

            # Verify the method returns self and modifies the query
            assert result == query_builder
            assert query_builder.query == mock_modified_query

            # Verify apply_optimized_loads was called with correct parameters
            mock_apply_optimized_loads.assert_called_once_with(
                ANY, models.Test, False, True, nested_relationships
            )

    def test_query_builder_chaining(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test QueryBuilder method chaining across with_joined and with_optimized_loads."""
        query_builder = QueryBuilder(test_db, models.Test)
        original_query = MagicMock()
        query_builder.query = original_query
        stage1 = MagicMock()
        original_query.options.return_value = stage1

        with patch(
            "rhesis.backend.app.utils.query_utils.apply_optimized_loads"
        ) as mock_apply_optimized_loads:
            mock_final = MagicMock()
            mock_apply_optimized_loads.return_value = mock_final

            result = query_builder.with_joined("prompt").with_optimized_loads(
                skip_one_to_many=True
            )

            assert result is query_builder
            assert original_query.options.call_count == 1
            mock_apply_optimized_loads.assert_called_once()
            assert query_builder.query is mock_final

    def test_query_builder_state_isolation(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test that QueryBuilder instances are isolated from each other."""
        # Create two QueryBuilder instances
        query_builder_1 = QueryBuilder(test_db, models.Test)
        query_builder_2 = QueryBuilder(test_db, models.TestSet)

        # Verify they have different queries and models
        assert query_builder_1.query != query_builder_2.query
        assert query_builder_1.model != query_builder_2.model
        assert query_builder_1.model == models.Test
        assert query_builder_2.model == models.TestSet

        # Verify they have independent state
        query_builder_1._skip = 10
        query_builder_1._limit = 50

        assert query_builder_2._skip == 0
        assert query_builder_2._limit is None

    def test_query_builder_attributes_initialized(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test that QueryBuilder attributes are properly initialized."""
        query_builder = QueryBuilder(test_db, models.Prompt)

        # Verify all attributes are properly initialized
        assert query_builder.db == test_db
        assert query_builder.model == models.Prompt
        assert query_builder.query is not None
        assert query_builder._skip == 0
        assert query_builder._limit is None
        assert query_builder._sort_by is None
        assert query_builder._sort_order == "asc"

        # Verify the query is actually a query object for the correct model
        assert hasattr(query_builder.query, "filter")
        assert hasattr(query_builder.query, "first")
        assert hasattr(query_builder.query, "all")
