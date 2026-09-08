"""
Tests for SDK message handler in rhesis.backend.app.services.connector.handler

This module tests the SDKMessageHandler class including:
- SDK function endpoint syncing
- Message-specific handlers (register, test_result, pong)
- Error handling and logging
"""

import logging
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.handler import SDKMessageHandler
from rhesis.backend.app.services.connector.schemas import TestResultMessage

TEST_RESULT_LOGGER = "rhesis.backend.app.services.connector.handlers.test_result"


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

            mock_log.assert_called_once()
            logged_project, logged_env, logged_result = mock_log.call_args.args
            assert logged_project == project_context["project_id"]
            assert logged_env == project_context["environment"]
            assert logged_result.test_run_id == sample_test_result_message["test_run_id"]

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
        self, handler: SDKMessageHandler, sample_test_result_message, project_context, caplog
    ):
        """A successful result costs exactly one INFO record."""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        with caplog.at_level(logging.INFO, logger=TEST_RESULT_LOGGER):
            test_result_handler._log_test_result(
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                result=TestResultMessage(**sample_test_result_message),
            )

        records = [r for r in caplog.records if r.name == TEST_RESULT_LOGGER]
        assert len(records) == 1
        assert records[0].levelno == logging.INFO
        assert sample_test_result_message["test_run_id"] in records[0].getMessage()

    def test_log_test_result_error(
        self, handler: SDKMessageHandler, sample_test_result_error_message, project_context, caplog
    ):
        """A failed result costs one ERROR record carrying the error."""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        with caplog.at_level(logging.INFO, logger=TEST_RESULT_LOGGER):
            test_result_handler._log_test_result(
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                result=TestResultMessage(**sample_test_result_error_message),
            )

        records = [r for r in caplog.records if r.name == TEST_RESULT_LOGGER]
        assert len(records) == 1
        assert records[0].levelno == logging.ERROR
        assert sample_test_result_error_message["error"] in records[0].getMessage()

    def test_log_test_result_output_only_at_debug(
        self, handler: SDKMessageHandler, project_context, caplog
    ):
        """The payload never reaches INFO, and is truncated when it does appear."""
        from rhesis.backend.app.services.connector.handlers.test_result import test_result_handler

        result = TestResultMessage(
            test_run_id="test_abc123",
            status="success",
            output="x" * 1000,
            duration_ms=100.0,
        )

        with caplog.at_level(logging.INFO, logger=TEST_RESULT_LOGGER):
            test_result_handler._log_test_result(
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                result=result,
            )
        assert not any("xxx" in r.getMessage() for r in caplog.records)

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger=TEST_RESULT_LOGGER):
            test_result_handler._log_test_result(
                project_id=project_context["project_id"],
                environment=project_context["environment"],
                result=result,
            )

        debug_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_messages) == 1
        assert "..." in debug_messages[0]
        assert len(debug_messages[0]) < 1000

    @pytest.mark.asyncio
    async def test_handle_test_result_message_invalid(
        self, handler: SDKMessageHandler, project_context
    ):
        """A malformed frame is logged and dropped, never raised."""
        await handler.handle_test_result_message(
            project_id=project_context["project_id"],
            environment=project_context["environment"],
            message={"type": "test_result", "invalid": "data"},
        )
