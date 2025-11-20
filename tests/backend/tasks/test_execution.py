"""
Tests for test execution functionality in rhesis.backend.tasks.execution.test_execution

This module tests the core test execution logic including:
- Tenant context setup
- Test data retrieval
- Endpoint invocation
- Response evaluation
- Result processing and storage
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

# setup_tenant_context was removed - tenant context now passed directly to CRUD operations
from rhesis.backend.app.models.test import Test

# TestSetupTenantContext class removed - setup_tenant_context function no longer exists
# Tenant context is now passed directly to CRUD operations


class TestDataRetrievalFunctions:
    """Test data retrieval functions (if they exist in the module)"""

    def test_retrieve_test_data_success(self):
        """Test successful test data retrieval"""
        # This is a placeholder for testing data retrieval functions
        # The actual implementation would depend on the specific functions in the module

        mock_db = Mock(spec=Session)
        test_id = "test-123"

        # Mock test object
        mock_test = Mock(spec=Test)
        mock_test.id = test_id
        mock_test.input_data = "Test input"
        mock_test.expected_output = "Expected output"

        # This would test actual data retrieval functions when they exist
        # For now, this is a structure for future implementation
        pass

    def test_retrieve_test_data_not_found(self):
        """Test test data retrieval when test not found"""
        # Placeholder for testing error handling in data retrieval
        pass


class TestEndpointInvocation:
    """Test endpoint invocation functionality"""

    @pytest.mark.skip(reason="Placeholder test - endpoint invocation is now handled by executors")
    def test_invoke_endpoint_with_context(self):
        """Test endpoint invocation with proper tenant context"""
        # This would test the endpoint invocation logic
        # when it's available in the test_execution module
        # Note: Endpoint invocation is now handled by the executor classes
        # and tested in those modules instead

        mock_db = Mock(spec=Session)
        endpoint_id = "endpoint-123"
        input_data = {"input": "test message"}

        # This is a placeholder - actual endpoint invocation tests are in
        # tests/backend/services/test_endpoint_service.py
        pass


class TestResponseEvaluation:
    """Test response evaluation functionality"""

    def test_evaluate_response_success(self):
        """Test successful response evaluation"""
        # This would test the response evaluation logic
        # when it's available in the test_execution module

        response = "AI generated response"
        expected = "Expected response"
        metrics = ["accuracy", "relevance"]

        # Mock evaluation results
        expected_results = {
            "accuracy": {"score": 0.85, "details": "Good accuracy"},
            "relevance": {"score": 0.90, "details": "Highly relevant"},
        }

        # This would test actual evaluation when implemented
        pass

    def test_evaluate_response_with_metrics(self):
        """Test response evaluation with specific metrics"""
        # Placeholder for testing metric-specific evaluation
        pass


class TestResultProcessing:
    """Test result processing and storage"""

    def test_process_and_store_results(self):
        """Test processing and storing evaluation results"""
        # This would test result processing logic
        # when it's available in the test_execution module

        mock_db = Mock(spec=Session)
        test_id = "test-123"
        results = {
            "status": "completed",
            "response": "AI response",
            "evaluation_results": {"accuracy": 0.85},
        }

        # This would test actual result storage when implemented
        pass

    def test_handle_execution_failure(self):
        """Test handling of execution failures"""
        # Placeholder for testing failure handling
        pass


class TestExecutionWorkflow:
    """Test complete execution workflow integration"""

    def test_full_execution_workflow(self):
        """Test complete test execution workflow"""
        # Note: setup_tenant_context was removed - tenant context now passed directly to CRUD operations
        # This test would need to be updated to test actual execution workflow components
        pass

    def test_execution_with_error_handling(self):
        """Test execution workflow with proper error handling"""
        # Note: setup_tenant_context was removed - tenant context now passed directly to CRUD operations
        # This test would need to be updated to test actual error handling in execution workflow
        pass


class TestMetricConfiguration:
    """Test metric configuration and loading"""

    def test_create_metric_config_from_model(self):
        """Test creating metric configuration from model"""
        # This would test metric configuration creation
        pass


class TestExecutionUtilities:
    """Test execution utility functions"""

    @pytest.mark.skip(reason="Placeholder test - utility functions are now in executors module")
    def test_extract_response_with_fallback(self):
        """Test response extraction with fallback logic"""
        # This would test response extraction utilities
        # Note: Response extraction is now handled by executor classes
        # and tested in those modules instead

        raw_response = {"data": {"response": "Extracted response"}}

        # This is a placeholder - actual utility tests would be in
        # tests/backend/tasks/test_executors.py or similar
        pass

    @pytest.mark.skip(reason="Placeholder test - utility functions are now in executors module")
    def test_get_or_create_status(self):
        """Test status creation/retrieval utility"""
        # This would test status management utilities
        # Note: Status management is now handled elsewhere
        # and tested in those modules instead

        mock_db = Mock(spec=Session)
        status_name = "completed"

        # This is a placeholder - actual status handling tests would be
        # in the appropriate service/crud test modules
        pass


@pytest.fixture
def mock_test_execution_db():
    """Fixture providing a mock database session for test execution"""
    db = Mock(spec=Session)
    db.execute.return_value = Mock()  # Mock successful SQL execution
    return db


@pytest.fixture
def sample_test_data():
    """Fixture providing sample test data"""
    return {
        "id": "test-123",
        "input_data": "What is the capital of France?",
        "expected_output": "The capital of France is Paris.",
        "context": "Geography question",
        "metrics": ["accuracy", "relevance"],
    }


@pytest.fixture
def sample_execution_context():
    """Fixture providing sample execution context"""
    return {
        "organization_id": "org-456",
        "user_id": "user-789",
        "test_id": "test-123",
        "endpoint_id": "endpoint-456",
    }


class TestExecutionContextFixtures:
    """Test execution context management with fixtures"""

    def test_with_execution_context(self, mock_test_execution_db, sample_execution_context):
        """Test execution with proper context using fixtures"""
        # Note: setup_tenant_context was removed - tenant context now passed directly to CRUD operations
        # This test would need to be updated to test actual execution context management
        pass

    def test_with_sample_data(self, sample_test_data):
        """Test execution workflow with sample test data"""

        # Verify sample data structure
        assert "id" in sample_test_data
        assert "input_data" in sample_test_data
        assert "expected_output" in sample_test_data
        assert isinstance(sample_test_data["metrics"], list)


class TestBackendEndpointTargetConversationContext:
    """Test conversation context maintenance in BackendEndpointTarget"""

    def test_conversation_id_extraction_from_response(self):
        """Test that BackendEndpointTarget correctly extracts conversation_id from endpoint responses"""
        from unittest.mock import Mock, patch
        from uuid import uuid4

        from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock endpoint service response with session_id
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint.return_value = {
            "output": "Test response",
            "session_id": "test-session-123",
            "metadata": {"test": "data"},
        }

        # Create valid UUIDs for testing
        endpoint_id = str(uuid4())
        organization_id = str(uuid4())

        # Create BackendEndpointTarget instance
        with (
            patch(
                "rhesis.backend.tasks.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.tasks.execution.penelope_target.crud.get_endpoint"
            ) as mock_get_endpoint,
        ):
            # Mock endpoint exists
            mock_endpoint = Mock()
            mock_endpoint.name = "test-endpoint"
            mock_endpoint.url = "https://test.com"
            mock_endpoint.description = "Test endpoint"
            mock_endpoint.protocol = "REST"
            mock_get_endpoint.return_value = mock_endpoint

            target = BackendEndpointTarget(
                db=mock_db, endpoint_id=endpoint_id, organization_id=organization_id
            )

            # Send message without conversation_id
            response = target.send_message("Hello")

            # Verify response contains extracted conversation_id
            assert response.success is True
            assert response.content == "Test response"
            assert response.conversation_id == "test-session-123"

    def test_conversation_id_passthrough_to_endpoint(self):
        """Test that BackendEndpointTarget passes conversation_id to endpoint service"""
        from unittest.mock import Mock, patch
        from uuid import uuid4

        from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock endpoint service
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint.return_value = {
            "output": "Follow-up response",
            "session_id": "test-session-123",
        }

        # Create valid UUIDs for testing
        endpoint_id = str(uuid4())
        organization_id = str(uuid4())

        # Create BackendEndpointTarget instance
        with (
            patch(
                "rhesis.backend.tasks.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.tasks.execution.penelope_target.crud.get_endpoint"
            ) as mock_get_endpoint,
        ):
            # Mock endpoint exists
            mock_endpoint = Mock()
            mock_endpoint.name = "test-endpoint"
            mock_get_endpoint.return_value = mock_endpoint

            target = BackendEndpointTarget(
                db=mock_db, endpoint_id=endpoint_id, organization_id=organization_id
            )

            # Send message with conversation_id
            response = target.send_message("Follow up", conversation_id="test-session-123")

            # Verify endpoint service was called with session_id
            mock_endpoint_service.invoke_endpoint.assert_called_once()
            call_args = mock_endpoint_service.invoke_endpoint.call_args
            input_data = call_args.kwargs["input_data"]
            assert input_data["session_id"] == "test-session-123"

            # Verify response maintains conversation_id
            assert response.conversation_id == "test-session-123"

    def test_flexible_conversation_field_extraction(self):
        """Test that BackendEndpointTarget handles multiple conversation field names"""
        from unittest.mock import Mock, patch
        from uuid import uuid4

        from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget

        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock endpoint service response with thread_id instead of session_id
        mock_endpoint_service = Mock()
        mock_endpoint_service.invoke_endpoint.return_value = {
            "output": "Response with thread_id",
            "thread_id": "thread-456",
            "metadata": {},
        }

        # Create valid UUID for testing
        endpoint_id = str(uuid4())

        # Create BackendEndpointTarget instance
        with (
            patch(
                "rhesis.backend.tasks.execution.penelope_target.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.tasks.execution.penelope_target.crud.get_endpoint"
            ) as mock_get_endpoint,
        ):
            # Mock endpoint exists
            mock_endpoint = Mock()
            mock_get_endpoint.return_value = mock_endpoint

            target = BackendEndpointTarget(db=mock_db, endpoint_id=endpoint_id)

            # Send message with thread_id in kwargs
            response = target.send_message("Hello", thread_id="thread-456")

            # Verify thread_id was extracted and used
            assert response.conversation_id == "thread-456"
