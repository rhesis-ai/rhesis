"""Connector manager for bidirectional communication."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from rhesis.sdk.connector.connection import WebSocketConnection
from rhesis.sdk.connector.executor import TestExecutor
from rhesis.sdk.connector.registry import FunctionRegistry, MetricRegistry
from rhesis.sdk.connector.schemas import (
    ExecuteMetricMessage,
    ExecuteTestMessage,
    MetricResultMessage,
    RegisterMessage,
    TestResultMessage,
    TestStatus,
)
from rhesis.sdk.connector.types import ConnectionState, Environment, MessageType, RetryConfig
from rhesis.sdk.telemetry import Tracer

logger = logging.getLogger(__name__)


class ConnectorManager:
    """Manages WebSocket connection and function registry for remote endpoint testing."""

    def __init__(
        self,
        api_key: str,
        project_id: str | None = None,
        environment: str = "development",
        base_url: str = "ws://localhost:8080",
    ):
        """
        Initialize connector manager.

        Args:
            api_key: API key for authentication
            project_id: Project identifier (optional for metrics-only)
            environment: Environment name (default: "development")
            base_url: Base URL for WebSocket connection

        Raises:
            ValueError: If environment is not valid
        """
        environment = environment.lower()

        if environment not in Environment.ALL:
            raise ValueError(
                f"Invalid environment: '{environment}'. "
                f"Valid environments: {', '.join(Environment.ALL)}"
            )

        self.api_key = api_key
        self.project_id = project_id
        self.environment = environment
        self.base_url = base_url

        self._registry = FunctionRegistry()
        self._metric_registry = MetricRegistry()
        self._executor = TestExecutor()
        self._tracer = Tracer(
            api_key=api_key,
            project_id=project_id or "",
            environment=environment,
            base_url=base_url,
        )

        self._connection: WebSocketConnection | None = None
        self._connection_id: str | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize WebSocket connection."""
        if self._initialized:
            logger.warning("Connector already initialized")
            return

        ws_url = self._get_websocket_url()

        headers = {"Authorization": f"Bearer {self.api_key}"}
        # Send project/env headers for backward compat with old backends
        if self.project_id:
            headers["X-Rhesis-Project"] = self.project_id
            headers["X-Rhesis-Environment"] = self.environment

        self._connection = WebSocketConnection(
            url=ws_url,
            headers=headers,
            on_message=self._handle_message,
            on_connect=self._handle_connect,
        )

        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._connection.connect())
        except RuntimeError:
            logger.debug("No event loop running, connection will be established later")

        self._initialized = True
        msg = "Connector initialized"
        if self.project_id:
            msg += f" for project {self.project_id}"
        logger.info(msg)

    @property
    def connection_id(self) -> str | None:
        """The server-assigned connection ID, available after connect."""
        return self._connection_id

    def _ensure_connection(self) -> None:
        """Ensure WebSocket connection is started (if not already)."""
        if not self._initialized:
            return

        # Check if connection exists but isn't started
        if self._connection and self._connection.state == ConnectionState.DISCONNECTED:
            try:
                asyncio.create_task(self._connection.connect())
            except RuntimeError:
                # No event loop, connection will start when available
                pass

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
                # No event loop running, registration will be sent when connection is established
                logger.debug("No event loop running, registration will be sent on connection")

    def register_metric(self, name: str, func: Callable, metadata: dict[str, Any]) -> None:
        """
        Register an SDK-side metric for remote evaluation.

        Args:
            name: Metric name
            func: Metric callable
            metadata: Additional metadata (score_type, accepted_params, etc.)
        """
        if not self._initialized:
            self.initialize()

        self._metric_registry.register(name, func, metadata)

        # If connection is active, send updated registration
        if self._connection and self._connection.websocket:
            try:
                asyncio.create_task(self._send_registration())
            except RuntimeError:
                logger.debug("No event loop running, registration will be sent on connection")

    async def _handle_connect(self) -> None:
        """Handle successful connection/reconnection - send registration."""
        try:
            # Brief delay to ensure connection is stable
            await asyncio.sleep(RetryConfig.REGISTRATION_DELAY)
            await self._send_registration()
        except Exception as e:
            logger.error(f"Error handling connection: {e}")

    async def _send_registration(self) -> None:
        """Send function and metric registration to backend."""
        if not self._connection:
            return

        functions = self._registry.get_all_metadata()
        metrics = self._metric_registry.get_all_metadata()

        message = RegisterMessage(
            project_id=self.project_id or None,
            environment=self.environment if self.project_id else None,
            functions=functions,
            metrics=metrics,
        )

        try:
            await self._connection.send(message.model_dump())
            logger.info(
                f"Sent registration for {len(functions)} function(s) and {len(metrics)} metric(s)"
            )
        except Exception as e:
            logger.error(f"Error sending registration: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """
        Handle incoming messages from backend.

        Args:
            message: Message dictionary
        """
        message_type = message.get("type")

        if message_type == MessageType.EXECUTE_TEST.value:
            await self._handle_test_request(message)
        elif message_type == MessageType.EXECUTE_METRIC.value:
            await self._handle_metric_request(message)
        elif message_type == MessageType.PING.value:
            await self._handle_ping()
        elif message_type == MessageType.CONNECTED.value:
            cid = message.get("connection_id")
            if cid:
                self._connection_id = cid
            logger.debug(f"Connected (connection_id={self._connection_id})")
        elif message_type == MessageType.REGISTERED.value:
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
                    status=TestStatus.ERROR,
                    error=f"Function '{function_name}' not found in registry",
                    duration_ms=0,
                )
                return

            # Get function and its metadata (including serializers)
            func = self._registry.get(function_name)
            metadata = self._registry.get_metadata(function_name) or {}
            serializers = metadata.get("serializers")

            # Execute function via executor with serializers
            result = await self._executor.execute(
                func, function_name, inputs, serializers=serializers
            )

            # Send result
            await self._send_test_result(
                test_run_id,
                status=result["status"],
                output=result["output"],
                error=result["error"],
                duration_ms=result["duration_ms"],
                trace_id=result.get("trace_id"),
            )

        except Exception as e:
            logger.error(f"Error handling test request: {e}")

    async def _send_test_result(
        self,
        test_run_id: str,
        status: TestStatus,
        output: Any = None,
        error: str | None = None,
        duration_ms: float = 0,
        trace_id: str | None = None,
    ) -> None:
        """
        Send test result back to backend.

        Args:
            test_run_id: Test run identifier
            status: "success" or "error"
            output: Function output (if successful)
            error: Error message (if failed)
            duration_ms: Execution duration in milliseconds
            trace_id: Optional trace ID for linking to traces
        """
        if not self._connection:
            return

        message = TestResultMessage(
            test_run_id=test_run_id,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )

        try:
            await self._connection.send(message.model_dump())
            logger.info(f"Sent test result for run {test_run_id}: {status}")
        except Exception as e:
            logger.error(f"Error sending test result: {e}")

    async def _handle_metric_request(self, message: dict[str, Any]) -> None:
        """
        Handle metric execution request from backend.

        Args:
            message: Execute metric message
        """
        try:
            metric_msg = ExecuteMetricMessage(**message)
            metric_name = metric_msg.metric_name
            metric_run_id = metric_msg.metric_run_id
            inputs = metric_msg.inputs

            logger.info(f"Executing metric: {metric_name}")

            if not self._metric_registry.has(metric_name):
                await self._send_metric_result(
                    metric_run_id,
                    status=TestStatus.ERROR,
                    error=f"Metric '{metric_name}' not found in registry",
                    duration_ms=0,
                )
                return

            metric_func = self._metric_registry.get(metric_name)
            metadata = self._metric_registry.get_metadata(metric_name) or {}
            accepted_params = metadata.get("accepted_params", ["input", "output"])

            result = await self._executor.execute_metric(
                metric_func, metric_name, inputs, accepted_params
            )

            await self._send_metric_result(
                metric_run_id,
                status=result["status"],
                score=result.get("score"),
                details=result.get("details", {}),
                error=result.get("error"),
                duration_ms=result["duration_ms"],
            )

        except Exception as e:
            logger.error(f"Error handling metric request: {e}")

    async def _send_metric_result(
        self,
        metric_run_id: str,
        status: TestStatus,
        score: Any = None,
        details: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: float = 0,
    ) -> None:
        """
        Send metric result back to backend.

        Args:
            metric_run_id: Metric run identifier
            status: "success" or "error"
            score: Metric score (if successful)
            details: Additional details (if successful)
            error: Error message (if failed)
            duration_ms: Execution duration in milliseconds
        """
        if not self._connection:
            return

        message = MetricResultMessage(
            metric_run_id=metric_run_id,
            status=status,
            score=score,
            details=details or {},
            error=error,
            duration_ms=duration_ms,
        )

        try:
            await self._connection.send(message.model_dump())
            logger.info(f"Sent metric result for run {metric_run_id}: {status}")
        except Exception as e:
            logger.error(f"Error sending metric result: {e}")

    async def _handle_ping(self) -> None:
        """Handle ping message by sending pong."""
        if not self._connection:
            return

        logger.info(
            f"Received ping from backend [project={self.project_id}, env={self.environment}]"
        )

        try:
            await self._connection.send({"type": MessageType.PONG.value})
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
