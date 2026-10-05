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

from rhesis.backend.app.error_handlers import PublicHTTPException
from rhesis.backend.app.utils.execution_validation import (
    handle_execution_error,
    validate_generation_model,
)
from rhesis.backend.app.utils.model_errors import (
    MODEL_NOT_CONFIGURED,
    ModelConfigurationError,
    ModelNotConfiguredError,
)


def _own_model_broken(message: str) -> ModelNotConfiguredError:
    """What ``validate_model`` raises for a configured model that cannot be built."""
    return ModelNotConfiguredError("generation", ModelConfigurationError(message))


class TestGenerationModelValidation:
    """Test generation model validation dependency."""

    def test_validate_generation_model_success(self, test_db, authenticated_user):
        """Test that validation passes with valid generation model."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.return_value = None  # No exception means success

            # Should not raise any exception
            validate_generation_model(db=test_db, current_user=authenticated_user)

            mock_validate.assert_called_once_with(test_db, authenticated_user, "generation")

    def test_validate_generation_model_missing_api_key(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for missing API key."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = _own_model_broken(
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
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = _own_model_broken("Unknown provider: fake_llm")

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

    def test_handle_model_configuration_error_with_api_key(self):
        """Test ModelConfigurationError about API key is converted to specific message."""
        error = ModelConfigurationError(
            "API key not found for provider 'openai'. Please configure your model settings."
        )

        result = handle_execution_error(error, "execute tests")

        assert result.status_code == 400
        detail = str(result.detail).lower()
        assert "configured model" in detail
        assert "api key" in detail

    def test_handle_model_configuration_error_with_provider(self):
        """Test ModelConfigurationError about provider is converted to specific message."""
        error = ModelConfigurationError("Unsupported provider: custom_llm")

        result = handle_execution_error(error, "generate test set")

        assert result.status_code == 400
        detail = str(result.detail).lower()
        assert "configured model" in detail
        assert "provider" in detail

    def test_handle_model_not_configured_own_model(self):
        """The run's model check already knows which model failed: 400 for the org's own."""
        error = ModelNotConfiguredError(
            "evaluation", ModelConfigurationError("API key not found for provider 'openai'")
        )

        result = handle_execution_error(error, operation="execute test set")

        assert result.status_code == 400
        assert result.detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "deployment_hint" not in result.detail
        assert "api key" in result.detail["message"].lower()

    def test_handle_model_not_configured_deployment_default(self):
        """A deployment default that cannot be built stays a 500 naming its own purpose."""
        error = ModelNotConfiguredError("execution", ValueError("RHESIS_API_KEY is not set"))

        result = handle_execution_error(error, operation="execute test set")

        assert result.status_code == 500
        assert isinstance(result, PublicHTTPException)
        assert result.detail["error_code"] == MODEL_NOT_CONFIGURED
        assert "DEFAULT_EXECUTION_MODEL" in result.detail["deployment_hint"]
        assert "RHESIS_API_KEY" not in str(result.detail)

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
        """Test generic exceptions are converted to a masked 500."""
        error = RuntimeError("Something unexpected happened")

        result = handle_execution_error(error, "execute test configuration")

        assert result.status_code == 500
        # The reason belongs in the log, not the response. See app/error_handlers.py.
        assert result.detail == "An unexpected error occurred."
        assert "something unexpected happened" not in str(result.detail).lower()
        assert getattr(result, "rhesis_logged", False) is True


class TestErrorMessageContent:
    """Test that error messages contain helpful information for users."""

    def test_api_key_error_mentions_configuration(self, test_db, authenticated_user):
        """Test API key errors guide users to configuration."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = _own_model_broken(
                "API key not found for provider 'openai'"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_generation_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "api key" in detail or "api_key" in detail

    def test_provider_error_mentions_supported_providers(self, test_db, authenticated_user):
        """Test provider errors mention the issue with provider configuration."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = _own_model_broken(
                "Unsupported provider: fake_provider"
            )

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
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = _own_model_broken(
                "Model 'gpt-10' not found in provider 'openai'"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_generation_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "model" in detail
