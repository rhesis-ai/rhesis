"""
Tests for crud_utils functions.

These tests verify the current behavior of functions before they are refactored
to use the new direct parameter passing approach.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.utils import crud_utils

# Use existing data factories from the established pattern
from tests.backend.routes.fixtures.data_factories import (
    BehaviorDataFactory,
    CategoryDataFactory,
    TopicDataFactory,
)

fake = Faker()


# Use existing data factories instead of custom ones
def create_status_data(entity_type_id=None, **overrides):
    """Create status data using established patterns."""
    data = {"name": fake.word().title() + " Status"}
    if entity_type_id:
        data["entity_type_id"] = entity_type_id
    data.update(overrides)
    return data


def create_type_lookup_data(**overrides):
    """Create type lookup data using established patterns."""
    data = {"type_name": "TestType", "type_value": fake.word() + "_" + fake.word()}
    data.update(overrides)
    return data


def create_topic_data(**overrides):
    """Create topic data using existing factory."""
    data = TopicDataFactory.sample_data()
    data.update(overrides)
    return data


def create_category_data(**overrides):
    """Create category data using existing factory."""
    data = CategoryDataFactory.sample_data()
    data.update(overrides)
    return data


def create_behavior_data(**overrides):
    """Create behavior data using existing factory."""
    data = BehaviorDataFactory.sample_data()
    data.update(overrides)
    return data


@pytest.mark.unit
@pytest.mark.utils
class TestGetOrCreateEntity:
    """Test get_or_create_entity function."""

    def test_get_or_create_entity_create_new(
        self, test_db: Session, authenticated_user_id, test_org_id, test_entity_type
    ):
        """Test get_or_create_entity creates new entity when none exists."""
        entity_data = create_status_data(entity_type_id=test_entity_type.id)

        # Mock QueryBuilder and its methods
        with (
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
            patch("rhesis.backend.app.utils.crud_utils.create_item") as mock_create_item,
        ):
            # Setup mock query builder instance
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder
            mock_query_builder.first.return_value = None  # No existing entity found

            # Setup mock create_item
            mock_created_entity = MagicMock()
            mock_create_item.return_value = mock_created_entity

            # Call the function
            result = crud_utils.get_or_create_entity(
                db=test_db, model=models.Status, entity_data=entity_data, commit=True
            )

            # Verify result
            assert result == mock_created_entity

            # Verify QueryBuilder was created and configured
            mock_query_builder_class.assert_called_once_with(test_db, models.Status)
            mock_query_builder.with_organization_filter.assert_called_once()
            mock_query_builder.with_visibility_filter.assert_called_once()

            # Verify create_item was called with new signature (includes organization_id, user_id)
            mock_create_item.assert_called_once_with(
                test_db, models.Status, entity_data, None, None, commit=True
            )

    def test_get_or_create_entity_find_existing_by_id(
        self, test_db: Session, authenticated_user_id, test_org_id, test_entity_type
    ):
        """Test get_or_create_entity finds existing entity by ID."""
        entity_id = uuid.uuid4()
        entity_data = create_status_data(entity_type_id=test_entity_type.id)
        entity_data["id"] = entity_id

        # Mock QueryBuilder and its methods
        with (
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
            patch(
                "rhesis.backend.app.utils.crud_utils._build_search_filters_for_model"
            ) as mock_build_filters,
        ):
            # Setup mock query builder instance
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder

            # Mock existing entity found by ID
            mock_existing_entity = MagicMock()
            mock_query_builder.first.return_value = mock_existing_entity

            # Mock search filters
            mock_build_filters.return_value = []

            # Call the function
            result = crud_utils.get_or_create_entity(
                db=test_db, model=models.Status, entity_data=entity_data, commit=True
            )

            # Verify result
            assert result == mock_existing_entity

            # Verify QueryBuilder was used
            mock_query_builder_class.assert_called_once_with(test_db, models.Status)
            mock_query_builder.with_organization_filter.assert_called_once()
            mock_query_builder.with_visibility_filter.assert_called_once()

            # Verify search filters were built for ID lookup
            mock_build_filters.assert_called_once_with(models.Status, entity_data)

    def test_get_or_create_entity_find_existing_by_name(
        self, test_db: Session, authenticated_user_id, test_org_id, test_entity_type
    ):
        """Test get_or_create_entity finds existing entity by identifying fields."""
        entity_data = create_status_data(entity_type_id=test_entity_type.id)

        # Mock QueryBuilder and its methods
        with (
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
            patch(
                "rhesis.backend.app.utils.crud_utils._build_search_filters_for_model"
            ) as mock_build_filters,
        ):
            # Setup mock query builder instance
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder

            # Mock existing entity found by name (no ID in entity_data so only one call to first())
            mock_existing_entity = MagicMock()
            mock_query_builder.first.return_value = mock_existing_entity

            # Mock search filters (at least one filter for identifying fields)
            mock_build_filters.return_value = [MagicMock()]  # At least one filter

            # Call the function
            result = crud_utils.get_or_create_entity(
                db=test_db, model=models.Status, entity_data=entity_data, commit=True
            )

            # Verify result
            assert result == mock_existing_entity

            # Verify QueryBuilder was used
            mock_query_builder_class.assert_called_once_with(test_db, models.Status)
            mock_query_builder.with_organization_filter.assert_called_once()
            mock_query_builder.with_visibility_filter.assert_called_once()

            # Verify search filters were built once (no ID in data, so only identifying fields lookup)
            assert mock_build_filters.call_count == 1


@pytest.mark.unit
@pytest.mark.utils
class TestGetOrCreateSpecializedFunctions:
    """Test specialized get_or_create functions."""

    def test_get_or_create_status_success(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test successful get_or_create_status operation."""
        status_name = "active"
        entity_type = EntityType.TEST

        # Mock dependencies
        with (
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_type_lookup") as mock_get_type,
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
            patch("rhesis.backend.app.utils.crud_utils.create_item") as mock_create_item,
        ):
            # Setup mock type lookup
            mock_type_lookup = MagicMock()
            mock_type_lookup.id = uuid.uuid4()
            mock_get_type.return_value = mock_type_lookup

            # Setup mock query builder
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder
            mock_query_builder.first.return_value = None  # No existing status found

            # Setup mock create_item
            mock_created_status = MagicMock()
            mock_create_item.return_value = mock_created_status

            # Call the function
            result = crud_utils.get_or_create_status(
                db=test_db, name=status_name, entity_type=entity_type, commit=True
            )

            # Verify result
            assert result == mock_created_status

            # Verify get_or_create_type_lookup was called
            mock_get_type.assert_called_once_with(
                db=test_db,
                type_name="EntityType",
                type_value=entity_type.value,
                organization_id=None,
                user_id=None,
                commit=True,
            )

            # Verify create_item was called with correct data
            mock_create_item.assert_called_once_with(
                db=test_db,
                model=models.Status,
                item_data={"name": status_name, "entity_type_id": mock_type_lookup.id},
                organization_id=None,
                user_id=None,
                commit=True,
            )

    def test_get_or_create_status_existing(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test get_or_create_status finds existing status."""
        status_name = "active"
        entity_type = EntityType.TEST

        # Mock dependencies
        with (
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_type_lookup") as mock_get_type,
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
        ):
            # Setup mock type lookup
            mock_type_lookup = MagicMock()
            mock_type_lookup.id = uuid.uuid4()
            mock_get_type.return_value = mock_type_lookup

            # Setup mock query builder
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder

            # Mock existing status found
            mock_existing_status = MagicMock()
            mock_query_builder.first.return_value = mock_existing_status

            # Call the function
            result = crud_utils.get_or_create_status(
                db=test_db, name=status_name, entity_type=entity_type, commit=True
            )

            # Verify result
            assert result == mock_existing_status

            # Verify get_or_create_type_lookup was called
            mock_get_type.assert_called_once_with(
                db=test_db,
                type_name="EntityType",
                type_value=entity_type.value,
                organization_id=None,
                user_id=None,
                commit=True,
            )

    def test_get_or_create_type_lookup_success(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test successful get_or_create_type_lookup operation."""
        type_name = "TestType"
        type_value = "test_value"

        # Mock dependencies
        with (
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
            patch("rhesis.backend.app.utils.crud_utils.create_item") as mock_create_item,
        ):
            # Setup mock query builder
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder
            mock_query_builder.first.return_value = None  # No existing type found

            # Setup mock create_item
            mock_created_type = MagicMock()
            mock_create_item.return_value = mock_created_type

            # Call the function
            result = crud_utils.get_or_create_type_lookup(
                db=test_db, type_name=type_name, type_value=type_value, commit=True
            )

            # Verify result
            assert result == mock_created_type

            # Verify create_item was called with correct data
            mock_create_item.assert_called_once_with(
                db=test_db,
                model=models.TypeLookup,
                item_data={"type_name": type_name, "type_value": type_value},
                organization_id=None,
                user_id=None,
                commit=True,
            )

    def test_get_or_create_type_lookup_with_description(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test get_or_create_type_lookup with description parameter."""
        type_name = "TestType"
        type_value = "test_value"
        description = "Test description"

        # Mock dependencies
        with (
            patch("rhesis.backend.app.utils.crud_utils.QueryBuilder") as mock_query_builder_class,
            patch("rhesis.backend.app.utils.crud_utils.create_item") as mock_create_item,
        ):
            # Setup mock query builder
            mock_query_builder = MagicMock()
            mock_query_builder_class.return_value = mock_query_builder
            mock_query_builder.with_organization_filter.return_value = mock_query_builder
            mock_query_builder.with_visibility_filter.return_value = mock_query_builder
            mock_query_builder.with_custom_filter.return_value = mock_query_builder
            mock_query_builder.first.return_value = None  # No existing type found

            # Setup mock create_item
            mock_created_type = MagicMock()
            mock_create_item.return_value = mock_created_type

            # Call the function with description
            result = crud_utils.get_or_create_type_lookup(
                db=test_db,
                type_name=type_name,
                type_value=type_value,
                organization_id=str(test_org_id),
                user_id=str(authenticated_user_id),
                commit=True,
                description=description,
            )

            # Verify result
            assert result == mock_created_type

            # Verify create_item was called with correct data including description
            mock_create_item.assert_called_once_with(
                db=test_db,
                model=models.TypeLookup,
                item_data={
                    "type_name": type_name,
                    "type_value": type_value,
                    "description": description,
                },
                organization_id=str(test_org_id),
                user_id=str(authenticated_user_id),
                commit=True,
            )

    def test_get_or_create_topic_with_all_params(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test get_or_create_topic with all optional parameters."""
        topic_name = "Test Topic"
        entity_type = "test"
        description = "Test description"
        status = "active"

        # Mock dependencies
        with (
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_type_lookup") as mock_get_type,
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_status") as mock_get_status,
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_entity") as mock_get_entity,
        ):
            # Setup mock type lookup
            mock_type_lookup = MagicMock()
            mock_type_lookup.id = uuid.uuid4()
            mock_get_type.return_value = mock_type_lookup

            # Setup mock status
            mock_status_obj = MagicMock()
            mock_status_obj.id = uuid.uuid4()
            mock_get_status.return_value = mock_status_obj

            # Setup mock entity
            mock_topic = MagicMock()
            mock_get_entity.return_value = mock_topic

            # Call the function
            result = crud_utils.get_or_create_topic(
                db=test_db,
                name=topic_name,
                entity_type=entity_type,
                description=description,
                status=status,
                commit=True,
            )

            # Verify result
            assert result == mock_topic

            # Verify get_or_create_type_lookup was called (now includes organization_id and user_id)
            mock_get_type.assert_called_once_with(
                db=test_db,
                type_name="EntityType",
                type_value=entity_type,
                organization_id=None,
                user_id=None,
                commit=True,
            )

            # Verify get_or_create_status was called (now includes organization_id and user_id)
            mock_get_status.assert_called_once_with(
                db=test_db,
                name=status,
                entity_type=EntityType.GENERAL,
                organization_id=None,
                user_id=None,
                commit=True,
            )

            # Verify get_or_create_entity was called with complete data
            expected_topic_data = {
                "name": topic_name,
                "description": description,
                "entity_type_id": mock_type_lookup.id,
                "status_id": mock_status_obj.id,
            }
            mock_get_entity.assert_called_once_with(
                test_db, models.Topic, expected_topic_data, None, None, commit=True
            )

    def test_get_or_create_category_minimal_params(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test get_or_create_category with minimal parameters."""
        category_name = "Test Category"

        # Mock dependencies
        with patch("rhesis.backend.app.utils.crud_utils.get_or_create_entity") as mock_get_entity:
            # Setup mock entity
            mock_category = MagicMock()
            mock_get_entity.return_value = mock_category

            # Call the function
            result = crud_utils.get_or_create_category(db=test_db, name=category_name, commit=True)

            # Verify result
            assert result == mock_category

            # Verify get_or_create_entity was called with minimal data
            expected_category_data = {"name": category_name}
            mock_get_entity.assert_called_once_with(
                test_db, models.Category, expected_category_data, None, None, commit=True
            )

    def test_get_or_create_behavior_with_description_and_status(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test get_or_create_behavior with description and status."""
        behavior_name = "Test Behavior"
        description = "Test description"
        status = "active"

        # Mock dependencies
        with (
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_status") as mock_get_status,
            patch("rhesis.backend.app.utils.crud_utils.get_or_create_entity") as mock_get_entity,
        ):
            # Setup mock status
            mock_status_obj = MagicMock()
            mock_status_obj.id = uuid.uuid4()
            mock_get_status.return_value = mock_status_obj

            # Setup mock entity
            mock_behavior = MagicMock()
            mock_get_entity.return_value = mock_behavior

            # Call the function
            result = crud_utils.get_or_create_behavior(
                db=test_db, name=behavior_name, description=description, status=status, commit=True
            )

            # Verify result
            assert result == mock_behavior

            # Verify get_or_create_status was called (now includes organization_id and user_id)
            mock_get_status.assert_called_once_with(
                db=test_db,
                name=status,
                entity_type=EntityType.GENERAL,
                organization_id=None,
                user_id=None,
                commit=True,
            )

            # Verify get_or_create_entity was called with complete data
            expected_behavior_data = {
                "name": behavior_name,
                "description": description,
                "status_id": mock_status_obj.id,
            }
            mock_get_entity.assert_called_once_with(
                test_db, models.Behavior, expected_behavior_data, None, None, commit=True
            )
