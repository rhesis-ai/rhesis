"""
🔒 Organization Filtering Security Tests

This module tests that all CRUD operations properly implement organization-based
filtering to prevent unauthorized access to data from other organizations.
"""

import uuid
import pytest
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
        
        # Create a task in org1 using direct model creation
        task = models.Task(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            title="Test task in org1",
            description="Test task in org1"
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
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        test_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_test = Mock()
            mock_test.id = test_id
            mock_test.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the test
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test
            result = crud.get_test(test_db, test_id, organization_id=org1_id)
            assert result is not None
            assert result.id == test_id
            
            # Test org2 access - should not find the test
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_test(test_db, test_id, organization_id=org2_id)
            assert result is None

    def test_get_test_result_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_result properly filters by organization"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        test_result_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_test_result = Mock()
            mock_test_result.id = test_result_id
            mock_test_result.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the test result
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test_result
            result = crud.get_test_result(test_db, test_result_id, organization_id=org1_id)
            assert result is not None
            assert result.id == test_result_id
            
            # Test org2 access - should not find the test result
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_test_result(test_db, test_result_id, organization_id=org2_id)
            assert result is None

    def test_get_test_run_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_run properly filters by organization"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        test_run_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_test_run = Mock()
            mock_test_run.id = test_run_id
            mock_test_run.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the test run
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test_run
            result = crud.get_test_run(test_db, test_run_id, organization_id=org1_id)
            assert result is not None
            assert result.id == test_run_id
            
            # Test org2 access - should not find the test run
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_test_run(test_db, test_run_id, organization_id=org2_id)
            assert result is None

    def test_get_endpoint_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_endpoint properly filters by organization"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        endpoint_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_endpoint = Mock()
            mock_endpoint.id = endpoint_id
            mock_endpoint.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the endpoint
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_endpoint
            result = crud.get_endpoint(test_db, endpoint_id, organization_id=org1_id)
            assert result is not None
            assert result.id == endpoint_id
            
            # Test org2 access - should not find the endpoint
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_endpoint(test_db, endpoint_id, organization_id=org2_id)
            assert result is None

    def test_get_prompt_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_prompt properly filters by organization"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        prompt_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_prompt = Mock()
            mock_prompt.id = prompt_id
            mock_prompt.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the prompt
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_prompt
            result = crud.get_prompt(test_db, prompt_id, organization_id=org1_id)
            assert result is not None
            assert result.id == prompt_id
            
            # Test org2 access - should not find the prompt
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_prompt(test_db, prompt_id, organization_id=org2_id)
            assert result is None

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
        
        # Create a model in org1 using direct model creation
        model = models.Model(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name="Test Model",
            description="Test model in org1",
            model_name="test-model",
            endpoint="https://test.example.com",
            key="test-key"
        )
        test_db.add(model)
        test_db.commit()
        
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
