"""
Tests for test_set service functions.

These tests verify the current requirement of functions before they are refactored
to use the new direct parameter passing approach.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from pydantic import ValidationError
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.constants import (
    EXPLORER_REQUIREMENT_NAME,
    TestSetType,
    TestType,
)
from rhesis.backend.app.schemas.validators import resolve_test_type
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
        # Set metrics to empty list to prevent lazy loading (table may not exist in test DB)
        test_set.metrics = []

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
                "rhesis.backend.app.services.test_set.count_test_set_tests",
                return_value=1,
            ),
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
            mock_submit.return_value = (mock_task, "test_run_id_123")

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
            assert result["test_run_id"] == "test_run_id_123"
            assert result["task_id"] == "task_id_123"

            # Verify all mocks were called
            # The function uses current_user.organization_id, not the passed-in test_org_id
            mock_resolve_test_set.assert_called_once_with(
                str(test_set.id), test_db, organization_id=str(user.organization_id)
            )
            mock_get_endpoint.assert_called_once_with(
                test_db,
                endpoint_id=endpoint.id,
                organization_id=str(user.organization_id),
                user_id=str(user.id),
            )
            mock_validate_access.assert_called_once_with(user, test_set, endpoint)
            mock_create_config.assert_called_once_with(
                test_db,
                endpoint.id,
                test_set.id,
                user,
                {"param": "value"},
                None,
                None,
                None,
                "requirement",
                reference_test_run_id=None,
                execution_model_id=None,
                evaluation_model_id=None,
                parameters_ref=None,
            )
            mock_submit.assert_called_once_with(test_db, "test_config_id", user)

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

    def test_count_test_set_tests_excludes_soft_deleted_tests(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        """Stale associations to soft-deleted tests do not make a test set executable."""
        test_set = models.TestSet(
            **create_test_set_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test = models.Test(
            **create_test_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add_all([test_set, test])
        test_db.flush()
        test_db.execute(
            models.test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.commit()

        assert test_set_service.count_test_set_tests(test_db, test_set.id) == 1

        test.soft_delete()
        test_db.commit()

        assert test_set_service.count_test_set_tests(test_db, test_set.id) == 0

    def test_execute_test_set_on_endpoint_empty_test_set(
        self, test_db: Session, authenticated_user_id, test_org_id, db_user, test_organization
    ):
        """Empty test sets are rejected before configuration or task submission."""
        test_set = models.TestSet(
            **create_test_set_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()

        project = models.Project(
            name="Empty Test Set Project",
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        endpoint = models.Endpoint(
            **create_endpoint_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            project_id=project.id,
        )
        test_db.add(endpoint)
        test_db.commit()

        user = test_db.query(models.User).filter(models.User.id == authenticated_user_id).first()

        with (
            patch("rhesis.backend.app.crud.resolve_test_set", return_value=test_set),
            patch("rhesis.backend.app.crud.get_endpoint", return_value=endpoint),
            patch(
                "rhesis.backend.app.services.test_set._validate_user_access",
                return_value=None,
            ),
            patch(
                "rhesis.backend.app.services.test_set._create_test_configuration"
            ) as mock_create_config,
            patch(
                "rhesis.backend.app.services.test_set._submit_test_configuration_for_execution"
            ) as mock_submit,
        ):
            with pytest.raises(ValueError, match="Cannot execute test set with 0 tests"):
                test_set_service.execute_test_set_on_endpoint(
                    db=test_db,
                    test_set_identifier=str(test_set.id),
                    endpoint_id=endpoint.id,
                    current_user=user,
                )

            mock_create_config.assert_not_called()
            mock_submit.assert_not_called()

    def test_execute_test_set_on_endpoint_empty_returns_http_400(self):
        """Empty-test ValueError is converted to HTTP 400 by handle_execution_error."""
        from rhesis.backend.app.utils.execution_validation import handle_execution_error

        error = ValueError(
            "Cannot execute test set with 0 tests. Please add tests before executing."
        )
        result = handle_execution_error(error, operation="execute test set")

        assert result.status_code == 400
        assert "cannot execute test set with 0 tests" in str(result.detail).lower()

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
                "rhesis.backend.app.services.test_set.count_test_set_tests",
                return_value=1,
            ),
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
            mock_submit.return_value = (mock_task, "test_run_id_123")

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
            test_set_type="Single-Turn",
            tests=[
                schemas.TestData(
                    prompt=schemas.TestPrompt(content="Test prompt 1"),
                    requirement="Security",
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
            "test_set_type": "Single-Turn",
            "tests": [
                {
                    "prompt": {"content": "Test prompt 1"},
                    "requirement": "Security",
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


@pytest.mark.unit
@pytest.mark.service
class TestBulkCreateEnforcesUniformTestType:
    def test_prompt_only_test_rejected_for_multi_turn_set(self):
        with pytest.raises(ValidationError, match="does not match test set type"):
            schemas.TestSetBulkCreate(
                name="Mismatched",
                test_set_type="Multi-Turn",
                tests=[
                    schemas.TestData(
                        prompt=schemas.TestPrompt(content="single turn"),
                        requirement="Security",
                        category="Injection",
                        topic="Prompt Injection",
                    )
                ],
            )

    def test_goal_config_test_rejected_for_single_turn_set(self):
        with pytest.raises(ValidationError, match="does not match test set type"):
            schemas.TestSetBulkCreate(
                name="Mismatched",
                test_set_type="Single-Turn",
                tests=[
                    schemas.TestData(
                        test_configuration={"goal": "multi turn"},
                        requirement="Security",
                        category="Injection",
                        topic="Prompt Injection",
                    )
                ],
            )

    def test_mixed_payload_rejected_with_split_guidance(self):
        with pytest.raises(ValidationError, match="mixed turn types"):
            schemas.TestSetBulkCreate(
                name="Mixed",
                test_set_type="Multi-Turn",
                tests=[
                    schemas.TestData(
                        prompt=schemas.TestPrompt(content="single turn"),
                        requirement="Security",
                        category="Injection",
                        topic="Prompt Injection",
                    ),
                    schemas.TestData(
                        test_configuration={"goal": "multi turn"},
                        requirement="Security",
                        category="Injection",
                        topic="Prompt Injection",
                    ),
                ],
            )

    def test_enum_typed_inputs_resolve_to_plain_strings(self):
        """Enum instances (pydantic-coerced) must resolve to plain strings."""
        payload = schemas.TestSetBulkCreate(
            name="Enum",
            test_set_type=TestSetType.SINGLE_TURN,
            tests=[
                schemas.TestData(
                    prompt=schemas.TestPrompt(content="single turn"),
                    test_type=TestType.SINGLE_TURN,
                    requirement="Security",
                    category="Injection",
                    topic="Prompt Injection",
                )
            ],
        )
        effective_type = resolve_test_type(
            payload.tests[0].model_dump(exclude_none=True),
            test_set_type=TestSetType.get_value(payload.test_set_type),
            default_test_type=TestSetType.get_value(payload.test_set_type),
        )
        assert effective_type == "Single-Turn"
        assert type(effective_type) is str

    def test_uniform_single_turn_payload_is_accepted(self):
        payload = schemas.TestSetBulkCreate(
            name="Single",
            test_set_type="Single-Turn",
            tests=[
                schemas.TestData(
                    prompt=schemas.TestPrompt(content="single turn"),
                    requirement="Security",
                    category="Injection",
                    topic="Prompt Injection",
                )
            ],
        )
        assert payload.tests[0].test_type is None

    def test_uniform_multi_turn_payload_is_accepted(self):
        payload = schemas.TestSetBulkCreate(
            name="Multi",
            test_set_type="Multi-Turn",
            tests=[
                schemas.TestData(
                    test_configuration={"goal": "multi turn"},
                    requirement="Security",
                    category="Injection",
                    topic="Prompt Injection",
                )
            ],
        )
        # TestData normalises a goal-bearing config through MultiTurnTestConfig,
        # whose max_turns defaults to 10 — so it is always present on the way out.
        assert payload.tests[0].test_configuration == {"goal": "multi turn", "max_turns": 10}

    def test_effective_type_precedence_is_shared(self):
        base = {
            "prompt": {"content": "prompt wins over parent"},
            "test_configuration": {},
        }
        assert resolve_test_type(base, "Multi-Turn", "Single-Turn") == "Single-Turn"
        assert (
            resolve_test_type({"test_configuration": {"goal": "g"}}, "Single-Turn", "Multi-Turn")
            == "Multi-Turn"
        )
        assert (
            resolve_test_type(
                {"test_type": "Single-Turn", "test_configuration": {"goal": "g"}},
                "Multi-Turn",
                "Multi-Turn",
            )
            == "Single-Turn"
        )
        assert resolve_test_type({}, "Multi-Turn", "Single-Turn") == "Multi-Turn"
        assert resolve_test_type({}, None, None) == "Single-Turn"


@pytest.mark.unit
@pytest.mark.service
class TestGetTestSetsExcludesExplorer:
    """crud.get_test_sets must omit explorer sets (general test set list API)."""

    def test_get_test_sets_excludes_explorer_metadata_requirement(
        self, test_db: Session, authenticated_user_id, test_org_id
    ):
        regular = models.TestSet(
            name="Regular set for list filter",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            visibility="organization",
            attributes={"metadata": {"requirements": ["Safety"]}},
        )
        explorer = models.TestSet(
            name="Explorer set for list filter",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            visibility="organization",
            attributes={"metadata": {"requirements": [EXPLORER_REQUIREMENT_NAME]}},
            explorer_row=True,
        )
        test_db.add_all([regular, explorer])
        test_db.commit()

        results = crud.get_test_sets(
            test_db,
            organization_id=str(test_org_id),
            user_id=str(authenticated_user_id),
            limit=100,
        )
        ids = {ts.id for ts in results}
        assert regular.id in ids
        assert explorer.id not in ids


class TestGetTestSetSoftDeleteContract:
    """services.test_set.get_test_set must raise ItemDeletedException for a
    soft-deleted row, like every other entity's single-item fetch -- not
    silently collapse it into "not found" like get_item does for None."""

    def test_raises_for_deleted_test_set(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

        test_set = models.TestSet(
            name="Soft Delete Services Test Set",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()
        test_db.refresh(test_set)

        crud.delete_test_set(
            test_db, test_set.id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        with pytest.raises(ItemDeletedException):
            test_set_service.get_test_set(test_db, test_set.id, str(test_org_id))

    def test_returns_none_for_nonexistent(self, test_db: Session, test_org_id):
        result = test_set_service.get_test_set(test_db, uuid.uuid4(), str(test_org_id))
        assert result is None
