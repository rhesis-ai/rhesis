"""
Execution validation utilities.

Provides reusable validation functions and dependencies for test execution
and generation endpoints. Follows separation of concerns and DRY principles.
"""

import logging
from typing import Literal, Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.error_handlers import (
    PublicHTTPException,
    UpstreamHTTPException,
    internal_error,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.app.services.invokers.common.errors import (
    INTERNAL_ERROR_TYPE,
    EndpointInvocationError,
)
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.backend.app.utils.model_errors import (
    ModelConfigurationError,
    ModelNotConfiguredError,
)
from rhesis.backend.app.utils.user_model_utils import validate_model

logger = logging.getLogger(__name__)


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
        HTTPException: 400 if the organization's own model configuration is
            invalid, 500 if this deployment cannot build its own default model.

    Example:
        @router.post("/generate", dependencies=[Depends(validate_generation_model)])
        async def generate_endpoint(...):
            ...
    """
    try:
        validate_model(db, current_user, "generation")
    except ModelNotConfiguredError as problem:
        raise model_setup_http_exception(problem, "generate tests") from problem


def model_setup_http_exception(
    problem: ModelNotConfiguredError, context: str, status_code: Optional[int] = None
) -> HTTPException:
    """The HTTP error every model check returns. Status split from #2681: the org's own
    model is a 400 (fixable), a deployment default a 500; *status_code* overrides it."""
    if problem.own_model:
        logger.warning("Model configuration error for %s: %s", context, problem.cause)
        return HTTPException(
            status_code=status_code or 400,
            detail=problem.detail(
                f"Cannot {context} due to a problem with your configured model: "
                f"{problem.message}. Please check your model settings in the Models page."
            ),
        )
    logger.error("%s (%s)", problem.log_message, context)
    status_code = status_code or 500
    cls = PublicHTTPException if status_code >= 500 else HTTPException
    http_exc = cls(status_code=status_code, detail=problem.detail())
    # Logged above with the cause; stops the global handler logging it again.
    http_exc.rhesis_logged = True
    return http_exc


def handle_execution_error(
    error: Exception,
    operation: str = "execute tests",
    purpose: Literal["generation", "execution"] = "execution",
) -> HTTPException:
    """
    Convert execution-related exceptions to appropriate HTTP responses.

    Centralizes error handling logic for execution endpoints.

    Args:
        error: The exception that occurred
        operation: Human-readable description of the operation
        purpose: Which model the operation builds, for the error message

    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(error, HTTPException):
        # Already an HTTPException, re-raise as-is
        raise error

    if isinstance(error, (ItemDeletedException, QuotaExceededError)):
        # Let the app-level handlers turn these into their 410 / 402 responses
        raise error

    # The run's model check already names the model. Before ValueError, which it subclasses.
    if isinstance(error, ModelNotConfiguredError):
        return model_setup_http_exception(error, operation)

    if isinstance(error, ModelConfigurationError):
        problem = ModelNotConfiguredError(purpose, error)
        return model_setup_http_exception(problem, operation)

    if isinstance(error, ValueError):
        logger.error(f"Validation error for {operation}: {str(error)}", exc_info=True)
        return HTTPException(status_code=400, detail=str(error))

    if isinstance(error, PermissionError):
        logger.warning(f"Permission denied for {operation}: {str(error)}")
        return HTTPException(status_code=403, detail=str(error))

    if isinstance(error, EndpointInvocationError):
        status_code = error.status_code or 500
        # EndpointService wraps our *own* unexpected exceptions in this same type, so the
        # error_type is what separates the user's endpoint from our bug. Without this
        # branch a Rhesis-side failure answers with the raw exception text (paths,
        # connection details) attributed to the caller's endpoint.
        if error.error_type == INTERNAL_ERROR_TYPE:
            return internal_error(error, context=f"failed to {operation}", status_code=status_code)
        # The target refused the call, which is the reportable fact the caller needs; an
        # opaque 500 from the fallback below is not something they can act on.
        # UpstreamHTTPException so the global handler passes the detail through, exactly as
        # routers/endpoint.py does for the same exception.
        logger.warning(
            "Endpoint invocation failed for %s: %s (status=%s, type=%s)",
            operation,
            error,
            error.status_code,
            error.error_type,
        )
        return UpstreamHTTPException(status_code=status_code, detail=str(error))

    # Unexpected: the reason goes to the log with a stack, not to the caller.
    return internal_error(error, context=f"failed to {operation}")
