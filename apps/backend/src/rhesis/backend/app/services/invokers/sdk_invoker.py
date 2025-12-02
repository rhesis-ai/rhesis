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

    def _validate_and_extract_metadata(self, endpoint: Endpoint) -> tuple[str, str, str]:
        """
        Validate endpoint and extract SDK metadata.

        Args:
            endpoint: The SDK endpoint

        Returns:
            Tuple of (function_name, project_id, environment)

        Raises:
            HTTPException: If metadata is missing or invalid
        """
        if not endpoint.endpoint_metadata:
            raise HTTPException(
                status_code=500,
                detail="SDK endpoint missing metadata (function_name, project_id, environment)",
            )

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

        return function_name, str(project_id), environment

    def _determine_invocation_context(self, project_id: str, environment: str) -> tuple[bool, str]:
        """
        Determine whether to use RPC or direct WebSocket.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Tuple of (use_rpc, context_type_description)
        """
        is_worker = os.getenv("CELERY_WORKER_NAME") is not None

        from rhesis.backend.app.services.connector.manager import connection_manager

        connection_key = connection_manager.get_connection_key(project_id, environment)
        has_local_connection = connection_key in connection_manager._connections

        # Determine invocation method:
        # - Workers: always use RPC (they never have WebSocket connections)
        # - Backend with local connection: use direct WebSocket
        # - Backend without local connection: use RPC (connection on another instance)
        use_rpc = is_worker or not has_local_connection

        if is_worker:
            context_type = "WORKER (RPC via Redis)"
        elif has_local_connection:
            context_type = "BACKEND (direct WebSocket connection)"
        else:
            context_type = "BACKEND (RPC via Redis - connection on another instance)"

        return use_rpc, context_type

    def _prepare_function_kwargs(
        self, endpoint: Endpoint, input_data: Dict[str, Any], function_name: str
    ) -> Dict[str, Any]:
        """
        Prepare function kwargs from input data using request mapping.

        Args:
            endpoint: The SDK endpoint
            input_data: Raw input data
            function_name: Name of the function (for logging)

        Returns:
            Transformed function kwargs ready to send to SDK
        """
        # Prepare conversation context
        template_context, _ = self._prepare_conversation_context(endpoint, input_data)

        # Filter out system fields
        system_fields = {"organization_id", "user_id"}
        filtered_context = {k: v for k, v in template_context.items() if k not in system_fields}

        # Transform using request_mapping
        request_mapping = endpoint.request_mapping or {}

        if not request_mapping:
            logger.warning(f"No request_mapping configured for {function_name}, using passthrough")
            return filtered_context

        return self.template_renderer.render(request_mapping, filtered_context)

    async def _execute_via_rpc(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        function_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute SDK function via RPC (Redis pub/sub).

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Unique test run ID
            function_name: Function to invoke
            function_kwargs: Function arguments

        Returns:
            Result dictionary from SDK

        Raises:
            Returns ErrorResponse via _create_error_response if RPC unavailable or not connected
        """
        from rhesis.backend.app.services.connector.rpc_client import SDKRpcClient

        try:
            rpc_client = SDKRpcClient()
            await rpc_client.initialize()
            logger.info("✅ RPC client initialized successfully")
        except RuntimeError as e:
            logger.error(f"❌ Failed to initialize RPC client: {e}")
            return self._create_error_response(
                error_type="sdk_rpc_unavailable",
                output_message=(
                    "Cannot invoke SDK: Redis not configured for multi-instance deployment"
                ),
                message=str(e),
                request_details=self._safe_request_details(locals(), "SDK"),
            )

        try:
            # Check connection via RPC client
            is_connected = await rpc_client.is_connected(project_id, environment)

            if not is_connected:
                logger.warning(f"SDK not connected: {project_id}:{environment}")
                return self._create_error_response(
                    error_type="sdk_not_connected",
                    output_message=f"SDK not connected: {project_id} in {environment}",
                    message="SDK client is not currently connected",
                    request_details=self._safe_request_details(locals(), "SDK"),
                )

            # Send request via RPC
            return await rpc_client.send_and_await_result(
                project_id=project_id,
                environment=environment,
                test_run_id=test_run_id,
                function_name=function_name,
                inputs=function_kwargs,
                timeout=30.0,
            )
        finally:
            await rpc_client.close()

    async def _execute_via_websocket(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        function_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute SDK function via direct WebSocket connection.

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Unique test run ID
            function_name: Function to invoke
            function_kwargs: Function arguments

        Returns:
            Result dictionary from SDK
        """
        from rhesis.backend.app.services.connector.manager import connection_manager

        return await connection_manager.send_and_await_result(
            project_id=project_id,
            environment=environment,
            test_run_id=test_run_id,
            function_name=function_name,
            inputs=function_kwargs,
            timeout=30.0,
        )

    def _check_result_errors(
        self, result: Dict[str, Any], function_name: str
    ) -> Union[ErrorResponse, None]:
        """
        Check result for errors and return ErrorResponse if found.

        Args:
            result: Result dictionary from SDK execution
            function_name: Name of the function (for logging)

        Returns:
            ErrorResponse if error found, None otherwise
        """
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

        return None

    def _map_sdk_response(
        self, result: Dict[str, Any], endpoint: Endpoint, function_name: str
    ) -> Dict[str, Any]:
        """
        Map SDK output to standardized response format.

        Args:
            result: Raw result from SDK
            endpoint: The SDK endpoint
            function_name: Name of the function (for logging)

        Returns:
            Mapped response dictionary
        """
        raw_output = result.get("output", {})
        logger.debug(f"Raw SDK output: {raw_output}")

        response_mapping = endpoint.response_mapping or {}

        if not response_mapping:
            logger.warning(f"No response_mapping configured for {function_name}, using raw output")
            return {"output": raw_output}

        return self.response_mapper.map_response(raw_output, response_mapping)

    def _extract_conversation_id(
        self, mapped_response: Dict[str, Any], conversation_field: str
    ) -> None:
        """
        Extract and log conversation ID if present.

        Args:
            mapped_response: Mapped response dictionary
            conversation_field: Field name containing conversation ID
        """
        if conversation_field and conversation_field in mapped_response:
            conversation_id = mapped_response[conversation_field]
            logger.info(f"Extracted {conversation_field}: {conversation_id}")

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
            # Step 1: Validate and extract metadata
            function_name, project_id, environment = self._validate_and_extract_metadata(endpoint)

            # Step 2: Determine invocation context (RPC vs direct WebSocket)
            use_rpc, context_type = self._determine_invocation_context(project_id, environment)
            logger.info(f"SDK invocation context: {context_type}")

            # Step 3: Prepare function kwargs
            _, conversation_field = self._prepare_conversation_context(endpoint, input_data)
            function_kwargs = self._prepare_function_kwargs(endpoint, input_data, function_name)

            logger.info(
                f"Invoking SDK function: {function_name} "
                f"(project: {project_id}, env: {environment}, use_rpc: {use_rpc})"
            )
            logger.debug(f"Function kwargs: {function_kwargs}")

            # Step 4: Execute via RPC or direct WebSocket
            test_run_id = f"invoke_{uuid.uuid4().hex[:12]}"

            if use_rpc:
                result = await self._execute_via_rpc(
                    project_id, environment, test_run_id, function_name, function_kwargs
                )
            else:
                result = await self._execute_via_websocket(
                    project_id, environment, test_run_id, function_name, function_kwargs
                )

            # Step 5: Check for execution errors
            error_response = self._check_result_errors(result, function_name)
            if error_response:
                return error_response

            # Step 6: Map SDK response to standardized format
            mapped_response = self._map_sdk_response(result, endpoint, function_name)

            # Step 7: Extract conversation ID if present
            self._extract_conversation_id(mapped_response, conversation_field)

            logger.info(
                f"SDK function {function_name} completed successfully "
                f"in {result.get('duration_ms', 0)}ms"
            )

            return mapped_response

        except HTTPException:
            # Re-raise HTTPExceptions (configuration errors)
            raise
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for SDK function")
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
