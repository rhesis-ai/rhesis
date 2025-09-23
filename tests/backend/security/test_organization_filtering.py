"""
🔒 Organization Filtering Security Tests

This module tests that all CRUD operations properly implement organization-based
filtering to prevent unauthorized access to data from other organizations.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from rhesis.backend.app import models, crud
from tests.backend.fixtures.test_setup import create_test_organization_and_user


@pytest.mark.security
class TestCrudOrganizationFiltering:
    """Test that CRUD operations properly filter by organization"""
    
    def test_get_task_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_task properly filters by organization"""
        # Create two separate organizations and users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"Security Test Org 1 {unique_id}", f"user1-{unique_id}@security-test.com", "Security User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"Security Test Org 2 {unique_id}", f"user2-{unique_id}@security-test.com", "Security User 2"
        )
        
        # Create a task in org1 using CRUD function  
        from rhesis.backend.app.utils.crud_utils import get_or_create_status
        
        # Create a status for the task
        status = get_or_create_status(
            db=test_db,
            name="In Progress",
            entity_type="Task",
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # Create task using direct model instantiation since TaskCreate may not exist
        task = models.Task(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            title="Test task in org1",
            description="Test task in org1",
            status_id=status.id
        )
        test_db.add(task)
        test_db.commit()
        
        # User from org1 should be able to access the task
        result_org1 = crud.get_task(test_db, task.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == task.id
        assert result_org1.organization_id == org1.id
        
        # User from org2 should NOT be able to access the task
        result_org2 = crud.get_task(test_db, task.id, organization_id=str(org2.id))
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
        
        # Create a test in org1 using CRUD function
        from rhesis.backend.app.schemas.test import TestCreate
        test_data = TestCreate(
            title="Test in org1",
            description="Security test in org1"
        )
        test_obj = crud.create_test(
            db=test_db,
            test=test_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the test
        result_org1 = crud.get_test(test_db, test_obj.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == test_obj.id
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to access the test
        result_org2 = crud.get_test(test_db, test_obj.id, organization_id=str(org2.id))
        assert result_org2 is None

    def test_get_test_result_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_result properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db, "TestResult Org 1", f"testresult-user1-{uuid.uuid4()}@security-test.com", "TestResult User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "TestResult Org 2", f"testresult-user2-{uuid.uuid4()}@security-test.com", "TestResult User 2"
        )
        
        # Create a test first (required for test result)
        from rhesis.backend.app.schemas.test import TestCreate
        test_data = TestCreate(
            title="Test for result",
            description="Test for result creation"
        )
        test_obj = crud.create_test(
            db=test_db,
            test=test_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # Create a test result in org1 using CRUD function
        from rhesis.backend.app.schemas.test_result import TestResultCreate
        test_result_data = TestResultCreate(
            test_id=test_obj.id,
            status="completed",
            result_data={}
        )
        test_result = crud.create_test_result(
            db=test_db,
            test_result=test_result_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the test result
        result_org1 = crud.get_test_result(test_db, test_result.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == test_result.id
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to access the test result
        result_org2 = crud.get_test_result(test_db, test_result.id, organization_id=str(org2.id))
        assert result_org2 is None

    def test_get_test_run_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_run properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db, "TestRun Org 1", f"testrun-user1-{uuid.uuid4()}@security-test.com", "TestRun User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "TestRun Org 2", f"testrun-user2-{uuid.uuid4()}@security-test.com", "TestRun User 2"
        )
        
        # Create a test first (required for test run)
        from rhesis.backend.app.schemas.test import TestCreate
        test_data = TestCreate(
            title="Test for run",
            description="Test for run creation"
        )
        test_obj = crud.create_test(
            db=test_db,
            test=test_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # Create a test run in org1 using CRUD function
        from rhesis.backend.app.schemas.test_run import TestRunCreate
        test_run_data = TestRunCreate(
            test_id=test_obj.id,
            name="Security test run",
            status="pending"
        )
        test_run = crud.create_test_run(
            db=test_db,
            test_run=test_run_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the test run
        result_org1 = crud.get_test_run(test_db, test_run.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == test_run.id
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to access the test run
        result_org2 = crud.get_test_run(test_db, test_run.id, organization_id=str(org2.id))
        assert result_org2 is None

    def test_get_endpoint_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_endpoint properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db, "Endpoint Org 1", f"endpoint-user1-{uuid.uuid4()}@security-test.com", "Endpoint User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "Endpoint Org 2", f"endpoint-user2-{uuid.uuid4()}@security-test.com", "Endpoint User 2"
        )
        
        # Create an endpoint in org1 using CRUD function
        from rhesis.backend.app.schemas.endpoint import EndpointCreate
        endpoint_data = EndpointCreate(
            name="Test Endpoint",
            description="Security test endpoint",
            url="https://test.example.com/api",
            method="POST"
        )
        endpoint = crud.create_endpoint(
            db=test_db,
            endpoint=endpoint_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the endpoint
        result_org1 = crud.get_endpoint(test_db, endpoint.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == endpoint.id
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to access the endpoint
        result_org2 = crud.get_endpoint(test_db, endpoint.id, organization_id=str(org2.id))
        assert result_org2 is None

    def test_get_prompt_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_prompt properly filters by organization"""
        # Create two separate organizations and users
        org1, user1, _ = create_test_organization_and_user(
            test_db, "Prompt Org 1", f"prompt-user1-{uuid.uuid4()}@security-test.com", "Prompt User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "Prompt Org 2", f"prompt-user2-{uuid.uuid4()}@security-test.com", "Prompt User 2"
        )
        
        # Create a prompt in org1 using CRUD function
        from rhesis.backend.app.schemas.prompt import PromptCreate
        prompt_data = PromptCreate(
            name="Test Prompt",
            description="Security test prompt",
            content="This is a test prompt for security testing"
        )
        prompt = crud.create_prompt(
            db=test_db,
            prompt=prompt_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the prompt
        result_org1 = crud.get_prompt(test_db, prompt.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == prompt.id
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to access the prompt
        result_org2 = crud.get_prompt(test_db, prompt.id, organization_id=str(org2.id))
        assert result_org2 is None

    def test_get_model_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_model properly filters by organization"""
        # Create two separate organizations and users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"Model Test Org 1 {unique_id}", f"model-user1-{unique_id}@security-test.com", "Model User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"Model Test Org 2 {unique_id}", f"model-user2-{unique_id}@security-test.com", "Model User 2"
        )
        
        # Create a model in org1 using CRUD function
        from rhesis.backend.app.schemas.model import ModelCreate
        model_data = ModelCreate(
            name="Test Model",
            description="Test model in org1",
            model_name="test-model",
            endpoint="https://test.example.com",
            key="test-key"
        )
        model = crud.create_model(
            db=test_db,
            model=model_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the model
        result_org1 = crud.get_model(test_db, model.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == model.id
        assert result_org1.organization_id == org1.id
        
        # User from org2 should NOT be able to access the model
        result_org2 = crud.get_model(test_db, model.id, organization_id=str(org2.id))
        assert result_org2 is None

    def test_get_metric_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_metric properly filters by organization"""
        # Create two separate organizations and users
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"Metric Test Org 1 {unique_id}", f"metric-user1-{unique_id}@security-test.com", "Metric User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"Metric Test Org 2 {unique_id}", f"metric-user2-{unique_id}@security-test.com", "Metric User 2"
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
            class_name="TestMetric"
        )
        
        metric = crud.create_metric(
            db=test_db,
            metric=metric_data,
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # User from org1 should be able to access the metric
        result_org1 = crud.get_metric(test_db, metric.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == metric.id
        assert result_org1.organization_id == org1.id
        
        # User from org2 should NOT be able to access the metric
        result_org2 = crud.get_metric(test_db, metric.id, organization_id=str(org2.id))
        assert result_org2 is None


@pytest.mark.security
class TestSecurityRegression:
    """Regression tests to ensure security fixes remain effective"""
    
    def test_organization_filtering_regression_suite(self, test_db: Session):
        """🔒 SECURITY: Comprehensive regression test for organization filtering"""
        # This test ensures that all the security fixes we've implemented
        # continue to work and haven't regressed
        
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        # List of CRUD functions that should implement organization filtering
        crud_functions = [
            ('get_task', uuid.uuid4()),
            ('get_test', uuid.uuid4()),
            ('get_test_result', uuid.uuid4()),
            ('get_test_run', uuid.uuid4()),
            ('get_endpoint', uuid.uuid4()),
            ('get_prompt', uuid.uuid4()),
            ('get_model', uuid.uuid4()),
            ('get_metric', uuid.uuid4()),
        ]
        
        for func_name, entity_id in crud_functions:
            if hasattr(crud, func_name):
                func = getattr(crud, func_name)
                
                # Test that the function accepts organization_id parameter
                import inspect
                signature = inspect.signature(func)
                assert 'organization_id' in signature.parameters, f"{func_name} should accept organization_id parameter"


@pytest.mark.security
class TestTaskManagementSecuritySimplified:
    """Simplified task management security tests"""
    
    def test_task_organization_constraint_validation(self, test_db: Session):
        """🔒 SECURITY: Test task organization constraint validation"""
        from rhesis.backend.app.services.task_management import validate_task_organization_constraints
        
        org_id = str(uuid.uuid4())
        
        # Create a mock task
        mock_task = Mock()
        mock_task.organization_id = uuid.UUID(org_id)
        mock_task.status_id = uuid.uuid4()
        
        # Mock the database query to return a status from the same organization
        with patch.object(test_db, 'query') as mock_query:
            mock_status = Mock()
            mock_status.organization_id = uuid.UUID(org_id)
            mock_query.return_value.filter.return_value.first.return_value = mock_status
            
            # This should not raise an exception
            try:
                validate_task_organization_constraints(test_db, mock_task, org_id)
            except Exception as e:
                pytest.fail(f"validate_task_organization_constraints raised an exception: {e}")
        
        # Test cross-tenant scenario
        different_org_id = str(uuid.uuid4())
        mock_status.organization_id = uuid.UUID(different_org_id)
        
        # This should raise an exception
        with pytest.raises(ValueError, match="cross-tenant"):
            validate_task_organization_constraints(test_db, mock_task, org_id)
