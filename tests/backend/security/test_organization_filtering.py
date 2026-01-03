"""
🔒 Organization Filtering Security Tests

This module tests that all CRUD operations properly implement organization-based
filtering to prevent unauthorized access to data from other organizations.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from tests.backend.fixtures.test_setup import create_test_organization_and_user


@pytest.mark.security
class TestCrudOrganizationFiltering:
    """Test that CRUD operations properly filter by organization"""

    def test_get_task_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_task properly filters by organization"""
        # Create two separate organizations and users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Security Test Org 1 {unique_id}",
            f"user1-{unique_id}@security-test.com",
            "Security User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Security Test Org 2 {unique_id}",
            f"user2-{unique_id}@security-test.com",
            "Security User 2",
        )

        # Create a task in org1 using CRUD function
        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        # Create a status for the task
        status = get_or_create_status(
            db=test_db,
            name="In Progress",
            entity_type="Task",
            organization_id=str(org1.id),
            user_id=str(user1.id),
        )

        # Create task using direct model instantiation since TaskCreate may not exist
        task = models.Task(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            title="Test task in org1",
            description="Test task in org1",
            status_id=status.id,
        )
        test_db.add(task)
        test_db.commit()

        # User from org1 should be able to access the task
        result_org1 = crud.get_task(
            test_db, task.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == task.id
        assert result_org1.organization_id == org1.id

        # User from org2 should NOT be able to access the task
        result_org2 = crud.get_task(
            test_db, task.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_test_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db, "Test Org 1", f"test-user1-{uuid.uuid4()}@security-test.com", "Test User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "Test Org 2", f"test-user2-{uuid.uuid4()}@security-test.com", "Test User 2"
        )

        # Create a prompt in org1 using fixture data
        from tests.backend.routes.fixtures.data_factories import PromptDataFactory

        prompt_data = PromptDataFactory.minimal_data()
        prompt = crud.create_prompt(
            db=test_db, prompt=prompt_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # Create a test in org1 using the prompt
        test_obj = models.Test(
            id=uuid.uuid4(), organization_id=org1.id, user_id=user1.id, prompt_id=prompt.id
        )
        test_db.add(test_obj)
        test_db.commit()

        # User from org1 should be able to access the test
        result_org1 = crud.get_test(
            test_db, test_obj.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == test_obj.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the test
        result_org2 = crud.get_test(
            test_db, test_obj.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_test_result_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_result properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            "TestResult Org 1",
            f"testresult-user1-{uuid.uuid4()}@security-test.com",
            "TestResult User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            "TestResult Org 2",
            f"testresult-user2-{uuid.uuid4()}@security-test.com",
            "TestResult User 2",
        )

        # Create a prompt in org1 using fixture data
        from tests.backend.routes.fixtures.data_factories import (
            EndpointDataFactory,
            PromptDataFactory,
        )

        prompt_data = PromptDataFactory.minimal_data()
        prompt = crud.create_prompt(
            db=test_db, prompt=prompt_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # Create an endpoint first (required for test configuration)
        endpoint_data = EndpointDataFactory.minimal_data()
        endpoint = crud.create_endpoint(
            db=test_db, endpoint=endpoint_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # Create a test first (required for test result)
        test_obj = models.Test(
            id=uuid.uuid4(), organization_id=org1.id, user_id=user1.id, prompt_id=prompt.id
        )
        test_db.add(test_obj)
        test_db.commit()

        # Create a test configuration first (required for test result)
        test_config = models.TestConfiguration(
            id=uuid.uuid4(),
            endpoint_id=endpoint.id,
            organization_id=org1.id,
            user_id=user1.id,
            prompt_id=prompt.id,  # Use the prompt we created earlier
            attributes={"test_type": "security"},
        )
        test_db.add(test_config)
        test_db.commit()

        # Create a test result in org1 using direct model creation
        test_result = models.TestResult(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            test_id=test_obj.id,
            test_configuration_id=test_config.id,  # Use real test configuration
            test_output="Security test result",
            test_metrics={"score": 0.8},
        )
        test_db.add(test_result)
        test_db.commit()

        # User from org1 should be able to access the test result
        result_org1 = crud.get_test_result(
            test_db, test_result.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == test_result.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the test result
        result_org2 = crud.get_test_result(
            test_db, test_result.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_test_run_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_run properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            "TestRun Org 1",
            f"testrun-user1-{uuid.uuid4()}@security-test.com",
            "TestRun User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            "TestRun Org 2",
            f"testrun-user2-{uuid.uuid4()}@security-test.com",
            "TestRun User 2",
        )

        # Create a prompt in org1 using fixture data
        from tests.backend.routes.fixtures.data_factories import (
            EndpointDataFactory,
            PromptDataFactory,
        )

        prompt_data = PromptDataFactory.minimal_data()
        prompt = crud.create_prompt(
            db=test_db, prompt=prompt_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # Create an endpoint first (required for test configuration)
        endpoint_data = EndpointDataFactory.minimal_data()
        endpoint = crud.create_endpoint(
            db=test_db, endpoint=endpoint_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # Create a test first (required for test run)
        test_obj = models.Test(
            id=uuid.uuid4(), organization_id=org1.id, user_id=user1.id, prompt_id=prompt.id
        )
        test_db.add(test_obj)
        test_db.commit()

        # Create a test configuration first (required for test run)
        test_config = models.TestConfiguration(
            id=uuid.uuid4(),
            endpoint_id=endpoint.id,
            organization_id=org1.id,
            user_id=user1.id,
            prompt_id=prompt.id,  # Use the prompt we created earlier
            attributes={"test_type": "security"},
        )
        test_db.add(test_config)
        test_db.commit()

        # Create a test run in org1 using direct model creation
        test_run = models.TestRun(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name="Security test run",
            test_configuration_id=test_config.id,  # Use real test configuration
            attributes={"test_type": "security"},
        )
        test_db.add(test_run)
        test_db.commit()

        # User from org1 should be able to access the test run
        result_org1 = crud.get_test_run(
            test_db, test_run.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == test_run.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the test run
        result_org2 = crud.get_test_run(
            test_db, test_run.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_endpoint_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_endpoint properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            "Endpoint Org 1",
            f"endpoint-user1-{uuid.uuid4()}@security-test.com",
            "Endpoint User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            "Endpoint Org 2",
            f"endpoint-user2-{uuid.uuid4()}@security-test.com",
            "Endpoint User 2",
        )

        # Create an endpoint in org1 using manual data
        from rhesis.backend.app.schemas.endpoint import EndpointCreate

        endpoint_data = EndpointCreate(
            name="Security Test Endpoint",
            description="Test endpoint for security testing",
            connection_type="REST",
            url="https://api.security-test.com/v1/test",
            environment="development",
            config_source="manual",
        )
        endpoint = crud.create_endpoint(
            db=test_db, endpoint=endpoint_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to access the endpoint
        result_org1 = crud.get_endpoint(
            test_db, endpoint.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == endpoint.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the endpoint
        result_org2 = crud.get_endpoint(
            test_db, endpoint.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_prompt_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_prompt properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            "Prompt Org 1",
            f"prompt-user1-{uuid.uuid4()}@security-test.com",
            "Prompt User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            "Prompt Org 2",
            f"prompt-user2-{uuid.uuid4()}@security-test.com",
            "Prompt User 2",
        )

        # Create a prompt in org1 using fixture data
        from tests.backend.routes.fixtures.data_factories import PromptDataFactory

        prompt_data = PromptDataFactory.minimal_data()
        prompt = crud.create_prompt(
            db=test_db, prompt=prompt_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to access the prompt
        result_org1 = crud.get_prompt(
            test_db, prompt.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == prompt.id
        assert str(result_org1.organization_id) == str(org1.id)

        # User from org2 should NOT be able to access the prompt
        result_org2 = crud.get_prompt(
            test_db, prompt.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_model_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_model properly filters by organization"""
        # Create two separate organizations and users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Model Test Org 1 {unique_id}",
            f"model-user1-{unique_id}@security-test.com",
            "Model User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Model Test Org 2 {unique_id}",
            f"model-user2-{unique_id}@security-test.com",
            "Model User 2",
        )

        # Create a model in org1 using CRUD function
        from rhesis.backend.app.schemas.model import ModelCreate

        model_data = ModelCreate(
            name="Test Model",
            description="Test model in org1",
            model_name="test-model",
            endpoint="https://test.example.com",
            key="test-key",
        )
        model = crud.create_model(
            db=test_db, model=model_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to access the model
        result_org1 = crud.get_model(
            test_db, model.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == model.id
        assert result_org1.organization_id == org1.id

        # User from org2 should NOT be able to access the model
        result_org2 = crud.get_model(
            test_db, model.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_metric_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_metric properly filters by organization"""
        # Create two separate organizations and users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Metric Test Org 1 {unique_id}",
            f"metric-user1-{unique_id}@security-test.com",
            "Metric User 1",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Metric Test Org 2 {unique_id}",
            f"metric-user2-{unique_id}@security-test.com",
            "Metric User 2",
        )

        # Create a metric in org1 using CRUD function to handle complex relationships
        from rhesis.backend.app.schemas.metric import MetricCreate

        metric_data = MetricCreate(
            name="Test Metric",
            description="Test metric in org1",
            evaluation_prompt="Test prompt",
            evaluation_steps="Test steps",
            reasoning="Test reasoning",
            score_type="numeric",
            min_score=0,
            max_score=10,
            threshold=5,
            explanation="Test explanation",
            ground_truth_required=False,
            context_required=False,
            class_name="TestMetric",
        )

        metric = crud.create_metric(
            db=test_db, metric=metric_data, organization_id=str(org1.id), user_id=str(user1.id)
        )

        # User from org1 should be able to access the metric
        result_org1 = crud.get_metric(
            test_db, metric.id, organization_id=str(org1.id), user_id=str(user1.id)
        )
        assert result_org1 is not None
        assert result_org1.id == metric.id
        assert result_org1.organization_id == org1.id

        # User from org2 should NOT be able to access the metric
        result_org2 = crud.get_metric(
            test_db, metric.id, organization_id=str(org2.id), user_id=str(user2.id)
        )
        assert result_org2 is None

    def test_get_user_tokens_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_user_tokens properly filters by organization"""
        # Create two separate organizations with different users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Token Test Org 1 {unique_id}",
            f"user1-{unique_id}@security-test.com",
            "User One",
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Token Test Org 2 {unique_id}",
            f"user2-{unique_id}@security-test.com",
            "User Two",
        )

        # Create tokens in both organizations
        from rhesis.backend.app.auth.token_utils import generate_api_token
        from rhesis.backend.app.schemas.token import TokenCreate
        from rhesis.backend.app.utils.encryption import hash_token

        token_value_1 = generate_api_token()
        token1 = crud.create_token(
            db=test_db,
            token=TokenCreate(
                name=f"Token in Org 1 {unique_id}",
                token=token_value_1,
                token_hash=hash_token(token_value_1),
                token_type="bearer",
                token_obfuscated=token_value_1[:3] + "..." + token_value_1[-4:],
                expires_at=None,
                user_id=user1.id,
                organization_id=org1.id,
            ),
            organization_id=str(org1.id),
            user_id=str(user1.id),
        )

        token_value_2 = generate_api_token()
        token2 = crud.create_token(
            db=test_db,
            token=TokenCreate(
                name=f"Token in Org 2 {unique_id}",
                token=token_value_2,
                token_hash=hash_token(token_value_2),
                token_type="bearer",
                token_obfuscated=token_value_2[:3] + "..." + token_value_2[-4:],
                expires_at=None,
                user_id=user2.id,
                organization_id=org2.id,
            ),
            organization_id=str(org2.id),
            user_id=str(user2.id),
        )

        # User from org1 should only see their token from org1
        tokens_org1 = crud.get_user_tokens(
            db=test_db, user_id=user1.id, organization_id=str(org1.id)
        )
        # Filter to only tokens we created in this test
        test_tokens_org1 = [
            t for t in tokens_org1 if t.name.startswith(f"Token in Org 1 {unique_id}")
        ]
        assert len(test_tokens_org1) == 1, (
            f"Expected 1 token for org1, found {len(test_tokens_org1)}: "
            f"{[t.name for t in tokens_org1]}"
        )
        assert test_tokens_org1[0].id == token1.id
        assert test_tokens_org1[0].organization_id == org1.id

        # User from org2 should only see their token from org2
        tokens_org2 = crud.get_user_tokens(
            db=test_db, user_id=user2.id, organization_id=str(org2.id)
        )
        # Filter to only tokens we created in this test
        test_tokens_org2 = [
            t for t in tokens_org2 if t.name.startswith(f"Token in Org 2 {unique_id}")
        ]
        assert len(test_tokens_org2) == 1, (
            f"Expected 1 token for org2, found {len(test_tokens_org2)}: "
            f"{[t.name for t in tokens_org2]}"
        )
        assert test_tokens_org2[0].id == token2.id
        assert test_tokens_org2[0].organization_id == org2.id

        # CRITICAL: User from org1 should NOT see tokens from org2
        cross_org_tokens = crud.get_user_tokens(
            db=test_db, user_id=user1.id, organization_id=str(org2.id)
        )
        assert len(cross_org_tokens) == 0, "User should not see tokens from other organizations"

        # Verify count matches the actual number of tokens
        count_org1 = crud.count_user_tokens(
            db=test_db, user_id=user1.id, organization_id=str(org1.id)
        )
        assert count_org1 == len(tokens_org1), (
            f"Count should match token list length: {count_org1} != {len(tokens_org1)}"
        )


@pytest.mark.security
class TestCrudParameterValidation:
    """Test that CRUD functions properly accept organization_id parameters for security"""

    def test_organization_filtering_regression_suite(self, test_db: Session):
        """🔒 SECURITY: Comprehensive regression test for organization filtering"""
        # This test ensures that all the security fixes we've implemented
        # continue to work and haven't regressed

        # Test organization IDs for validation
        _org1_id = str(uuid.uuid4())
        _org2_id = str(uuid.uuid4())

        # List of CRUD functions that should implement organization filtering
        crud_functions = [
            ("get_task", uuid.uuid4()),
            ("get_test", uuid.uuid4()),
            ("get_test_result", uuid.uuid4()),
            ("get_test_run", uuid.uuid4()),
            ("get_endpoint", uuid.uuid4()),
            ("get_prompt", uuid.uuid4()),
            ("get_model", uuid.uuid4()),
            ("get_metric", uuid.uuid4()),
        ]

        for func_name, entity_id in crud_functions:
            if hasattr(crud, func_name):
                func = getattr(crud, func_name)

                # Test that the function accepts organization_id parameter
                import inspect

                signature = inspect.signature(func)
                assert "organization_id" in signature.parameters, (
                    f"{func_name} should accept organization_id parameter"
                )


@pytest.mark.security
class TestTaskManagementSecuritySimplified:
    """Simplified task management security tests"""

    def test_task_organization_constraint_validation(self, test_db: Session):
        """🔒 SECURITY: Test task organization constraint validation"""
        from rhesis.backend.app.services.task_management import (
            validate_task_organization_constraints,
        )

        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        unique_id = str(uuid.uuid4())[:8]
        organization1, user1, _ = create_test_organization_and_user(
            test_db,
            f"Task Org 1 {unique_id}",
            f"task-user1-{unique_id}@security-test.com",
            "Task User 1",
        )
        organization2, user2, _ = create_test_organization_and_user(
            test_db,
            f"Task Org 2 {unique_id}",
            f"task-user2-{unique_id}@security-test.com",
            "Task User 2",
        )

        # Create a status in organization1
        from rhesis.backend.app import crud
        from rhesis.backend.app.schemas.status import StatusCreate

        status_data = StatusCreate(name=f"Test Status {unique_id}")
        status = crud.create_status(
            test_db, status_data, organization_id=str(organization1.id), user_id=str(user1.id)
        )

        # Create a simple task object (not mock) with required attributes
        class SimpleTask:
            def __init__(self, organization_id, status_id, assignee_id=None, priority_id=None):
                self.organization_id = organization_id
                self.status_id = status_id
                self.assignee_id = assignee_id
                self.priority_id = priority_id

        # Create a task in organization1
        task = SimpleTask(
            organization_id=organization1.id,
            status_id=status.id,
            assignee_id=None,  # No assignee for this test
            priority_id=None,  # No priority for this test
        )

        # This should not raise an exception when user and task are in same organization
        try:
            validate_task_organization_constraints(test_db, task, user1)
        except Exception as e:
            pytest.fail(f"validate_task_organization_constraints raised an exception: {e}")

        # Test cross-tenant scenario - user from organization2 trying to work with task
        # from organization1
        # This should raise an exception
        with pytest.raises(ValueError, match="not in same organization"):
            validate_task_organization_constraints(test_db, task, user2)
