"""Connection manager for WebSocket connections with SDKs."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from sqlalchemy.orm import Session
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.services.connector.handler import message_handler
from rhesis.backend.app.services.connector.redis_client import redis_manager
from rhesis.backend.app.services.connector.schemas import (
    ConnectionStatus,
    ExecuteTestMessage,
    FunctionMetadata,
    RegisterMessage,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with SDK clients."""

    def __init__(self):
        """Initialize connection manager."""
        # Store active connections: {project_id:environment: WebSocket}
        self._connections: Dict[str, WebSocket] = {}

        # Store function registries: {project_id:environment: [FunctionMetadata]}
        self._registries: Dict[str, List[FunctionMetadata]] = {}

        # Store completed test results: {test_run_id: result_dict}
        self._test_results: Dict[str, Dict[str, Any]] = {}

        # Track cancelled/timed-out test runs to prevent storing late results
        self._cancelled_tests: set = set()

        # Track background tasks to prevent silent failures
        self._background_tasks: set = set()

    def get_connection_key(self, project_id: str, environment: str) -> str:
        """
        Generate connection key.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Connection key string
        """
        return f"{project_id}:{environment}"

    def _track_background_task(self, coro) -> asyncio.Task:
        """
        Create and track a background task to prevent silent failures.

        Args:
            coro: Coroutine to run as background task

        Returns:
            Created task
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Add exception handler to log errors
        def log_exception(t: asyncio.Task) -> None:
            try:
                t.result()
            except Exception as e:
                logger.error(f"Background task failed: {e}", exc_info=True)

        task.add_done_callback(log_exception)
        return task

    async def connect(self, project_id: str, environment: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Args:
            project_id: Project identifier
            environment: Environment name
            websocket: WebSocket connection
        """
        key = self.get_connection_key(project_id, environment)
        self._connections[key] = websocket
        logger.info(f"Connected: {key}")

        # Store in Redis for worker visibility
        if redis_manager.is_available:
            try:
                redis_key = f"ws:connection:{key}"
                await redis_manager.client.setex(
                    redis_key,
                    3600,  # 1 hour TTL
                    "active",
                )
                logger.info(
                    f"✅ SDK connection registered in Redis: {key} (redis_key={redis_key}, TTL=1h)"
                )
            except Exception as e:
                logger.error(f"❌ Failed to store connection in Redis for {key}: {e}")

    def disconnect(self, project_id: str, environment: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            project_id: Project identifier
            environment: Environment name
        """
        key = self.get_connection_key(project_id, environment)
        if key in self._connections:
            del self._connections[key]
        if key in self._registries:
            del self._registries[key]
        logger.info(f"Disconnected: {key}")

        # Remove from Redis
        if redis_manager.is_available:
            try:
                # Create tracked task to delete from Redis (non-blocking)
                self._track_background_task(self._remove_connection_from_redis(key))
            except Exception as e:
                logger.warning(f"Failed to schedule Redis cleanup: {e}")

    async def _remove_connection_from_redis(self, key: str) -> None:
        """Remove connection from Redis (async helper)."""
        try:
            await redis_manager.client.delete(f"ws:connection:{key}")
            logger.debug(f"Removed connection from Redis: {key}")
        except Exception as e:
            logger.warning(f"Failed to remove connection from Redis: {e}")

    def register_functions(
        self, project_id: str, environment: str, functions: List[FunctionMetadata]
    ) -> None:
        """
        Register functions for a project.

        Args:
            project_id: Project identifier
            environment: Environment name
            functions: List of function metadata
        """
        key = self.get_connection_key(project_id, environment)
        self._registries[key] = functions
        logger.info(f"Registered {len(functions)} function(s) for {key}")

    async def send_test_request(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        inputs: Dict[str, Any],
    ) -> bool:
        """
        Send test execution request to SDK.

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Test run identifier
            function_name: Function to execute
            inputs: Function inputs

        Returns:
            True if message sent successfully, False otherwise
        """
        key = self.get_connection_key(project_id, environment)

        if key not in self._connections:
            logger.error(f"No connection for {key}")
            return False

        websocket = self._connections[key]
        message = ExecuteTestMessage(
            test_run_id=test_run_id, function_name=function_name, inputs=inputs
        )

        try:
            await websocket.send_json(message.model_dump())
            logger.info(f"Sent test request to {key}: {function_name}")
            return True
        except Exception as e:
            logger.error(f"Error sending test request to {key}: {e}")
            return False

    async def send_and_await_result(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        inputs: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Send test request and wait for result.

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Test run identifier
            function_name: Function to execute
            inputs: Function inputs
            timeout: Timeout in seconds (default: 30.0)

        Returns:
            Result dictionary with one of:
            - {"status": "success", "output": {...}, "duration_ms": float}
            - {"status": "error", "error": str, "duration_ms": float}
            - {"error": "send_failed", "details": str}
            - {"error": "timeout"}
        """
        # Send the request
        sent = await self.send_test_request(
            project_id, environment, test_run_id, function_name, inputs
        )

        if not sent:
            return {"error": "send_failed", "details": "Failed to send message to SDK"}

        # Wait for result with timeout
        start_time = asyncio.get_event_loop().time()
        poll_interval = 0.1  # Poll every 100ms

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                # Mark as cancelled immediately to prevent race condition with late results
                self.cleanup_test_result(test_run_id)
                logger.error(f"Timeout waiting for SDK result: {test_run_id}")
                return {"error": "timeout"}

            # Check if result is available
            result = self.get_test_result(test_run_id)
            if result:
                logger.debug(f"Received SDK result for {test_run_id}")
                # Clean up after successful retrieval
                self.cleanup_test_result(test_run_id)
                return result

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    def _resolve_test_result(self, test_run_id: str, result: Dict[str, Any]) -> None:
        """
        Store test result for synchronous retrieval.

        Args:
            test_run_id: Test run identifier
            result: Test result data
        """
        # Check if test run was cancelled/timed out - don't store late results
        if test_run_id in self._cancelled_tests:
            logger.warning(f"Ignoring late result for cancelled test run: {test_run_id}")
            return

        logger.debug(f"Storing test result: {test_run_id}")

        # Store result in memory for backend process
        self._test_results[test_run_id] = result

        # Also publish to Redis for workers
        if redis_manager.is_available:
            try:
                # Publish to response channel for RPC (tracked)
                self._track_background_task(self._publish_rpc_response(test_run_id, result))
            except Exception as e:
                logger.warning(f"Failed to publish RPC response: {e}")

    async def _publish_rpc_response(self, test_run_id: str, result: Dict[str, Any]) -> None:
        """Publish RPC response to Redis (async helper)."""
        try:
            await redis_manager.client.publish(f"ws:rpc:response:{test_run_id}", json.dumps(result))
            logger.debug(f"Published RPC response to Redis: {test_run_id}")
        except Exception as e:
            logger.warning(f"Failed to publish RPC response: {e}")

    def get_test_result(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get test result if available (non-destructive).

        Note: This method does not delete the result. Callers must explicitly
        call cleanup_test_result() when done to prevent memory leaks.

        Args:
            test_run_id: Test run identifier

        Returns:
            Test result dict if available, None otherwise
        """
        return self._test_results.get(test_run_id)

    def cleanup_test_result(self, test_run_id: str) -> None:
        """
        Remove a test result from memory and mark as cancelled to prevent memory leaks.

        This should be called when a test times out, errors, or is no longer needed.
        Marking as cancelled prevents late-arriving results from being stored.

        Args:
            test_run_id: Test run identifier to clean up
        """
        # Mark as cancelled to prevent late results from being stored
        self._cancelled_tests.add(test_run_id)

        # Remove any existing result
        if test_run_id in self._test_results:
            del self._test_results[test_run_id]
            logger.debug(f"Cleaned up test result: {test_run_id}")
        else:
            logger.debug(f"Marked test run as cancelled: {test_run_id}")

        # Perform periodic cleanup if the cancelled set grows too large
        # This prevents unbounded memory growth from the cancelled tests set
        if len(self._cancelled_tests) > 10000:
            self._cleanup_old_cancelled_tests()

    def _cleanup_old_cancelled_tests(self) -> None:
        """
        Clean up old cancelled test entries to prevent unbounded memory growth.

        Keeps only the most recent 5000 entries. This is a simple LRU-style
        cleanup that should be sufficient for most use cases.
        """
        if len(self._cancelled_tests) > 5000:
            # Convert to list, keep last 5000, convert back to set
            # Note: set order is insertion order in Python 3.7+
            cancelled_list = list(self._cancelled_tests)
            self._cancelled_tests = set(cancelled_list[-5000:])
            logger.info(
                f"Cleaned up old cancelled tests. "
                f"Removed {len(cancelled_list) - 5000} entries, kept 5000"
            )

    def get_connection_status(self, project_id: str, environment: str) -> ConnectionStatus:
        """
        Get connection status for a project.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Connection status
        """
        key = self.get_connection_key(project_id, environment)
        connected = key in self._connections
        functions = self._registries.get(key, [])

        return ConnectionStatus(
            project_id=project_id,
            environment=environment,
            connected=connected,
            functions=functions,
        )

    def is_connected(self, project_id: str, environment: str) -> bool:
        """
        Check if project is connected.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            True if connected, False otherwise
        """
        key = self.get_connection_key(project_id, environment)
        return key in self._connections

    async def handle_registration(
        self, project_id: str, environment: str, message: Dict[str, Any]
    ) -> None:
        """
        Handle registration message from SDK - update local function registry.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Registration message
        """
        try:
            reg_msg = RegisterMessage(**message)
            self.register_functions(project_id, environment, reg_msg.functions)
        except Exception as e:
            logger.error(f"Error handling registration: {e}")

    async def handle_message(
        self,
        project_id: str,
        environment: str,
        message: Dict[str, Any],
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle incoming WebSocket message from SDK.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Message data
            db: Optional database session for registration
            organization_id: Optional organization ID for metadata updates
            user_id: Optional user ID for metadata updates

        Returns:
            Response message to send back, or None if no response needed
        """
        message_type = message.get("type")
        logger.info(f"Processing message type: {message_type} from {project_id}:{environment}")

        if message_type == "register":
            # Update local function registry
            await self.handle_registration(project_id, environment, message)
            # Handle registration via message handler (includes DB updates)
            return await message_handler.handle_register_message(
                project_id=project_id,
                environment=environment,
                message=message,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
            )

        elif message_type == "test_result":
            # Resolve pending future if awaiting result
            test_run_id = message.get("test_run_id")
            if test_run_id:
                self._resolve_test_result(test_run_id, message)

            # Handle test result via message handler (logging, late validation updates, etc.)
            await message_handler.handle_test_result_message(project_id, environment, message, db)
            return None

        elif message_type == "pong":
            # Handle pong via message handler
            await message_handler.handle_pong_message(project_id, environment)
            return None

        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None

    async def _listen_for_rpc_requests(self) -> None:
        """
        Background task to handle RPC requests from workers.

        Subscribes to ws:rpc:requests channel and forwards requests to WebSocket connections.
        Uses tenacity for exponential backoff and retry limits to prevent infinite crash loops.
        """
        if not redis_manager.is_available:
            logger.warning("⚠️ Redis not available, RPC listener not started")
            return

        logger.info(
            "🎧 RPC LISTENER STARTED - Subscribing to 'ws:rpc:requests' channel "
            "for worker SDK invocations"
        )

        # Track pubsub instance to ensure cleanup
        pubsub = None

        try:
            # Use tenacity for retry logic with exponential backoff
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(10),
                wait=wait_exponential(multiplier=5, min=5, max=300),
                retry=retry_if_exception_type(Exception),
                reraise=False,
            ):
                with attempt:
                    try:
                        # Close previous pubsub if it exists (from failed attempt)
                        if pubsub:
                            try:
                                await pubsub.close()
                            except Exception:
                                pass  # Ignore errors closing stale pubsub

                        pubsub = redis_manager.client.pubsub()
                        await pubsub.subscribe("ws:rpc:requests")

                        async for message in pubsub.listen():
                            if message["type"] == "message":
                                try:
                                    request = json.loads(message["data"])
                                    await self._handle_rpc_request(request)
                                except Exception as e:
                                    logger.error(f"Error handling RPC request: {e}", exc_info=True)

                    except Exception as e:
                        attempt_num = attempt.retry_state.attempt_number
                        logger.error(
                            f"RPC listener crashed (attempt {attempt_num}/10): {e}",
                            exc_info=True,
                        )
                        if attempt_num < 10:
                            logger.warning("RPC listener will retry with exponential backoff...")
                        raise

            # If we exit the retry loop, we've exhausted all attempts
            logger.error(
                "RPC listener failed 10 times. Giving up on automatic restarts. "
                "Manual intervention required."
            )

        finally:
            # Always clean up pubsub connection
            if pubsub:
                try:
                    await pubsub.close()
                    logger.debug("RPC listener pubsub connection closed")
                except Exception as e:
                    logger.warning(f"Error closing RPC listener pubsub: {e}")

    async def _handle_rpc_request(self, request: Dict[str, Any]) -> None:
        """
        Handle RPC request from worker.

        Args:
            request: RPC request with keys: request_id, project_id, environment,
                    function_name, inputs
        """
        request_id = request.get("request_id")
        project_id = request.get("project_id")
        environment = request.get("environment")
        function_name = request.get("function_name")
        inputs = request.get("inputs", {})

        logger.info(
            f"Handling RPC request {request_id}: {function_name} "
            f"(project: {project_id}, env: {environment})"
        )

        # Look up WebSocket connection
        key = self.get_connection_key(project_id, environment)

        if key not in self._connections:
            logger.error(f"No connection for RPC request: {key}")
            # Publish error response
            if redis_manager.is_available:
                try:
                    error_response = {"error": "send_failed", "details": f"No connection for {key}"}
                    await redis_manager.client.publish(
                        f"ws:rpc:response:{request_id}", json.dumps(error_response)
                    )
                except Exception as e:
                    logger.error(f"Failed to publish error response: {e}")
            return

        # Forward to SDK via WebSocket
        websocket = self._connections[key]
        message = ExecuteTestMessage(
            test_run_id=request_id, function_name=function_name, inputs=inputs
        )

        try:
            await websocket.send_json(message.model_dump())
            logger.debug(f"Forwarded RPC request to WebSocket: {request_id}")
        except Exception as e:
            logger.error(f"Error forwarding RPC request to WebSocket: {e}")
            # Publish error response
            if redis_manager.is_available:
                try:
                    error_response = {"error": "send_failed", "details": str(e)}
                    await redis_manager.client.publish(
                        f"ws:rpc:response:{request_id}", json.dumps(error_response)
                    )
                except Exception as pub_err:
                    logger.error(f"Failed to publish error response: {pub_err}")


# Global connection manager instance
connection_manager = ConnectionManager()
