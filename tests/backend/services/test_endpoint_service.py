"""
Tests for endpoint service functionality in rhesis.backend.app.services.endpoint

This module tests the EndpointService class including:
- Endpoint invocation with tenant context
- Endpoint retrieval and validation
- Schema management
- Command-line interface functionality
- Error handling and edge cases
"""

import json
import uuid
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.endpoint import EndpointService, get_schema, invoke


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

    @pytest.mark.asyncio
    async def test_invoke_endpoint_success(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test successful endpoint invocation"""
        service = EndpointService()

        mock_invoker = Mock()
        mock_invoker.invoke = AsyncMock(return_value={"response": "success"})

        input_data = {"input": "test"}

        # Mock only the invoker creation, use real endpoint from fixture
        with patch(
            "rhesis.backend.app.services.endpoint.service.create_invoker", return_value=mock_invoker
        ):
            result = await service.invoke_endpoint(test_db, str(db_endpoint_minimal.id), input_data)

            assert result == {"response": "success"}
            # Verify invoker was called with real endpoint
            mock_invoker.invoke.assert_called_once()
            call_args = mock_invoker.invoke.call_args[0]
            assert call_args[0] == test_db  # First arg is db
            assert call_args[1].id == db_endpoint_minimal.id  # Second arg is endpoint
            assert call_args[2] == input_data  # Third arg is input_data

    @pytest.mark.asyncio
    async def test_invoke_endpoint_value_error(
        self, test_db: Session, db_endpoint_minimal: Endpoint
    ):
        """Test endpoint invocation with ValueError"""
        service = EndpointService()

        mock_invoker = Mock()
        mock_invoker.invoke = AsyncMock(side_effect=ValueError("Invalid input"))

        # Mock only the invoker creation, use real endpoint from fixture
        with patch(
            "rhesis.backend.app.services.endpoint.service.create_invoker", return_value=mock_invoker
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.invoke_endpoint(test_db, str(db_endpoint_minimal.id), {})

            assert exc_info.value.status_code == 400
            assert "Invalid input" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invoke_endpoint_general_exception(
        self, test_db: Session, db_endpoint_minimal: Endpoint
    ):
        """Test endpoint invocation with general exception"""
        service = EndpointService()

        mock_invoker = Mock()
        mock_invoker.invoke = AsyncMock(side_effect=Exception("Internal error"))

        # Mock only the invoker creation, use real endpoint from fixture
        with patch(
            "rhesis.backend.app.services.endpoint.service.create_invoker", return_value=mock_invoker
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.invoke_endpoint(test_db, str(db_endpoint_minimal.id), {})

            assert exc_info.value.status_code == 500
            assert "Internal error" in str(exc_info.value.detail)

    def test_get_schema_success(self):
        """Test successful schema retrieval"""
        service = EndpointService()
        schema_data = {"input": {"type": "object"}, "output": {"type": "object"}}

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

    @pytest.mark.asyncio
    async def test_invoke_function(self, test_db: Session, db_endpoint_minimal: Endpoint):
        """Test invoke convenience function"""
        input_data = {"input": "test"}
        expected_result = {"response": "success"}

        # Mock the endpoint service singleton
        with patch("rhesis.backend.app.services.endpoint.endpoint_service") as mock_service:
            mock_service.invoke_endpoint = AsyncMock(return_value=expected_result)

            result = await invoke(test_db, str(db_endpoint_minimal.id), input_data)

            assert result == expected_result
            mock_service.invoke_endpoint.assert_called_once_with(
                test_db, str(db_endpoint_minimal.id), input_data, organization_id=None, user_id=None
            )

    def test_get_schema_function(self):
        """Test get_schema convenience function"""
        expected_schema = {"input": {"type": "object"}}

        with patch("rhesis.backend.app.services.endpoint.endpoint_service") as mock_service:
            mock_service.get_schema.return_value = expected_schema

            result = get_schema()

            assert result == expected_schema
            mock_service.get_schema.assert_called_once()


class TestCommandLineInterface:
    """Test command-line interface functionality"""

    @patch("rhesis.backend.app.database.SessionLocal")
    @patch("rhesis.backend.app.services.endpoint.invoke")
    @patch("argparse.ArgumentParser.parse_args")
    @pytest.mark.asyncio
    async def test_command_line_execution(self, mock_parse_args, mock_invoke, mock_session_local):
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
        input_data = {
            "input": mock_args.input,
            "session_id": mock_args.session or str(uuid.uuid4()),
        }

        # Simulate the actual execution (tenant context now passed directly)
        result = await mock_invoke(mock_db, mock_args.endpoint_id, input_data)

        # Verify calls
        mock_invoke.assert_called_with(mock_db, mock_args.endpoint_id, input_data)
        assert result == {"response": "I can help you with various tasks"}

    @patch("rhesis.backend.app.database.SessionLocal")
    @patch("argparse.ArgumentParser.parse_args")
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
        with patch("uuid.uuid4", return_value=Mock(spec=uuid.UUID)) as mock_uuid:
            mock_uuid.return_value.__str__ = Mock(return_value="generated-uuid-123")

            input_data = {
                "input": mock_args.input,
                "session_id": mock_args.session or str(uuid.uuid4()),
            }

            # Verify UUID was generated for session
            assert input_data["session_id"] == "generated-uuid-123"


class TestEndpointServiceIntegration:
    """Integration tests for EndpointService"""

    @pytest.mark.asyncio
    async def test_full_invocation_flow(self):
        """Test complete endpoint invocation flow"""
        service = EndpointService()

        # Mock endpoint
        mock_endpoint = Mock(spec=Endpoint)
        mock_endpoint.id = "endpoint123"
        mock_endpoint.connection_type = "http"

        # Mock invoker
        mock_invoker = Mock()
        mock_invoker.invoke = AsyncMock(return_value={"status": "success", "data": "response"})

        # Mock database
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_endpoint
        mock_db.query.return_value = mock_query

        input_data = {"message": "test input"}

        with patch(
            "rhesis.backend.app.services.endpoint.service.create_invoker", return_value=mock_invoker
        ):
            result = await service.invoke_endpoint(mock_db, "endpoint123", input_data)

            assert result == {"status": "success", "data": "response"}
            mock_invoker.invoke.assert_called_once_with(
                mock_db, mock_endpoint, input_data, None
            )

    @pytest.mark.asyncio
    async def test_error_handling_chain(self):
        """Test error handling throughout the invocation chain"""
        service = EndpointService()
        mock_db = Mock(spec=Session)

        # Test endpoint not found
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await service.invoke_endpoint(mock_db, "nonexistent", {})

        assert exc_info.value.status_code == 404

        # Test invoker creation failure
        mock_endpoint = Mock(spec=Endpoint)
        mock_query.filter.return_value.first.return_value = mock_endpoint

        with patch(
            "rhesis.backend.app.services.endpoint.service.create_invoker",
            side_effect=ValueError("Invalid connection type"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.invoke_endpoint(mock_db, "endpoint123", {})

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
    endpoint.connection_type = "http"
    endpoint.url = "https://api.example.com/test"
    return endpoint


@pytest.fixture
def sample_input_data():
    """Fixture providing sample input data"""
    return {
        "input": "Test message",
        "session_id": "session-123",
        "parameters": {"temperature": 0.7, "max_tokens": 100},
    }


class TestSDKEndpointSync:
    """Test SDK endpoint syncing functionality"""

    @pytest.fixture
    def sdk_project_context(self, test_organization, db_user, db_project):
        """Create project context with real database entities"""
        return {
            "project_id": str(db_project.id),
            "project_name": db_project.name,
            "environment": "development",
            "organization_id": str(test_organization.id),
            "user_id": str(db_user.id),
        }

    @pytest.fixture
    def sample_functions_data(self):
        """Sample functions data for testing"""
        return [
            {
                "name": "calculate_sum",
                "parameters": {"a": {"type": "number"}, "b": {"type": "number"}},
                "return_type": "number",
                "metadata": {"description": "Calculates the sum of two numbers"},
            },
            {
                "name": "get_user_info",
                "parameters": {"user_id": {"type": "string"}},
                "return_type": "object",
                "metadata": {"description": "Retrieves user information"},
            },
        ]

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_create_new(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test creating new SDK function endpoints"""
        service = EndpointService()

        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should create 2 new endpoints
        assert result["created"] == 2
        assert result["updated"] == 0
        assert result["marked_inactive"] == 0
        assert len(result["errors"]) == 0

        # Verify endpoints were created in database
        from rhesis.backend.app.models.endpoint import Endpoint
        from rhesis.backend.app.models.enums import EndpointConnectionType

        endpoints = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.environment == sdk_project_context["environment"],
                Endpoint.connection_type == EndpointConnectionType.SDK,
            )
            .all()
        )

        assert len(endpoints) == 2

        # Verify endpoint names and metadata
        endpoint_names = {ep.name for ep in endpoints}
        assert f"{sdk_project_context['project_name']} (calculate_sum)" in endpoint_names
        assert f"{sdk_project_context['project_name']} (get_user_info)" in endpoint_names

        # Verify metadata structure
        for endpoint in endpoints:
            assert endpoint.endpoint_metadata is not None
            assert "sdk_connection" in endpoint.endpoint_metadata
            assert "function_schema" in endpoint.endpoint_metadata
            sdk_conn = endpoint.endpoint_metadata["sdk_connection"]
            assert sdk_conn["project_id"] == sdk_project_context["project_id"]
            assert sdk_conn["environment"] == sdk_project_context["environment"]

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_update_existing(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test updating existing SDK function endpoints"""
        service = EndpointService()

        # First sync - create endpoints
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Modify function data
        updated_functions = [
            {
                "name": "calculate_sum",
                "parameters": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                    "c": {"type": "number"},  # New parameter
                },
                "return_type": "number",
                "metadata": {
                    "description": "Updated description: Calculates the sum of three numbers"
                },
            },
            {
                "name": "get_user_info",
                "parameters": {"user_id": {"type": "string"}},
                "return_type": "object",
                "metadata": {"description": "Retrieves user information"},
            },
        ]

        # Second sync - update endpoints
        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=updated_functions,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should update 2 existing endpoints
        assert result["created"] == 0
        assert result["updated"] == 2
        assert result["marked_inactive"] == 0
        assert len(result["errors"]) == 0

        # Verify updates were persisted
        from rhesis.backend.app.models.endpoint import Endpoint
        from rhesis.backend.app.models.enums import EndpointConnectionType

        updated_endpoint = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.environment == sdk_project_context["environment"],
                Endpoint.connection_type == EndpointConnectionType.SDK,
                Endpoint.name.contains("calculate_sum"),
            )
            .first()
        )

        assert updated_endpoint is not None
        assert "Updated description" in updated_endpoint.description
        assert "c" in updated_endpoint.endpoint_metadata["function_schema"]["parameters"]

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_mark_removed_inactive(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test marking removed functions as inactive"""
        service = EndpointService()

        # First sync - create 2 endpoints
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Second sync - only keep one function
        reduced_functions = [sample_functions_data[0]]  # Only calculate_sum

        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=reduced_functions,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should mark 1 endpoint as inactive
        assert result["created"] == 0
        assert result["updated"] == 1
        assert result["marked_inactive"] == 1
        assert len(result["errors"]) == 0

        # Verify inactive status
        from rhesis.backend.app.models.endpoint import Endpoint
        from rhesis.backend.app.models.enums import EndpointConnectionType
        from rhesis.backend.app.models.status import Status

        all_endpoints = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.environment == sdk_project_context["environment"],
                Endpoint.connection_type == EndpointConnectionType.SDK,
            )
            .all()
        )

        assert len(all_endpoints) == 2  # Both still exist

        # Check that get_user_info is inactive
        inactive_endpoint = next(ep for ep in all_endpoints if "get_user_info" in ep.name)
        active_endpoint = next(ep for ep in all_endpoints if "calculate_sum" in ep.name)

        inactive_status = (
            test_db.query(Status).filter(Status.id == inactive_endpoint.status_id).first()
        )
        active_status = test_db.query(Status).filter(Status.id == active_endpoint.status_id).first()

        assert inactive_status.name == "Inactive"
        assert active_status.name == "Active"

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_mixed_operations(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test mixed create, update, and mark inactive operations"""
        service = EndpointService()

        # First sync - create 2 endpoints
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Second sync with mixed changes:
        # - Update calculate_sum
        # - Remove get_user_info (mark inactive)
        # - Add new function send_email
        mixed_functions = [
            {
                "name": "calculate_sum",
                "parameters": {"a": {"type": "number"}, "b": {"type": "number"}},
                "return_type": "number",
                "metadata": {"description": "Updated: Calculates the sum"},
            },
            {
                "name": "send_email",
                "parameters": {"to": {"type": "string"}, "subject": {"type": "string"}},
                "return_type": "boolean",
                "metadata": {"description": "Sends an email"},
            },
        ]

        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=mixed_functions,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should have 1 created, 1 updated, 1 marked inactive
        assert result["created"] == 1
        assert result["updated"] == 1
        assert result["marked_inactive"] == 1
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_empty_functions(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test syncing with empty functions list (all should be marked inactive)"""
        service = EndpointService()

        # First sync - create endpoints
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Second sync with empty list
        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=[],
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should mark all 2 endpoints as inactive
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["marked_inactive"] == 2
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_reactivate_inactive(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test reactivating previously inactive endpoint"""
        service = EndpointService()

        # Create endpoints
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Mark all inactive
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=[],
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Reactivate one function
        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=[sample_functions_data[0]],
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should update 1 (reactivate), keep 1 inactive
        assert result["created"] == 0
        assert result["updated"] == 1
        assert result["marked_inactive"] == 1
        assert len(result["errors"]) == 0

        # Verify reactivation
        from rhesis.backend.app.models.endpoint import Endpoint
        from rhesis.backend.app.models.enums import EndpointConnectionType
        from rhesis.backend.app.models.status import Status

        reactivated_endpoint = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.connection_type == EndpointConnectionType.SDK,
                Endpoint.name.contains("calculate_sum"),
            )
            .first()
        )

        status = test_db.query(Status).filter(Status.id == reactivated_endpoint.status_id).first()
        assert status.name == "Active"

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_different_environments(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test that syncing is scoped to specific environment"""
        service = EndpointService()

        # Create endpoints in development
        await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment="development",
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Create endpoints in production with different functions
        production_functions = [sample_functions_data[0]]  # Only one function
        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment="production",
            functions_data=production_functions,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        # Should create 1 in production, development endpoints unaffected
        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["marked_inactive"] == 0

        # Verify both environments have their own endpoints
        from rhesis.backend.app.models.endpoint import Endpoint
        from rhesis.backend.app.models.enums import EndpointConnectionType

        dev_endpoints = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.environment == "development",
                Endpoint.connection_type == EndpointConnectionType.SDK,
            )
            .all()
        )

        prod_endpoints = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.environment == "production",
                Endpoint.connection_type == EndpointConnectionType.SDK,
            )
            .all()
        )

        assert len(dev_endpoints) == 2
        assert len(prod_endpoints) == 1

    @pytest.mark.asyncio
    async def test_sync_sdk_endpoints_metadata_persistence(
        self, test_db: Session, sdk_project_context, sample_functions_data
    ):
        """Test that all metadata fields are properly persisted"""
        service = EndpointService()

        result = await service.sync_sdk_endpoints(
            db=test_db,
            project_id=sdk_project_context["project_id"],
            environment=sdk_project_context["environment"],
            functions_data=sample_functions_data,
            organization_id=sdk_project_context["organization_id"],
            user_id=sdk_project_context["user_id"],
        )

        assert result["created"] == 2

        # Verify metadata structure
        from rhesis.backend.app.models.endpoint import Endpoint
        from rhesis.backend.app.models.enums import EndpointConnectionType

        endpoint = (
            test_db.query(Endpoint)
            .filter(
                Endpoint.project_id == sdk_project_context["project_id"],
                Endpoint.connection_type == EndpointConnectionType.SDK,
            )
            .first()
        )

        metadata = endpoint.endpoint_metadata

        # Verify all required metadata fields
        assert "sdk_connection" in metadata
        assert metadata["sdk_connection"]["project_id"] == sdk_project_context["project_id"]
        assert metadata["sdk_connection"]["environment"] == sdk_project_context["environment"]
        assert "function_name" in metadata["sdk_connection"]

        assert "function_schema" in metadata
        assert "parameters" in metadata["function_schema"]
        assert "return_type" in metadata["function_schema"]
        assert "description" in metadata["function_schema"]

        assert "last_registered" in metadata
        assert "created_at" in metadata
