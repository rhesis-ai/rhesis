import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException
from jinja2 import Template
from sqlalchemy.orm import Session
import jsonpath_ng
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType
from .base import BaseEndpointInvoker

# Use rhesis logger
from rhesis.backend.logging import logger


class RestEndpointInvoker(BaseEndpointInvoker):
    """REST endpoint invoker with support for different auth types."""

    def __init__(self):
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
            # Log input data for debugging
            logger.info(f"Invoking endpoint {endpoint.name} with input_data: {json.dumps(input_data, indent=2)}")
            
            # Get appropriate request handler
            method = (endpoint.method or "POST").upper()
            handler = self.request_handlers.get(method)
            if not handler:
                raise HTTPException(status_code=400, detail=f"Unsupported HTTP method: {method}")

            # Prepare headers with authentication if needed
            headers = self._prepare_headers(db, endpoint)
            logger.info(f"Prepared headers: {json.dumps(headers, indent=2)}")

            # Prepare request body using template
            request_body = self.template_renderer.render(
                endpoint.request_body_template or {}, input_data
            )
            logger.info(f"Rendered request body: {json.dumps(request_body, indent=2)}")

            # Make the request with retry logic
            url = endpoint.url + (endpoint.endpoint_path or "")
            logger.info(f"Making request to URL: {url}")
            
            response = self._make_request(handler, url, headers, request_body)
            response_data = response.json()

            # Map response
            return self.response_mapper.map_response(response_data, endpoint.response_mappings or {})
        except requests.exceptions.HTTPError as e:
            # Log the response details for HTTP errors
            logger.error(f"HTTP error occurred: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response headers: {dict(e.response.headers)}")
                try:
                    logger.error(f"Response body: {e.response.text}")
                except:
                    logger.error("Could not read response body")
            raise HTTPException(status_code=500, detail=f"API error: {e.response.status_code} - {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def _prepare_headers(self, db: Session, endpoint: Endpoint) -> Dict[str, str]:
        """Prepare request headers with proper authentication."""
        headers = endpoint.request_headers or {"Content-Type": "application/json"}

        if endpoint.auth_type:
            # Get valid token based on auth type
            auth_token = self._get_valid_token(db, endpoint)
            
            # Replace auth_token placeholder in headers
            if headers:
                context = {"auth_token": auth_token}
                for key, value in headers.items():
                    if isinstance(value, str) and "{{ auth_token }}" in value:
                        template = Template(value)
                        headers[key] = template.render(**context)

        return headers

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
            raise HTTPException(status_code=400, detail="Token URL is required for client credentials flow")

        # Prepare token request
        payload = {
            "client_id": endpoint.client_id,
            "client_secret": endpoint.client_secret,
            "audience": endpoint.audience,
            "grant_type": "client_credentials"
        }

        try:
            # Make token request
            response = requests.post(endpoint.token_url, json=payload)
            response.raise_for_status()
            token_data = response.json()

            # Update endpoint with new token info
            endpoint.last_token = token_data["access_token"]
            endpoint.last_token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
            db.commit()

            return endpoint.last_token
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get client credentials token: {str(e)}")

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _make_request(self, handler, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        """Make HTTP request with retry logic for transient failures."""
        response = handler(url, headers, body)
        response.raise_for_status()
        return response

    def _handle_post_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.post(url, headers=headers, json=body)

    def _handle_get_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.get(url, headers=headers, params=body)

    def _handle_put_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.put(url, headers=headers, json=body)

    def _handle_delete_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.delete(url, headers=headers, json=body)


class TemplateRenderer:
    """Handles template rendering using Jinja2."""

    def render(self, template_data: Any, input_data: Dict[str, Any]) -> Any:
        # Ensure session_id exists if it's referenced in template but missing from input
        if isinstance(template_data, (dict, str)):
            template_str = json.dumps(template_data) if isinstance(template_data, dict) else template_data
            if "{{ session_id }}" in template_str and "session_id" not in input_data:
                import uuid
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
        return result 