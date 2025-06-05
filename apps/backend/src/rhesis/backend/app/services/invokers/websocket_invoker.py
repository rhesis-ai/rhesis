import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import uuid

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatusCode
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
from .base import BaseEndpointInvoker, TemplateRenderer, ResponseMapper

from rhesis.backend.logging import logger


class WebSocketEndpointInvoker(BaseEndpointInvoker):
    """WebSocket endpoint invoker with support for different auth types."""

    def __init__(self):
        super().__init__()

    def invoke(self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the WebSocket endpoint with proper authentication."""
        try:
            logger.info(f"Starting WebSocket invocation for endpoint: {endpoint.name}")
            logger.debug(f"Endpoint URL: {endpoint.url}")
            logger.debug(f"Endpoint path: {endpoint.endpoint_path}")
            logger.debug(f"Auth type: {endpoint.auth_type}")
            
            # Run the async WebSocket communication in a sync context
            return asyncio.run(self._async_invoke(db, endpoint, input_data))
        except Exception as e:
            logger.error(f"WebSocket invocation failed: {str(e)}", exc_info=True)
            return self._create_error_response(
                error_type="websocket_error",
                output_message=f"WebSocket invocation failed: {str(e)}",
                message=f"WebSocket invocation failed: {str(e)}",
                request_details=self._safe_request_details(locals(), "WebSocket")
            )

    async def _async_invoke(self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Async implementation of WebSocket communication."""
        uri = None
        message_data = None
        additional_headers = None
        
        try:
            # Get authentication token
            logger.debug("Getting authentication token...")
            auth_token = self._get_valid_token(db, endpoint)
            if auth_token:
                logger.debug(f"Auth token obtained (length: {len(auth_token)})")
                logger.debug(f"Auth token preview: {auth_token[:50]}...")
            else:
                logger.warning("No auth token obtained")
            
            # Prepare the WebSocket message using the request body template
            logger.debug("Preparing WebSocket message...")
            message_data = self.template_renderer.render(
                endpoint.request_body_template or {}, 
                {**input_data, "auth_token": auth_token}
            )
            
            # Generate session_id if not provided
            if "session_id" not in message_data:
                message_data["session_id"] = str(uuid.uuid4())
                logger.debug(f"Generated session_id: {message_data['session_id']}")

            logger.debug(f"Message data prepared: {json.dumps(message_data, indent=2)}")

            # Connect to WebSocket and send message
            uri = self._build_websocket_uri(endpoint)
            logger.info(f"Connecting to WebSocket URI: {uri}")

            # Prepare headers for WebSocket connection
            additional_headers = self._prepare_additional_headers_with_auth(endpoint, auth_token)
            logger.debug(f"Additional headers: {json.dumps(additional_headers, indent=2)}")
            
            try:
                # Use the new websockets.asyncio.client.connect API
                logger.debug("Attempting WebSocket connection...")
                async with connect(uri, additional_headers=additional_headers) as websocket:
                    logger.info("WebSocket connection established successfully")
                    
                    # Send the message
                    message_json = json.dumps(message_data)
                    logger.debug(f"Sending message: {message_json}")
                    await websocket.send(message_json)
                    logger.info("Message sent successfully")
                    
                    # Collect all responses
                    responses = []
                    conversation_id = None
                    error_message = None
                    message_count = 0
                    
                    logger.debug("Starting to receive messages...")
                    async for message in websocket:
                        message_count += 1
                        logger.debug(f"Received message #{message_count}: {message}")
                        
                        try:
                            response_data = json.loads(message)
                            responses.append(response_data)
                            
                            # Extract conversation_id if present
                            if "conversation_id" in response_data:
                                conversation_id = response_data["conversation_id"]
                                logger.debug(f"Extracted conversation_id: {conversation_id}")
                            
                            # Check for error
                            if "error" in response_data:
                                error_message = response_data["error"]
                                logger.warning(f"Error in response: {error_message}")
                            
                            # Check if this is the end message
                            if response_data.get("message") == "response ended":
                                logger.info("Received 'response ended' message, closing connection")
                                break
                                
                        except json.JSONDecodeError as json_err:
                            logger.warning(f"Failed to parse JSON message: {json_err}")
                            # Handle non-JSON messages
                            responses.append({"raw_message": message})
                    
                    logger.info(f"Received {message_count} messages total")
                    
                    # Prepare the final response
                    final_response = {
                        "responses": responses,
                        "conversation_id": conversation_id,
                        "error": error_message,
                        "status": "completed" if not error_message else "error"
                    }
                    
                    logger.debug(f"Final response prepared: {json.dumps(final_response, indent=2)}")
                    
                    # Map response using configured mappings
                    mapped_response = self.response_mapper.map_response(final_response, endpoint.response_mappings or {})
                    logger.debug(f"Mapped response: {json.dumps(mapped_response, indent=2)}")
                    
                    return mapped_response
                    
            except InvalidStatusCode as status_err:
                logger.error(f"WebSocket connection rejected with status code: {status_err.status_code}")
                logger.error(f"Response headers: {status_err.headers}")
                logger.error(f"Response body: {status_err.body}")
                
                error_output = f"WebSocket connection rejected: HTTP {status_err.status_code}"
                if status_err.body:
                    error_output += f". Response: {status_err.body}"
                
                return self._create_error_response(
                    error_type="websocket_connection_error",
                    output_message=error_output,
                    message=f"WebSocket connection rejected: HTTP {status_err.status_code}",
                    request_details={
                        "protocol": "WebSocket",
                        "uri": uri,
                        "headers": additional_headers,
                        "body": message_data
                    },
                    status_code=status_err.status_code,
                    response_headers=dict(status_err.headers) if status_err.headers else {},
                    response_body=status_err.body
                )
                
            except Exception as e:
                # Enhanced error logging for WebSocket failures
                error_type = type(e).__name__
                logger.error(f"WebSocket communication error ({error_type}): {str(e)}")
                
                # Try to get more details about the websocket error
                if hasattr(e, 'response'):
                    logger.error(f"WebSocket response: {e.response}")
                if hasattr(e, 'code'):
                    logger.error(f"WebSocket error code: {e.code}")
                if hasattr(e, 'reason'):
                    logger.error(f"WebSocket error reason: {e.reason}")
                    
                # Log the full traceback for debugging
                logger.error(f"Full error traceback:", exc_info=True)
                
                return self._create_error_response(
                    error_type="websocket_communication_error",
                    output_message=f"WebSocket communication failed: {str(e)}",
                    message=f"WebSocket communication failed: {str(e)}",
                    request_details={
                        "protocol": "WebSocket",
                        "uri": uri,
                        "headers": additional_headers,
                        "body": message_data
                    }
                )
                
        except Exception as e:
            logger.error(f"Async invoke error: {str(e)}", exc_info=True)
            return self._create_error_response(
                error_type="websocket_error",
                output_message=f"WebSocket error: {str(e)}",
                message=f"WebSocket error: {str(e)}",
                request_details={
                    "protocol": "WebSocket",
                    "uri": uri or "unknown",
                    "headers": additional_headers or {},
                    "body": message_data
                }
            )

    def _build_websocket_uri(self, endpoint: Endpoint) -> str:
        """Build the complete WebSocket URI."""
        uri = endpoint.url
        if endpoint.endpoint_path:
            # Handle WebSocket URL construction - avoid duplicating path if already present
            if endpoint.endpoint_path.startswith('/'):
                path_to_check = endpoint.endpoint_path
            else:
                path_to_check = '/' + endpoint.endpoint_path
            
            # Check if the URL already contains the endpoint path
            if not endpoint.url.endswith(path_to_check):
                if endpoint.url.endswith('/'):
                    uri = endpoint.url.rstrip('/') + path_to_check
                else:
                    uri = endpoint.url + path_to_check
            else:
                # URL already contains the path, use as-is
                uri = endpoint.url
                logger.debug(f"Endpoint URL already contains the path '{path_to_check}', using URL as-is")
        return uri

    def _prepare_additional_headers(self, endpoint: Endpoint) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection (excluding standard WebSocket headers)."""
        headers = {}
        
        logger.debug("Preparing additional headers...")
        
        # Use configured headers if available, but exclude standard WebSocket headers
        # as they are handled automatically by the websockets library
        if endpoint.request_headers:
            logger.debug(f"Original request headers: {json.dumps(endpoint.request_headers, indent=2)}")
            standard_ws_headers = {"Upgrade", "Connection", "Sec-WebSocket-Version", "Sec-WebSocket-Key"}
            for key, value in endpoint.request_headers.items():
                if key not in standard_ws_headers:
                    headers[key] = value
                    logger.debug(f"Added header: {key} = {value}")
                else:
                    logger.debug(f"Filtered out standard WebSocket header: {key}")
        else:
            logger.debug("No request headers configured")
        
        logger.debug(f"Final additional headers: {json.dumps(headers, indent=2)}")
        return headers

    def _prepare_additional_headers_with_auth(self, endpoint: Endpoint, auth_token: Optional[str]) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection, but exclude Authorization for WebSocket handshake."""
        headers = self._prepare_additional_headers(endpoint)
        
        # For WebSocket connections, don't add Authorization header during handshake
        # The auth_token will be sent in the message body instead
        logger.debug("WebSocket connection - not adding Authorization header to handshake (auth_token will be in message body)")
        
        # Add common headers that WebSocket servers often require
        # Parse the base domain from the endpoint URL for Origin header
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(endpoint.url)
            base_origin = f"{parsed_url.scheme.replace('ws', 'http')}://{parsed_url.netloc}"
            headers["Origin"] = base_origin
            logger.debug(f"Added Origin header: {base_origin}")
        except Exception as e:
            logger.warning(f"Could not parse URL for Origin header: {e}")
        
        # Add User-Agent header
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        logger.debug("Added User-Agent header")
        
        logger.debug(f"Final headers for WebSocket handshake: {json.dumps(headers, indent=2)}")
        return headers
