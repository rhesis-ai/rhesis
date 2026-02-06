"""
Tests for execution validation dependencies and error handling.

This module tests the validation logic introduced for:
- Worker availability checks
- Model configuration validation (generation and evaluation)
- Error message conversion and handling
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from rhesis.backend.app.utils.execution_validation import (
    WorkerUnavailableError,
    handle_execution_error,
    validate_execution_model,
    validate_generation_model,
    validate_workers_available,
)


class TestWorkerValidation:
    """Test worker availability validation dependency."""

    def test_validate_workers_available_success(self):
        """Test that validation passes when workers are available."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.check_workers_available",
            return_value=True,
        ):
            # Should not raise any exception
            validate_workers_available()

    def test_validate_workers_unavailable_raises_503(self):
        """Test that validation raises 503 when workers are unavailable."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.check_workers_available",
            return_value=False,
        ):
            with pytest.raises(HTTPException) as exc_info:
                validate_workers_available()

            assert exc_info.value.status_code == 503
            assert "worker" in str(exc_info.value.detail).lower()


class TestExecutionModelValidation:
    """Test evaluation model validation dependency."""

    def test_validate_execution_model_success(self, test_db, authenticated_user):
        """Test that validation passes with valid evaluation model."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.return_value = None  # No exception means success

            # Should not raise any exception
            validate_execution_model(db=test_db, current_user=authenticated_user)

            mock_validate.assert_called_once_with(test_db, authenticated_user)

    def test_validate_execution_model_missing_api_key(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for missing API key."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError(
                "API key not found for provider 'openai'. Please configure your model settings."
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "api key" in detail

    def test_validate_execution_model_unsupported_provider(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for unsupported provider."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Unsupported LLM provider: custom_provider")

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "provider" in detail

    def test_validate_execution_model_invalid_model_name(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for invalid model name."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError(
                "Model 'gpt-5-ultra' not found in provider 'openai'"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "model" in detail

    def test_validate_execution_model_generic_error(self, test_db, authenticated_user):
        """Test validation raises 400 with generic message for unknown errors."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Something went wrong")

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            # Non-model-related errors return the error message as-is
            assert exc_info.value.status_code == 400
            assert "something went wrong" in str(exc_info.value.detail).lower()


class TestGenerationModelValidation:
    """Test generation model validation dependency."""

    def test_validate_generation_model_success(self, test_db, authenticated_user):
        """Test that validation passes with valid generation model."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_generation_model"
        ) as mock_validate:
            mock_validate.return_value = None  # No exception means success

            # Should not raise any exception
            validate_generation_model(db=test_db, current_user=authenticated_user)

            mock_validate.assert_called_once_with(test_db, authenticated_user)

    def test_validate_generation_model_missing_api_key(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for missing API key."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_generation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError(
                "API key not found for provider 'anthropic'. Please configure your model settings."
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_generation_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "api key" in detail

    def test_validate_generation_model_unsupported_provider(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for unsupported provider."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_generation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Unknown provider: fake_llm")

            with pytest.raises(HTTPException) as exc_info:
                validate_generation_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "provider" in detail


class TestHandleExecutionError:
    """Test the centralized error handler for execution operations."""

    def test_handle_http_exception_passthrough(self):
        """Test that HTTPException is re-raised unchanged."""
        original_exception = HTTPException(status_code=404, detail="Not found")

        # handle_execution_error raises HTTPException instead of returning it
        with pytest.raises(HTTPException) as exc_info:
            handle_execution_error(original_exception, "test operation")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not found"

    def test_handle_value_error_with_api_key(self):
        """Test ValueError about API key is converted to specific message."""
        error = ValueError(
            "API key not found for provider 'openai'. Please configure your model settings."
        )

        result = handle_execution_error(error, "execute tests")

        assert result.status_code == 400
        detail = str(result.detail).lower()
        assert "configured model" in detail
        assert "api key" in detail

    def test_handle_value_error_with_provider(self):
        """Test ValueError about provider is converted to specific message."""
        error = ValueError("Unsupported provider: custom_llm")

        result = handle_execution_error(error, "generate test set")

        assert result.status_code == 400
        detail = str(result.detail).lower()
        assert "configured model" in detail
        assert "provider" in detail

    def test_handle_value_error_generic(self):
        """Test generic ValueError without model keywords returns original message."""
        error = ValueError("Random validation error")

        result = handle_execution_error(error, "execute tests")

        assert result.status_code == 400
        assert "random validation error" in str(result.detail).lower()

    def test_handle_permission_error(self):
        """Test PermissionError is converted to 403."""
        error = PermissionError("User does not have access")

        result = handle_execution_error(error, "execute tests")

        assert result.status_code == 403
        assert "user does not have access" in str(result.detail).lower()

    def test_handle_generic_exception(self):
        """Test generic exceptions are converted to 500."""
        error = RuntimeError("Something unexpected happened")

        result = handle_execution_error(error, "execute test configuration")

        assert result.status_code == 500
        assert "execute test configuration" in str(result.detail).lower()
        assert "something unexpected happened" in str(result.detail).lower()

    def test_handle_worker_unavailable_error(self):
        """Test WorkerUnavailableError falls through to generic 500 handler."""
        error = WorkerUnavailableError("Workers are down")

        result = handle_execution_error(error, "execute tests")

        # WorkerUnavailableError is not specifically handled in handle_execution_error,
        # so it falls through to the generic exception handler (500)
        assert result.status_code == 500
        assert "execute tests" in str(result.detail).lower()


class TestErrorMessageContent:
    """Test that error messages contain helpful information for users."""

    def test_api_key_error_mentions_configuration(self, test_db, authenticated_user):
        """Test API key errors guide users to configuration."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("API key not found for provider 'openai'")

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            # Should mention it's the user's configured model
            assert "configured model" in detail
            # Should mention the issue is with API key
            assert "api key" in detail or "api_key" in detail

    def test_provider_error_mentions_supported_providers(self, test_db, authenticated_user):
        """Test provider errors mention the issue with provider configuration."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_generation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Unsupported provider: fake_provider")

            with pytest.raises(HTTPException) as exc_info:
                validate_generation_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            # Should mention it's the user's configured model
            assert "configured model" in detail
            # Should mention the issue is with the provider
            assert "provider" in detail

    def test_model_name_error_is_specific(self, test_db, authenticated_user):
        """Test model name errors are specific about the issue."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_user_evaluation_model"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Model 'gpt-10' not found in provider 'openai'")

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            # Should mention it's the user's configured model
            assert "configured model" in detail
            # Should mention the issue is with the model
            assert "model" in detail
