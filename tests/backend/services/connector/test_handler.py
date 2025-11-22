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
        """Test successful SDK function endpoints sync"""
        functions_data = [
            {"name": "test_func", "parameters": {}, "return_type": "string", "metadata": {}}
        ]
        expected_stats = {"created": 1, "updated": 0, "marked_inactive": 0, "errors": []}

        with patch("rhesis.backend.app.services.endpoint.EndpointService") as mock_service:
            mock_endpoint_service = Mock()
            mock_endpoint_service.sync_sdk_function_endpoints = Mock(return_value=expected_stats)
            mock_service.return_value = mock_endpoint_service

            result = await handler.sync_function_endpoints(
                db=test_db,
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                functions_data=functions_data,
                organization_id=project_context["organization_id"],
                user_id=project_context["user_id"],
            )

            assert result == expected_stats
            mock_endpoint_service.sync_sdk_function_endpoints.assert_called_once_with(
                db=test_db,
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                functions_data=functions_data,
                organization_id=project_context["organization_id"],
                user_id=project_context["user_id"],
            )

    @pytest.mark.asyncio
    async def test_sync_function_endpoints_error(
        self, handler: SDKMessageHandler, test_db: Session, project_context
    ):
        """Test sync function endpoints when exception occurs"""
        functions_data = [{"name": "test_func"}]

        with patch("rhesis.backend.app.services.endpoint.EndpointService") as mock_service:
            mock_endpoint_service = Mock()
            mock_endpoint_service.sync_sdk_function_endpoints.side_effect = Exception(
                "Database error"
            )
            mock_service.return_value = mock_endpoint_service

            result = await handler.sync_function_endpoints(
                db=test_db,
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                functions_data=functions_data,
                organization_id=project_context["organization_id"],
                user_id=project_context["user_id"],
            )

            assert result["created"] == 0
            assert result["updated"] == 0
            assert result["marked_inactive"] == 0
            assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_handle_register_message_success(
        self, handler: SDKMessageHandler, test_db: Session, sample_register_message, project_context
    ):
        """Test successful registration message handling"""
        expected_stats = {"created": 2, "updated": 0, "marked_inactive": 0, "errors": []}

        with patch.object(handler, "sync_function_endpoints", return_value=expected_stats):
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
        with patch.object(handler, "_log_test_result") as mock_log:
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
        with patch.object(handler, "_log_test_result") as mock_log:
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
        # Should not raise any exceptions
        handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=sample_test_result_message,
        )

    def test_log_test_result_error(
        self, handler: SDKMessageHandler, sample_test_result_error_message, project_context
    ):
        """Test logging of error test result"""
        # Should not raise any exceptions
        handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=sample_test_result_error_message,
        )

    def test_log_test_result_long_output(self, handler: SDKMessageHandler, project_context):
        """Test logging of test result with long output"""
        long_output_message = {
            "type": "test_result",
            "test_run_id": "test_abc123",
            "status": "success",
            "output": "x" * 1000,  # Long output to trigger truncation
            "error": None,
            "duration_ms": 100.0,
        }

        # Should not raise any exceptions
        handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=long_output_message,
        )

    def test_log_test_result_invalid_message(self, handler: SDKMessageHandler, project_context):
        """Test logging of invalid test result message"""
        invalid_message = {"type": "test_result", "invalid": "data"}

        # Should handle gracefully and not raise exceptions
        handler._log_test_result(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message=invalid_message,
        )
