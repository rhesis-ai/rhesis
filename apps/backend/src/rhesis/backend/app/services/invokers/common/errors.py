"""Error response handling for endpoint invokers."""

from typing import Dict


class ErrorResponseBuilder:
    """Handles creation of standardized error responses."""

    @staticmethod
    def create_error_response(
        error_type: str,
        output_message: str,
        message: str,
        request_details: Dict = None,
        **kwargs,
    ) -> Dict:
        """
        Create standardized error response.

        Args:
            error_type: Type of error (e.g., 'network_error', 'http_error')
            output_message: User-facing error message
            message: Technical error message
            request_details: Optional request details for debugging
            **kwargs: Additional fields to include in response

        Returns:
            Standardized error response dictionary
        """
        error_response = {
            "output": output_message,
            "error": True,
            "error_type": error_type,
            "message": message,
        }
        if request_details:
            error_response["request"] = request_details
        error_response.update(kwargs)
        return error_response

    @staticmethod
    def safe_request_details(local_vars: Dict, protocol: str = "unknown") -> Dict:
        """
        Safely create request details from local variables.

        Args:
            local_vars: Local variables dict (typically from locals())
            protocol: Protocol type (REST, WebSocket, etc.)

        Returns:
            Sanitized request details dictionary
        """
        from .headers import HeaderManager

        return {
            "protocol": protocol,
            "method": local_vars.get("method", "UNKNOWN"),
            "url": local_vars.get("url", local_vars.get("uri", "UNKNOWN")),
            "headers": HeaderManager.sanitize_headers(local_vars.get("headers", {})),
            "body": local_vars.get("request_body", local_vars.get("message_data")),
        }
