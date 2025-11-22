"""Connector manager for bidirectional communication."""

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Dict, Optional

from rhesis.sdk.connector.connection import WebSocketConnection
from rhesis.sdk.connector.schemas import (
    ExecuteTestMessage,
    FunctionMetadata,
    RegisterMessage,
    TestResultMessage,
)
from rhesis.sdk.connector.types import MessageType

logger = logging.getLogger(__name__)


class ConnectorManager:
    """Manages WebSocket connection and function registry for collaborative testing."""

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
        """
        self.api_key = api_key
        self.project_id = project_id
        self.environment = environment
        self.base_url = base_url

        # Function registry
        self._registry: Dict[str, Callable] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

        # WebSocket connection
        self._connection: Optional[WebSocketConnection] = None
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
        )

        # Start connection in background
        asyncio.create_task(self._initialize_connection())
        self._initialized = True
        logger.info(f"Connector initialized for project {self.project_id}")

    def register_function(self, name: str, func: Callable, metadata: Dict[str, Any]) -> None:
        """
        Register a function for remote triggering.

        Args:
            name: Function name
            func: Function callable
            metadata: Additional metadata
        """
        if not self._initialized:
            self.initialize()

        self._registry[name] = func
        self._metadata[name] = metadata
        logger.info(f"Registered function: {name}")

        # If connection is active, send updated registration
        if self._connection and self._connection.websocket:
            asyncio.create_task(self._send_registration())

    async def _initialize_connection(self) -> None:
        """Initialize connection and send registration."""
        try:
            await self._connection.connect()
            await asyncio.sleep(0.5)  # Wait for connection to establish
            await self._send_registration()
        except Exception as e:
            logger.error(f"Error initializing connection: {e}")

    async def _send_registration(self) -> None:
        """Send function registration to backend."""
        if not self._connection:
            return

        functions = []
        for name, func in self._registry.items():
            signature = self._get_function_signature(func)
            functions.append(
                FunctionMetadata(
                    name=name,
                    parameters=signature["parameters"],
                    return_type=signature["return_type"],
                    metadata=self._metadata.get(name, {}),
                )
            )

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

    async def _handle_message(self, message: Dict[str, Any]) -> None:
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

    async def _handle_test_request(self, message: Dict[str, Any]) -> None:
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
            if function_name not in self._registry:
                await self._send_test_result(
                    test_run_id,
                    status="error",
                    error=f"Function '{function_name}' not found in registry",
                    duration_ms=0,
                )
                return

            # Execute function
            func = self._registry[function_name]
            start_time = time.time()

            try:
                # Execute function (sync or async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(**inputs)
                else:
                    result = func(**inputs)

                # Check if result is a generator and consume it
                import inspect

                if inspect.isgenerator(result) or inspect.isasyncgen(result):
                    # Consume the generator and collect all chunks
                    chunks = []
                    if inspect.isasyncgen(result):
                        async for chunk in result:
                            chunks.append(str(chunk))
                    else:
                        for chunk in result:
                            chunks.append(str(chunk))
                    result = "".join(chunks)

                duration_ms = (time.time() - start_time) * 1000

                # Send success result
                await self._send_test_result(
                    test_run_id, status="success", output=result, duration_ms=duration_ms
                )

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"Error executing function {function_name}: {e}")

                # Send error result
                await self._send_test_result(
                    test_run_id, status="error", error=str(e), duration_ms=duration_ms
                )

        except Exception as e:
            logger.error(f"Error handling test request: {e}")

    async def _send_test_result(
        self,
        test_run_id: str,
        status: str,
        output: Any = None,
        error: Optional[str] = None,
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

        try:
            await self._connection.send({"type": MessageType.PONG})
        except Exception as e:
            logger.error(f"Error sending pong: {e}")

    def _get_function_signature(self, func: Callable) -> Dict[str, Any]:
        """
        Extract function signature for validation.

        Args:
            func: Function to inspect

        Returns:
            Dictionary with parameters and return type
        """
        sig = inspect.signature(func)

        return {
            "parameters": {
                name: {
                    "type": (
                        str(param.annotation)
                        if param.annotation != inspect.Parameter.empty
                        else "Any"
                    ),
                    "default": (
                        str(param.default) if param.default != inspect.Parameter.empty else None
                    ),
                }
                for name, param in sig.parameters.items()
            },
            "return_type": (
                str(sig.return_annotation)
                if sig.return_annotation != inspect.Signature.empty
                else "Any"
            ),
        }

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
