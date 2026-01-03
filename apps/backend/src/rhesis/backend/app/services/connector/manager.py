"""Connection manager for WebSocket connections with SDKs."""

import asyncio
import json
import logging
import os
from collections import OrderedDict
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
        # Get unique worker ID from environment (format: worker@hostname-pid)
        self.worker_id = os.getenv("CELERY_WORKER_NAME", "worker@unknown")

        # Store active connections: {project_id:environment: WebSocket}
        self._connections: Dict[str, WebSocket] = {}

        # Store function registries: {project_id:environment: [FunctionMetadata]}
        self._registries: Dict[str, List[FunctionMetadata]] = {}

        # Store completed test results: {test_run_id: result_dict}
        self._test_results: Dict[str, Dict[str, Any]] = {}

        # Track cancelled/timed-out test runs to prevent storing late results
        # Use OrderedDict to preserve insertion order for proper LRU cleanup
        self._cancelled_tests: OrderedDict = OrderedDict()

        # Track background tasks to prevent silent failures
        self._background_tasks: set = set()

        # Track heartbeat tasks for each connection
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

    def get_connection_key(self, project_id: str, environment: str) -> str:
        """
        Generate connection key.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Connection key string (with environment normalized to lowercase)
        """
        # Normalize environment to lowercase for consistent key generation
        # This ensures keys match regardless of the casing used in headers or database
        environment = environment.lower()
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

        # Store in Redis for worker visibility with short TTL and heartbeat
        if redis_manager.is_available:
            try:
                redis_key = f"ws:connection:{key}"
                # Use 30-second TTL - will be refreshed by heartbeat every 10 seconds
                await redis_manager.client.setex(
                    redis_key,
                    30,  # 30 seconds TTL - heartbeat will refresh
                    "active",
                )
                logger.debug(f"Stored connection in Redis: {redis_key}")

                # Register this worker as handler for the connection (for direct routing)
                await self._register_worker_for_connection(key)

                # Start heartbeat task to keep Redis key alive
                heartbeat_task = self._track_background_task(self._heartbeat_loop(key))
                self._heartbeat_tasks[key] = heartbeat_task
            except Exception as e:
                logger.error(f"Failed to store connection in Redis for {key}: {e}")

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

        # Cancel heartbeat task if exists
        if key in self._heartbeat_tasks:
            heartbeat_task = self._heartbeat_tasks[key]
            if not heartbeat_task.done():
                heartbeat_task.cancel()
            del self._heartbeat_tasks[key]

        # Remove from Redis
        if redis_manager.is_available:
            try:
                # Unregister worker routing
                self._track_background_task(self._unregister_worker_for_connection(key))
                # Create tracked task to delete from Redis (non-blocking)
                self._track_background_task(self._remove_connection_from_redis(key))
            except Exception as e:
                logger.warning(f"Failed to schedule Redis cleanup for {key}: {e}")

    async def _remove_connection_from_redis(self, key: str) -> None:
        """Remove connection from Redis (async helper)."""
        try:
            redis_key = f"ws:connection:{key}"
            await redis_manager.client.delete(redis_key)
            logger.debug(f"Removed connection from Redis: {redis_key}")
        except Exception as e:
            logger.warning(f"Failed to remove connection from Redis for {key}: {e}")

    async def _heartbeat_loop(self, key: str) -> None:
        """
        Periodically refresh the connection key in Redis to keep it alive.

        Args:
            key: Connection key (project_id:environment)
        """
        redis_key = f"ws:connection:{key}"

        try:
            while key in self._connections:
                # Wait 10 seconds between heartbeats (TTL is 30s, so plenty of margin)
                await asyncio.sleep(10)

                # Check if connection still exists
                if key not in self._connections:
                    break

                # Refresh the Redis key
                try:
                    await redis_manager.client.setex(redis_key, 30, "active")
                except Exception as e:
                    logger.warning(f"Heartbeat failed for {key}: {e}")
                    # Continue trying - connection might still be valid

        except asyncio.CancelledError:
            # Task was cancelled (normal during disconnect)
            raise
        except Exception as e:
            logger.error(f"Unexpected error in heartbeat loop for {key}: {e}")

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
            # Don't log error here - this method is used for direct WebSocket calls only
            # For RPC-based invocations, the connection may exist on another instance
            logger.debug(f"No local WebSocket connection for {key} - may be on another instance")
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

        logger.info(
            f"📨 Received test result from SDK: {test_run_id} "
            f"(status: {result.get('status', 'unknown')})"
        )

        # Store result in memory for backend process
        self._test_results[test_run_id] = result
        logger.info(f"💾 Stored result in memory for {test_run_id}")

        # Also publish to Redis for workers
        if redis_manager.is_available:
            logger.info(f"📡 Redis available - publishing RPC response for {test_run_id}")
            try:
                # Publish to response channel for RPC (tracked)
                self._track_background_task(self._publish_rpc_response(test_run_id, result))
                logger.info(f"✅ Scheduled RPC response publish task for {test_run_id}")
            except Exception as e:
                logger.error(f"❌ Failed to schedule RPC response publish: {e}", exc_info=True)
        else:
            logger.warning(
                f"⚠️  Redis NOT available - cannot publish RPC response for {test_run_id}"
            )

    async def _publish_rpc_response(self, test_run_id: str, result: Dict[str, Any]) -> None:
        """Publish RPC response to Redis (async helper)."""
        try:
            channel = f"ws:rpc:response:{test_run_id}"
            json_payload = json.dumps(result)
            logger.info(
                f"📤 Publishing to channel: {channel} (payload size: {len(json_payload)} bytes)"
            )
            await redis_manager.client.publish(channel, json_payload)
            logger.info(f"✅ Successfully published RPC response: {test_run_id}")
        except Exception as e:
            logger.error(f"❌ Failed to publish RPC response for {test_run_id}: {e}", exc_info=True)

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
        self._cancelled_tests[test_run_id] = True

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

        Keeps only the most recent 5000 entries. This is called when the dict
        grows beyond 10000 entries to trim it back down to a reasonable size.
        """
        # Keep only the last 5000 entries (most recent)
        # OrderedDict preserves insertion order, so [-5000:] gets the newest entries
        cancelled_items = list(self._cancelled_tests.items())
        removed_count = len(cancelled_items) - 5000
        self._cancelled_tests = OrderedDict(cancelled_items[-5000:])
        logger.info(f"Cleaned up old cancelled tests. Removed {removed_count} entries, kept 5000")

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

    async def is_connected(self, project_id: str, environment: str) -> bool:
        """
        Check if project is connected (checks both local connections and Redis).

        In multi-instance deployments, the WebSocket might be connected to a different
        backend instance. We check Redis first to see if ANY instance has the connection,
        then fall back to checking local connections.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            True if connected (either locally or in another instance), False otherwise
        """
        key = self.get_connection_key(project_id, environment)

        # First check local connections (fast path)
        if key in self._connections:
            return True

        # Check Redis for connections on other instances (multi-instance support)
        if redis_manager.is_available:
            try:
                redis_key = f"ws:connection:{key}"
                exists = await redis_manager.client.exists(redis_key)
                return exists > 0
            except Exception as e:
                logger.warning(f"Failed to check Redis for connection {key}: {e}")

        return False

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

        Listens on worker-specific channel for direct routing.
        Uses tenacity for exponential backoff and retry limits to prevent infinite crash loops.
        """
        if not redis_manager.is_available:
            logger.warning("⚠️ Redis not available, RPC listener not started")
            return

        worker_channel = f"ws:rpc:{self.worker_id}"
        logger.info(
            f"🎧 RPC LISTENER STARTED - Listening on '{worker_channel}' channel "
            f"for direct-routed SDK invocations"
        )

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
                        while True:
                            try:
                                # Use BLPOP to wait for messages on worker-specific queue
                                # timeout=1 means check every second (allows for graceful shutdown)
                                result = await redis_manager.client.blpop(worker_channel, timeout=1)

                                if result:
                                    # result is a tuple: (channel, message)
                                    _, message = result
                                    try:
                                        request = json.loads(message)
                                        await self._handle_rpc_request(request)
                                    except Exception as e:
                                        logger.error(
                                            f"Error handling RPC request: {e}", exc_info=True
                                        )
                            except asyncio.CancelledError:
                                logger.info("RPC listener cancelled, shutting down")
                                raise
                            except Exception as e:
                                logger.error(f"Error in RPC listener loop: {e}", exc_info=True)
                                # Continue listening despite errors

                    except asyncio.CancelledError:
                        raise  # Re-raise cancellation
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
            logger.debug("RPC listener shutdown complete")

    async def _publish_error_response(self, request_id: str, key: str, details: str) -> None:
        """
        Publish error response to RPC client.

        Args:
            request_id: RPC request ID
            key: Connection key
            details: Error details
        """
        if not redis_manager.is_available:
            logger.error("Cannot publish error - Redis manager not available")
            return

        try:
            error_response = {
                "error": "send_failed",
                "details": details,
            }
            response_channel = f"ws:rpc:response:{request_id}"
            await redis_manager.client.publish(response_channel, json.dumps(error_response))
            logger.debug(f"Published error response for {request_id}")
        except Exception as e:
            logger.error(f"Failed to publish error response: {e}")

    async def _register_worker_for_connection(self, connection_id: str) -> None:
        """
        Register this worker as handler for a connection.

        Args:
            connection_id: Connection key (project_id:environment)
        """
        routing_key = f"ws:routing:{connection_id}"
        try:
            await redis_manager.client.setex(
                routing_key,
                300,  # 5 minute TTL
                self.worker_id,
            )
            logger.debug(f"Registered worker {self.worker_id} for connection {connection_id}")
        except Exception as e:
            logger.error(f"Failed to register worker for connection {connection_id}: {e}")

    async def _unregister_worker_for_connection(self, connection_id: str) -> None:
        """
        Remove worker registration for a connection.

        Args:
            connection_id: Connection key (project_id:environment)
        """
        routing_key = f"ws:routing:{connection_id}"
        try:
            await redis_manager.client.delete(routing_key)
            logger.debug(f"Unregistered worker for connection {connection_id}")
        except Exception as e:
            logger.warning(f"Failed to unregister worker for connection {connection_id}: {e}")

    async def _handle_rpc_request(self, request: Dict[str, Any]) -> None:
        """
        Handle RPC request from worker.

        With direct routing, this worker is guaranteed to have the connection.
        If somehow the connection is missing, publish an error response.

        Args:
            request: RPC request with keys: request_id, project_id, environment,
                    function_name, inputs
        """
        # Extract request parameters
        request_id = request.get("request_id")
        project_id = request.get("project_id")
        environment = request.get("environment")
        function_name = request.get("function_name")
        inputs = request.get("inputs", {})

        logger.debug(f"RPC request received: {request_id} - {function_name}")

        # Direct routing guarantees we have the connection
        key = self.get_connection_key(project_id, environment)

        if key not in self._connections:
            # This shouldn't happen with direct routing, but handle gracefully
            logger.error(
                f"Worker routing mismatch: received RPC for {key} but connection not found. "
                f"Race condition between routing registration and connection state."
            )
            await self._publish_error_response(
                request_id, key, f"Worker routing mismatch for {key}"
            )
            return

        # Forward request to SDK
        await self._forward_to_sdk(request_id, key, function_name, inputs)

    async def _forward_to_sdk(
        self, request_id: str, key: str, function_name: str, inputs: Dict[str, Any]
    ) -> None:
        """
        Forward RPC request to SDK via local WebSocket connection.

        Args:
            request_id: RPC request ID
            key: Connection key
            function_name: SDK function to invoke
            inputs: Function inputs
        """
        websocket = self._connections[key]
        message = ExecuteTestMessage(
            test_run_id=request_id, function_name=function_name, inputs=inputs
        )

        try:
            logger.info(f"Forwarding RPC request {request_id} ({function_name}) to SDK")
            await websocket.send_json(message.model_dump())
        except Exception as e:
            logger.error(f"Error forwarding RPC request {request_id}: {e}")

            # Connection is stale - clean it up
            await self._cleanup_stale_connection(key)

            # Publish error response
            await self._publish_error_response(
                request_id, key, f"Failed to forward to WebSocket: {str(e)}"
            )

    async def _cleanup_stale_connection(self, key: str) -> None:
        """
        Remove stale connection from local dict and Redis.

        Args:
            key: Connection key
        """
        if key in self._connections:
            logger.warning(f"Removing stale WebSocket connection: {key}")
            del self._connections[key]

        # Also remove from Redis
        if redis_manager.is_available:
            try:
                redis_key = f"ws:connection:{key}"
                await redis_manager.client.delete(redis_key)
                logger.debug(f"Removed stale connection from Redis: {redis_key}")
            except Exception as redis_err:
                logger.warning(f"Failed to remove stale connection from Redis: {redis_err}")


# Global connection manager instance
connection_manager = ConnectionManager()
