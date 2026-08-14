"""
Error handling utilities for FastAPI validation errors and responses.
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_validation_error_response(exc: RequestValidationError) -> JSONResponse:
    """
    Create a clean JSON response for validation errors.

    Handles Pydantic validation errors that may contain non-JSON-serializable
    objects (like ValueError instances) in the error context.

    Pydantic's ``input`` is deliberately dropped. For a *missing* field it holds
    the whole request body rather than one value, so a signup that forgets its
    email address answers with the password in cleartext -- and from there into
    the browser console, which logs the error body for a 422. `loc`, `msg` and
    `ctx` say which field, what is wrong and which rule broke it; the value adds
    nothing the caller didn't just send us. Not masked by field name: the name
    lists we have already miss `credentials` and `code`.

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
        }
        # Only include ctx if it exists, and convert any non-serializable values to strings
        if "ctx" in error and error["ctx"]:
            clean_error["ctx"] = {k: str(v) for k, v in error["ctx"].items()}

        errors.append(clean_error)

    return JSONResponse(status_code=422, content={"detail": errors})


def log_validation_error(exc: RequestValidationError, request: Request) -> None:
    """
    Log which fields a request failed validation on, and why.

    Never the submitted value, for the same reason the response omits it. The
    redaction patterns can't rescue this one: they match the word after
    "password:", which in a validation message is the message itself, leaving
    the real value sitting in "(input: ...)" further along the line.

    Warning, not error: a 422 is the caller's mistake, not a server fault.

    Args:
        exc: The RequestValidationError from FastAPI/Pydantic
        request: The FastAPI request object
    """
    for error in exc.errors():
        # Build a readable field path
        field_path = " -> ".join(str(loc) for loc in error["loc"])

        logger.warning(
            "Validation error on %s %s: %s: %s",
            request.method,
            request.url.path,
            field_path,
            error["msg"],
        )
