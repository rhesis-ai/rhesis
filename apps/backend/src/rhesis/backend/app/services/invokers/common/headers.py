"""Header management utilities for endpoint invokers."""

from typing import Any, Dict


class HeaderManager:
    """Handles header sanitization and injection for endpoint requests."""

    # Sensitive header keys to redact in logs
    SENSITIVE_KEYS = {
        "authorization",
        "auth",
        "x-api-key",
        "api-key",
        "x-auth-token",
        "bearer",
        "token",
        "secret",
        "password",
        "x-access-token",
        "cookie",
    }

    @staticmethod
    def sanitize_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize headers by redacting sensitive information.

        Args:
            headers: Headers dictionary to sanitize

        Returns:
            Sanitized headers with sensitive values redacted
        """
        if not headers:
            return {}

        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            # Check if any sensitive keyword is in the header key
            if any(sensitive in key_lower for sensitive in HeaderManager.SENSITIVE_KEYS):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized

    @staticmethod
    def inject_context_headers(headers: Dict[str, str], input_data: Dict[str, Any] = None) -> None:
        """
        Inject context headers (organization_id, user_id) into headers dict.

        These come from backend context, NOT user input (SECURITY CRITICAL).
        Only adds headers if they don't already exist.

        Args:
            headers: Headers dictionary to inject into (modified in-place)
            input_data: Input data containing organization_id and user_id from backend context
        """
        if input_data:
            if "organization_id" in input_data and "X-Organization-ID" not in headers:
                headers["X-Organization-ID"] = str(input_data["organization_id"])
            if "user_id" in input_data and "X-User-ID" not in headers:
                headers["X-User-ID"] = str(input_data["user_id"])
