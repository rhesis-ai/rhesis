"""Connector manager for bidirectional communication."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from rhesis.sdk.connector.connection import WebSocketConnection
from rhesis.sdk.connector.executor import TestExecutor
from rhesis.sdk.connector.registry import FunctionRegistry
from rhesis.sdk.connector.schemas import (
    ExecuteTestMessage,
    RegisterMessage,
    TestResultMessage,
)
from rhesis.sdk.connector.types import MessageType
from rhesis.sdk.telemetry import Tracer

logger = logging.getLogger(__name__)


class ConnectorManager:
    """Manages WebSocket connection and function registry for remote endpoint testing."""

    def __init__(
        self,
        api_key: str,
        project_id: str,
        environment: str = "development",
        base_url: str = "ws://localhost:8080",
    ):
        """
        Initialize connector manager.

        Args:
            api_key: API key for authentication
            project_id: Project identifier
            environment: Environment name (default: "development")
            base_url: Base URL for WebSocket connection

        Raises:
            ValueError: If environment is not valid
        """
        # Validate and normalize environment
        valid_environments = ["production", "staging", "development", "local"]
        environment = environment.lower()  # Normalize to lowercase

        if environment not in valid_environments:
            raise ValueError(
                f"Invalid environment: '{environment}'. "
                f"Valid environments: {', '.join(valid_environments)}"
            )

        self.api_key = api_key
        self.project_id = project_id
        self.environment = environment
        self.base_url = base_url

        # Components
        self._registry = FunctionRegistry()
        self._executor = TestExecutor()
        self._tracer = Tracer(
            api_key=api_key,
            project_id=project_id,
            environment=environment,
            base_url=base_url,
        )

        # WebSocket connection
        self._connection: WebSocketConnection | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize WebSocket connection."""
        if self._initialized:
            logger.warning("Connector already initialized")
            return

        # Construct WebSocket URL
        ws_url = self._get_websocket_url()

        # Create connection
        self._connection = WebSocketConnection(
            url=ws_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Rhesis-Project": self.project_id,
                "X-Rhesis-Environment": self.environment,
            },
            on_message=self._handle_message,
            on_connect=self._handle_connect,
        )

        # Start connection in background (if event loop is available)
        self._start_connection_task()
        self._initialized = True
        logger.info(f"Connector initialized for project {self.project_id}")

    def _start_connection_task(self) -> None:
        """Start connection task if event loop is available."""
        if not self._connection:
            return

        try:
            # Try to get running event loop
            asyncio.get_running_loop()
            # If we get here, there's a running loop
            asyncio.create_task(self._connection.connect())
            logger.debug("Connection task created in running event loop")
        except RuntimeError:
            # No running event loop - defer connection
            logger.debug("No event loop available, deferring connection")

    def register_function(self, name: str, func: Callable, metadata: dict[str, Any]) -> None:
        """
        Register a function for remote triggering.

        Args:
            name: Function name
            func: Function callable
            metadata: Additional metadata
        """
        if not self._initialized:
            self.initialize()

        self._registry.register(name, func, metadata)

        # If connection is active, send updated registration
        if self._connection and self._connection.websocket:
            try:
                asyncio.create_task(self._send_registration())
            except RuntimeError:
                # No running event loop - registration will be sent on next connection
                logger.debug("No event loop available, will send registration on connection")

    async def _handle_connect(self) -> None:
        """Handle successful connection/reconnection - send registration."""
        try:
            await asyncio.sleep(0.5)  # Brief delay to ensure connection is stable
            await self._send_registration()
        except Exception as e:
            logger.error(f"Error handling connection: {e}")

    async def _send_registration(self) -> None:
        """Send function registration to backend."""
        if not self._connection:
            return

        functions = self._registry.get_all_metadata()

        message = RegisterMessage(
            project_id=self.project_id,
            environment=self.environment,
            functions=functions,
        )

        try:
            await self._connection.send(message.model_dump())
            logger.info(f"Sent registration for {len(functions)} function(s)")
        except Exception as e:
            logger.error(f"Error sending registration: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """
        Handle incoming messages from backend.

        Args:
            message: Message dictionary
        """
        message_type = message.get("type")

        if message_type == MessageType.EXECUTE_TEST:
            await self._handle_test_request(message)
        elif message_type == MessageType.PING:
            await self._handle_ping()
        elif message_type in ("connected", "registered"):
            # Acknowledgment messages from backend - no action needed
            logger.debug(f"Received acknowledgment: {message_type}")
        else:
            logger.warning(f"Unknown message type: {message_type}")

    async def _handle_test_request(self, message: dict[str, Any]) -> None:
        """
        Handle test execution request.

        Args:
            message: Test execution message
        """
        try:
            test_msg = ExecuteTestMessage(**message)
            function_name = test_msg.function_name
            test_run_id = test_msg.test_run_id
            inputs = test_msg.inputs

            logger.info(f"Executing test for function: {function_name}")

            # Validate function exists
            if not self._registry.has(function_name):
                await self._send_test_result(
                    test_run_id,
                    status="error",
                    error=f"Function '{function_name}' not found in registry",
                    duration_ms=0,
                )
                return

            # Execute function via executor
            func = self._registry.get(function_name)
            result = await self._executor.execute(func, function_name, inputs)

            # Send result
            await self._send_test_result(
                test_run_id,
                status=result["status"],
                output=result["output"],
                error=result["error"],
                duration_ms=result["duration_ms"],
            )

        except Exception as e:
            logger.error(f"Error handling test request: {e}")

    async def _send_test_result(
        self,
        test_run_id: str,
        status: str,
        output: Any = None,
        error: str | None = None,
        duration_ms: float = 0,
    ) -> None:
        """
        Send test result back to backend.

        Args:
            test_run_id: Test run identifier
            status: "success" or "error"
            output: Function output (if successful)
            error: Error message (if failed)
            duration_ms: Execution duration in milliseconds
        """
        if not self._connection:
            return

        message = TestResultMessage(
            test_run_id=test_run_id,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
        )

        try:
            await self._connection.send(message.model_dump())
            logger.info(f"Sent test result for run {test_run_id}: {status}")
        except Exception as e:
            logger.error(f"Error sending test result: {e}")

    async def _handle_ping(self) -> None:
        """Handle ping message by sending pong."""
        if not self._connection:
            return

        logger.info(
            f"Received ping from backend [project={self.project_id}, env={self.environment}]"
        )

        try:
            await self._connection.send({"type": MessageType.PONG})
            logger.debug(
                f"Pong sent successfully [project={self.project_id}, env={self.environment}]"
            )
        except Exception as e:
            logger.error(
                f"Error sending pong [project={self.project_id}, env={self.environment}]: {e}"
            )

    def _get_websocket_url(self) -> str:
        """
        Construct WebSocket URL.

        Returns:
            WebSocket URL
        """
        # Convert http(s) to ws(s)
        if self.base_url.startswith("http://"):
            ws_url = self.base_url.replace("http://", "ws://")
        elif self.base_url.startswith("https://"):
            ws_url = self.base_url.replace("https://", "wss://")
        else:
            ws_url = self.base_url

        # Ensure no trailing slash
        ws_url = ws_url.rstrip("/")

        return f"{ws_url}/connector/ws"

    async def shutdown(self) -> None:
        """Shutdown connector and close connection."""
        if self._connection:
            await self._connection.disconnect()
        self._initialized = False
        logger.info("Connector shutdown complete")

    def trace_execution(
        self,
        function_name: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        span_name: str | None = None,
    ) -> Any:
        """
        Trace function execution and send telemetry to backend.

        Delegates to the Tracer for actual tracing logic.

        Args:
            function_name: Name of the function being traced
            func: The function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            span_name: Optional custom span name (e.g., 'ai.llm.invoke')

        Returns:
            Function result (or wrapped generator)
        """
        return self._tracer.trace_execution(function_name, func, args, kwargs, span_name)

    async def trace_execution_async(
        self,
        function_name: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        span_name: str | None = None,
    ) -> Any:
        """
        Trace async function execution and send telemetry to backend.

        Delegates to the Tracer for actual tracing logic.

        Args:
            function_name: Name of the function being traced
            func: The async function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            span_name: Optional custom span name (e.g., 'ai.llm.invoke')

        Returns:
            Function result
        """
        return await self._tracer.trace_execution_async(
            function_name, func, args, kwargs, span_name
        )
