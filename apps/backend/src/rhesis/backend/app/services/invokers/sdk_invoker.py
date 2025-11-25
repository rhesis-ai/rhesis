"""SDK endpoint invoker for WebSocket-connected SDK functions."""

import asyncio
import os
import uuid
from typing import Any, Dict, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.logging import logger

from .base import BaseEndpointInvoker
from .common.schemas import ErrorResponse


class SdkEndpointInvoker(BaseEndpointInvoker):
    """Invoker for SDK-connected endpoints via WebSocket."""

    def __init__(self):
        """Initialize SDK invoker."""
        super().__init__()

    async def invoke(
        self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """
        Invoke SDK function through WebSocket connection.

        Args:
            db: Database session
            endpoint: The SDK endpoint to invoke
            input_data: Standardized input data (input, session_id, context, metadata, tool_calls)

        Returns:
            Standardized response dict with output and metadata, or ErrorResponse for errors
        """
        try:
            # Validate endpoint has required metadata
            if not endpoint.endpoint_metadata:
                raise HTTPException(
                    status_code=500,
                    detail="SDK endpoint missing metadata (function_name, project_id, environment)",
                )

            # Extract function name from nested sdk_connection metadata
            sdk_connection = endpoint.endpoint_metadata.get("sdk_connection", {})
            function_name = sdk_connection.get("function_name")
            project_id = endpoint.project_id
            environment = endpoint.environment

            if not all([function_name, project_id, environment]):
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"SDK endpoint incomplete: function_name={function_name}, "
                        f"project_id={project_id}, environment={environment}"
                    ),
                )

            # Detect if running in worker context
            is_worker = os.getenv("CELERY_WORKER_NAME") is not None
            context_type = "WORKER (will use RPC)" if is_worker else "BACKEND (direct connection)"
            logger.info(f"SDK invocation context: {context_type}")

            # Prepare conversation context (includes input_data + any extra context)
            template_context, conversation_field = self._prepare_conversation_context(
                endpoint, input_data
            )

            # Filter out system fields that shouldn't be passed to SDK functions
            # These are internal fields used by the backend but not part of the API contract
            system_fields = {"organization_id", "user_id"}
            filtered_template_context = {
                k: v for k, v in template_context.items() if k not in system_fields
            }

            # Transform ALL input fields to function kwargs using request_mapping
            # Note: filtered_template_context contains fields from input_data (minus system fields)
            # This allows custom fields to be mapped through request_mapping templates
            request_mapping = endpoint.request_mapping or {}

            if not request_mapping:
                # Fallback: pass through all fields as-is (excluding system fields)
                logger.warning(
                    f"No request_mapping configured for {function_name}, using passthrough"
                )
                function_kwargs = filtered_template_context
            else:
                # Render template with available fields from input_data (excluding system fields)
                # This ensures custom/additional fields can be mapped in the template
                function_kwargs = self.template_renderer.render(
                    request_mapping, filtered_template_context
                )

            logger.info(
                f"Invoking SDK function: {function_name} "
                f"(project: {project_id}, env: {environment}, worker: {is_worker})"
            )
            logger.debug(f"Function kwargs: {function_kwargs}")

            # Generate unique test run ID for this invocation
            test_run_id = f"invoke_{uuid.uuid4().hex[:12]}"

            # Choose invocation method based on context
            if is_worker:
                # Use RPC client for worker context
                from rhesis.backend.app.services.connector.rpc_client import SDKRpcClient

                try:
                    rpc_client = SDKRpcClient()
                    await rpc_client.initialize()
                except RuntimeError as e:
                    # Redis not available - fail with clear message
                    return self._create_error_response(
                        error_type="sdk_rpc_unavailable",
                        output_message="Cannot invoke SDK from worker: Redis not configured",
                        message=str(e),
                        request_details=self._safe_request_details(locals(), "SDK"),
                    )

                # Use try-finally to ensure RPC client is always closed
                try:
                    # Check connection via RPC client
                    if not await rpc_client.is_connected(str(project_id), environment):
                        return self._create_error_response(
                            error_type="sdk_not_connected",
                            output_message=f"SDK not connected: {project_id} in {environment}",
                            message="SDK client is not currently connected",
                            request_details=self._safe_request_details(locals(), "SDK"),
                        )

                    # Send request via RPC
                    result = await rpc_client.send_and_await_result(
                        project_id=str(project_id),
                        environment=environment,
                        test_run_id=test_run_id,
                        function_name=function_name,
                        inputs=function_kwargs,
                        timeout=30.0,
                    )
                finally:
                    # Always clean up RPC client, even on early returns
                    await rpc_client.close()

            else:
                # Direct access for backend context (no Redis needed)
                from rhesis.backend.app.services.connector.manager import connection_manager

                if not connection_manager.is_connected(str(project_id), environment):
                    return self._create_error_response(
                        error_type="sdk_not_connected",
                        output_message=f"SDK not connected: {project_id} in {environment}",
                        message="SDK client is not currently connected",
                        request_details=self._safe_request_details(locals(), "SDK"),
                    )

                # Send request directly
                result = await connection_manager.send_and_await_result(
                    project_id=str(project_id),
                    environment=environment,
                    test_run_id=test_run_id,
                    function_name=function_name,
                    inputs=function_kwargs,
                    timeout=30.0,
                )

            # Check if request failed to send
            if result.get("error") == "send_failed":
                return self._create_error_response(
                    error_type="sdk_send_failed",
                    output_message="Failed to send request to SDK",
                    message=result.get("details", "Unknown error"),
                    request_details=self._safe_request_details(locals(), "SDK"),
                )

            # Check if timeout occurred
            if result.get("error") == "timeout":
                return self._create_error_response(
                    error_type="sdk_timeout",
                    output_message="SDK function execution timed out",
                    message="Function did not respond within 30 seconds",
                    request_details=self._safe_request_details(locals(), "SDK"),
                )

            # Check if SDK function returned error
            if result.get("status") == "error":
                return self._create_error_response(
                    error_type="sdk_function_error",
                    output_message=f"SDK function error: {result.get('error', 'Unknown error')}",
                    message=result.get("error", "Function execution failed"),
                    request_details=self._safe_request_details(locals(), "SDK"),
                    duration_ms=result.get("duration_ms"),
                )

            # Extract raw output from SDK
            raw_output = result.get("output", {})
            logger.debug(f"Raw SDK output: {raw_output}")

            # Transform SDK output to standardized format using response_mapping
            response_mapping = endpoint.response_mapping or {}

            if not response_mapping:
                # Fallback: use raw output
                logger.warning(
                    f"No response_mapping configured for {function_name}, using raw output"
                )
                mapped_response = {"output": raw_output}
            else:
                # Map the response using response_mapper
                mapped_response = self.response_mapper.map_response(raw_output, response_mapping)

            # Extract conversation ID if configured
            if conversation_field and conversation_field in mapped_response:
                conversation_id = mapped_response[conversation_field]
                logger.info(f"Extracted {conversation_field}: {conversation_id}")

            logger.info(
                f"SDK function {function_name} completed successfully "
                f"in {result.get('duration_ms', 0)}ms"
            )

            return mapped_response

        except HTTPException:
            # Re-raise HTTPExceptions (configuration errors)
            raise
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for SDK function {function_name}")
            return self._create_error_response(
                error_type="sdk_timeout",
                output_message="SDK function execution timed out",
                message="Function did not respond in time",
                request_details=self._safe_request_details(locals(), "SDK"),
            )
        except Exception as e:
            logger.error(f"Unexpected error invoking SDK function: {e}", exc_info=True)
            return self._create_error_response(
                error_type="sdk_unexpected_error",
                output_message=f"Unexpected SDK error: {str(e)}",
                message=str(e),
                request_details=self._safe_request_details(locals(), "SDK"),
            )
