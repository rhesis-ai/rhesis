"""
Error handling utilities for FastAPI validation errors and responses.
"""

import logging

from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from rhesis.backend.app.utils.request_context import request_id_of

logger = logging.getLogger(__name__)

#: What the client is told when the real reason must not leave the server.
#: Keyed by status code; anything unlisted falls back by class (see below).
PUBLIC_ERROR_MESSAGES = {
    500: "An unexpected error occurred.",
    502: "An upstream service returned an invalid response.",
    503: "The service is temporarily unavailable.",
    504: "The request timed out.",
}

#: 4xx fallback. Describing a client error as "an unexpected error occurred"
#: tells the caller the wrong thing about whose fault it is.
_CLIENT_ERROR_MESSAGE = "The request could not be processed."


def public_message(status_code: int) -> str:
    if status_code in PUBLIC_ERROR_MESSAGES:
        return PUBLIC_ERROR_MESSAGES[status_code]
    if 400 <= status_code < 500:
        return _CLIENT_ERROR_MESSAGE
    return PUBLIC_ERROR_MESSAGES[500]


class PublicHTTPException(HTTPException):
    """A 5xx whose detail is written for the caller to read.

    Masking is the default because a detail built from an exception leaks
    whatever the exception happened to carry. That reasoning does not apply to
    a fixed string someone wrote on purpose -- "Garak package is not installed",
    "No Celery workers available" -- which names the one thing the caller can
    act on and reveals nothing.

    The detail must be a literal, not interpolated from an exception. The moment
    it carries `str(exc)` this is a leak with a blessing on it.
    """


class UpstreamHTTPException(PublicHTTPException):
    """A failure of the *caller's* system, not ours -- detail is theirs to see.

    Endpoint testing and invocation exist to report what is wrong with a user's
    own endpoint: a refused connection, a rejected token, an unparseable body.
    Masking those explains nothing to the person debugging and conceals nothing
    of ours, so the global handler passes the detail through even on a 5xx.

    Only for text that came from the upstream service. An exception raised by
    our own code is not upstream detail, however much it looks like it.
    """


def internal_error(
    exc: Exception,
    *,
    context: str,
    status_code: int = 500,
    public_detail: str | None = None,
) -> HTTPException:
    """Log ``exc`` and return an HTTPException that reveals none of it.

    Only for cases where the router genuinely adds context a global handler
    can't infer. Otherwise don't catch at all — the global handler logs the
    same traceback and the `except` block is just noise.

    The level follows the status: a 4xx is the caller's mistake, so it gets one
    warning line and no stack. If a failure is ours to debug it belongs in the
    5xx branch, which is what puts a traceback in the log.

    ``public_detail`` replaces the generic message with one the caller can act
    on -- "No generation model is configured", not "The request could not be
    processed." It must be a literal: interpolating ``exc`` into it defeats the
    whole point of routing through this function.
    """
    if status_code >= 500:
        logger.exception("%s: %s", context, exc)
    else:
        logger.warning("%s: %s", context, exc)
    # A 5xx detail only survives the global handler on a PublicHTTPException, so
    # asking for one and getting a plain HTTPException would silently mask it.
    cls = PublicHTTPException if public_detail else HTTPException
    http_exc = cls(status_code=status_code, detail=public_detail or public_message(status_code))
    # Already in the log with `context` attached; without this the handler below
    # logs the same failure a second time, saying less.
    http_exc.rhesis_logged = True
    return http_exc


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort for anything no router caught.

    Without this, an uncaught error becomes a bare Starlette 500 that logs
    nothing, which is how errors used to disappear entirely.
    """
    request_id = request_id_of(request)
    logger.exception(
        "[%s] Unhandled exception on %s %s: %s",
        request_id or "-",
        request.method,
        request.url.path,
        exc,
        # RequestIDMiddleware's `finally` has already cleared the ContextVar by
        # now, so the logging filter cannot recover the id for these records --
        # the ones an error_id actually points at. Pass it in by hand.
        extra={"request_id": request_id},
    )
    # Header set here, not by the middleware: an unhandled exception is turned
    # into a response by ServerErrorMiddleware, which sits outside it.
    return JSONResponse(
        status_code=500,
        content={"detail": public_message(500), "error_id": request_id},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Log server-side HTTPExceptions and strip their detail.

    Sub-500s pass through untouched: a 400 "name already exists" is a message
    we intend the user to read. A 5xx detail is an internal failure that only
    belongs in the logs.
    """
    if exc.status_code < 500:
        return await default_http_exception_handler(request, exc)

    request_id = request_id_of(request)
    deliberate = isinstance(exc, PublicHTTPException)

    if not getattr(exc, "rhesis_logged", False):
        # A deliberate 5xx is not a fault of ours to debug: an unreachable user
        # endpoint or a missing optional package is a warning with a readable
        # reason, not an ERROR with a stack that only points back at the raise.
        logger.log(
            logging.WARNING if deliberate else logging.ERROR,
            "%s on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
            exc_info=not deliberate,
        )

    # No X-Request-ID here: this response is built inside ExceptionMiddleware,
    # which RequestIDMiddleware wraps, so the header is added on the way out.
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail if deliberate else public_message(exc.status_code),
            "error_id": request_id,
        },
        headers=getattr(exc, "headers", None),
    )


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
