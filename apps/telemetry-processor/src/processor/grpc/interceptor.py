"""
gRPC Interceptor for API Key Authentication

Validates incoming requests have the correct x-api-key header.
Reads TELEMETRY_API_KEY from environment variable for validation.
"""

import logging
import os
from typing import Any, Callable

import grpc

logger = logging.getLogger(__name__)


class APIKeyInterceptor(grpc.ServerInterceptor):
    """
    Intercepts all gRPC requests to validate API key.

    Checks for x-api-key header and compares with TELEMETRY_API_KEY env var.
    Rejects requests with invalid or missing API keys.
    """

    def __init__(self):
        """Initialize the interceptor with API key from environment."""
        self.api_key = os.getenv("TELEMETRY_API_KEY")
        if not self.api_key:
            logger.error(
                "🚨 CRITICAL: TELEMETRY_API_KEY not set! All requests will be rejected. "
                "Set TELEMETRY_API_KEY environment variable to enable authentication."
            )
        else:
            logger.info("✅ API Key authentication enabled")

    def intercept_service(
        self,
        continuation: Callable,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Any:
        """
        Intercept and validate incoming requests.

        Args:
            continuation: Function to call next interceptor or handler
            handler_call_details: Details about the RPC call

        Returns:
            RPC handler or terminates request if unauthorized
        """
        try:
            # Extract metadata (headers)
            metadata = dict(handler_call_details.invocation_metadata)

            # Get the x-api-key from headers (gRPC converts to lowercase)
            provided_key = metadata.get("x-api-key", "")

            # Validate API key (reject if not configured or doesn't match)
            if not self.api_key or provided_key != self.api_key:
                reason = (
                    "TELEMETRY_API_KEY not configured" if not self.api_key else "Invalid API key"
                )
                logger.warning(
                    f"🚫 Unauthorized request attempt from "
                    f"{metadata.get('user-agent', 'unknown')} - {reason}"
                )

                # Get the actual handler first
                handler = continuation(handler_call_details)

                # Check if handler exists
                if handler is None:
                    logger.error("Handler is None - unable to create terminating handler")
                    return None

                # Return a terminating handler that aborts with UNAUTHENTICATED
                def abort_unauthenticated(request, context: grpc.ServicerContext):
                    context.abort(
                        grpc.StatusCode.UNAUTHENTICATED,
                        "Invalid or missing x-api-key header",
                    )

                # Wrap the handler to abort on any call
                return grpc.unary_unary_rpc_method_handler(
                    abort_unauthenticated,
                    request_deserializer=handler.request_deserializer,
                    response_serializer=handler.response_serializer,
                )

            # API key is valid - continue with the request
            logger.debug("✅ Request authenticated successfully")
            return continuation(handler_call_details)

        except Exception as e:
            logger.error(f"Error in API key interceptor: {e}", exc_info=True)
            # On error, deny access by default (fail-secure)
            handler = continuation(handler_call_details)

            if handler is None:
                return None

            def abort_error(request, context: grpc.ServicerContext):
                context.abort(
                    grpc.StatusCode.INTERNAL,
                    "Authentication error occurred",
                )

            return grpc.unary_unary_rpc_method_handler(
                abort_error,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
