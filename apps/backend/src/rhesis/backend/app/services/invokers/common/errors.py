"""Error response handling and domain exceptions for endpoint invokers.

Contains:
- ``ErrorResponseBuilder``: creates standardised ``ErrorResponse`` Pydantic
  objects from invoker code.
- ``EndpointInvocationError``: domain exception replacing ``HTTPException``
  in non-HTTP contexts (Celery workers, SDK) so callers can distinguish
  transient from permanent failures and retry accordingly.
"""

from typing import Dict, Optional

from .schemas import ErrorResponse, RequestDetails

# ---------------------------------------------------------------------------
# ErrorResponseBuilder (existing)
# ---------------------------------------------------------------------------


class ErrorResponseBuilder:
    """Handles creation of standardized error responses."""

    @staticmethod
    def create_error_response(
        error_type: str,
        output_message: str,
        message: str,
        request_details: Optional[Dict] = None,
        **kwargs,
    ) -> ErrorResponse:
        """
        Create standardized error response using Pydantic schema.

        Args:
            error_type: Type of error (e.g., 'network_error', 'http_error')
            output_message: User-facing error message
            message: Technical error message
            request_details: Optional request details for debugging
            **kwargs: Additional fields to include in response

        Returns:
            Typed ErrorResponse object
        """
        request_schema = None
        if request_details:
            if isinstance(request_details, RequestDetails):
                request_schema = request_details
            else:
                request_schema = RequestDetails(**request_details)

        return ErrorResponse(
            output=output_message,
            error_type=error_type,
            message=message,
            request=request_schema,
            **kwargs,
        )

    @staticmethod
    def safe_request_details(local_vars: Dict, connection_type: str = "unknown") -> RequestDetails:
        """
        Safely create request details from local variables using Pydantic schema.

        Args:
            local_vars: Local variables dict (typically from locals())
            connection_type: Connection type (REST, WebSocket, SDK, etc.)

        Returns:
            Typed RequestDetails object
        """
        from .headers import HeaderManager

        project_id = local_vars.get("project_id")
        if project_id is not None:
            project_id = str(project_id)

        return RequestDetails(
            connection_type=connection_type,
            method=local_vars.get("method", "UNKNOWN"),
            url=local_vars.get("url", local_vars.get("uri", "UNKNOWN")),
            headers=HeaderManager.sanitize_headers(local_vars.get("headers", {})),
            body=local_vars.get("request_body", local_vars.get("message_data")),
            project_id=project_id,
            environment=local_vars.get("environment"),
            function_name=local_vars.get("function_name"),
        )


# ---------------------------------------------------------------------------
# Domain exceptions for endpoint invocation
# ---------------------------------------------------------------------------


class EndpointInvocationError(Exception):
    """Raised when an endpoint invocation fails.

    Attributes:
        transient: ``True`` for errors that may succeed on retry
            (rate limits, gateway errors, connection issues).
            ``False`` for permanent failures (bad request, auth,
            not found, application-level errors).
        status_code: HTTP status code when available.
        error_type: Machine-readable error category from the invoker.
        retry_after: Seconds to wait before retrying (from Retry-After
            header or rate-limit response), or ``None``.
    """

    def __init__(
        self,
        message: str,
        *,
        transient: bool = False,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.transient = transient
        self.status_code = status_code
        self.error_type = error_type
        self.retry_after = retry_after


_TRANSIENT_STATUS_CODES = frozenset({408, 429, 502, 503, 504})

_TRANSIENT_ERROR_TYPES = frozenset(
    {
        "network_error",
        "websocket_error",
        "timeout_error",
        "connection_error",
    }
)


def classify_error_response(error_response: ErrorResponse) -> EndpointInvocationError:
    """Build an ``EndpointInvocationError`` from an invoker ``ErrorResponse``.

    Inspects ``status_code`` and ``error_type`` to decide whether the
    failure is transient.
    """
    status_code = getattr(error_response, "status_code", None)
    error_type = getattr(error_response, "error_type", None) or ""
    message = getattr(error_response, "output", str(error_response))

    retry_after: Optional[float] = None
    if status_code == 429:
        headers = getattr(error_response, "response_headers", None) or {}
        raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw is not None:
            try:
                retry_after = float(raw)
            except (ValueError, TypeError):
                pass

    transient = (status_code in _TRANSIENT_STATUS_CODES) or (error_type in _TRANSIENT_ERROR_TYPES)

    return EndpointInvocationError(
        message,
        transient=transient,
        status_code=status_code,
        error_type=error_type,
        retry_after=retry_after,
    )
