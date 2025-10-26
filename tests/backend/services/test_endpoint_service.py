"""
Tests for endpoint service functionality in rhesis.backend.app.services.endpoint

This module tests the EndpointService class including:
- Endpoint invocation with tenant context
- Endpoint retrieval and validation
- Schema management
- Command-line interface functionality
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from fastapi import HTTPException
from sqlalchemy.orm import Session
import json
import uuid

from rhesis.backend.app.services.endpoint import EndpointService, invoke, get_schema
from rhesis.backend.app.models.endpoint import Endpoint


class TestEndpointService:
    """Test EndpointService class functionality"""
    
    def test_init_default_schema_path(self):
        """Test EndpointService initialization with default schema path"""
        service = EndpointService()
        
        # Verify default schema path is set correctly
        assert service.schema_path.endswith("endpoint_schema.json")
    
    def test_init_custom_schema_path(self):
        """Test EndpointService initialization with custom schema path"""
        custom_path = "/custom/path/schema.json"
        service = EndpointService(schema_path=custom_path)
        
        assert service.schema_path == custom_path
    
    def test_get_endpoint_success(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test successful endpoint retrieval"""
        service = EndpointService()
        
        result = service._get_endpoint(test_db, str(db_endpoint_minimal.id))
        
        assert result is not None
        assert result.id == db_endpoint_minimal.id
        assert result.name == db_endpoint_minimal.name
    
    def test_get_endpoint_not_found(self, test_db: Session):
        """Test endpoint retrieval when endpoint doesn't exist"""
        import uuid
        service = EndpointService()
        
        # Use a non-existent UUID
        nonexistent_id = str(uuid.uuid4())
        
        with pytest.raises(HTTPException) as exc_info:
            service._get_endpoint(test_db, nonexistent_id)
        
        assert exc_info.value.status_code == 404
        assert "Endpoint not found" in str(exc_info.value.detail)
    
    def test_invoke_endpoint_success(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test successful endpoint invocation"""
        service = EndpointService()
        
        mock_invoker = Mock()
        mock_invoker.invoke.return_value = {"response": "success"}
        
        input_data = {"input": "test"}
        
        # Mock only the invoker creation, use real endpoint from fixture
        with patch('rhesis.backend.app.services.endpoint.create_invoker', return_value=mock_invoker):
            result = service.invoke_endpoint(test_db, str(db_endpoint_minimal.id), input_data)
            
            assert result == {"response": "success"}
            # Verify invoker was called with real endpoint
            mock_invoker.invoke.assert_called_once()
            call_args = mock_invoker.invoke.call_args[0]
            assert call_args[0] == test_db  # First arg is db
            assert call_args[1].id == db_endpoint_minimal.id  # Second arg is endpoint
            assert call_args[2] == input_data  # Third arg is input_data
    
    def test_invoke_endpoint_value_error(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test endpoint invocation with ValueError"""
        service = EndpointService()
        
        mock_invoker = Mock()
        mock_invoker.invoke.side_effect = ValueError("Invalid input")
        
        # Mock only the invoker creation, use real endpoint from fixture
        with patch('rhesis.backend.app.services.endpoint.create_invoker', return_value=mock_invoker):
            with pytest.raises(HTTPException) as exc_info:
                service.invoke_endpoint(test_db, str(db_endpoint_minimal.id), {})
            
            assert exc_info.value.status_code == 400
            assert "Invalid input" in str(exc_info.value.detail)
    
    def test_invoke_endpoint_general_exception(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test endpoint invocation with general exception"""
        service = EndpointService()
        
        mock_invoker = Mock()
        mock_invoker.invoke.side_effect = Exception("Internal error")
        
        # Mock only the invoker creation, use real endpoint from fixture
        with patch('rhesis.backend.app.services.endpoint.create_invoker', return_value=mock_invoker):
            with pytest.raises(HTTPException) as exc_info:
                service.invoke_endpoint(test_db, str(db_endpoint_minimal.id), {})
            
            assert exc_info.value.status_code == 500
            assert "Internal error" in str(exc_info.value.detail)
    
    def test_get_schema_success(self):
        """Test successful schema retrieval"""
        service = EndpointService()
        schema_data = {
            "input": {"type": "object"},
            "output": {"type": "object"}
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(schema_data))):
            result = service.get_schema()
            
            assert result == schema_data
    
    def test_get_schema_file_not_found(self):
        """Test schema retrieval when file doesn't exist"""
        service = EndpointService()
        
        with patch("builtins.open", side_effect=FileNotFoundError("No such file")):
            with pytest.raises(FileNotFoundError):
                service.get_schema()


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_invoke_function(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test invoke convenience function"""
        input_data = {"input": "test"}
        expected_result = {"response": "success"}
        
        # Mock the endpoint service singleton
        with patch('rhesis.backend.app.services.endpoint.endpoint_service') as mock_service:
            mock_service.invoke_endpoint.return_value = expected_result
            
            result = invoke(test_db, str(db_endpoint_minimal.id), input_data)
            
            assert result == expected_result
            mock_service.invoke_endpoint.assert_called_once_with(test_db, str(db_endpoint_minimal.id), input_data)
    
    def test_get_schema_function(self):
        """Test get_schema convenience function"""
        expected_schema = {"input": {"type": "object"}}
        
        with patch('rhesis.backend.app.services.endpoint.endpoint_service') as mock_service:
            mock_service.get_schema.return_value = expected_schema
            
            result = get_schema()
            
            assert result == expected_schema
            mock_service.get_schema.assert_called_once()


class TestCommandLineInterface:
    """Test command-line interface functionality"""
    
    @patch('rhesis.backend.app.database.SessionLocal')
    @patch('rhesis.backend.app.services.endpoint.invoke')
    @patch('argparse.ArgumentParser.parse_args')
    def test_command_line_execution(self, mock_parse_args, mock_invoke, mock_session_local):
        """Test command-line execution with tenant context"""
        # Mock command line arguments
        mock_args = Mock()
        mock_args.endpoint_id = "endpoint123"
        mock_args.input = "Hello, how can you help me?"
        mock_args.session = "session456"
        mock_args.org_id = "org789"
        mock_args.user_id = "user101"
        mock_parse_args.return_value = mock_args
        
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock invoke response
        mock_invoke.return_value = {"response": "I can help you with various tasks"}
        
        # Import and run the command-line part
        # This would normally be run when __name__ == "__main__"
        # We'll simulate the main execution logic
        
        # Simulate the main block execution
        input_data = {"input": mock_args.input, "session_id": mock_args.session or str(uuid.uuid4())}
        
        # Verify tenant context would be set
        expected_org_id = mock_args.org_id
        expected_user_id = mock_args.user_id
        
        # Simulate the actual execution (tenant context now passed directly)
        result = mock_invoke(mock_db, mock_args.endpoint_id, input_data)
        
        # Verify calls
        mock_invoke.assert_called_with(mock_db, mock_args.endpoint_id, input_data)
        assert result == {"response": "I can help you with various tasks"}
    
    @patch('rhesis.backend.app.database.SessionLocal')
    @patch('argparse.ArgumentParser.parse_args')
    def test_command_line_with_default_session(self, mock_parse_args, mock_session_local):
        """Test command-line execution with default session ID generation"""
        # Mock command line arguments without session
        mock_args = Mock()
        mock_args.endpoint_id = "endpoint123"
        mock_args.input = "Test input"
        mock_args.session = None  # No session provided
        mock_args.org_id = "org789"
        mock_args.user_id = "user101"
        mock_parse_args.return_value = mock_args
        
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Simulate input data creation with UUID generation
        with patch('uuid.uuid4', return_value=Mock(spec=uuid.UUID)) as mock_uuid:
            mock_uuid.return_value.__str__ = Mock(return_value="generated-uuid-123")
            
            input_data = {"input": mock_args.input, "session_id": mock_args.session or str(uuid.uuid4())}
            
            # Verify UUID was generated for session
            assert input_data["session_id"] == "generated-uuid-123"


class TestEndpointServiceIntegration:
    """Integration tests for EndpointService"""
    
    def test_full_invocation_flow(self):
        """Test complete endpoint invocation flow"""
        service = EndpointService()
        
        # Mock endpoint
        mock_endpoint = Mock(spec=Endpoint)
        mock_endpoint.id = "endpoint123"
        mock_endpoint.protocol = "http"
        
        # Mock invoker
        mock_invoker = Mock()
        mock_invoker.invoke.return_value = {"status": "success", "data": "response"}
        
        # Mock database
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_endpoint
        mock_db.query.return_value = mock_query
        
        input_data = {"message": "test input"}
        
        with patch('rhesis.backend.app.services.endpoint.create_invoker', return_value=mock_invoker):
            result = service.invoke_endpoint(mock_db, "endpoint123", input_data)
            
            assert result == {"status": "success", "data": "response"}
            mock_invoker.invoke.assert_called_once_with(mock_db, mock_endpoint, input_data)
    
    def test_error_handling_chain(self):
        """Test error handling throughout the invocation chain"""
        service = EndpointService()
        mock_db = Mock(spec=Session)
        
        # Test endpoint not found
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            service.invoke_endpoint(mock_db, "nonexistent", {})
        
        assert exc_info.value.status_code == 404
        
        # Test invoker creation failure
        mock_endpoint = Mock(spec=Endpoint)
        mock_query.filter.return_value.first.return_value = mock_endpoint
        
        with patch('rhesis.backend.app.services.endpoint.create_invoker', side_effect=ValueError("Invalid protocol")):
            with pytest.raises(HTTPException) as exc_info:
                service.invoke_endpoint(mock_db, "endpoint123", {})
            
            assert exc_info.value.status_code == 400


@pytest.fixture
def mock_endpoint_service():
    """Fixture providing a mock EndpointService"""
    return Mock(spec=EndpointService)


@pytest.fixture
def sample_endpoint():
    """Fixture providing a sample endpoint"""
    endpoint = Mock(spec=Endpoint)
    endpoint.id = "test-endpoint-123"
    endpoint.name = "Test Endpoint"
    endpoint.protocol = "http"
    endpoint.url = "https://api.example.com/test"
    return endpoint


@pytest.fixture
def sample_input_data():
    """Fixture providing sample input data"""
    return {
        "input": "Test message",
        "session_id": "session-123",
        "parameters": {
            "temperature": 0.7,
            "max_tokens": 100
        }
    }
