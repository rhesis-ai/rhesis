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

    def test_query_builder_with_joinedloads(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test QueryBuilder with_joinedloads method."""
        # Create QueryBuilder instance
        query_builder = QueryBuilder(test_db, models.Test)

        # Mock the apply_joinedloads function
        with patch(
            "rhesis.backend.app.utils.query_utils.apply_joinedloads"
        ) as mock_apply_joinedloads:
            mock_modified_query = MagicMock()
            mock_apply_joinedloads.return_value = mock_modified_query

            # Call with_joinedloads
            result = query_builder.with_joinedloads(skip_many_to_many=True, skip_one_to_many=False)

            # Verify the method returns self and modifies the query
            assert result == query_builder
            assert query_builder.query == mock_modified_query

            # Verify apply_joinedloads was called with correct parameters
            mock_apply_joinedloads.assert_called_once_with(ANY, models.Test, True, False)

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
        """Test QueryBuilder method chaining."""
        # Create QueryBuilder instance
        query_builder = QueryBuilder(test_db, models.Test)

        # Mock the functions used in chaining
        with (
            patch(
                "rhesis.backend.app.utils.query_utils.apply_joinedloads"
            ) as mock_apply_joinedloads,
            patch(
                "rhesis.backend.app.utils.query_utils.apply_optimized_loads"
            ) as mock_apply_optimized_loads,
        ):
            mock_query_1 = MagicMock()
            mock_query_2 = MagicMock()
            mock_apply_joinedloads.return_value = mock_query_1
            mock_apply_optimized_loads.return_value = mock_query_2

            # Chain multiple methods
            result = query_builder.with_joinedloads(skip_many_to_many=True).with_optimized_loads(
                skip_one_to_many=True
            )

            # Verify chaining works and returns the same instance
            assert result == query_builder

            # Verify both methods were called
            mock_apply_joinedloads.assert_called_once()
            mock_apply_optimized_loads.assert_called_once()

            # Verify the query was modified by the second method
            assert query_builder.query == mock_query_2

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
