"""Connection manager for WebSocket connections with SDKs."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.dispatcher import Dispatcher
from rhesis.backend.app.services.connector.handler import message_handler
from rhesis.backend.app.services.connector.redis_client import redis_manager
from rhesis.backend.app.services.connector.result_store import ResultStore
from rhesis.backend.app.services.connector.rpc_bridge import RpcBridge
from rhesis.backend.app.services.connector.schemas import (
    ConnectionStatus,
    FunctionMetadata,
    MetricMetadata,
    RegisterMessage,
    WebSocketConnectionContext,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with SDK clients.

    Acts as a facade that owns shared transport/routing state and
    delegates result storage, dispatch, and RPC bridging to focused
    collaborators:

    - :class:`ResultStore` -- test/metric result storage & cancellation
    - :class:`Dispatcher` -- send requests and await results
    - :class:`RpcBridge` -- Redis-based cross-instance RPC listener
    """

    # Send an application-level ping every N heartbeat ticks (10 s each).
    # 6 ticks = ~60 s, well within the default 300 s idle timeout.
    _PING_INTERVAL_TICKS = int(os.getenv("WS_PING_INTERVAL_TICKS", "6"))

    def __init__(self):
        """Initialize connection manager."""
        import socket
        import uuid

        short_uuid = str(uuid.uuid4())[:8]
        self.worker_id = f"backend@{socket.gethostname()}-{short_uuid}"

        # --- Transport layer (connection-id keyed) ---
        self._connections: Dict[str, WebSocket] = {}
        self._contexts: Dict[str, WebSocketConnectionContext] = {}

        # --- Routing layer (project:env keyed) ---
        self._project_routing: Dict[str, List[str]] = {}
        self._routing_counter: Dict[str, int] = {}
        self._connection_projects: Dict[str, set] = {}

        # --- Registry layer ---
        self._registries: Dict[str, List[FunctionMetadata]] = {}
        self._metric_registries: Dict[str, List[MetricMetadata]] = {}

        # --- Background task tracking ---
        self._background_tasks: set = set()
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

        # --- Collaborators ---
        self._result_store = ResultStore(
            track_background_task=self._track_background_task,
        )
        self._dispatcher = Dispatcher(
            connections=self._connections,
            resolve_route=self._next_route,
            result_store=self._result_store,
            get_connection_key=self.get_connection_key,
            remove_connection_route=self._remove_connection_route,
        )
        self._rpc_bridge = RpcBridge(
            worker_id=self.worker_id,
            connections=self._connections,
            resolve_route=self._next_route,
            get_connection_key=self.get_connection_key,
            remove_connection_route=self._remove_connection_route,
        )

    # ==================================================================
    # Key helpers
    # ==================================================================

    def get_connection_key(self, project_id: str, environment: str) -> str:
        """Generate a normalized ``project_id:environment`` key."""
        environment = environment.lower()
        return f"{project_id}:{environment}"

    def _next_route(self, project_id: str, environment: str) -> Optional[str]:
        """Round-robin select a live connection for a project:env.

        Prunes dead connections from the pool on each call.
        Returns ``None`` when no live connection exists.
        """
        key = self.get_connection_key(project_id, environment)
        pool = self._project_routing.get(key)
        if not pool:
            return None

        live = [c for c in pool if c in self._connections]
        if not live:
            del self._project_routing[key]
            self._routing_counter.pop(key, None)
            return None

        if len(live) != len(pool):
            self._project_routing[key] = live

        idx = self._routing_counter.get(key, 0) % len(live)
        self._routing_counter[key] = (idx + 1) % len(live)
        return live[idx]

    def _remove_connection_route(self, key: str, connection_id: str) -> None:
        """Remove one connection from a project:env routing pool.

        Also removes the key from the connection's project set so that
        the heartbeat no longer refreshes the Redis routing key for a
        connection that has been evicted from the pool.

        When the pool becomes empty the routing entry, registries,
        and round-robin counter are cleaned up.
        """
        pool = self._project_routing.get(key)
        if pool is None:
            return
        if connection_id in pool:
            pool.remove(connection_id)

        projects = self._connection_projects.get(connection_id)
        if projects is not None:
            projects.discard(key)

        if not pool:
            del self._project_routing[key]
            self._registries.pop(key, None)
            self._metric_registries.pop(key, None)
            self._routing_counter.pop(key, None)

    # ==================================================================
    # Background task tracking
    # ==================================================================

    def _track_background_task(self, coro) -> asyncio.Task:
        """Create and track a background task to prevent silent failures."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        def log_exception(t: asyncio.Task) -> None:
            try:
                t.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Background task failed: {e}", exc_info=True)

        task.add_done_callback(log_exception)
        return task

    # ==================================================================
    # Connection lifecycle
    # ==================================================================

    async def connect(
        self,
        connection_id: str,
        context: WebSocketConnectionContext,
        websocket: WebSocket,
    ) -> None:
        """Register a new WebSocket connection.

        Stores the websocket and its immutable context.  A connection-level
        Redis key is created immediately; project routing is set up later
        when a ``register`` message arrives.
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
        """Disconnect and clean up all state for a connection."""
        logger.info(f"Disconnected: connection_id={connection_id}")

        heartbeat = self._heartbeat_tasks.pop(connection_id, None)
        if heartbeat and not heartbeat.done():
            heartbeat.cancel()

        self._connections.pop(connection_id, None)
        self._contexts.pop(connection_id, None)

        project_keys = self._connection_projects.pop(connection_id, set())
        for pk in project_keys:
            self._remove_connection_route(pk, connection_id)

        if redis_manager.is_available:
            try:
                self._track_background_task(
                    self._cleanup_redis_for_connection(connection_id, project_keys)
                )
            except Exception as e:
                logger.warning(f"Failed to schedule Redis cleanup for {connection_id}: {e}")

    async def _cleanup_redis_for_connection(self, connection_id: str, project_keys: set) -> None:
        """Remove Redis keys for a disconnected connection.

        The ``ws:routing:{pk}`` key is only deleted when no other
        connections remain in the local pool for that route (to avoid
        wiping a route that is still served by another worker).
        """
        try:
            await redis_manager.client.delete(f"ws:conn:{connection_id}")
            for pk in project_keys:
                if not self._project_routing.get(pk):
                    await redis_manager.client.delete(f"ws:routing:{pk}")
            logger.debug(
                f"Cleaned Redis for connection {connection_id} ({len(project_keys)} project key(s))"
            )
        except Exception as e:
            logger.warning(f"Failed to clean Redis for {connection_id}: {e}")

    async def _heartbeat_loop(self, connection_id: str) -> None:
        """Refresh Redis keys and send application-level pings.

        Runs every 10 s while the connection is alive.  On each tick it:

        1. Refreshes the connection-level Redis key and every project
           routing key registered through this connection.
        2. Every ``_PING_INTERVAL_TICKS`` ticks (default 6 = ~60 s) sends
           an application-level ``{"type": "ping"}`` to the SDK so that
           the resulting ``pong`` text frame resets the idle-timeout
           counter in ``_message_loop``.
        """
        ticks_since_ping = 0
        try:
            while connection_id in self._connections:
                await asyncio.sleep(10)

                if connection_id not in self._connections:
                    break

                # --- Application-level ping ---
                ticks_since_ping += 1
                if ticks_since_ping >= self._PING_INTERVAL_TICKS:
                    ticks_since_ping = 0
                    websocket = self._connections.get(connection_id)
                    if websocket:
                        try:
                            await websocket.send_json({"type": "ping"})
                            logger.debug(f"Ping sent to {connection_id}")
                        except Exception as e:
                            logger.warning(f"Failed to send ping to {connection_id}: {e}")

                # --- Redis key refresh ---
                if not redis_manager.is_available:
                    continue

                try:
                    await redis_manager.client.setex(
                        f"ws:conn:{connection_id}",
                        30,
                        self.worker_id,
                    )
                    for pk in self._connection_projects.get(connection_id, set()):
                        # Only refresh the routing key if this connection
                        # is the first entry in the pool, avoiding N
                        # redundant SETEX calls when N workers share
                        # the same project:env route.
                        pool = self._project_routing.get(pk)
                        if pool and pool[0] == connection_id:
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

    # ==================================================================
    # Registry management
    # ==================================================================

    def register_functions(
        self,
        project_id: str,
        environment: str,
        functions: List[FunctionMetadata],
    ) -> None:
        """Register functions for a project."""
        key = self.get_connection_key(project_id, environment)
        self._registries[key] = functions
        logger.info(f"Registered {len(functions)} function(s) for {key}")

    def register_metrics(
        self,
        project_id: str,
        environment: str,
        metrics: List[MetricMetadata],
    ) -> None:
        """Register metrics for a project."""
        key = self.get_connection_key(project_id, environment)
        self._metric_registries[key] = metrics
        logger.info(f"Registered {len(metrics)} metric(s) for {key}")

    async def handle_registration(
        self, project_id: str, environment: str, message: Dict[str, Any]
    ) -> None:
        """Handle registration message from SDK -- update local registries."""
        try:
            reg_msg = RegisterMessage(**message)
            self.register_functions(project_id, environment, reg_msg.functions)
            if reg_msg.metrics:
                self.register_metrics(project_id, environment, reg_msg.metrics)
        except Exception as e:
            logger.error(f"Error handling registration: {e}")

    # ==================================================================
    # Status queries
    # ==================================================================

    def has_local_route(self, project_id: str, environment: str) -> bool:
        """Check whether this instance has a local route for a project:env."""
        key = self.get_connection_key(project_id, environment)
        pool = self._project_routing.get(key)
        return bool(pool) and any(c in self._connections for c in pool)

    def get_connection_status(self, project_id: str, environment: str) -> ConnectionStatus:
        """Get connection status for a project:environment."""
        key = self.get_connection_key(project_id, environment)
        pool = self._project_routing.get(key)
        connected = bool(pool) and any(c in self._connections for c in pool)
        functions = self._registries.get(key, [])

        return ConnectionStatus(
            project_id=project_id,
            environment=environment,
            connected=connected,
            functions=functions,
        )

    async def is_connected(self, project_id: str, environment: str) -> bool:
        """Check if a project:environment has an active connection.

        Checks local routing table first (with liveness verification),
        then Redis for connections on other instances.
        """
        if self.has_local_route(project_id, environment):
            return True

        if redis_manager.is_available:
            key = self.get_connection_key(project_id, environment)
            try:
                exists = await redis_manager.client.exists(f"ws:routing:{key}")
                return exists > 0
            except Exception as e:
                logger.warning(f"Failed to check Redis for routing {key}: {e}")

        return False

    # ==================================================================
    # Message handling
    # ==================================================================

    def _resolve_project_for_connection(self, connection_id: str) -> tuple:
        """Return (project_id, environment) for a registered connection."""
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
            return await self._handle_register(connection_id, message, db, organization_id, user_id)

        elif message_type == "test_result":
            test_run_id = message.get("test_run_id")
            if test_run_id:
                self._result_store.resolve_test_result(test_run_id, message)
            await message_handler.handle_test_result_message(
                msg_project_id, msg_environment, message, db
            )
            return None

        elif message_type == "metric_result":
            metric_run_id = message.get("metric_run_id")
            if metric_run_id:
                self._result_store.resolve_metric_result(metric_run_id, message)
            return None

        elif message_type == "pong":
            await message_handler.handle_pong_message(msg_project_id, msg_environment)
            return None

        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None

    async def _handle_register(
        self,
        connection_id: str,
        message: Dict[str, Any],
        db: Optional[Session],
        organization_id: Optional[str],
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        """Process a ``register`` message."""
        reg_project_id = message.get("project_id") or ""
        reg_environment = message.get("environment") or ""

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

        if reg_project_id and reg_environment:
            await self.handle_registration(reg_project_id, reg_environment, message)
            return await message_handler.handle_register_message(
                project_id=reg_project_id,
                environment=reg_environment,
                message=message,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
            )

        logger.info(f"Metrics-only registration for connection {connection_id}")
        response = await message_handler.handle_register_message(
            project_id="",
            environment="",
            message=message,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )
        response["connection_id"] = connection_id
        return response

    async def _authorize_and_register(
        self,
        connection_id: str,
        project_id: str,
        environment: str,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Authorize the project and add routing for this connection."""
        context = self._contexts.get(connection_id)
        if not context:
            logger.error(f"No context for connection {connection_id}")
            return False

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

        key = self.get_connection_key(project_id, environment)
        pool = self._project_routing.setdefault(key, [])
        if connection_id not in pool:
            pool.append(connection_id)
        self._connection_projects.setdefault(connection_id, set()).add(key)

        if redis_manager.is_available:
            try:
                await redis_manager.client.setex(f"ws:routing:{key}", 30, self.worker_id)
            except Exception as e:
                logger.error(f"Failed to set Redis routing for {key}: {e}")

        return True

    # ==================================================================
    # Delegation to collaborators (preserves public API)
    # ==================================================================

    # --- ResultStore ---

    def get_test_result(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        return self._result_store.get_test_result(test_run_id)

    def cleanup_test_result(self, test_run_id: str) -> None:
        self._result_store.cleanup_test_result(test_run_id)

    def get_metric_result(self, metric_run_id: str) -> Optional[Dict[str, Any]]:
        return self._result_store.get_metric_result(metric_run_id)

    def cleanup_metric_result(self, metric_run_id: str) -> None:
        self._result_store.cleanup_metric_result(metric_run_id)

    # --- Dispatcher ---

    async def send_test_request(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        inputs: Dict[str, Any],
    ) -> bool:
        return await self._dispatcher.send_test_request(
            project_id, environment, test_run_id, function_name, inputs
        )

    async def send_and_await_result(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        inputs: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        return await self._dispatcher.send_and_await_result(
            project_id,
            environment,
            test_run_id,
            function_name,
            inputs,
            timeout,
        )

    async def send_metric_by_connection(
        self,
        connection_id: str,
        metric_run_id: str,
        metric_name: str,
        inputs: Dict[str, Any],
    ) -> bool:
        return await self._dispatcher.send_metric_by_connection(
            connection_id, metric_run_id, metric_name, inputs
        )

    async def send_and_await_metric_by_connection(
        self,
        connection_id: str,
        metric_run_id: str,
        metric_name: str,
        inputs: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        return await self._dispatcher.send_and_await_metric_by_connection(
            connection_id, metric_run_id, metric_name, inputs, timeout
        )

    # --- RpcBridge ---

    async def _listen_for_rpc_requests(self) -> None:
        return await self._rpc_bridge.listen()


# Global connection manager instance
connection_manager = ConnectionManager()
