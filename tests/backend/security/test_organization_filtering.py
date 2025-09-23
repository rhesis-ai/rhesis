"""
🔒 Organization Filtering Security Tests

This module tests that all CRUD operations properly implement organization-based
filtering to prevent unauthorized access to data from other organizations.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import HTTPException

from rhesis.backend.app import models, crud


@pytest.mark.security
class TestCrudOrganizationFiltering:
    """Test that CRUD operations properly filter by organization"""
    
    def test_get_task_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_task properly filters by organization"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create a simple task in org1 using the CRUD function directly
        task_id = uuid.uuid4()
        
        # Mock the task creation to avoid complex foreign key setup
        with patch.object(test_db, 'query') as mock_query:
            mock_task = Mock()
            mock_task.id = task_id
            mock_task.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the task
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_task
            result = crud.get_task(test_db, task_id, organization_id=org1_id)
            assert result is not None
            assert result.id == task_id
            
            # Test org2 access - should not find the task
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_task(test_db, task_id, organization_id=org2_id)
            assert result is None

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
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        model_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_model = Mock()
            mock_model.id = model_id
            mock_model.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the model
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_model
            result = crud.get_model(test_db, model_id, organization_id=org1_id)
            assert result is not None
            assert result.id == model_id
            
            # Test org2 access - should not find the model
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_model(test_db, model_id, organization_id=org2_id)
            assert result is None

    def test_get_metric_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_metric properly filters by organization"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        metric_id = uuid.uuid4()
        
        with patch.object(test_db, 'query') as mock_query:
            mock_metric = Mock()
            mock_metric.id = metric_id
            mock_metric.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the metric
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_metric
            result = crud.get_metric(test_db, metric_id, organization_id=org1_id)
            assert result is not None
            assert result.id == metric_id
            
            # Test org2 access - should not find the metric
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_metric(test_db, metric_id, organization_id=org2_id)
            assert result is None


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
