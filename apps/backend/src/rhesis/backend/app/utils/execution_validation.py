"""
Execution validation utilities.

Provides reusable validation functions and dependencies for test execution
and generation endpoints. Follows separation of concerns and DRY principles.
"""

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.app.utils.user_model_utils import (
    validate_user_evaluation_model,
    validate_user_execution_model,
    validate_user_generation_model,
)

logger = logging.getLogger(__name__)


def validate_execution_model(
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
) -> None:
    """
    Validate that user's evaluation and execution models are properly configured.

    This is a FastAPI dependency for test execution endpoints that ensures
    the user has valid evaluation and execution models before running tests.

    Args:
        db: Database session (injected by FastAPI)
        current_user: Current authenticated user (injected by FastAPI)

    Raises:
        HTTPException: 400 if model configuration is invalid

    Example:
        @router.post("/execute", dependencies=[Depends(validate_execution_model)])
        async def execute_endpoint(...):
            ...
    """
    try:
        validate_user_evaluation_model(db, current_user)
        validate_user_execution_model(db, current_user)
    except ModelConfigurationError as e:
        raise _convert_model_error_to_http_exception(e, "execution")


def validate_generation_model(
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
) -> None:
    """
    Validate that user's generation model is properly configured.

    This is a FastAPI dependency for test generation endpoints that ensures
    the user has a valid generation model before creating tests.

    Args:
        db: Database session (injected by FastAPI)
        current_user: Current authenticated user (injected by FastAPI)

    Raises:
        HTTPException: 400 if model configuration is invalid

    Example:
        @router.post("/generate", dependencies=[Depends(validate_generation_model)])
        async def generate_endpoint(...):
            ...
    """
    try:
        validate_user_generation_model(db, current_user)
    except ModelConfigurationError as e:
        raise _convert_model_error_to_http_exception(e, "generation")


def _convert_model_error_to_http_exception(
    error: ModelConfigurationError, context: str
) -> HTTPException:
    """
    Convert a model configuration error to an HTTPException.

    Args:
        error: The model configuration error
        context: Context string ("execution" or "generation")

    Returns:
        HTTPException with appropriate status code and message
    """
    error_msg = str(error)
    logger.warning(f"Model configuration error for {context}: {error_msg}")
    action = "execute tests" if context == "execution" else "generate tests"
    return HTTPException(
        status_code=400,
        detail=(
            f"Cannot {action} due to a problem with your configured model: {error_msg}. "
            "Please check your model settings in the Models page."
        ),
    )


def handle_execution_error(error: Exception, operation: str = "execute tests") -> HTTPException:
    """
    Convert execution-related exceptions to appropriate HTTP responses.

    Centralizes error handling logic for execution endpoints.

    Args:
        error: The exception that occurred
        operation: Human-readable description of the operation

    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(error, HTTPException):
        # Already an HTTPException, re-raise as-is
        raise error

    if isinstance(error, ModelConfigurationError):
        return _convert_model_error_to_http_exception(error, operation)

    if isinstance(error, ValueError):
        logger.error(f"Validation error for {operation}: {str(error)}", exc_info=True)
        return HTTPException(status_code=400, detail=str(error))

    if isinstance(error, PermissionError):
        logger.warning(f"Permission denied for {operation}: {str(error)}")
        return HTTPException(status_code=403, detail=str(error))

    # Unexpected error - include error details for better debugging
    error_msg = str(error) if str(error) else "An unexpected error occurred"
    logger.error(f"Failed to {operation}: {error_msg}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=f"Failed to {operation}: {error_msg}",
    )
