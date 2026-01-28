"""
Tests for test_set service functions.

These tests verify the current behavior of functions before they are refactored
to use the new direct parameter passing approach.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.services import test_set as test_set_service

# Use existing data factories from the established pattern

fake = Faker()


# Use existing data factories instead of custom ones
def create_test_set_data(**overrides):
    """Create test set data using established patterns."""
    data = {"name": fake.catch_phrase() + " Test Set", "description": fake.text(max_nb_chars=200)}
    data.update(overrides)
    return data


def create_test_data(**overrides):
    """Create test data using established patterns."""
    data = {"test_configuration": {}}
    data.update(overrides)
    return data


def create_endpoint_data(**overrides):
    """Create endpoint data using established patterns."""
    data = {
        "name": fake.catch_phrase() + " Endpoint",
        "url": fake.url() + "/api/test",
        "method": fake.random_element(elements=("GET", "POST", "PUT", "DELETE")),
        "connection_type": "REST",
        "request_headers": {},
        "environment": fake.random_element(elements=("development", "staging", "production")),
    }
    data.update(overrides)
    return data


@pytest.mark.unit
@pytest.mark.service
class TestTestSetAssociations:
    """Test test set association operations."""

    def test_create_test_set_associations_success(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test successful creation of test set associations."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Create tests
        test_data_1 = create_test_data()
        test_data_2 = create_test_data()

        test1 = models.Test(
            **test_data_1, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test2 = models.Test(
            **test_data_2, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add_all([test1, test2])
        test_db.commit()

        test_ids = [str(test1.id), str(test2.id)]

        # Mock the bulk_create_test_set_associations function
        with patch(
            "rhesis.backend.app.services.test_set.bulk_create_test_set_associations"
        ) as mock_bulk_create:
            mock_bulk_create.return_value = {
                "success": True,
                "total_tests": 2,
                "new_associations": 2,
                "existing_associations": 0,
                "invalid_associations": 0,
            }

            # Mock the generate_test_set_attributes function
            with patch(
                "rhesis.backend.app.services.test_set.generate_test_set_attributes"
            ) as mock_generate_attrs:
                mock_generate_attrs.return_value = {"updated": True}

                # Call the function
                result = test_set_service.create_test_set_associations(
                    db=test_db,
                    test_set_id=str(test_set.id),
                    test_ids=test_ids,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )

                # Verify result
                assert result["success"] is True
                assert result["total_tests"] == 2
                assert result["new_associations"] == 2

                # Verify bulk_create_test_set_associations was called
                mock_bulk_create.assert_called_once_with(
                    db=test_db,
                    test_ids=test_ids,
                    test_set_id=str(test_set.id),
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )

                # Verify attributes were updated
                mock_generate_attrs.assert_called_once()

    def test_create_test_set_associations_test_set_not_found(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test create_test_set_associations with non-existent test set."""
        non_existent_id = str(uuid.uuid4())
        test_ids = [str(uuid.uuid4())]

        result = test_set_service.create_test_set_associations(
            db=test_db,
            test_set_id=non_existent_id,
            test_ids=test_ids,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result["success"] is False
        assert result["total_tests"] == 0
        assert "not found" in result["message"]

    def test_create_test_set_associations_no_new_associations(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test create_test_set_associations when no new associations are created."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        test_ids = [str(uuid.uuid4())]

        # Mock the bulk_create_test_set_associations function to return no new associations
        with patch(
            "rhesis.backend.app.services.test_set.bulk_create_test_set_associations"
        ) as mock_bulk_create:
            mock_bulk_create.return_value = {
                "success": True,
                "total_tests": 1,
                "new_associations": 0,
                "existing_associations": 1,
                "invalid_associations": 0,
            }

            # Mock the generate_test_set_attributes function
            with patch(
                "rhesis.backend.app.services.test_set.generate_test_set_attributes"
            ) as mock_generate_attrs:
                # Call the function
                result = test_set_service.create_test_set_associations(
                    db=test_db,
                    test_set_id=str(test_set.id),
                    test_ids=test_ids,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )

                # Verify result
                assert result["success"] is True
                assert result["new_associations"] == 0

                # Verify attributes were NOT updated (no new associations)
                mock_generate_attrs.assert_not_called()


@pytest.mark.unit
@pytest.mark.service
class TestTestSetExecution:
    """Test test set execution operations."""

    def test_execute_test_set_on_endpoint_success(
        self, test_db: Session, authenticated_user_id, test_org_id, db_user, test_organization
    ):
        """Test successful test set execution on endpoint."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Create a project first (required for endpoint.project_id FK)
        project = models.Project(
            name="Test Set Project",
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        # Create endpoint
        endpoint_data = create_endpoint_data()
        endpoint = models.Endpoint(
            **endpoint_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            project_id=project.id,
        )
        test_db.add(endpoint)
        test_db.commit()

        # User already exists from authenticated_user_id fixture - get it from DB
        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()

        # Mock all the dependencies
        with (
            patch("rhesis.backend.app.crud.resolve_test_set") as mock_resolve_test_set,
            patch("rhesis.backend.app.crud.get_endpoint") as mock_get_endpoint,
            patch(
                "rhesis.backend.app.services.test_set._validate_user_access"
            ) as mock_validate_access,
            patch(
                "rhesis.backend.app.services.test_set._create_test_configuration"
            ) as mock_create_config,
            patch(
                "rhesis.backend.app.services.test_set._submit_test_configuration_for_execution"
            ) as mock_submit,
        ):
            # Setup mocks
            mock_resolve_test_set.return_value = test_set
            mock_get_endpoint.return_value = endpoint
            mock_validate_access.return_value = None  # No exception means validation passed
            mock_create_config.return_value = "test_config_id"

            # Mock task result
            mock_task = MagicMock()
            mock_task.id = "task_id_123"
            mock_submit.return_value = mock_task

            # Call the function
            result = test_set_service.execute_test_set_on_endpoint(
                db=test_db,
                test_set_identifier=str(test_set.id),
                endpoint_id=endpoint.id,
                current_user=user,
                test_configuration_attributes={"param": "value"},
            )

            # Verify result
            assert result["status"] == "submitted"
            assert result["test_set_id"] == str(test_set.id)
            assert result["test_set_name"] == test_set.name
            assert result["endpoint_id"] == str(endpoint.id)
            assert result["endpoint_name"] == endpoint.name
            assert result["test_configuration_id"] == "test_config_id"
            assert result["task_id"] == "task_id_123"

            # Verify all mocks were called
            mock_resolve_test_set.assert_called_once_with(
                str(test_set.id), test_db, organization_id=test_org_id
            )
            mock_get_endpoint.assert_called_once_with(
                test_db,
                endpoint_id=endpoint.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
            mock_validate_access.assert_called_once_with(user, test_set, endpoint)
            mock_create_config.assert_called_once_with(
                test_db, endpoint.id, test_set.id, user, {"param": "value"}, None, None
            )
            mock_submit.assert_called_once_with("test_config_id", user)

    def test_execute_test_set_on_endpoint_test_set_not_found(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test execute_test_set_on_endpoint with non-existent test set."""
        non_existent_id = str(uuid.uuid4())
        endpoint_id = uuid.uuid4()

        # User already exists from authenticated_user_id fixture - get it from DB
        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()

        # Mock crud.resolve_test_set to return None
        with patch("rhesis.backend.app.crud.resolve_test_set") as mock_resolve_test_set:
            mock_resolve_test_set.return_value = None

            # Call the function and expect ValueError
            with pytest.raises(ValueError, match="Test Set not found"):
                test_set_service.execute_test_set_on_endpoint(
                    db=test_db,
                    test_set_identifier=non_existent_id,
                    endpoint_id=endpoint_id,
                    current_user=user,
                )

    def test_execute_test_set_on_endpoint_endpoint_not_found(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test execute_test_set_on_endpoint with non-existent endpoint."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # User already exists from authenticated_user_id fixture - get it from DB
        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()

        non_existent_endpoint_id = uuid.uuid4()

        # Mock dependencies
        with (
            patch("rhesis.backend.app.crud.resolve_test_set") as mock_resolve_test_set,
            patch("rhesis.backend.app.crud.get_endpoint") as mock_get_endpoint,
        ):
            mock_resolve_test_set.return_value = test_set
            mock_get_endpoint.return_value = None

            # Call the function and expect ValueError
            with pytest.raises(ValueError, match="Endpoint not found"):
                test_set_service.execute_test_set_on_endpoint(
                    db=test_db,
                    test_set_identifier=str(test_set.id),
                    endpoint_id=non_existent_endpoint_id,
                    current_user=user,
                )

    def test_execute_test_set_on_endpoint_missing_endpoint_id(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test execute_test_set_on_endpoint with missing endpoint_id."""
        # User already exists from authenticated_user_id fixture - get it from DB
        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()

        # Call the function with None endpoint_id and expect ValueError
        with pytest.raises(ValueError, match="endpoint_id is required"):
            test_set_service.execute_test_set_on_endpoint(
                db=test_db, test_set_identifier="test_set_id", endpoint_id=None, current_user=user
            )

    def test_execute_test_set_on_endpoint_with_metrics(
        self, test_db: Session, authenticated_user_id, test_org_id, db_user, test_organization
    ):
        """Test test set execution with execution-time metrics."""
        # Create test set
        test_set_data = create_test_set_data()
        test_set = models.TestSet(
            **test_set_data, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(test_set)
        test_db.commit()

        # Create a project first (required for endpoint.project_id FK)
        project = models.Project(
            name="Test Set Project with Metrics",
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        # Create endpoint
        endpoint_data = create_endpoint_data()
        endpoint = models.Endpoint(
            **endpoint_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            project_id=project.id,
        )
        test_db.add(endpoint)
        test_db.commit()

        # User already exists from authenticated_user_id fixture - get it from DB
        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()

        # Define execution-time metrics
        metrics = [
            {"id": str(uuid.uuid4()), "name": "Execution Metric 1", "scope": ["Single-Turn"]},
            {"id": str(uuid.uuid4()), "name": "Execution Metric 2", "scope": ["Single-Turn"]},
        ]

        # Mock all the dependencies
        with (
            patch("rhesis.backend.app.crud.resolve_test_set") as mock_resolve_test_set,
            patch("rhesis.backend.app.crud.get_endpoint") as mock_get_endpoint,
            patch(
                "rhesis.backend.app.services.test_set._validate_user_access"
            ) as mock_validate_access,
            patch(
                "rhesis.backend.app.services.test_set._create_test_configuration"
            ) as mock_create_config,
            patch(
                "rhesis.backend.app.services.test_set._submit_test_configuration_for_execution"
            ) as mock_submit,
        ):
            # Setup mocks
            mock_resolve_test_set.return_value = test_set
            mock_get_endpoint.return_value = endpoint
            mock_validate_access.return_value = None
            mock_create_config.return_value = "test_config_id"

            # Mock task result
            mock_task = MagicMock()
            mock_task.id = "task_id_123"
            mock_submit.return_value = mock_task

            # Call the function with metrics
            result = test_set_service.execute_test_set_on_endpoint(
                db=test_db,
                test_set_identifier=str(test_set.id),
                endpoint_id=endpoint.id,
                current_user=user,
                test_configuration_attributes={"execution_mode": "Parallel"},
                metrics=metrics,
            )

            # Verify result
            assert result["status"] == "submitted"
            assert result["test_configuration_id"] == "test_config_id"

            # Verify _create_test_configuration was called with metrics
            mock_create_config.assert_called_once()
            call_args = mock_create_config.call_args
            # Check that metrics were passed
            assert call_args[0][7] == metrics  # metrics is the 8th positional arg


@pytest.mark.unit
@pytest.mark.service
class TestTestSetGeneration:
    """Test test set generation with custom names."""

    def test_bulk_create_test_set_with_custom_name(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test that bulk_create_test_set uses the provided name."""
        custom_name = "My Custom Test Set"
        test_set_data = schemas.TestSetBulkCreate(
            name=custom_name,
            description="A test set with custom name",
            short_description="Custom test set",
            tests=[
                schemas.TestData(
                    prompt=schemas.TestPrompt(content="Test prompt 1"),
                    behavior="Security",
                    category="Injection",
                    topic="SQL Injection",
                )
            ],
        )

        result = test_set_service.bulk_create_test_set(
            db=test_db,
            test_set_data=test_set_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result.name == custom_name
        assert result.description == "A test set with custom name"

    def test_bulk_create_test_set_with_auto_generated_name(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Test that bulk_create_test_set auto-generates name when using SDK."""
        # This test simulates the behavior when the SDK generates a test set
        # The SDK will auto-generate a name based on the test set properties
        test_set_data = {
            "name": "Generated Test Set",  # This would come from SDK's set_properties()
            "description": "Auto-generated test set",
            "short_description": "Auto-generated",
            "tests": [
                {
                    "prompt": {"content": "Test prompt 1"},
                    "behavior": "Security",
                    "category": "Injection",
                    "topic": "SQL Injection",
                }
            ],
        }

        result = test_set_service.bulk_create_test_set(
            db=test_db,
            test_set_data=test_set_data,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result.name == "Generated Test Set"
        assert len(result.tests) == 1
