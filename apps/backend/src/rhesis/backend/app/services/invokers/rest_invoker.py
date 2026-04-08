import json
import logging
import threading
from typing import Any, Dict, Union

import httpx
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

from .base import BaseEndpointInvoker
from .common.schemas import ErrorResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-local HTTP client
# ---------------------------------------------------------------------------
# In the async batch engine each Celery worker thread runs its own event loop
# (see batch/__init__.py:_thread_local).  httpx.AsyncClient is tied to the
# event loop it is first used on, so one client per thread is both correct
# and optimal — connections are pooled across all tests executing in the same
# worker thread (i.e. the same batch), avoiding the TCP handshake overhead of
# creating a fresh client per invocation.
_tls = threading.local()
_HTTP_TIMEOUT = 30.0


def _get_http_client() -> httpx.AsyncClient:
    """Return the thread-local AsyncClient, creating it on first access."""
    client: httpx.AsyncClient | None = getattr(_tls, "http_client", None)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)
        _tls.http_client = client
    return client


def _close_thread_local_client() -> None:
    """Close the thread-local AsyncClient if one exists.

    Called from the Celery worker-shutdown signal so sockets are released
    cleanly rather than relying on process-exit garbage collection.
    """
    client: httpx.AsyncClient | None = getattr(_tls, "http_client", None)
    if client is not None and not client.is_closed:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(client.aclose())
            else:
                loop.run_until_complete(client.aclose())
        except Exception:
            pass
        finally:
            _tls.http_client = None


