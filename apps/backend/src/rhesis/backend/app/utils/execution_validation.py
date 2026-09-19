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
from rhesis.backend.app.error_handlers import UpstreamHTTPException, internal_error
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.invokers.common.errors import (
    INTERNAL_ERROR_TYPE,
    EndpointInvocationError,
)
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.app.utils.user_model_utils import validate_model

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
        HTTPException: 400 if the organization's own model configuration is
            invalid, 500 if this deployment cannot build its own default model.

    Example:
        @router.post("/execute", dependencies=[Depends(validate_execution_model)])
        async def execute_endpoint(...):
            ...
    """
    for purpose in ("evaluation", "execution"):
        try:
            validate_model(db, current_user, purpose)
        except ModelConfigurationError as e:
            raise _convert_model_error_to_http_exception(e, "execution")
        except (ValueError, ImportError) as e:
            raise _deployment_model_error(e, purpose)


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
    except ModelConfigurationError as e:
        raise _convert_model_error_to_http_exception(e, "generation")
    except (ValueError, ImportError) as e:
        raise _deployment_model_error(e, "generation")


def _deployment_model_error(error: Exception, purpose: str) -> HTTPException:
    """A 500 that names the deployment setting at fault instead of hiding it.

    Only a *deployment* default can get here. Every failure to build an
    organization's own configured model is raised as a ``ModelConfigurationError``
    by ``_build_configured_model`` and answered with the 400 above, so what is
    left is this backend failing to build its own ``DEFAULT_*_MODEL`` -- typically
    a missing credential.

    Still a 500, as decided on #2681: the request was fine, the server is not,
    and telling an API caller to check their model settings would misdirect. What
    changes here is only that the body names the setting, rather than the generic
    "An unexpected error occurred." that left the cause in the logs alone.

    ``ImportError`` as well as ``ValueError`` because a provider can fail on an
    optional dependency (huggingface needs torch). An organization's own model
    raising that is caught by ``_build_configured_model`` alongside ``ValueError``
    for this reason, so what reaches here is only the deployment default's.

    Not a bare ``Exception``: ``QuotaExceededError`` also crosses this frame and
    has to reach its own handler to become a 402.
    """
    # `purpose` is one of our own literals, not exception text, so interpolating
    # it does not leak anything -- which is the rule `internal_error` is enforcing.
    return internal_error(
        error,
        context=f"deployment default {purpose} model could not be built",
        public_detail=(
            f"This deployment's default {purpose} model could not be built. Check the "
            f"backend's DEFAULT_{purpose.upper()}_MODEL setting and the credentials it needs."
        ),
    )


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

    if isinstance(error, ItemDeletedException):
        # Let the app-level handler turn this into its 410 response
        raise error

    if isinstance(error, ModelConfigurationError):
        return _convert_model_error_to_http_exception(error, operation)

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
