"""
Tests for SDK message handler in rhesis.backend.app.services.connector.handler

This module tests the SDKMessageHandler class including:
- SDK function endpoint syncing
- Message-specific handlers (register, test_result, pong)
- Error handling and logging
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.handler import SDKMessageHandler


class TestSDKMessageHandler:
    """Test SDKMessageHandler class functionality"""

    @pytest.fixture
    def handler(self):
        """Create a fresh handler instance for each test."""
        return SDKMessageHandler()

    @pytest.mark.asyncio
    async def test_sync_function_endpoints_success(
        self, handler: SDKMessageHandler, test_db: Session, project_context
    ):
        """Test successful SDK function endpoints sync via registration handler"""
        functions_data = [
            {"name": "test_func", "parameters": {}, "return_type": "string", "metadata": {}}
        ]
        expected_stats = {"created": 1, "updated": 0, "marked_inactive": 0, "errors": []}

        # Create a complete registration message
        register_message = {
            "type": "register",
            "project_id": project_context["project_id"],
            "environment": project_context["environment"],
            "sdk_version": "1.0.0",
            "functions": functions_data,
        }

        with patch("rhesis.backend.app.services.endpoint.EndpointService") as mock_service:
            mock_endpoint_service = Mock()

            # Make sync_sdk_endpoints async
            async def mock_sync_endpoints(*args, **kwargs):
                return expected_stats

            mock_endpoint_service.sync_sdk_endpoints = mock_sync_endpoints
            mock_service.return_value = mock_endpoint_service

            # Mock the endpoint validation service to avoid circular imports
            with patch(
                "rhesis.backend.app.services.connector.mapping.get_endpoint_validation_service"
            ) as mock_validation:
                mock_validation_service = Mock()

                # Make start_validation async
                async def mock_start_validation(*args, **kwargs):
                    pass

                mock_validation_service.start_validation = mock_start_validation
                mock_validation.return_value = mock_validation_service

                result = await handler.handle_register_message(
                    project_id=project_context["project_id"],
                    environment=project_context["environment"],
                    message=register_message,
                    db=test_db,
                    organization_id=project_context["organization_id"],
                    user_id=project_context["user_id"],
                )

                assert result["type"] == "registered"
                assert result["status"] == "success"
                assert result["sync_stats"] == expected_stats

                # Note: We can't easily assert the mock was called with exact parameters
                # because the registration handler creates its own EndpointService instance
                # and calls the async method. The important thing is that the result
                # contains the expected sync_stats, which proves the mocking worked.

    @pytest.mark.asyncio
    async def test_sync_function_endpoints_error(
        self, handler: SDKMessageHandler, test_db: Session, project_context
    ):
        """Test sync function endpoints when exception occurs via registration handler"""
        functions_data = [{"name": "test_func", "parameters": {}, "return_type": "string"}]

        # Create a complete registration message
        register_message = {
            "type": "register",
            "project_id": project_context["project_id"],
            "environment": project_context["environment"],
            "sdk_version": "1.0.0",
            "functions": functions_data,
        }

        with patch("rhesis.backend.app.services.endpoint.EndpointService") as mock_service:
            mock_endpoint_service = Mock()

            # Make sync_sdk_endpoints async with exception
            async def mock_sync_endpoints_error(*args, **kwargs):
                raise Exception("Database error")

            mock_endpoint_service.sync_sdk_endpoints = mock_sync_endpoints_error
            mock_service.return_value = mock_endpoint_service

            # Mock the endpoint validation service to avoid circular imports
            with patch(
                "rhesis.backend.app.services.connector.mapping.get_endpoint_validation_service"
            ) as mock_validation:
                mock_validation_service = Mock()

                # Make start_validation async
                async def mock_start_validation(*args, **kwargs):
                    pass

                mock_validation_service.start_validation = mock_start_validation
                mock_validation.return_value = mock_validation_service

                result = await handler.handle_register_message(
                    project_id=project_context["project_id"],
                    environment=project_context["environment"],
                    message=register_message,
                    db=test_db,
                    organization_id=project_context["organization_id"],
                    user_id=project_context["user_id"],
                )

                # When sync fails, the registration handler catches the exception
                # and returns status "error" with stats containing errors
                assert result["type"] == "registered"
                assert result["status"] == "error"  # Registration fails when sync errors occur
                assert result["sync_stats"]["created"] == 0
                assert result["sync_stats"]["updated"] == 0
                assert result["sync_stats"]["marked_inactive"] == 0
                assert len(result["sync_stats"]["errors"]) == 1
                assert "errors" in result
                assert "message" in result

    @pytest.mark.asyncio
    async def test_handle_register_message_success(
        self, handler: SDKMessageHandler, test_db: Session, sample_register_message, project_context
    ):
        """Test successful registration message handling"""
        expected_stats = {"created": 2, "updated": 0, "marked_inactive": 0, "errors": []}

        with patch("rhesis.backend.app.services.endpoint.EndpointService") as mock_service:
            mock_endpoint_service = Mock()

            # Make sync_sdk_endpoints async
            async def mock_sync_endpoints(*args, **kwargs):
                return expected_stats

            mock_endpoint_service.sync_sdk_endpoints = mock_sync_endpoints
            mock_service.return_value = mock_endpoint_service

            # Mock the endpoint validation service to avoid circular imports
            with patch(
                "rhesis.backend.app.services.connector.mapping.get_endpoint_validation_service"
            ) as mock_validation:
                mock_validation_service = Mock()

                # Make start_validation async
                async def mock_start_validation(*args, **kwargs):
                    pass

                mock_validation_service.start_validation = mock_start_validation
                mock_validation.return_value = mock_validation_service

                response = await handler.handle_register_message(
                    project_id=project_context["project_id"],
                    environment=project_context["environment"],
                    message=sample_register_message,
                    db=test_db,
                    organization_id=project_context["organization_id"],
                    user_id=project_context["user_id"],
                )

                assert response["type"] == "registered"
                assert response["status"] == "success"
                assert response["sync_stats"] == expected_stats

    @pytest.mark.asyncio
    async def test_handle_register_message_without_db(
        self, handler: SDKMessageHandler, sample_register_message, project_context
    ):
        """Test registration message handling without database session"""
        response = await handler.handle_register_message(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=sample_register_message,
            db=None,
            organization_id=None,
            user_id=None,
        )

        assert response["type"] == "registered"
        assert response["status"] == "success"
        assert "sync_stats" not in response

    @pytest.mark.asyncio
    async def test_handle_register_message_invalid(
        self, handler: SDKMessageHandler, project_context
    ):
        """Test registration message handling with invalid message"""
        invalid_message = {"type": "register", "invalid_field": "value"}

        response = await handler.handle_register_message(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=invalid_message,
            db=None,
            organization_id=None,
            user_id=None,
        )

        assert response["type"] == "registered"
        assert response["status"] == "error"
        assert "error" in response

    @pytest.mark.asyncio
    async def test_handle_test_result_message_success(
        self, handler: SDKMessageHandler, sample_test_result_message, project_context
    ):
        """Test successful test result message handling"""
        with patch(
            "rhesis.backend.app.services.connector.handlers.test_result_handler._log_test_result"
        ) as mock_log:
            await handler.handle_test_result_message(
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                message=sample_test_result_message,
            )

            mock_log.assert_called_once_with(
                project_context["project_id"],
                project_context["environment"],
                sample_test_result_message,
            )

    @pytest.mark.asyncio
    async def test_handle_test_result_message_error(
        self, handler: SDKMessageHandler, sample_test_result_error_message, project_context
    ):
        """Test test result message handling with error status"""
        with patch(
            "rhesis.backend.app.services.connector.handlers.test_result_handler._log_test_result"
        ) as mock_log:
            await handler.handle_test_result_message(
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                message=sample_test_result_error_message,
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_pong_message(self, handler: SDKMessageHandler, project_context):
        """Test pong message handling"""
        # Should just log debug message, no errors
        await handler.handle_pong_message(
            project_id=project_context["project_id"], environment=project_context["environment"]
        )

    def test_log_test_result_success(
        self, handler: SDKMessageHandler, sample_test_result_message, project_context
    ):
        """Test logging of successful test result"""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        # Should not raise any exceptions
        test_result_handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=sample_test_result_message,
        )

    def test_log_test_result_error(
        self, handler: SDKMessageHandler, sample_test_result_error_message, project_context
    ):
        """Test logging of error test result"""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        # Should not raise any exceptions
        test_result_handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=sample_test_result_error_message,
        )

    def test_log_test_result_long_output(self, handler: SDKMessageHandler, project_context):
        """Test logging of test result with long output"""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        long_output_message = {
            "type": "test_result",
            "test_run_id": "test_abc123",
            "status": "success",
            "output": "x" * 1000,  # Long output to trigger truncation
            "error": None,
            "duration_ms": 100.0,
        }

        # Should not raise any exceptions
        test_result_handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=long_output_message,
        )

    def test_log_test_result_invalid_message(self, handler: SDKMessageHandler, project_context):
        """Test logging of invalid test result message"""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        invalid_message = {"type": "test_result", "invalid": "data"}

        # Should handle gracefully and not raise exceptions
        test_result_handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=invalid_message,
        )
