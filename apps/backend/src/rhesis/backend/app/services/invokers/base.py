import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jsonpath_ng
import requests
from fastapi import HTTPException
from jinja2 import Template
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType
from rhesis.backend.logging import logger


class BaseEndpointInvoker(ABC):
    """Base class for endpoint invokers with shared functionality."""

    def __init__(self):
        self.template_renderer = TemplateRenderer()
        self.response_mapper = ResponseMapper()

    @abstractmethod
    def invoke(self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the endpoint with the given input data.

        Args:
            db: Database session
            endpoint: The endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template

        Returns:
            Dict containing the mapped response from the endpoint
        """
        pass

    # Shared authentication methods
    def _get_valid_token(self, db: Session, endpoint: Endpoint) -> Optional[str]:
        """Get a valid authentication token based on the endpoint's auth type."""
        # Check if we have a valid cached token
        if endpoint.last_token and endpoint.last_token_expires_at:
            if endpoint.last_token_expires_at > datetime.utcnow():
                return endpoint.last_token

        # No valid cached token, get new one based on auth type
        if endpoint.auth_type == EndpointAuthType.BEARER_TOKEN.value:
            return endpoint.auth_token
        elif endpoint.auth_type == EndpointAuthType.CLIENT_CREDENTIALS.value:
            return self._get_client_credentials_token(db, endpoint)

        return None

    def _get_client_credentials_token(self, db: Session, endpoint: Endpoint) -> str:
        """Get a new token using client credentials flow."""
        if not endpoint.token_url:
            raise HTTPException(
                status_code=400, detail="Token URL is required for client credentials flow"
            )

        # Prepare token request
        payload = {
            "client_id": endpoint.client_id,
            "client_secret": endpoint.client_secret,
            "audience": endpoint.audience,
            "grant_type": "client_credentials",
        }

        # Add scopes if configured
        if endpoint.scopes:
            payload["scope"] = " ".join(endpoint.scopes)

        # Add extra payload if configured
        if endpoint.extra_payload:
            payload.update(endpoint.extra_payload)

        try:
            # Make token request
            response = requests.post(endpoint.token_url, json=payload)
            response.raise_for_status()
            token_data = response.json()

            # Update endpoint with new token info
            endpoint.last_token = token_data["access_token"]
            endpoint.last_token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data.get("expires_in", 3600)
            )
            # Transaction commit is handled by the session context manager

            return endpoint.last_token
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get client credentials token: {str(e)}"
            )

    # Shared header injection methods
    def _inject_context_headers(
        self, headers: Dict[str, str], input_data: Dict[str, Any] = None
    ) -> None:
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

    # Shared error handling methods
    def _create_error_response(
        self,
        error_type: str,
        output_message: str,
        message: str,
        request_details: Dict = None,
        **kwargs,
    ) -> Dict:
        """Create standardized error response."""
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

    def _sanitize_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize headers by redacting sensitive information."""
        if not headers:
            return {}

        sensitive_keys = {
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

        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            # Check if any sensitive keyword is in the header key
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized

    def _safe_request_details(self, local_vars: Dict, protocol: str = "unknown") -> Dict:
        """Safely create request details from local variables."""
        return {
            "protocol": protocol,
            "method": local_vars.get("method", "UNKNOWN"),
            "url": local_vars.get("url", local_vars.get("uri", "UNKNOWN")),
            "headers": self._sanitize_headers(local_vars.get("headers", {})),
            "body": local_vars.get("request_body", local_vars.get("message_data")),
        }


class TemplateRenderer:
    """Handles template rendering using Jinja2."""

    def render(self, template_data: Any, input_data: Dict[str, Any]) -> Any:
        # Ensure session_id exists if it's referenced in template but missing from input
        if isinstance(template_data, (dict, str)):
            template_str = (
                json.dumps(template_data) if isinstance(template_data, dict) else template_data
            )
            if "{{ session_id }}" in template_str and "session_id" not in input_data:
                input_data = input_data.copy()
                input_data["session_id"] = str(uuid.uuid4())
                logger.info(f"Auto-generated session_id: {input_data['session_id']}")

        if isinstance(template_data, str):
            template = Template(template_data)
            rendered = template.render(**input_data)
            try:
                return json.loads(rendered)
            except json.JSONDecodeError:
                return rendered
        elif isinstance(template_data, dict):
            result = template_data.copy()
            for key, value in result.items():
                if isinstance(value, str):
                    template = Template(value)
                    result[key] = template.render(**input_data)
            return result
        return template_data


class ResponseMapper:
    """Handles response mapping using JSONPath."""

    def map_response(
        self, response_data: Dict[str, Any], mappings: Dict[str, str]
    ) -> Dict[str, Any]:
        if not mappings:
            return response_data

        result = {}
        for output_key, jsonpath in mappings.items():
            jsonpath_expr = jsonpath_ng.parse(jsonpath)
            matches = jsonpath_expr.find(response_data)
            if matches:
                result[output_key] = matches[0].value
            else:
                # If no match found, set to None
                result[output_key] = None
        return result
