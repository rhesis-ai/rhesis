import json
from typing import Any, Dict

import requests
from fastapi import HTTPException
from jinja2 import Template
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.models.endpoint import Endpoint

# Use rhesis logger
from rhesis.backend.logging import logger

from .base import BaseEndpointInvoker, ResponseMapper, TemplateRenderer


class RestEndpointInvoker(BaseEndpointInvoker):
    """REST endpoint invoker with support for different auth types."""

    def __init__(self):
        super().__init__()
        self.request_handlers = {
            "POST": self._handle_post_request,
            "GET": self._handle_get_request,
            "PUT": self._handle_put_request,
            "DELETE": self._handle_delete_request,
        }
        self.template_renderer = TemplateRenderer()
        self.response_mapper = ResponseMapper()

    def invoke(self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the REST endpoint with proper authentication."""
        try:
            # Prepare request components
            method, headers, request_body, url = self._prepare_request(db, endpoint, input_data)

            # Make request and handle response
            response = self._make_request_without_raise(
                self.request_handlers[method], url, headers, request_body
            )

            # Log response summary
            logger.debug(f"Response received: {response.status_code}")

            # Handle different response scenarios
            if response.status_code >= 400:
                return self._handle_http_error(response, method, url, headers, request_body)

            return self._handle_successful_response(
                response, endpoint, method, url, headers, request_body
            )

        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                error_type="network_error",
                output_message=f"Network/connection error: {str(e)}",
                message=f"Network/connection error: {str(e)}",
                request_details=self._safe_request_details(locals(), "REST"),
            )
        except HTTPException:
            # Re-raise HTTPExceptions (configuration errors that should still fail)
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return self._create_error_response(
                error_type="unexpected_error",
                output_message=f"Unexpected error: {str(e)}",
                message=f"Unexpected error: {str(e)}",
                request_details=self._safe_request_details(locals(), "REST"),
            )

    def _prepare_request(
        self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]
    ) -> tuple:
        """Prepare all request components."""
        logger.debug(f"Invoking endpoint: {endpoint.name}")

        # Get method and validate
        method = (endpoint.method or "POST").upper()
        if method not in self.request_handlers:
            raise HTTPException(status_code=400, detail=f"Unsupported HTTP method: {method}")

        # Prepare headers and body
        headers = self._prepare_headers(db, endpoint, input_data)
        request_body = self.template_renderer.render(
            endpoint.request_body_template or {}, input_data
        )

        # Build URL
        url = endpoint.url + (endpoint.endpoint_path or "")
        logger.debug(f"Making {method} request to: {url}")

        return method, headers, request_body, url

    def _create_request_details(self, method: str, url: str, headers: Dict, body: Any) -> Dict:
        """Create request details dictionary with sanitized headers."""
        return {
            "protocol": "REST",
            "method": method,
            "url": url,
            "headers": self._sanitize_headers(headers),
            "body": body,
        }

    def _safe_request_details(self, local_vars: Dict, protocol: str) -> Dict:
        """Safely create request details from local variables with sanitized headers."""
        return {
            "protocol": protocol,
            "method": local_vars.get("method", "UNKNOWN"),
            "url": local_vars.get("url", "UNKNOWN"),
            "headers": self._sanitize_headers(local_vars.get("headers", {})),
            "body": local_vars.get("request_body"),
        }

    def _handle_http_error(
        self, response: requests.Response, method: str, url: str, headers: Dict, request_body: Any
    ) -> Dict:
        """Handle HTTP error responses."""
        logger.error(f"HTTP {response.status_code} error from {url}: {response.reason}")

        error_output = f"HTTP {response.status_code} error from endpoint: {response.reason}"
        if response.text:
            error_output += f". Response content: {response.text}"

        return self._create_error_response(
            error_type="http_error",
            output_message=error_output,
            message=f"HTTP {response.status_code} error from endpoint",
            request_details=self._create_request_details(method, url, headers, request_body),
            status_code=response.status_code,
            reason=response.reason,
            response_headers=dict(response.headers),
            response_content=response.text,
        )

    def _handle_successful_response(
        self,
        response: requests.Response,
        endpoint: Endpoint,
        method: str,
        url: str,
        headers: Dict,
        request_body: Any,
    ) -> Dict:
        """Handle successful response with JSON parsing."""
        try:
            response_data = response.json()

            mapped_response = self.response_mapper.map_response(
                response_data, endpoint.response_mappings or {}
            )

            return mapped_response
        except (json.JSONDecodeError, requests.exceptions.JSONDecodeError) as json_error:
            logger.error(f"JSON parsing error from {url}: {str(json_error)}")

            # Create error response
            error_message = (
                "Empty response received from endpoint"
                if not response.text
                else "Invalid JSON response from endpoint"
            )
            error_output = f"{error_message} (status: {response.status_code})"
            if response.text:
                error_output += f". Response content: {response.text}"

            return self._create_error_response(
                error_type="json_parsing_error",
                output_message=error_output,
                message=f"{error_message} (status: {response.status_code})",
                request_details=self._create_request_details(method, url, headers, request_body),
                status_code=response.status_code,
                response_headers=dict(response.headers),
                response_content=response.text,
                response_content_length=len(response.text) if response.text else 0,
                json_error=str(json_error),
            )

    def _prepare_headers(
        self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """Prepare request headers with proper authentication and context injection."""
        headers = (endpoint.request_headers or {}).copy()

        # Ensure Content-Type is set
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        # Add auth_token if auth is configured (legacy auth_token placeholder support)
        if endpoint.auth_type:
            auth_token = self._get_valid_token(db, endpoint)

            # Replace {{ auth_token }} placeholders in header values
            for key, value in headers.items():
                if isinstance(value, str) and "{{ auth_token }}" in value:
                    template = Template(value)
                    headers[key] = template.render(auth_token=auth_token)

            # Automatically add Authorization header if not explicitly set
            if "Authorization" not in headers and auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

        # Inject context headers using shared base method
        self._inject_context_headers(headers, input_data)

        return headers

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _make_request(
        self, handler, url: str, headers: Dict[str, str], body: Any
    ) -> requests.Response:
        """Make HTTP request with retry logic for transient failures."""
        response = handler(url, headers, body)
        response.raise_for_status()
        return response

    def _make_request_without_raise(
        self, handler, url: str, headers: Dict[str, str], body: Any
    ) -> requests.Response:
        """Make HTTP request without raising for HTTP errors."""
        response = handler(url, headers, body)
        # Don't raise for status - let the caller handle HTTP errors gracefully
        return response

    def _handle_post_request(
        self, url: str, headers: Dict[str, str], body: Any
    ) -> requests.Response:
        return requests.post(url, headers=headers, json=body)

    def _handle_get_request(
        self, url: str, headers: Dict[str, str], body: Any
    ) -> requests.Response:
        return requests.get(url, headers=headers, params=body)

    def _handle_put_request(
        self, url: str, headers: Dict[str, str], body: Any
    ) -> requests.Response:
        return requests.put(url, headers=headers, json=body)

    def _handle_delete_request(
        self, url: str, headers: Dict[str, str], body: Any
    ) -> requests.Response:
        return requests.delete(url, headers=headers, json=body)
