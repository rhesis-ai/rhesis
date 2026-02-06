"""
Execution validation utilities.

Provides reusable validation functions and dependencies for test execution
and generation endpoints. Follows separation of concerns and DRY principles.
"""

from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.llm_utils import (
    validate_user_evaluation_model,
    validate_user_generation_model,
)
from rhesis.backend.logging import logger
from rhesis.backend.tasks import check_workers_available


class WorkerUnavailableError(Exception):
    """Raised when no Celery workers are available."""

    pass


class ModelConfigurationError(Exception):
    """Raised when user's model configuration is invalid."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


def validate_workers_available() -> None:
    """
    Validate that Celery workers are available.

    This is a FastAPI dependency that can be used to ensure workers
    are available before submitting tasks.

    Raises:
        HTTPException: 503 if no workers are available

    Example:
        @router.post("/execute", dependencies=[Depends(validate_workers_available)])
        async def execute_endpoint(...):
            ...
    """
    if not check_workers_available():
        logger.error("No Celery workers available for task submission")
        raise HTTPException(
            status_code=503,
            detail=(
                "Background task workers are currently unavailable. "
                "Please ensure the worker service is running or contact support. "
                "Tasks cannot be processed without active workers."
            ),
        )


def validate_execution_model(
    current_user: User,
    db: Session = Depends(get_tenant_db_session),
) -> None:
    """
    Validate that user's evaluation model is properly configured.

    This is a FastAPI dependency for test execution endpoints that ensures
    the user has a valid evaluation model before running tests.

    Args:
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: 400 if model configuration is invalid

    Example:
        @router.post("/execute", dependencies=[Depends(validate_execution_model)])
        async def execute_endpoint(...):
            ...
    """
    try:
        validate_user_evaluation_model(db, current_user)
    except ValueError as e:
        raise _convert_model_error_to_http_exception(e, "execution")


def validate_generation_model(
    current_user: User,
    db: Session = Depends(get_tenant_db_session),
) -> None:
    """
    Validate that user's generation model is properly configured.

    This is a FastAPI dependency for test generation endpoints that ensures
    the user has a valid generation model before creating tests.

    Args:
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: 400 if model configuration is invalid

    Example:
        @router.post("/generate", dependencies=[Depends(validate_generation_model)])
        async def generate_endpoint(...):
            ...
    """
    try:
        validate_user_generation_model(db, current_user)
    except ValueError as e:
        raise _convert_model_error_to_http_exception(e, "generation")


def _convert_model_error_to_http_exception(error: ValueError, context: str) -> HTTPException:
    """
    Convert a model configuration ValueError to an HTTPException.

    Detects specific types of model configuration errors and provides
    appropriate user-facing error messages.

    Args:
        error: The ValueError from model validation
        context: Context string ("execution" or "generation")

    Returns:
        HTTPException with appropriate status code and message
    """
    error_msg = str(error)
    error_msg_lower = error_msg.lower()

    # Check if this is a model configuration error
    is_model_error = any(
        keyword in error_msg_lower
        for keyword in [
            "api_key",
            "not set",
            "not configured",
            "api key",
            "authentication",
            "provider",
            "not supported",
            "model",
            "not found",
            "invalid",
        ]
    )

    if is_model_error:
        logger.warning(f"Model configuration error for {context}: {error_msg}")
        action = "execute tests" if context == "execution" else "generate tests"
        return HTTPException(
            status_code=400,
            detail=(
                f"Cannot {action} due to a problem with your configured model: {error_msg}. "
                "Please check your model settings in the Models page."
            ),
        )

    # Generic validation error
    logger.error(f"Validation error for {context}: {error_msg}", exc_info=True)
    return HTTPException(status_code=400, detail=error_msg)


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

    if isinstance(error, ValueError):
        return _convert_model_error_to_http_exception(error, operation)

    if isinstance(error, PermissionError):
        logger.warning(f"Permission denied for {operation}: {str(error)}")
        return HTTPException(status_code=403, detail=str(error))

    # Unexpected error
    logger.error(f"Failed to {operation}: {str(error)}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=f"Failed to {operation}. Please try again or contact support if the issue persists.",
    )
