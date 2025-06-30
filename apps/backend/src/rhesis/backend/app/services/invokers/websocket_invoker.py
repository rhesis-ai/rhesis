import asyncio
import json
import logging
import unicodedata
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

    def _normalize_unicode_text(self, text: str) -> str:
        """
        Normalize Unicode text to handle various Unicode characters commonly used in AI responses.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text with common Unicode characters converted to ASCII equivalents
        """
        if not text:
            return text
        
        # First, normalize Unicode using NFKC (Canonical Decomposition, then Canonical Composition)
        # This handles most Unicode normalization cases
        normalized = unicodedata.normalize('NFKC', text)
        
        # Handle specific common Unicode characters that AI services often use
        unicode_replacements = {
            # Quotation marks
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
            '\u201A': "'",  # Single low-9 quotation mark
            '\u201B': "'",  # Single high-reversed-9 quotation mark
            '\u201C': '"',  # Left double quotation mark
            '\u201D': '"',  # Right double quotation mark
            '\u201E': '"',  # Double low-9 quotation mark
            '\u201F': '"',  # Double high-reversed-9 quotation mark
            
            # Dashes
            '\u2010': '-',  # Hyphen
            '\u2011': '-',  # Non-breaking hyphen
            '\u2012': '-',  # Figure dash
            '\u2013': '-',  # En dash
            '\u2014': '-',  # Em dash
            '\u2015': '-',  # Horizontal bar
            
            # Spaces
            '\u00A0': ' ',  # Non-breaking space
            '\u2000': ' ',  # En quad
            '\u2001': ' ',  # Em quad
            '\u2002': ' ',  # En space
            '\u2003': ' ',  # Em space
            '\u2004': ' ',  # Three-per-em space
            '\u2005': ' ',  # Four-per-em space
            '\u2006': ' ',  # Six-per-em space
            '\u2007': ' ',  # Figure space
            '\u2008': ' ',  # Punctuation space
            '\u2009': ' ',  # Thin space
            '\u200A': ' ',  # Hair space
            '\u202F': ' ',  # Narrow no-break space
            '\u205F': ' ',  # Medium mathematical space
            
            # Other common symbols
            '\u2026': '...',  # Horizontal ellipsis
            '\u2022': '*',    # Bullet
            '\u2023': '*',    # Triangular bullet
            '\u2024': '.',    # One dot leader
            '\u2025': '..',   # Two dot leader
            '\u2032': "'",    # Prime
            '\u2033': '"',    # Double prime
        }
        
        # Apply the replacements
        for unicode_char, replacement in unicode_replacements.items():
            normalized = normalized.replace(unicode_char, replacement)
        
        return normalized

    def invoke(self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the WebSocket endpoint with proper authentication."""
        try:
            logger.info(f"Starting WebSocket invocation for endpoint: {endpoint.name}")
            
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
            auth_token = self._get_valid_token(db, endpoint)
            if not auth_token:
                logger.warning("No auth token obtained")
            
            # Prepare the WebSocket message using the request body template
            message_data = self.template_renderer.render(
                endpoint.request_body_template or {}, 
                {**input_data, "auth_token": auth_token}
            )
            
            # Generate session_id if not provided
            if "session_id" not in message_data:
                message_data["session_id"] = str(uuid.uuid4())

            # Connect to WebSocket and send message
            uri = self._build_websocket_uri(endpoint)
            logger.info(f"Connecting to WebSocket: {uri}")

            # Prepare headers for WebSocket connection
            additional_headers = self._prepare_additional_headers_with_auth(endpoint, auth_token)
            
            try:
                # Use the new websockets.asyncio.client.connect API
                async with connect(uri, additional_headers=additional_headers) as websocket:
                    logger.info("WebSocket connection established")
                    
                    # Send the message
                    message_json = json.dumps(message_data)
                    await websocket.send(message_json)
                    logger.info("Message sent successfully")
                    
                    # Collect all responses
                    responses = []
                    conversation_id = None
                    error_message = None
                    message_count = 0
                    streaming_text_buffer = ""  # Buffer for accumulating streaming text chunks
                    
                    async for message in websocket:
                        message_count += 1
                        
                        # Try to parse as JSON first
                        try:
                            response_data = json.loads(message)
                            
                            # If we have buffered streaming text, add it as a response before processing JSON
                            if streaming_text_buffer.strip():
                                # Normalize Unicode characters to ASCII equivalents
                                normalized_text = self._normalize_unicode_text(streaming_text_buffer)
                                responses.append({"content": normalized_text})
                                streaming_text_buffer = ""  # Reset buffer
                            
                            responses.append(response_data)
                            
                            # Extract conversation_id if present
                            if "conversation_id" in response_data:
                                conversation_id = response_data["conversation_id"]
                            
                            # Check for error
                            if "error" in response_data:
                                error_message = response_data["error"]
                                logger.warning(f"Error in response: {error_message}")
                            
                            # Check if this is the end message
                            if response_data.get("message") == "response ended":
                                logger.info("Response stream ended")
                                break
                                
                        except json.JSONDecodeError:
                            # This is a streaming text chunk, add it to buffer
                            streaming_text_buffer += message
                    
                    # Add any remaining buffered streaming text
                    if streaming_text_buffer.strip():
                        # Normalize Unicode characters to ASCII equivalents
                        normalized_text = self._normalize_unicode_text(streaming_text_buffer)
                        responses.append({"content": normalized_text})
                    
                    logger.info(f"Received {message_count} messages total")
                    
                    # Extract the main content from responses
                    main_content = ""
                    
                    for response in responses:
                        if "content" in response:
                            main_content += response["content"]
                    
                    # Prepare the final response
                    final_response = {
                        "output": main_content if main_content else None,
                        "conversation_id": conversation_id,
                        "error": error_message,
                        "status": "completed" if not error_message else "error"
                    }
                    
                    # Map response using configured mappings
                    mapped_response = self.response_mapper.map_response(final_response, endpoint.response_mappings or {})
                    logger.debug(f"Final mapped response: {json.dumps(mapped_response, indent=2)}")
                    
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
        return uri

    def _prepare_additional_headers(self, endpoint: Endpoint) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection (excluding standard WebSocket headers)."""
        headers = {}
        
        # Use configured headers if available, but exclude standard WebSocket headers
        # as they are handled automatically by the websockets library
        if endpoint.request_headers:
            standard_ws_headers = {"Upgrade", "Connection", "Sec-WebSocket-Version", "Sec-WebSocket-Key"}
            for key, value in endpoint.request_headers.items():
                if key not in standard_ws_headers:
                    headers[key] = value
        
        return headers

    def _prepare_additional_headers_with_auth(self, endpoint: Endpoint, auth_token: Optional[str]) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection, but exclude Authorization for WebSocket handshake."""
        headers = self._prepare_additional_headers(endpoint)
        
        # For WebSocket connections, don't add Authorization header during handshake
        # The auth_token will be sent in the message body instead
        
        # Add common headers that WebSocket servers often require
        # Parse the base domain from the endpoint URL for Origin header
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(endpoint.url)
            base_origin = f"{parsed_url.scheme.replace('ws', 'http')}://{parsed_url.netloc}"
            headers["Origin"] = base_origin
        except Exception as e:
            logger.warning(f"Could not parse URL for Origin header: {e}")
        
        # Add User-Agent header
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        return headers
