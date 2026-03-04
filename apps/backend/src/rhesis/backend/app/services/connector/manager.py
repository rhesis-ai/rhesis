"""Connection manager for WebSocket connections with SDKs."""

import asyncio
import json
import logging
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
    ExecuteMetricMessage,
    ExecuteTestMessage,
    FunctionMetadata,
    MetricMetadata,
    RegisterMessage,
    WebSocketConnectionContext,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with SDK clients."""

    def __init__(self):
        """Initialize connection manager."""
        # Generate unique worker ID using hostname + UUID
        # Format: backend@hostname-uuid (e.g., backend@server1-a1b2c3d4)
        # UUID ensures true uniqueness even with rapid process restarts
        # Note: We don't use CELERY_WORKER_NAME as it's only set for Celery workers,
        # not backend processes. Backend and Celery are separate process types.
        import socket
        import uuid

        short_uuid = str(uuid.uuid4())[:8]  # First 8 chars sufficient for uniqueness
        self.worker_id = f"backend@{socket.gethostname()}-{short_uuid}"

        # --- Transport layer (connection-id keyed) ---
        self._connections: Dict[str, WebSocket] = {}
        self._contexts: Dict[str, WebSocketConnectionContext] = {}

        # --- Routing layer (project:env keyed) ---
        # Maps project:env -> connection_id for dispatch
        self._project_routing: Dict[str, str] = {}
        # Reverse: connection_id -> set of project:env keys
        self._connection_projects: Dict[str, set] = {}

        # Store function registries: {project_id:environment: [FunctionMetadata]}
        self._registries: Dict[str, List[FunctionMetadata]] = {}

        # Store metric registries: {project_id:environment: [MetricMetadata]}
        self._metric_registries: Dict[str, List[MetricMetadata]] = {}

        # --- Result layer ---
        self._test_results: Dict[str, Dict[str, Any]] = {}
        self._metric_results: Dict[str, Dict[str, Any]] = {}
        # Events for instant notification when results arrive
        self._result_events: Dict[str, asyncio.Event] = {}

        # Cancelled/timed-out run tracking (prevents storing late results)
        self._cancelled_tests: OrderedDict = OrderedDict()
        self._cancelled_metrics: OrderedDict = OrderedDict()

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
            except asyncio.CancelledError:
                # Expected during shutdown, not an error
                pass
            except Exception as e:
                logger.error(f"Background task failed: {e}", exc_info=True)

        task.add_done_callback(log_exception)
        return task

    async def connect(
        self,
        connection_id: str,
        context: WebSocketConnectionContext,
        websocket: WebSocket,
    ) -> None:
        """Register a new WebSocket connection.

        Stores the websocket and its immutable context.  A connection-level
        Redis key (``ws:conn:{connection_id}``) is created immediately so
        that other instances can discover this connection for non-project
        scoped operations (e.g. metrics).  Project routing is set up later
        when a ``register`` message arrives.

        Args:
            connection_id: Unique identifier for this connection.
            context: Immutable authentication context.
            websocket: The accepted WebSocket.
        """
        self._connections[connection_id] = websocket
        self._contexts[connection_id] = context
        self._connection_projects[connection_id] = set()

        if redis_manager.is_available:
            try:
                await redis_manager.client.setex(f"ws:conn:{connection_id}", 30, self.worker_id)
            except Exception as e:
                logger.warning(f"Failed to set Redis conn key for {connection_id}: {e}")

        heartbeat = self._track_background_task(self._heartbeat_loop(connection_id))
        self._heartbeat_tasks[connection_id] = heartbeat

        logger.info(f"Connected: connection_id={connection_id}")

    def disconnect_by_connection_id(self, connection_id: str) -> None:
        """Disconnect and clean up all state for a connection.

        Cancels the heartbeat, removes the connection-level Redis key,
        and cleans up every project:environment routing entry that was
        registered through it.
        """
        logger.info(f"Disconnected: connection_id={connection_id}")

        # Cancel the per-connection heartbeat first
        heartbeat = self._heartbeat_tasks.pop(connection_id, None)
        if heartbeat and not heartbeat.done():
            heartbeat.cancel()

        self._connections.pop(connection_id, None)
        self._contexts.pop(connection_id, None)

        project_keys = self._connection_projects.pop(connection_id, set())
        for pk in project_keys:
            self._cleanup_project_routing(pk)

        if redis_manager.is_available:
            try:
                self._track_background_task(
                    self._cleanup_redis_for_connection(connection_id, project_keys)
                )
            except Exception as e:
                logger.warning(f"Failed to schedule Redis cleanup for {connection_id}: {e}")

    def _cleanup_project_routing(self, project_env_key: str) -> None:
        """Remove project:env routing and associated registries.

        Args:
            project_env_key: The ``project_id:environment`` key.
        """
        self._project_routing.pop(project_env_key, None)
        self._registries.pop(project_env_key, None)
        self._metric_registries.pop(project_env_key, None)

    async def _cleanup_redis_for_connection(self, connection_id: str, project_keys: set) -> None:
        """Remove all Redis keys for a disconnected connection.

        Deletes the connection-level key and all project routing keys.
        """
        try:
            await redis_manager.client.delete(f"ws:conn:{connection_id}")
            for pk in project_keys:
                await redis_manager.client.delete(f"ws:routing:{pk}")
            logger.debug(
                f"Cleaned Redis for connection {connection_id} ({len(project_keys)} project key(s))"
            )
        except Exception as e:
            logger.warning(f"Failed to clean Redis for {connection_id}: {e}")

    async def _heartbeat_loop(self, connection_id: str) -> None:
        """Refresh Redis keys for a connection and its project routes.

        Runs every 10 s while the connection is alive.  Refreshes the
        connection-level key (``ws:conn:{connection_id}``) and every
        project routing key registered through this connection.
        """
        try:
            while connection_id in self._connections:
                await asyncio.sleep(10)

                if connection_id not in self._connections:
                    break

                if not redis_manager.is_available:
                    continue

                try:
                    await redis_manager.client.setex(
                        f"ws:conn:{connection_id}",
                        30,
                        self.worker_id,
                    )
                    for pk in self._connection_projects.get(connection_id, set()):
                        await redis_manager.client.setex(
                            f"ws:routing:{pk}",
                            30,
                            self.worker_id,
                        )
                    logger.debug(f"Heartbeat refreshed for {connection_id}")
                except Exception as e:
                    logger.warning(f"Heartbeat failed for {connection_id}: {e}")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in heartbeat for {connection_id}: {e}")

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

    def register_metrics(
        self, project_id: str, environment: str, metrics: List[MetricMetadata]
    ) -> None:
        """
        Register metrics for a project.

        Args:
            project_id: Project identifier
            environment: Environment name
            metrics: List of metric metadata
        """
        key = self.get_connection_key(project_id, environment)
        self._metric_registries[key] = metrics
        logger.info(f"Registered {len(metrics)} metric(s) for {key}")

    def has_local_route(self, project_id: str, environment: str) -> bool:
        """Check whether this instance has a local route for a project:env."""
        key = self.get_connection_key(project_id, environment)
        conn_id = self._project_routing.get(key)
        return conn_id is not None and conn_id in self._connections

    def _resolve_websocket(self, project_id: str, environment: str) -> Optional[WebSocket]:
        """Resolve the WebSocket for a project:env via the routing table.

        Returns None if no local connection is registered for this
        project:environment.
        """
        key = self.get_connection_key(project_id, environment)
        conn_id = self._project_routing.get(key)
        if not conn_id:
            return None
        return self._connections.get(conn_id)

    async def send_test_request(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        inputs: Dict[str, Any],
    ) -> bool:
        """Send test execution request to SDK via project:env routing.

        Returns:
            True if message sent successfully, False otherwise.
        """
        websocket = self._resolve_websocket(project_id, environment)
        if not websocket:
            key = self.get_connection_key(project_id, environment)
            logger.debug(f"No local WebSocket for {key} - may be on another instance")
            return False

        message = ExecuteTestMessage(
            test_run_id=test_run_id,
            function_name=function_name,
            inputs=inputs,
        )

        try:
            await websocket.send_json(message.model_dump())
            key = self.get_connection_key(project_id, environment)
            logger.info(f"Sent test request to {key}: {function_name}")
            return True
        except Exception as e:
            key = self.get_connection_key(project_id, environment)
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
        """Send test request and wait for the result using an asyncio.Event.

        Returns:
            Result dictionary or an error dict on timeout / send failure.
        """
        event = asyncio.Event()
        self._result_events[test_run_id] = event

        try:
            sent = await self.send_test_request(
                project_id,
                environment,
                test_run_id,
                function_name,
                inputs,
            )
            if not sent:
                return {
                    "error": "send_failed",
                    "details": "Failed to send message to SDK",
                }

            await asyncio.wait_for(event.wait(), timeout=timeout)

            result = self._test_results.get(test_run_id)
            if result:
                logger.debug(f"Received SDK result for {test_run_id}")
                self.cleanup_test_result(test_run_id)
                return result

            return {
                "error": "send_failed",
                "details": "Event fired but no result stored",
            }

        except asyncio.TimeoutError:
            self.cleanup_test_result(test_run_id)
            logger.error(f"Timeout waiting for SDK result: {test_run_id}")
            return {"error": "timeout"}

        finally:
            self._result_events.pop(test_run_id, None)

    # --- Metric dispatch (connection-scoped, no project:env needed) ---

    async def send_metric_by_connection(
        self,
        connection_id: str,
        metric_run_id: str,
        metric_name: str,
        inputs: Dict[str, Any],
    ) -> bool:
        """Send a metric request directly to a connection_id.

        Returns True if sent, False if the connection is not local.
        """
        websocket = self._connections.get(connection_id)
        if not websocket:
            logger.debug(f"No local WebSocket for connection {connection_id}")
            return False

        message = ExecuteMetricMessage(
            metric_run_id=metric_run_id,
            metric_name=metric_name,
            inputs=inputs,
        )

        try:
            await websocket.send_json(message.model_dump())
            logger.info(f"Sent metric request to conn:{connection_id}: {metric_name}")
            return True
        except Exception as e:
            logger.error(f"Error sending metric to conn:{connection_id}: {e}")
            return False

    async def send_and_await_metric_by_connection(
        self,
        connection_id: str,
        metric_run_id: str,
        metric_name: str,
        inputs: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Send metric request by connection_id and await the result.

        Returns:
            Result dictionary or an error dict on timeout / send failure.
        """
        event = asyncio.Event()
        self._result_events[metric_run_id] = event

        try:
            sent = await self.send_metric_by_connection(
                connection_id,
                metric_run_id,
                metric_name,
                inputs,
            )
            if not sent:
                return {
                    "error": "send_failed",
                    "details": (
                        f"Failed to send metric message to SDK (connection {connection_id})"
                    ),
                }

            await asyncio.wait_for(event.wait(), timeout=timeout)

            result = self._metric_results.get(metric_run_id)
            if result:
                logger.debug(f"Received metric result for {metric_run_id}")
                self.cleanup_metric_result(metric_run_id)
                return result

            return {
                "error": "send_failed",
                "details": "Event fired but no metric result stored",
            }

        except asyncio.TimeoutError:
            self.cleanup_metric_result(metric_run_id)
            logger.error(f"Timeout waiting for metric result: {metric_run_id}")
            return {"error": "timeout"}

        finally:
            self._result_events.pop(metric_run_id, None)

    def _resolve_test_result(self, test_run_id: str, result: Dict[str, Any]) -> None:
        """Store a test result and wake up any waiting coroutine."""
        if test_run_id in self._cancelled_tests:
            logger.warning(f"Ignoring late result for cancelled test run: {test_run_id}")
            return

        logger.info(
            f"Received test result from SDK: {test_run_id} "
            f"(status: {result.get('status', 'unknown')})"
        )

        self._test_results[test_run_id] = result

        # Wake up the local waiter (instant notification)
        event = self._result_events.get(test_run_id)
        if event:
            event.set()

        # Publish to Redis for cross-instance waiters
        if redis_manager.is_available:
            try:
                self._track_background_task(self._publish_rpc_response(test_run_id, result))
            except Exception as e:
                logger.error(
                    f"Failed to schedule RPC response publish: {e}",
                    exc_info=True,
                )

    async def _publish_rpc_response(self, run_id: str, result: Dict[str, Any]) -> None:
        """Publish RPC response to Redis for cross-instance waiters."""
        try:
            channel = f"ws:rpc:response:{run_id}"
            await redis_manager.client.publish(channel, json.dumps(result))
            logger.debug(f"Published RPC response: {run_id}")
        except Exception as e:
            logger.error(
                f"Failed to publish RPC response for {run_id}: {e}",
                exc_info=True,
            )

    def _resolve_metric_result(self, metric_run_id: str, result: Dict[str, Any]) -> None:
        """Store a metric result and wake up any waiting coroutine."""
        if metric_run_id in self._cancelled_metrics:
            logger.warning(f"Ignoring late result for cancelled metric run: {metric_run_id}")
            return

        logger.info(
            f"Received metric result from SDK: {metric_run_id} "
            f"(status: {result.get('status', 'unknown')})"
        )
        self._metric_results[metric_run_id] = result

        event = self._result_events.get(metric_run_id)
        if event:
            event.set()

        if redis_manager.is_available:
            try:
                self._track_background_task(self._publish_rpc_response(metric_run_id, result))
            except Exception as e:
                logger.error(
                    f"Failed to publish metric RPC response: {e}",
                    exc_info=True,
                )

    def get_metric_result(self, metric_run_id: str) -> Optional[Dict[str, Any]]:
        """Get metric result if available (non-destructive)."""
        return self._metric_results.get(metric_run_id)

    def cleanup_metric_result(self, metric_run_id: str) -> None:
        """
        Remove a metric result from memory and mark as cancelled to prevent memory leaks.

        Should be called when a metric times out, errors, or is no longer needed.
        Marking as cancelled prevents late-arriving results from being stored.

        Args:
            metric_run_id: Metric run identifier to clean up
        """
        # Mark as cancelled to prevent late results from being stored
        self._cancelled_metrics[metric_run_id] = True

        # Remove any existing result
        if metric_run_id in self._metric_results:
            del self._metric_results[metric_run_id]
            logger.debug(f"Cleaned up metric result: {metric_run_id}")
        else:
            logger.debug(f"Marked metric run as cancelled: {metric_run_id}")

        # Periodic cleanup if the cancelled set grows too large
        if len(self._cancelled_metrics) > 10000:
            self._cleanup_old_cancelled_metrics()

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

    def _cleanup_old_cancelled_metrics(self) -> None:
        """
        Clean up old cancelled metric entries to prevent unbounded memory growth.

        Keeps only the most recent 5000 entries. This is called when the dict
        grows beyond 10000 entries to trim it back down to a reasonable size.
        """
        cancelled_items = list(self._cancelled_metrics.items())
        removed_count = len(cancelled_items) - 5000
        self._cancelled_metrics = OrderedDict(cancelled_items[-5000:])
        logger.info(f"Cleaned up old cancelled metrics. Removed {removed_count} entries, kept 5000")

    def get_connection_status(self, project_id: str, environment: str) -> ConnectionStatus:
        """Get connection status for a project:environment."""
        key = self.get_connection_key(project_id, environment)
        connected = key in self._project_routing
        functions = self._registries.get(key, [])

        return ConnectionStatus(
            project_id=project_id,
            environment=environment,
            connected=connected,
            functions=functions,
        )

    async def is_connected(self, project_id: str, environment: str) -> bool:
        """Check if a project:environment has an active connection.

        Checks local routing table first, then the ``ws:routing:`` key
        in Redis for connections on other instances.
        """
        key = self.get_connection_key(project_id, environment)

        if key in self._project_routing:
            return True

        if redis_manager.is_available:
            try:
                exists = await redis_manager.client.exists(f"ws:routing:{key}")
                return exists > 0
            except Exception as e:
                logger.warning(f"Failed to check Redis for routing {key}: {e}")

        return False

    async def handle_registration(
        self, project_id: str, environment: str, message: Dict[str, Any]
    ) -> None:
        """
        Handle registration message from SDK - update local registries.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Registration message
        """
        try:
            reg_msg = RegisterMessage(**message)
            self.register_functions(project_id, environment, reg_msg.functions)
            if reg_msg.metrics:
                self.register_metrics(project_id, environment, reg_msg.metrics)
        except Exception as e:
            logger.error(f"Error handling registration: {e}")

    def _resolve_project_for_connection(self, connection_id: str) -> tuple:
        """Return (project_id, environment) for a registered connection.

        Returns empty strings if the connection has no project routing.
        """
        project_keys = self._connection_projects.get(connection_id, set())
        if project_keys:
            pk = next(iter(project_keys))
            if ":" in pk:
                return pk.split(":", 1)
        return ("", "")

    async def handle_message(
        self,
        connection_id: str = "",
        message: Dict[str, Any] = None,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Handle incoming WebSocket message from SDK.

        For ``register`` messages the project_id/environment are taken
        from the message payload and authorized against the connection's
        immutable context. For other messages they are resolved from
        the routing table.

        Returns:
            Response message to send back, or None if no response needed.
        """
        if message is None:
            message = {}

        message_type = message.get("type")

        msg_project_id = message.get("project_id", "")
        msg_environment = message.get("environment", "")

        if not msg_project_id and connection_id:
            msg_project_id, msg_environment = self._resolve_project_for_connection(connection_id)

        logger.info(
            f"Processing message type: {message_type} "
            f"from connection={connection_id or 'rpc'} "
            f"({msg_project_id}:{msg_environment})"
        )

        if message_type == "register":
            reg_project_id = message.get("project_id", "")
            reg_environment = message.get("environment", "")

            if connection_id and reg_project_id and reg_environment:
                authorized = await self._authorize_and_register(
                    connection_id=connection_id,
                    project_id=reg_project_id,
                    environment=reg_environment,
                    db=db,
                    organization_id=organization_id,
                    user_id=user_id,
                )
                if not authorized:
                    return {
                        "type": "registered",
                        "status": "error",
                        "error": (f"Project {reg_project_id} not found or not accessible"),
                    }

            await self.handle_registration(reg_project_id, reg_environment, message)
            return await message_handler.handle_register_message(
                project_id=reg_project_id,
                environment=reg_environment,
                message=message,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
            )

        elif message_type == "test_result":
            test_run_id = message.get("test_run_id")
            if test_run_id:
                self._resolve_test_result(test_run_id, message)

            await message_handler.handle_test_result_message(
                msg_project_id, msg_environment, message, db
            )
            return None

        elif message_type == "metric_result":
            metric_run_id = message.get("metric_run_id")
            if metric_run_id:
                self._resolve_metric_result(metric_run_id, message)
            return None

        elif message_type == "pong":
            await message_handler.handle_pong_message(msg_project_id, msg_environment)
            return None

        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None

    async def _authorize_and_register(
        self,
        connection_id: str,
        project_id: str,
        environment: str,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Authorize the project and add routing for this connection.

        Validates that the project exists and belongs to the connection's
        organization (derived from the immutable authentication context,
        not from the message). On success, populates the routing table
        and sets up Redis keys.

        Returns:
            True if authorized and registered, False otherwise.
        """
        context = self._contexts.get(connection_id)
        if not context:
            logger.error(f"No context for connection {connection_id}")
            return False

        # Authorization: use org/user from immutable connection context
        auth_org_id = context.organization_id
        auth_user_id = context.user_id

        if db and auth_org_id and auth_user_id:
            from uuid import UUID

            from rhesis.backend.app import crud

            try:
                project_uuid = UUID(project_id)
            except ValueError:
                logger.error(f"Invalid project_id format: {project_id}")
                return False

            project = crud.get_project(db, project_uuid, auth_org_id, auth_user_id)
            if not project:
                logger.error(
                    f"Project {project_id} not found or not accessible for org {auth_org_id}"
                )
                return False

            logger.info(
                f"Project authorized: {project.name} ({project_id}) for connection {connection_id}"
            )

        # Populate routing table
        key = self.get_connection_key(project_id, environment)
        self._project_routing[key] = connection_id
        self._connection_projects.setdefault(connection_id, set()).add(key)

        # Set the project routing key in Redis; the per-connection
        # heartbeat (started in connect()) will keep it alive.
        if redis_manager.is_available:
            try:
                await redis_manager.client.setex(f"ws:routing:{key}", 30, self.worker_id)
            except Exception as e:
                logger.error(f"Failed to set Redis routing for {key}: {e}")

        return True

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

    async def _handle_rpc_request(self, request: Dict[str, Any]) -> None:
        """Handle RPC request from a Celery worker.

        Supports two dispatch modes:
        - **project:env** — test execution and project-scoped metrics
        - **connection_id** — connection-scoped metrics (no project needed)

        The dispatch mode is determined by the presence of ``connection_id``
        in the request payload.
        """
        request_id = request.get("request_id")
        request_type = request.get("request_type", "execute_test")
        inputs = request.get("inputs", {})
        name = request.get("function_name") or request.get("metric_name", "")
        logger.debug(f"RPC request received: {request_id} - {name} (type={request_type})")

        # Connection-scoped dispatch (metrics by connection_id)
        conn_id = request.get("connection_id")
        if conn_id:
            websocket = self._connections.get(conn_id)
            if not websocket:
                logger.error(f"Connection {conn_id} not found for RPC {request_id}")
                await self._publish_error_response(
                    request_id,
                    conn_id,
                    f"Connection {conn_id} not found",
                )
                return
            await self._forward_metric_to_sdk(request_id, conn_id, websocket, name, inputs)
            return

        # Project-scoped dispatch (resolves connection locally)
        project_id = request.get("project_id")
        environment = request.get("environment")
        key = self.get_connection_key(project_id, environment)
        routed_conn_id = self._project_routing.get(key)

        if not routed_conn_id or routed_conn_id not in self._connections:
            logger.error(f"Worker routing mismatch: RPC for {key} but connection not found.")
            await self._publish_error_response(
                request_id, key, f"Worker routing mismatch for {key}"
            )
            return

        websocket = self._connections[routed_conn_id]

        if request_type == "execute_metric":
            await self._forward_metric_to_sdk(request_id, key, websocket, name, inputs)
        else:
            await self._forward_to_sdk(request_id, key, websocket, name, inputs)

    async def _forward_to_sdk(
        self,
        request_id: str,
        project_env_key: str,
        websocket: WebSocket,
        function_name: str,
        inputs: Dict[str, Any],
    ) -> None:
        """Forward test RPC request to SDK via WebSocket."""
        message = ExecuteTestMessage(
            test_run_id=request_id,
            function_name=function_name,
            inputs=inputs,
        )

        try:
            logger.info(f"Forwarding RPC request {request_id} ({function_name}) to SDK")
            await websocket.send_json(message.model_dump())
        except Exception as e:
            logger.error(f"Error forwarding RPC request {request_id}: {e}")
            await self._cleanup_stale_routing(project_env_key)
            await self._publish_error_response(
                request_id,
                project_env_key,
                f"Failed to forward to WebSocket: {e}",
            )

    async def _forward_metric_to_sdk(
        self,
        request_id: str,
        project_env_key: str,
        websocket: WebSocket,
        metric_name: str,
        inputs: Dict[str, Any],
    ) -> None:
        """Forward metric RPC request to SDK via WebSocket."""
        message = ExecuteMetricMessage(
            metric_run_id=request_id,
            metric_name=metric_name,
            inputs=inputs,
        )

        try:
            logger.info(f"Forwarding metric RPC request {request_id} ({metric_name}) to SDK")
            await websocket.send_json(message.model_dump())
        except Exception as e:
            logger.error(f"Error forwarding metric RPC request {request_id}: {e}")
            await self._cleanup_stale_routing(project_env_key)
            await self._publish_error_response(
                request_id,
                project_env_key,
                f"Failed to forward metric to WebSocket: {e}",
            )

    async def _cleanup_stale_routing(self, project_env_key: str) -> None:
        """Remove stale project routing and associated Redis keys.

        Called when a send fails, indicating the underlying connection
        is broken.
        """
        logger.warning(f"Removing stale routing: {project_env_key}")

        self._cleanup_project_routing(project_env_key)

        if redis_manager.is_available:
            try:
                await redis_manager.client.delete(f"ws:routing:{project_env_key}")
            except Exception as e:
                logger.warning(f"Failed to remove stale routing key: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()