class RestEndpointInvoker(BaseEndpointInvoker):
    """REST endpoint invoker with support for different auth types."""

    async def invoke(
        self,
        db=None,
        endpoint=None,
        input_data=None,
        *,
        test_execution_context=None,
        trace_id=None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        # Backward-compat: callers that pass positional args build a temporary context.
        if db is not None or endpoint is not None:
            from .context import InvocationContext

            self.context = InvocationContext(
                db=db,
                endpoint=endpoint,
                input_data=input_data or {},
                test_execution_context=test_execution_context,
                trace_id=trace_id,
            )
        db = self.context.db
        endpoint = self.context.endpoint
        input_data = self.context.input_data
        test_execution_context = self.context.test_execution_context
        trace_id = self.context.trace_id
        """
        Invoke the REST endpoint with proper authentication.

        Args:
            db: Database session
            endpoint: The endpoint to invoke
            input_data: Input data
            test_execution_context: Optional test context (not used by REST invoker,
                                   handled by executor's manual tracing wrapper)
        """
        try:
            # Prepare request components
            method, headers, request_body, url, conversation_id = self._prepare_request(
                db, endpoint, input_data
            )

            # Make async request and handle response
            response = await self._async_request(method, url, headers, request_body)

            # Log response summary
            logger.debug(f"Response received: {response.status_code}")

            # Handle different response scenarios
            if response.status_code >= 400:
                return self._handle_http_error(response, method, url, headers, request_body)

            return self._handle_successful_response(
                response,
                endpoint,
                method,
                url,
                headers,
                request_body,
                conversation_id,
            )

        except httpx.HTTPError as e:
            return self._create_error_response(
                error_type="network_error",
                output_message=f"Network/connection error: {str(e)}",
                message=f"Network/connection error: {str(e)}",
                request_details=self._safe_request_details(locals(), "REST"),
            )
        except (ValueError, json.JSONDecodeError) as e:
            # Handle JSON parsing errors specifically
            logger.error(f"JSON parsing error: {str(e)}")
            return self._create_error_response(
                error_type="json_parsing_error",
                output_message=(f"Failed to parse JSON response: {str(e)}"),
                message=f"Failed to parse JSON response: {str(e)}",
                request_details=self._safe_request_details(locals(), "REST"),
            )
        except HTTPException:
            # Re-raise HTTPExceptions (configuration errors)
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
        supported_methods = {"GET", "POST", "PUT", "DELETE"}
        if method not in supported_methods:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported HTTP method: {method}",
            )

        # Prepare template context with conversation tracking
        template_context, conversation_field = self._prepare_conversation_context(
            endpoint, input_data
        )

        # Prepare headers and body
        headers = self._prepare_headers(db, endpoint, input_data)
        request_body = self.template_renderer.render(
            endpoint.request_mapping or {}, template_context
        )

        # Strip reserved meta keys (e.g. system_prompt) from the wire body
        self._strip_meta_keys(request_body)

        # Extract conversation ID from rendered body
        conversation_id = None
        if isinstance(request_body, dict):
            conversation_id = self._extract_conversation_id(
                request_body, input_data, conversation_field
            )

        # Build URL
        url = endpoint.url + (endpoint.endpoint_path or "")
        logger.debug(f"Making {method} request to: {url}")

        return method, headers, request_body, url, conversation_id

    def _create_request_details(self, method: str, url: str, headers: Dict, body: Any) -> Dict:
        """Create request details dictionary with sanitized headers."""
        return {
            "connection_type": "REST",
            "method": method,
            "url": url,
            "headers": self._sanitize_headers(headers),
            "body": body,
        }

    def _handle_http_error(
        self,
        response: httpx.Response,
        method: str,
        url: str,
        headers: Dict,
        request_body: Any,
    ) -> Dict:
        """Handle HTTP error responses."""
        reason = response.reason_phrase
        logger.error(f"HTTP {response.status_code} error from {url}: {reason}")

        error_output = f"HTTP {response.status_code} error from endpoint: {reason}"
        if response.text:
            error_output += f". Response content: {response.text}"

        return self._create_error_response(
            error_type="http_error",
            output_message=error_output,
            message=f"HTTP {response.status_code} error from endpoint",
            request_details=self._create_request_details(method, url, headers, request_body),
            status_code=response.status_code,
            reason=reason,
            response_headers=self._sanitize_headers(dict(response.headers)),
            response_content=response.text,
        )

    def _handle_successful_response(
        self,
        response: httpx.Response,
        endpoint: Endpoint,
        method: str,
        url: str,
        headers: Dict,
        request_body: Any,
        conversation_id: str = None,
    ) -> Dict:
        """Handle successful response with JSON parsing."""
        try:
            response_data = response.json()

            mapped_response = self.response_mapper.map_response(
                response_data, endpoint.response_mapping or {}
            )

            # Add conversation tracking field to response if configured and available
            conversation_field = self._detect_conversation_field(endpoint)
            if conversation_field:
                # Use extracted value from mapped response, or fall back to input value
                if conversation_field in mapped_response:
                    logger.debug(
                        f"Conversation field {conversation_field} already in mapped response"
                    )
                elif conversation_id:
                    mapped_response[conversation_field] = conversation_id
                    logger.debug(f"Added {conversation_field} to response: {conversation_id}")

            # Preserve important unmapped fields from original response (error info, message, etc.)
            important_fields = ["error", "status", "message"]
            for field in important_fields:
                if field in response_data and field not in mapped_response:
                    mapped_response[field] = response_data[field]
                    logger.debug(f"Preserved unmapped field '{field}': {response_data[field]}")

            return mapped_response
        except json.JSONDecodeError as json_error:
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
                response_headers=self._sanitize_headers(dict(response.headers)),
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
        # If no auth_type is set but auth_token exists, assume bearer token
        if endpoint.auth_type or endpoint.auth_token:
            auth_token = self._get_valid_token(db, endpoint)

            # Replace {{ auth_token }} placeholders in header values
            for key, value in headers.items():
                if isinstance(value, str):
                    # Handle {{ auth_token }} Jinja2 template
                    if "{{ auth_token }}" in value:
                        template = Template(value)
                        headers[key] = template.render(auth_token=auth_token)

                    # Handle legacy {API_KEY} placeholder (single braces)
                    elif "{API_KEY}" in value:
                        headers[key] = value.replace("{API_KEY}", auth_token or "")

                    # Handle {auth_token} placeholder (single braces)
                    elif "{auth_token}" in value:
                        headers[key] = value.replace("{auth_token}", auth_token or "")

            # Automatically add Authorization header if not explicitly set
            if "Authorization" not in headers and auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

        # Inject context headers using shared base method
        self._inject_context_headers(headers, input_data)

        return headers

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _async_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Any,
    ) -> httpx.Response:
        """Make an async HTTP request. Retried on transient failures.

        Uses the thread-local AsyncClient so TCP connections are pooled
        across all tests in the same worker-thread batch.
        """
        client = _get_http_client()
        if method == "GET":
            return await client.get(url, headers=headers, params=body)
        elif method == "POST":
            return await client.post(url, headers=headers, json=body)
        elif method == "PUT":
            return await client.put(url, headers=headers, json=body)
        elif method == "DELETE":
            return await client.delete(url, headers=headers, json=body)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
