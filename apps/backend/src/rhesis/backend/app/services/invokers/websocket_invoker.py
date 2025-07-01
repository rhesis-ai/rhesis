import asyncio
import json
import logging
import unicodedata
import time
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
        start_time = time.time()
        
        try:
            logger.info(f"=== Starting WebSocket invocation ===")
            logger.info(f"Endpoint: {endpoint.name} (ID: {endpoint.id})")
            logger.info(f"URL: {endpoint.url}")
            logger.info(f"Auth Type: {endpoint.auth_type}")
            logger.info(f"Input data keys: {list(input_data.keys())}")
            logger.debug(f"Full input data: {json.dumps(input_data, indent=2, default=str)}")
            
            # Run the async WebSocket communication in a sync context
            result = asyncio.run(self._async_invoke(db, endpoint, input_data))
            
            duration = time.time() - start_time
            logger.info(f"=== WebSocket invocation completed in {duration:.2f}s ===")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"=== WebSocket invocation failed after {duration:.2f}s ===")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}", exc_info=True)
            
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
        connection_start_time = None
        
        try:
            # Get authentication token
            logger.debug("Getting authentication token...")
            auth_start_time = time.time()
            auth_token = self._get_valid_token(db, endpoint)
            auth_duration = time.time() - auth_start_time
            
            if auth_token:
                logger.debug(f"Auth token obtained in {auth_duration:.2f}s (length: {len(auth_token)} chars)")
                # Log first and last few characters for debugging without exposing full token
                if len(auth_token) > 10:
                    logger.debug(f"Auth token preview: {auth_token[:5]}...{auth_token[-5:]}")
            else:
                logger.warning(f"No auth token obtained after {auth_duration:.2f}s")
            
            # Prepare the WebSocket message using the request body template
            logger.debug("Rendering request body template...")
            template_start_time = time.time()
            
            template_context = {**input_data, "auth_token": auth_token}
            logger.debug(f"Template context keys: {list(template_context.keys())}")
            
            message_data = self.template_renderer.render(
                endpoint.request_body_template or {}, 
                template_context
            )
            
            template_duration = time.time() - template_start_time
            logger.debug(f"Template rendered in {template_duration:.2f}s")
            logger.debug(f"Rendered message data keys: {list(message_data.keys()) if isinstance(message_data, dict) else 'Not a dict'}")
            logger.debug(f"Rendered message data: {json.dumps(message_data, indent=2, default=str)}")
            
            # Generate session_id if not provided
            if "session_id" not in message_data:
                session_id = str(uuid.uuid4())
                message_data["session_id"] = session_id
                logger.debug(f"Generated session_id: {session_id}")

            # Build WebSocket URI
            logger.debug("Building WebSocket URI...")
            uri = self._build_websocket_uri(endpoint)
            logger.info(f"WebSocket URI: {uri}")

            # Prepare headers for WebSocket connection
            logger.debug("Preparing WebSocket headers...")
            additional_headers = self._prepare_additional_headers_with_auth(endpoint, auth_token)
            logger.debug(f"Additional headers: {json.dumps(additional_headers, indent=2)}")
            
            try:
                # Use the new websockets.asyncio.client.connect API
                logger.info(f"Attempting WebSocket connection to: {uri}")
                connection_start_time = time.time()
                
                async with connect(uri, additional_headers=additional_headers) as websocket:
                    connection_duration = time.time() - connection_start_time
                    logger.info(f"WebSocket connection established in {connection_duration:.2f}s")
                    logger.debug(f"WebSocket state: {websocket.state}")
                    
                    # Send the message
                    logger.debug("Preparing to send WebSocket message...")
                    message_json = json.dumps(message_data)
                    message_size = len(message_json.encode('utf-8'))
                    logger.debug(f"Message size: {message_size} bytes")
                    logger.debug(f"Message to send: {message_json}")
                    
                    send_start_time = time.time()
                    await websocket.send(message_json)
                    send_duration = time.time() - send_start_time
                    logger.info(f"Message sent successfully in {send_duration:.2f}s")
                    
                    # Collect all responses
                    logger.debug("Starting to collect WebSocket responses...")
                    responses = []
                    conversation_id = None
                    error_message = None
                    message_count = 0
                    streaming_text_buffer = ""  # Buffer for accumulating streaming text chunks
                    first_message_time = None
                    last_message_time = None
                    
                    async for message in websocket:
                        message_count += 1
                        current_time = time.time()
                        
                        if first_message_time is None:
                            first_message_time = current_time
                            time_to_first_response = current_time - send_start_time
                            logger.debug(f"First response received in {time_to_first_response:.2f}s")
                        
                        last_message_time = current_time
                        
                        logger.debug(f"Received message #{message_count} (length: {len(message)} chars)")
                        
                        # Try to parse as JSON first
                        try:
                            response_data = json.loads(message)
                            logger.debug(f"Message #{message_count} parsed as JSON: {json.dumps(response_data, indent=2, default=str)}")
                            
                            # If we have buffered streaming text, add it as a response before processing JSON
                            if streaming_text_buffer.strip():
                                # Normalize Unicode characters to ASCII equivalents
                                normalized_text = self._normalize_unicode_text(streaming_text_buffer)
                                buffer_response = {"content": normalized_text}
                                responses.append(buffer_response)
                                logger.debug(f"Added buffered streaming text ({len(normalized_text)} chars) as response")
                                streaming_text_buffer = ""  # Reset buffer
                            
                            responses.append(response_data)
                            
                            # Extract conversation_id if present
                            if "conversation_id" in response_data:
                                conversation_id = response_data["conversation_id"]
                                logger.debug(f"Extracted conversation_id: {conversation_id}")
                            
                            # Check for error
                            if "error" in response_data:
                                error_message = response_data["error"]
                                logger.warning(f"Error in response #{message_count}: {error_message}")
                            
                            # Check if this is the end message
                            if response_data.get("message") == "response ended":
                                logger.info(f"Response stream ended at message #{message_count}")
                                break
                                
                        except json.JSONDecodeError:
                            # This is a streaming text chunk, add it to buffer
                            streaming_text_buffer += message
                            logger.debug(f"Message #{message_count} added to streaming buffer (buffer size now: {len(streaming_text_buffer)} chars)")
                            logger.debug(f"Streaming chunk preview: {message[:100]}{'...' if len(message) > 100 else ''}")
                    
                    # Add any remaining buffered streaming text
                    if streaming_text_buffer.strip():
                        # Normalize Unicode characters to ASCII equivalents
                        normalized_text = self._normalize_unicode_text(streaming_text_buffer)
                        final_buffer_response = {"content": normalized_text}
                        responses.append(final_buffer_response)
                        logger.debug(f"Added final buffered streaming text ({len(normalized_text)} chars) as response")
                    
                    total_response_time = last_message_time - send_start_time if last_message_time else 0
                    logger.info(f"Received {message_count} messages total in {total_response_time:.2f}s")
                    logger.debug(f"Total responses collected: {len(responses)}")
                    
                    # Extract the main content from responses
                    logger.debug("Extracting main content from responses...")
                    main_content = ""
                    content_responses = 0
                    
                    for i, response in enumerate(responses):
                        if "content" in response:
                            content_responses += 1
                            content_chunk = response["content"]
                            main_content += content_chunk
                            logger.debug(f"Response #{i+1} added {len(content_chunk)} chars to main content")
                    
                    logger.info(f"Extracted main content from {content_responses} responses (total length: {len(main_content)} chars)")
                    if main_content:
                        logger.debug(f"Main content preview: {main_content[:200]}{'...' if len(main_content) > 200 else ''}")
                    
                    # Prepare the final response
                    logger.debug("Preparing final response...")
                    final_response = {
                        "output": main_content if main_content else None,
                        "conversation_id": conversation_id,
                        "error": error_message,
                        "status": "completed" if not error_message else "error"
                    }
                    
                    logger.debug(f"Final response before mapping: {json.dumps(final_response, indent=2, default=str)}")
                    
                    # Map response using configured mappings
                    logger.debug("Applying response mappings...")
                    mapping_start_time = time.time()
                    
                    response_mappings = endpoint.response_mappings or {}
                    logger.debug(f"Response mappings: {json.dumps(response_mappings, indent=2, default=str)}")
                    
                    mapped_response = self.response_mapper.map_response(final_response, response_mappings)
                    mapping_duration = time.time() - mapping_start_time
                    
                    logger.debug(f"Response mapping completed in {mapping_duration:.2f}s")
                    logger.debug(f"Final mapped response: {json.dumps(mapped_response, indent=2, default=str)}")
                    
                    return mapped_response
                    
            except InvalidStatusCode as status_err:
                connection_duration = time.time() - connection_start_time if connection_start_time else 0
                logger.error(f"WebSocket connection rejected after {connection_duration:.2f}s")
                logger.error(f"Status code: {status_err.status_code}")
                logger.error(f"Response headers: {dict(status_err.headers) if status_err.headers else 'None'}")
                logger.error(f"Response body: {status_err.body}")
                logger.debug(f"Connection URI: {uri}")
                logger.debug(f"Connection headers: {json.dumps(additional_headers, indent=2)}")
                
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
                connection_duration = time.time() - connection_start_time if connection_start_time else 0
                error_type = type(e).__name__
                logger.error(f"WebSocket communication error after {connection_duration:.2f}s")
                logger.error(f"Error type: {error_type}")
                logger.error(f"Error message: {str(e)}")
                logger.debug(f"Connection URI: {uri}")
                logger.debug(f"Connection headers: {json.dumps(additional_headers, indent=2)}")
                logger.debug(f"Message data: {json.dumps(message_data, indent=2, default=str)}")
                
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
            logger.error(f"Async invoke error: {type(e).__name__}: {str(e)}", exc_info=True)
            logger.debug(f"Error context - URI: {uri}, Headers: {additional_headers}, Message: {message_data}")
            
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
        logger.debug(f"Building WebSocket URI from base URL: {endpoint.url}")
        logger.debug(f"Endpoint path: {endpoint.endpoint_path}")
        
        uri = endpoint.url
        if endpoint.endpoint_path:
            # Handle WebSocket URL construction - avoid duplicating path if already present
            if endpoint.endpoint_path.startswith('/'):
                path_to_check = endpoint.endpoint_path
            else:
                path_to_check = '/' + endpoint.endpoint_path
            
            logger.debug(f"Path to check: {path_to_check}")
            
            # Check if the URL already contains the endpoint path
            if not endpoint.url.endswith(path_to_check):
                if endpoint.url.endswith('/'):
                    uri = endpoint.url.rstrip('/') + path_to_check
                else:
                    uri = endpoint.url + path_to_check
                logger.debug(f"Appended path to URI: {uri}")
            else:
                # URL already contains the path, use as-is
                uri = endpoint.url
                logger.debug(f"Path already present in URL, using as-is: {uri}")
        
        logger.debug(f"Final WebSocket URI: {uri}")
        return uri

    def _prepare_additional_headers(self, endpoint: Endpoint) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection (excluding standard WebSocket headers)."""
        logger.debug("Preparing additional headers...")
        headers = {}
        
        # Use configured headers if available, but exclude standard WebSocket headers
        # as they are handled automatically by the websockets library
        if endpoint.request_headers:
            logger.debug(f"Configured headers: {json.dumps(endpoint.request_headers, indent=2)}")
            standard_ws_headers = {"Upgrade", "Connection", "Sec-WebSocket-Version", "Sec-WebSocket-Key"}
            
            for key, value in endpoint.request_headers.items():
                if key not in standard_ws_headers:
                    headers[key] = value
                    logger.debug(f"Added header: {key} = {value}")
                else:
                    logger.debug(f"Skipped standard WebSocket header: {key}")
        else:
            logger.debug("No configured headers found")
        
        return headers

    def _prepare_additional_headers_with_auth(self, endpoint: Endpoint, auth_token: Optional[str]) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection, but exclude Authorization for WebSocket handshake."""
        logger.debug("Preparing additional headers with auth...")
        headers = self._prepare_additional_headers(endpoint)
        
        # For WebSocket connections, don't add Authorization header during handshake
        # The auth_token will be sent in the message body instead
        logger.debug("Skipping Authorization header for WebSocket handshake (will be sent in message body)")
        
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
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        headers["User-Agent"] = user_agent
        logger.debug(f"Added User-Agent header: {user_agent}")
        
        logger.debug(f"Final headers with auth: {json.dumps(headers, indent=2)}")
        return headers
