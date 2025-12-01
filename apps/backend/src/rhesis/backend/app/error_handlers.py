"""
Error handling utilities for FastAPI validation errors and responses.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from rhesis.backend.logging import logger


def create_validation_error_response(exc: RequestValidationError) -> JSONResponse:
    """
    Create a clean JSON response for validation errors.

    Handles Pydantic validation errors that may contain non-JSON-serializable
    objects (like ValueError instances) in the error context.

    Args:
        exc: The RequestValidationError from FastAPI/Pydantic

    Returns:
        JSONResponse with properly serialized error details
    """
    errors = []
    for error in exc.errors():
        # Create a clean error dict, converting non-serializable values
        clean_error = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "input": error.get("input"),
        }
        # Only include ctx if it exists, and convert any non-serializable values to strings
        if "ctx" in error and error["ctx"]:
            clean_error["ctx"] = {k: str(v) for k, v in error["ctx"].items()}

        errors.append(clean_error)

    return JSONResponse(status_code=422, content={"detail": errors})


def log_validation_error(exc: RequestValidationError, request: Request) -> None:
    """
    Log validation errors with detailed information for debugging.

    Args:
        exc: The RequestValidationError from FastAPI/Pydantic
        request: The FastAPI request object
    """
    for error in exc.errors():
        # Build a readable field path
        field_path = " -> ".join(str(loc) for loc in error["loc"])

        logger.error(
            f"Validation error: {field_path}: {error['msg']} (input: {error.get('input', 'N/A')})"
        )
