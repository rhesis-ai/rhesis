import json
import os
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict

import jsonpath_ng
import requests
from fastapi import HTTPException
from jinja2 import Template
from sqlalchemy.orm import Session
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointProtocol


class RequestHandler(ABC):
    """Abstract base class for handling different HTTP methods"""

    @abstractmethod
    def handle_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        pass


class PostRequestHandler(RequestHandler):
    def handle_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.post(url, headers=headers, json=body)


class GetRequestHandler(RequestHandler):
    def handle_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        # For GET requests, body is converted to query parameters
        return requests.get(url, headers=headers, params=body)


class PutRequestHandler(RequestHandler):
    def handle_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.put(url, headers=headers, json=body)


class DeleteRequestHandler(RequestHandler):
    def handle_request(self, url: str, headers: Dict[str, str], body: Any) -> requests.Response:
        return requests.delete(url, headers=headers, json=body)


class TemplateRenderer:
    """Handles template rendering using Jinja2"""

    def render(self, template_data: Any, input_data: Dict[str, Any]) -> Any:
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
    """Handles response mapping using JSONPath"""

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


class EndpointInvoker:
    """Main class for invoking endpoints"""

    def __init__(self):
        self.request_handlers = {
            "POST": PostRequestHandler(),
            "GET": GetRequestHandler(),
            "PUT": PutRequestHandler(),
            "DELETE": DeleteRequestHandler(),
        }
        self.template_renderer = TemplateRenderer()
        self.response_mapper = ResponseMapper()

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _make_request(self, handler, url, headers, request_body):
        """Make HTTP request with retry logic for transient failures"""
        response = handler.handle_request(url, headers, request_body)
        response.raise_for_status()
        return response

    def invoke(self, db: Session, endpoint_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes an endpoint with the given input data using its configured protocol and mappings.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template

        Returns:
            Dict containing the mapped response from the endpoint
        """
        # Fetch endpoint configuration
        endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")

        # Validate protocol
        if endpoint.protocol != EndpointProtocol.REST:
            raise HTTPException(status_code=400, detail="Only REST protocol is currently supported")

        # Get appropriate request handler
        method = (endpoint.method or "POST").upper()
        handler = self.request_handlers.get(method)
        if not handler:
            raise HTTPException(status_code=400, detail=f"Unsupported HTTP method: {method}")

        # Prepare request headers
        headers = endpoint.request_headers or {"Content-Type": "application/json"}

        # Prepare request body using template
        request_body = self.template_renderer.render(
            endpoint.request_body_template or {}, input_data
        )

        # Make the request with retry logic
        try:
            url = endpoint.url + (endpoint.endpoint_path or "")
            response = self._make_request(handler, url, headers, request_body)
            response_data = response.json()
        except RetryError as e:
            error_msg = str(e.last_attempt.exception())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to invoke endpoint after multiple retries: {error_msg}",
            )
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Failed to invoke endpoint: {str(e)}")

        # Map response
        return self.response_mapper.map_response(response_data, endpoint.response_mappings or {})


# Create a singleton instance
endpoint_invoker = EndpointInvoker()


def invoke(db: Session, endpoint_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function that uses the singleton EndpointInvoker"""
    return endpoint_invoker.invoke(db, endpoint_id, input_data)


def get_schema() -> Dict[str, Any]:
    """
    Get the endpoint schema definition.

    Returns:
        Dict containing the input and output schema definitions
    """
    schema_path = os.path.join(os.path.dirname(__file__), "endpoint_schema.json")
    with open(schema_path, "r") as f:
        schema = json.load(f)
    return schema


# Add main section for command line testing
if __name__ == "__main__":
    import argparse

    from rhesis.backend.app.database import SessionLocal

    parser = argparse.ArgumentParser(description="Test endpoint invocation")
    parser.add_argument("endpoint_id", help="ID of the endpoint to invoke")
    parser.add_argument(
        "--input", "-i", help="Input message", default="Hello, how can you help me?"
    )
    parser.add_argument("--session", "-s", help="Session ID", default=None)

    args = parser.parse_args()

    # Prepare input data
    input_data = {"input": args.input, "session_id": args.session or str(uuid.uuid4())}

    # Create DB session
    db = SessionLocal()
    try:
        # Invoke endpoint
        print(f"\nInvoking endpoint {args.endpoint_id} with input: {input_data}")
        result = invoke(db, args.endpoint_id, input_data)
        print("\nResponse:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        db.close()

"""
Usage examples:

1. Basic usage:
python -m rhesis.app.services.endpoint "your-endpoint-id"

2. With custom input:
python -m rhesis.app.services.endpoint "your-endpoint-id" -i "What's the weather like?"

3. With custom input and session:
python -m rhesis.app.services.endpoint "your-endpoint-id" -i "Hello" -s "custom-session-123"
"""
