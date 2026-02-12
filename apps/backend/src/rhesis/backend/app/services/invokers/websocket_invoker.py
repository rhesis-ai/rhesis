import json
import time
import unicodedata
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.logging import logger

from .base import BaseEndpointInvoker
from .common.schemas import ErrorResponse


class WebSocketEndpointInvoker(BaseEndpointInvoker):
    """WebSocket endpoint invoker with support for different auth types."""

    # WebSocket endpoints do not automatically generate traces
    automatic_tracing: bool = False

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
        normalized = unicodedata.normalize("NFKC", text)

        # Handle specific common Unicode characters that AI services often use
        unicode_replacements = {
            # Quotation marks
            "\u2018": "'",  # Left single quotation mark
            "\u2019": "'",  # Right single quotation mark
            "\u201a": "'",  # Single low-9 quotation mark
            "\u201b": "'",  # Single high-reversed-9 quotation mark
            "\u201c": '"',  # Left double quotation mark
            "\u201d": '"',  # Right double quotation mark
            "\u201e": '"',  # Double low-9 quotation mark
            "\u201f": '"',  # Double high-reversed-9 quotation mark
            # Dashes
            "\u2010": "-",  # Hyphen
            "\u2011": "-",  # Non-breaking hyphen
            "\u2012": "-",  # Figure dash
            "\u2013": "-",  # En dash
            "\u2014": "-",  # Em dash
            "\u2015": "-",  # Horizontal bar
            # Spaces
            "\u00a0": " ",  # Non-breaking space
            "\u2000": " ",  # En quad
            "\u2001": " ",  # Em quad
            "\u2002": " ",  # En space
            "\u2003": " ",  # Em space
            "\u2004": " ",  # Three-per-em space
            "\u2005": " ",  # Four-per-em space
            "\u2006": " ",  # Six-per-em space
            "\u2007": " ",  # Figure space
            "\u2008": " ",  # Punctuation space
            "\u2009": " ",  # Thin space
            "\u200a": " ",  # Hair space
            "\u202f": " ",  # Narrow no-break space
            "\u205f": " ",  # Medium mathematical space
            # Other common symbols
            "\u2026": "...",  # Horizontal ellipsis
            "\u2022": "*",  # Bullet
            "\u2023": "*",  # Triangular bullet
            "\u2024": ".",  # One dot leader
            "\u2025": "..",  # Two dot leader
            "\u2032": "'",  # Prime
            "\u2033": '"',  # Double prime
        }

        # Apply the replacements
        for unicode_char, replacement in unicode_replacements.items():
            normalized = normalized.replace(unicode_char, replacement)

        return normalized

    async def invoke(
        self,
        db: Session,
        endpoint: Endpoint,
        input_data: Dict[str, Any],
        test_execution_context: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """
        Invoke the WebSocket endpoint with proper authentication.

        Args:
            db: Database session
            endpoint: The endpoint to invoke
            input_data: Input data
            test_execution_context: Optional test context (not used by WebSocket invoker,
                                   handled by executor's manual tracing wrapper)
        """
        start_time = time.time()

        try:
            logger.info("=== Starting WebSocket invocation ===")
            logger.info(f"Endpoint: {endpoint.name} (ID: {endpoint.id})")
            logger.info(f"URL: {endpoint.url}")
            logger.info(f"Auth Type: {endpoint.auth_type}")
            logger.info(f"Input data keys: {list(input_data.keys())}")
            logger.debug(f"Full input data: {json.dumps(input_data, indent=2, default=str)}")

            # Run the async WebSocket communication
            result = await self._async_invoke(db, endpoint, input_data)

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
                request_details=self._safe_request_details(locals(), "WebSocket"),
            )

    async def _async_invoke(
        self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
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
                logger.debug(
                    f"Auth token obtained successfully in {auth_duration:.2f}s "
                    f"(length: {len(auth_token)} chars)"
                )
            else:
                logger.warning(f"No auth token obtained after {auth_duration:.2f}s")

            # Prepare the WebSocket message using the request body template
            logger.debug("Rendering request body template...")
            template_start_time = time.time()

            # Prepare template context with conversation tracking
            template_context, conversation_field = self._prepare_conversation_context(
                endpoint, input_data, auth_token=auth_token
            )

            logger.debug(f"Template context keys: {list(template_context.keys())}")

            message_data = self.template_renderer.render(
                endpoint.request_mapping or {}, template_context
            )

            # Strip reserved meta keys (e.g. system_prompt) from the wire body
            self._strip_meta_keys(message_data)

            template_duration = time.time() - template_start_time
            logger.debug(f"Template rendered in {template_duration:.2f}s")
            message_keys = (
                list(message_data.keys()) if isinstance(message_data, dict) else "Not a dict"
            )
            logger.debug(f"Rendered message data keys: {message_keys}")
            logger.debug(
                f"Rendered message data: {json.dumps(message_data, indent=2, default=str)}"
            )

            # Extract conversation ID from rendered message
            conversation_id = self._extract_conversation_id(
                message_data, input_data, conversation_field
            )

            # Build WebSocket URI
            logger.debug("Building WebSocket URI...")
            uri = self._build_websocket_uri(endpoint)
            logger.info(f"WebSocket URI: {uri}")

            # Prepare headers for WebSocket connection
            logger.debug("Preparing WebSocket headers...")
            additional_headers = self._prepare_additional_headers_with_auth(
                endpoint, auth_token, input_data
            )
            sanitized_headers = json.dumps(self._sanitize_headers(additional_headers), indent=2)
            logger.debug(f"Additional headers: {sanitized_headers}")

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
                    message_size = len(message_json.encode("utf-8"))
                    logger.debug(f"Message size: {message_size} bytes")
                    logger.debug(f"Message to send: {message_json}")

                    send_start_time = time.time()
                    await websocket.send(message_json)
                    send_duration = time.time() - send_start_time
                    logger.info(f"Message sent successfully in {send_duration:.2f}s")

                    # Collect all responses
                    logger.debug("Starting to collect WebSocket responses...")
                    responses = []
                    extracted_conversation_id = None  # ID extracted from response
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
                            logger.debug(
                                f"First response received in {time_to_first_response:.2f}s"
                            )

                        last_message_time = current_time

                        logger.debug(
                            f"Received message #{message_count} (length: {len(message)} chars)"
                        )

                        # Try to parse as JSON first
                        try:
                            response_data = json.loads(message)
                            response_json = json.dumps(response_data, indent=2, default=str)
                            logger.debug(
                                f"Message #{message_count} parsed as JSON: {response_json}"
                            )

                            # If we have buffered streaming text, add it as a response
                            # before processing JSON
                            if streaming_text_buffer.strip():
                                # Normalize Unicode characters to ASCII equivalents
                                normalized_text = self._normalize_unicode_text(
                                    streaming_text_buffer
                                )
                                buffer_response = {"content": normalized_text}
                                responses.append(buffer_response)
                                logger.debug(
                                    f"Added buffered streaming text "
                                    f"({len(normalized_text)} chars) as response"
                                )
                                streaming_text_buffer = ""  # Reset buffer

                            responses.append(response_data)

                            # Handle string responses (like error messages)
                            if isinstance(response_data, str):
                                error_message = response_data
                                logger.warning(
                                    f"Received string response in message #{message_count}: "
                                    f"{error_message}"
                                )
                                # Don't break, continue collecting responses
                                continue

                            # Extract conversation tracking field if present and configured
                            if conversation_field and conversation_field in response_data:
                                extracted_conversation_id = response_data[conversation_field]
                                logger.debug(
                                    f"Extracted {conversation_field} from response: "
                                    f"{extracted_conversation_id}"
                                )

                            # Check for error
                            if "error" in response_data:
                                error_message = response_data["error"]
                                logger.warning(
                                    f"Error in response #{message_count}: {error_message}"
                                )

                            # Check if this is the end message
                            if response_data.get("message") == "response ended":
                                logger.info(f"Response stream ended at message #{message_count}")
                                break

                        except json.JSONDecodeError:
                            # This is a streaming text chunk, add it to buffer
                            streaming_text_buffer += message
                            buffer_size = len(streaming_text_buffer)
                            logger.debug(
                                f"Message #{message_count} added to streaming buffer "
                                f"(buffer size now: {buffer_size} chars)"
                            )
                            preview_suffix = "..." if len(message) > 100 else ""
                            logger.debug(
                                f"Streaming chunk preview: {message[:100]}{preview_suffix}"
                            )

                    # Add any remaining buffered streaming text
                    if streaming_text_buffer.strip():
                        # Normalize Unicode characters to ASCII equivalents
                        normalized_text = self._normalize_unicode_text(streaming_text_buffer)
                        final_buffer_response = {"content": normalized_text}
                        responses.append(final_buffer_response)
                        logger.debug(
                            f"Added final buffered streaming text "
                            f"({len(normalized_text)} chars) as response"
                        )

                    total_response_time = (
                        last_message_time - send_start_time if last_message_time else 0
                    )
                    logger.info(
                        f"Received {message_count} messages total in {total_response_time:.2f}s"
                    )
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
                            logger.debug(
                                f"Response #{i + 1} added {len(content_chunk)} chars "
                                f"to main content"
                            )

                    logger.info(
                        f"Extracted main content from {content_responses} responses "
                        f"(total length: {len(main_content)} chars)"
                    )
                    if main_content:
                        preview_suffix = "..." if len(main_content) > 200 else ""
                        logger.debug(f"Main content preview: {main_content[:200]}{preview_suffix}")

                    # Prepare the final response - merge all response data
                    logger.debug("Preparing final response...")
                    final_response = {
                        "output": main_content if main_content else None,
                        "error": error_message,
                        "status": "completed" if not error_message else "error",
                    }

                    # Add conversation tracking field if configured
                    if conversation_field:
                        # Use extracted value from response, or fall back to input value
                        final_conversation_id = extracted_conversation_id or conversation_id
                        if final_conversation_id:
                            final_response[conversation_field] = final_conversation_id
                            logger.debug(
                                f"Added {conversation_field} to response: {final_conversation_id}"
                            )
                        else:
                            logger.debug(f"No {conversation_field} available for response")

                    # Merge all structured response data (excluding special control messages)
                    for response in responses:
                        if isinstance(response, dict):
                            # Skip control messages like "response ended"
                            if response.get("message") == "response ended":
                                continue
                            # Skip string responses (already captured as error)
                            if isinstance(response, str):
                                continue
                            # Merge all other response data
                            for key, value in response.items():
                                # Don't override already set fields
                                if key not in final_response or final_response[key] is None:
                                    final_response[key] = value

                    final_response_json = json.dumps(final_response, indent=2, default=str)
                    logger.debug(f"Final response before mapping: {final_response_json}")

                    # Map response using configured mappings
                    logger.debug("Applying response mappings...")
                    mapping_start_time = time.time()

                    response_mapping = endpoint.response_mapping or {}
                    logger.debug(
                        f"Response mapping: {json.dumps(response_mapping, indent=2, default=str)}"
                    )

                    mapped_response = self.response_mapper.map_response(
                        final_response, response_mapping
                    )
                    mapping_duration = time.time() - mapping_start_time

                    logger.debug(f"Response mapping completed in {mapping_duration:.2f}s")

                    # Preserve all fields from final_response that aren't in mapped_response
                    # or where mapped value is None but original had a value
                    for field, value in final_response.items():
                        if field not in mapped_response:
                            # Field wasn't mapped, preserve original value
                            mapped_response[field] = value
                            logger.debug(f"Preserved unmapped field '{field}': {value}")
                        elif mapped_response[field] is None and value is not None:
                            # Mapping returned None but we have a valid original value
                            mapped_response[field] = value
                            logger.debug(
                                f"Restored field '{field}' from None to original value: {value}"
                            )

                    return mapped_response

            except InvalidStatus as status_err:
                connection_duration = (
                    time.time() - connection_start_time if connection_start_time else 0
                )
                logger.error(f"WebSocket connection rejected after {connection_duration:.2f}s")
                logger.error(f"Status code: {status_err.response.status_code}")
                response_headers_str = (
                    dict(status_err.response.headers) if status_err.response.headers else "None"
                )
                logger.error(f"Response headers: {response_headers_str}")
                logger.error(f"Response body: {status_err.response.body}")
                logger.debug(f"Connection URI: {uri}")
                sanitized_conn_headers = json.dumps(
                    self._sanitize_headers(additional_headers), indent=2
                )
                logger.debug(f"Connection headers: {sanitized_conn_headers}")

                error_output = (
                    f"WebSocket connection rejected: HTTP {status_err.response.status_code}"
                )
                if status_err.response.body:
                    error_output += f". Response: {status_err.response.body}"

                return self._create_error_response(
                    error_type="websocket_connection_error",
                    output_message=error_output,
                    message=(
                        f"WebSocket connection rejected: HTTP {status_err.response.status_code}"
                    ),
                    request_details={
                        "connection_type": "WebSocket",
                        "uri": uri,
                        "headers": additional_headers,
                        "body": message_data,
                    },
                    status_code=status_err.response.status_code,
                    response_headers=dict(status_err.response.headers)
                    if status_err.response.headers
                    else {},
                    response_body=status_err.response.body,
                )

            except Exception as e:
                # Enhanced error logging for WebSocket failures
                connection_duration = (
                    time.time() - connection_start_time if connection_start_time else 0
                )
                error_type = type(e).__name__
                logger.error(f"WebSocket communication error after {connection_duration:.2f}s")
                logger.error(f"Error type: {error_type}")
                logger.error(f"Error message: {str(e)}")
                logger.debug(f"Connection URI: {uri}")
                sanitized_comm_headers = json.dumps(
                    self._sanitize_headers(additional_headers), indent=2
                )
                logger.debug(f"Connection headers: {sanitized_comm_headers}")
                message_data_json = json.dumps(message_data, indent=2, default=str)
                logger.debug(f"Message data: {message_data_json}")

                # Try to get more details about the websocket error
                if hasattr(e, "response"):
                    logger.error(f"WebSocket response: {e.response}")
                if hasattr(e, "code"):
                    logger.error(f"WebSocket error code: {e.code}")
                if hasattr(e, "reason"):
                    logger.error(f"WebSocket error reason: {e.reason}")

                # Log the full traceback for debugging
                logger.error("Full error traceback:", exc_info=True)

                return self._create_error_response(
                    error_type="websocket_communication_error",
                    output_message=f"WebSocket communication failed: {str(e)}",
                    message=f"WebSocket communication failed: {str(e)}",
                    request_details={
                        "connection_type": "WebSocket",
                        "uri": uri,
                        "headers": additional_headers,
                        "body": message_data,
                    },
                )

        except Exception as e:
            logger.error(f"Async invoke error: {type(e).__name__}: {str(e)}", exc_info=True)
            logger.debug(
                f"Error context - URI: {uri}, Headers: {additional_headers}, "
                f"Message: {message_data}"
            )

            return self._create_error_response(
                error_type="websocket_error",
                output_message=f"WebSocket error: {str(e)}",
                message=f"WebSocket error: {str(e)}",
                request_details={
                    "connection_type": "WebSocket",
                    "uri": uri or "unknown",
                    "headers": additional_headers or {},
                    "body": message_data,
                },
            )

    def _build_websocket_uri(self, endpoint: Endpoint) -> str:
        """Build the complete WebSocket URI."""
        logger.debug(f"Building WebSocket URI from base URL: {endpoint.url}")
        logger.debug(f"Endpoint path: {endpoint.endpoint_path}")

        uri = endpoint.url
        if endpoint.endpoint_path:
            # Handle WebSocket URL construction - avoid duplicating path if already present
            if endpoint.endpoint_path.startswith("/"):
                path_to_check = endpoint.endpoint_path
            else:
                path_to_check = "/" + endpoint.endpoint_path

            logger.debug(f"Path to check: {path_to_check}")

            # Check if the URL already contains the endpoint path
            if not endpoint.url.endswith(path_to_check):
                if endpoint.url.endswith("/"):
                    uri = endpoint.url.rstrip("/") + path_to_check
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
        """Prepare additional headers for WebSocket connection.

        Excludes standard WebSocket headers.
        """
        logger.debug("Preparing additional headers...")
        headers = {}

        # Use configured headers if available, but exclude standard WebSocket headers
        # as they are handled automatically by the websockets library
        if endpoint.request_headers:
            sanitized_req_headers = json.dumps(
                self._sanitize_headers(endpoint.request_headers), indent=2
            )
            logger.debug(f"Configured headers: {sanitized_req_headers}")
            standard_ws_headers = {
                "Upgrade",
                "Connection",
                "Sec-WebSocket-Version",
                "Sec-WebSocket-Key",
            }

            for key, value in endpoint.request_headers.items():
                if key not in standard_ws_headers:
                    headers[key] = value
                    # Only log header key, not value for security
                    logger.debug(f"Added header: {key}")
                else:
                    logger.debug(f"Skipped standard WebSocket header: {key}")
        else:
            logger.debug("No configured headers found")

        return headers

    def _prepare_additional_headers_with_auth(
        self, endpoint: Endpoint, auth_token: Optional[str], input_data: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """Prepare additional headers for WebSocket connection.

        Excludes Authorization header for WebSocket handshake.
        """
        logger.debug("Preparing additional headers with auth...")
        headers = self._prepare_additional_headers(endpoint)

        # For WebSocket connections, don't add Authorization header during handshake
        # The auth_token will be sent in the message body instead
        logger.debug(
            "Skipping Authorization header for WebSocket handshake (will be sent in message body)"
        )

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
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        headers["User-Agent"] = user_agent
        logger.debug(f"Added User-Agent header: {user_agent}")

        # Inject context headers using shared base method
        self._inject_context_headers(headers, input_data)

        logger.debug(
            f"Final headers with auth: {json.dumps(self._sanitize_headers(headers), indent=2)}"
        )
        return headers
