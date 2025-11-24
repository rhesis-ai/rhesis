"""Error response handling for endpoint invokers."""

from typing import Dict, Optional

from .schemas import ErrorResponse, RequestDetails


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
        # Convert request_details dict to RequestDetails schema if provided
        request_schema = None
        if request_details:
            request_schema = RequestDetails(**request_details)

        # Create the error response with validation
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

        # Convert project_id to string if it's a UUID object
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
