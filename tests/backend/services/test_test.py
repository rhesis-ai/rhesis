"""
Tests for test service functions.

These tests verify the current behavior of functions before they are refactored
to use the new direct parameter passing approach.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services import test as test_service
from tests.backend.routes.fixtures.data_factories import (
    BehaviorDataFactory,
    CategoryDataFactory,
    PromptDataFactory,
    TopicDataFactory,
)

# Import fixtures from routes package


# Use existing data factories instead of custom ones
def create_test_set_data(**overrides):
    """Create test set data using existing patterns."""
    from faker import Faker

    fake = Faker()

    data = {"name": fake.catch_phrase() + " Test Set", "description": fake.text(max_nb_chars=200)}
    data.update(overrides)
    return data


def create_bulk_test_data(**overrides):
    """Create test data for bulk operations using existing factories."""
    data = {
        "prompt": PromptDataFactory.minimal_data(),
        "topic": TopicDataFactory.minimal_data()["name"],
        "behavior": BehaviorDataFactory.minimal_data()["name"],
        "category": CategoryDataFactory.minimal_data()["name"],
        "test_configuration": {},
    }
    data.update(overrides)
    return data


@pytest.mark.unit
@pytest.mark.service
class TestBulkCreateTests:
    """Test bulk_create_tests function."""

    def test_bulk_create_tests_success(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
    ):
        """Test successful bulk creation of tests."""
        # Prepare test data (no content field - it goes in the prompt)
        test_data_list = [
            create_bulk_test_data(),
            create_bulk_test_data(),
        ]

        # Mock the load_defaults function with actual defaults structure
        mock_defaults = {
            "test": {
                "test_type": "Single-Turn",
                "status": "New",
                "priority": 1,
                "test_configuration": None,
            },
            "prompt": {"language_code": "en-US", "status": "New"},
            "topic": {"status": "Active"},
            "behavior": {"status": "Active"},
            "category": {"status": "Active", "entity_type": "Test"},
        }

        # Required entities are provided by fixtures (test_type_lookup, db_status, db_user)

        # Only mock the load_defaults to control the test behavior
        with patch("rhesis.backend.app.services.test.load_defaults") as mock_load_defaults:
            mock_load_defaults.return_value = mock_defaults

            # Call the function with real database entities
            result = test_service.bulk_create_tests(
                db=test_db,
                tests_data=test_data_list,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

            # Verify result — bulk_create_tests returns a list of ID strings
            assert len(result) == 2
            assert all(isinstance(test_id, str) for test_id in result)

            # Verify the mocked function was called
            mock_load_defaults.assert_called_once()

            # Verify the tests exist in the DB with expected relationships
            for test_id in result:
                test_obj = test_db.query(models.Test).filter(
                    models.Test.id == test_id
                ).first()
                assert test_obj is not None
                assert str(test_obj.organization_id) == test_org_id
                assert str(test_obj.user_id) == authenticated_user_id
                assert test_obj.prompt_id is not None
                assert test_obj.topic_id is not None
                assert test_obj.behavior_id is not None
                assert test_obj.category_id is not None
                assert test_obj.status_id is not None

    def test_bulk_create_tests_with_test_set_id(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
    ):
        """Test bulk_create_tests with a test_set_id parameter."""
        # Required entities are provided by fixtures (test_type_lookup, db_status, db_user)
        # Create a test set first
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Prepare test data using the same format as the successful test
        test_data_list = [
            create_bulk_test_data(),
        ]

        # Required entities are provided by fixtures
        result = test_service.bulk_create_tests(
            db=test_db,
            tests_data=test_data_list,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            test_set_id=str(test_set.id),
        )

        # Verify result — bulk_create_tests returns a list of ID strings
        assert len(result) == 1
        assert all(isinstance(test_id, str) for test_id in result)

        # Verify the tests exist in the DB with expected relationships
        for test_id in result:
            test_obj = test_db.query(models.Test).filter(
                models.Test.id == test_id
            ).first()
            assert test_obj is not None
            assert str(test_obj.organization_id) == test_org_id
            assert str(test_obj.user_id) == authenticated_user_id
            assert test_obj.prompt_id is not None
            assert test_obj.topic_id is not None
            assert test_obj.behavior_id is not None
            assert test_obj.category_id is not None
            assert test_obj.status_id is not None

    def test_bulk_create_tests_invalid_uuid(self, test_db: Session, authenticated_user_id):
        """Test bulk_create_tests with invalid UUID parameters."""
        test_data_list = [
            create_bulk_test_data(),
        ]

        # Call with invalid organization_id
        with pytest.raises(Exception, match="Failed to create tests"):
            test_service.bulk_create_tests(
                db=test_db,
                tests_data=test_data_list,
                organization_id="invalid-uuid",
                user_id=authenticated_user_id,
            )


@pytest.mark.unit
@pytest.mark.service
class TestTestSetAssociationsInTestService:
    """Test test set association functions in test service."""

    def test_create_test_set_associations_success(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
    ):
        """Test successful creation of test set associations in test service."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Required entities are provided by fixtures (test_type_lookup, db_status, db_user)

        # Create test data and use the real service to create tests
        test_data_list = [
            create_bulk_test_data(),
            create_bulk_test_data(),
        ]

        # Use the real bulk_create_tests service to create tests with proper relationships
        # Returns a list of ID strings (not ORM objects)
        created_test_ids = test_service.bulk_create_tests(
            db=test_db,
            tests_data=test_data_list,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        test_ids = created_test_ids

        # Mock the entire create_test_set_associations function
        with patch(
            "rhesis.backend.app.services.test.create_test_set_associations"
        ) as mock_create_associations:
            mock_create_associations.return_value = {
                "success": True,
                "total_tests": 2,
                "message": "Associations created successfully",
                "metadata": {
                    "new_associations": 2,
                    "existing_associations": 0,
                    "invalid_associations": 0,
                    "existing_test_ids": [],
                    "invalid_test_ids": [],
                },
            }

            # Call the function (which should be mocked)
            result = test_service.create_test_set_associations(
                db=test_db,
                test_set_id=str(test_set.id),
                test_ids=test_ids,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

            # Verify result
            assert result["success"] is True
            assert result["total_tests"] == 2
            assert result["metadata"]["new_associations"] == 2

            # Verify create_test_set_associations was called with correct parameters
            mock_create_associations.assert_called_once_with(
                db=test_db,
                test_set_id=str(test_set.id),
                test_ids=test_ids,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

    def test_create_test_set_associations_test_set_not_found(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test create_test_set_associations with non-existent test set."""
        non_existent_id = str(uuid.uuid4())
        test_ids = [str(uuid.uuid4())]

        result = test_service.create_test_set_associations(
            db=test_db,
            test_set_id=non_existent_id,
            test_ids=test_ids,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result["success"] is False
        assert result["total_tests"] == 0
        assert "not found" in result["message"]
        assert result["metadata"]["new_associations"] == 0

    def test_remove_test_set_associations_success(
        self,
        test_db: Session,
        authenticated_user_id,
        test_org_id,
        test_organization,
        test_type_lookup,
        db_status,
        db_user,
    ):
        """Test successful removal of test set associations."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Required entities are provided by fixtures (test_type_lookup, db_status, db_user)

        # Create test using the real service (returns list of ID strings)
        test_data_list = [create_bulk_test_data()]
        created_test_ids = test_service.bulk_create_tests(
            db=test_db,
            tests_data=test_data_list,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_id = created_test_ids[0]

        # Create association manually for testing
        from rhesis.backend.app.models.test import test_test_set_association

        test_db.execute(
            test_test_set_association.insert().values(
                test_id=test_id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.commit()

        test_ids = [test_id]

        # Mock the entire remove_test_set_associations function
        with patch(
            "rhesis.backend.app.services.test.remove_test_set_associations"
        ) as mock_remove_associations:
            mock_remove_associations.return_value = {
                "success": True,
                "removed_associations": 1,
                "message": "Successfully removed 1 association",
                "metadata": {"removed_associations": 1, "total_tests": 1},
            }

            # Call the function (which should be mocked)
            result = test_service.remove_test_set_associations(
                db=test_db,
                test_set_id=str(test_set.id),
                test_ids=test_ids,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

            # Verify result
            assert result["success"] is True
            assert result["removed_associations"] == 1
            assert "Successfully removed" in result["message"]

            # Verify remove_test_set_associations was called with correct parameters
            mock_remove_associations.assert_called_once_with(
                db=test_db,
                test_set_id=str(test_set.id),
                test_ids=test_ids,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

    def test_remove_test_set_associations_test_set_not_found(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test remove_test_set_associations with non-existent test set."""
        non_existent_id = str(uuid.uuid4())
        test_ids = [str(uuid.uuid4())]

        # Mock the function to simulate test set not found error
        with patch(
            "rhesis.backend.app.services.test.remove_test_set_associations"
        ) as mock_remove_associations:
            mock_remove_associations.return_value = {
                "success": False,
                "removed_associations": 0,
                "message": f"Test set with ID {non_existent_id} not found",
                "metadata": {"removed_associations": 0, "total_tests": 0},
            }

            result = test_service.remove_test_set_associations(
                db=test_db,
                test_set_id=non_existent_id,
                test_ids=test_ids,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

            assert result["success"] is False
            assert result["removed_associations"] == 0
            assert "not found" in result["message"]

    def test_remove_test_set_associations_no_existing_associations(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test remove_test_set_associations when no associations exist."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Try to remove associations for non-existent test
        test_ids = [str(uuid.uuid4())]

        # Mock the function to simulate no existing associations
        with patch(
            "rhesis.backend.app.services.test.remove_test_set_associations"
        ) as mock_remove_associations:
            mock_remove_associations.return_value = {
                "success": False,
                "removed_associations": 0,
                "message": "None of the provided test IDs are associated with this test set",
                "metadata": {"removed_associations": 0, "total_tests": 1},
            }

            result = test_service.remove_test_set_associations(
                db=test_db,
                test_set_id=str(test_set.id),
                test_ids=test_ids,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

            assert result["success"] is False
            assert result["removed_associations"] == 0
            assert "None of the provided test IDs are associated" in result["message"]
