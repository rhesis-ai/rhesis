"""
Tests for execution validation dependencies and error handling.

This module tests the validation logic introduced for:
- Worker availability checks
- Model configuration validation (generation and evaluation)
- Error message conversion and handling
"""

from unittest.mock import call, patch

import pytest
from fastapi import HTTPException

from rhesis.backend.app.error_handlers import PublicHTTPException
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict
from rhesis.backend.app.utils.execution_validation import (
    handle_execution_error,
    validate_execution_model,
    validate_generation_model,
)
from rhesis.backend.app.utils.model_errors import ModelConfigurationError


class TestExecutionModelValidation:
    """Test evaluation model validation dependency."""

    def test_validate_execution_model_success(self, test_db, authenticated_user):
        """Test that validation passes with valid evaluation and execution models."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.return_value = None

            validate_execution_model(db=test_db, current_user=authenticated_user)

            assert mock_validate.call_args_list == [
                call(test_db, authenticated_user, "evaluation"),
                call(test_db, authenticated_user, "execution"),
            ]

    def test_validate_execution_model_missing_api_key(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for missing API key."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = ModelConfigurationError(
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
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = ModelConfigurationError(
                "Unsupported LLM provider: custom_provider"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "provider" in detail

    def test_validate_execution_model_invalid_model_name(self, test_db, authenticated_user):
        """Test validation raises 400 with specific message for invalid model name."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = ModelConfigurationError(
                "Model 'gpt-5-ultra' not found in provider 'openai'"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "model" in detail

    @pytest.mark.parametrize(
        "error", [ValueError("RHESIS_API_KEY is not set"), ImportError("No module named torch")]
    )
    def test_validate_execution_model_deployment_default_unbuildable(
        self, error, test_db, authenticated_user
    ):
        """A failure to build the *deployment's* default is a 500 that says so.

        Used to propagate as a bare ValueError and answer "An unexpected error
        occurred", leaving the cause in the logs alone (#2671). Still a 500 --
        the caller cannot fix a server setting -- but the body now names it.
        ImportError too, because a provider can fail on an optional dependency.
        """
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = error

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 500
            assert isinstance(exc_info.value, PublicHTTPException)
            assert "DEFAULT_EVALUATION_MODEL" in exc_info.value.detail
            # The exception text is server-side detail and stays in the log.
            assert str(error) not in exc_info.value.detail

    def test_validate_execution_model_names_the_purpose_that_failed(
        self, test_db, authenticated_user
    ):
        """Evaluation passing and execution failing names DEFAULT_EXECUTION_MODEL."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = [None, ValueError("RHESIS_API_KEY is not set")]

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert "DEFAULT_EXECUTION_MODEL" in exc_info.value.detail

    def test_validate_execution_model_quota_error_is_not_swallowed(
        self, test_db, authenticated_user
    ):
        """QuotaExceededError has to reach its own handler to become a 402."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = QuotaExceededError(
                QuotaVerdict(
                    resource=QuotaResource.MODEL_TOKENS,
                    used=2,
                    limit=1,
                    allowed=False,
                    over_limit=True,
                    kind="flow",
                    period_end="2026-10-01",
                )
            )

            with pytest.raises(QuotaExceededError):
                validate_execution_model(db=test_db, current_user=authenticated_user)

    def test_validate_execution_model_calls_both_validators(
        self, test_db, authenticated_user
    ):
        """Both evaluation and execution validators are called."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.return_value = None

            validate_execution_model(db=test_db, current_user=authenticated_user)

            assert mock_validate.call_args_list == [
                call(test_db, authenticated_user, "evaluation"),
                call(test_db, authenticated_user, "execution"),
            ]

    def test_validate_execution_model_execution_model_failure(
        self, test_db, authenticated_user
    ):
        """Execution model validation failure raises HTTPException even when evaluation passes."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            def fail_on_execution(db, user, purpose):
                if purpose == "execution":
                    raise ModelConfigurationError(
                        "API key not found for provider 'anthropic'."
                    )

            mock_validate.side_effect = fail_on_execution

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            assert exc_info.value.status_code == 400
            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "api key" in detail


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
            mock_validate.side_effect = ModelConfigurationError(
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
            mock_validate.side_effect = ModelConfigurationError("Unknown provider: fake_llm")

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
            mock_validate.side_effect = ModelConfigurationError(
                "API key not found for provider 'openai'"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "api key" in detail or "api_key" in detail

    def test_provider_error_mentions_supported_providers(self, test_db, authenticated_user):
        """Test provider errors mention the issue with provider configuration."""
        with patch(
            "rhesis.backend.app.utils.execution_validation.validate_model"
        ) as mock_validate:
            mock_validate.side_effect = ModelConfigurationError(
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
            mock_validate.side_effect = ModelConfigurationError(
                "Model 'gpt-10' not found in provider 'openai'"
            )

            with pytest.raises(HTTPException) as exc_info:
                validate_execution_model(db=test_db, current_user=authenticated_user)

            detail = str(exc_info.value.detail).lower()
            assert "configured model" in detail
            assert "model" in detail
