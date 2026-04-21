"""Redis-based RPC bridge for cross-instance SDK invocations."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

from fastapi import WebSocket
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rhesis.backend.app.services.connector.redis_client import redis_manager
from rhesis.backend.app.services.connector.schemas import (
    ExecuteMetricMessage,
    ExecuteTestMessage,
)

logger = logging.getLogger(__name__)


class RpcBridge:
    """Listens for Redis RPC requests and forwards them to local WebSockets.

    This is the backend-side counterpart to :class:`SDKRpcClient`
    (``rpc_client.py``).  Celery workers push requests into a
    worker-specific Redis queue; this bridge pops them and dispatches
    to the correct local WebSocket connection.

    Args:
        worker_id: Unique identifier for this backend process.
        connections: Shared ``connection_id -> WebSocket`` dict (read).
        resolve_route: Callable ``(project_id, environment) -> Optional[connection_id]``
            that round-robin selects a live connection.
        get_connection_key: Callable that builds a ``project:env`` key.
        remove_connection_route: Callback ``(key, connection_id)`` to
            remove a single stale connection from the routing pool.
    """

    def __init__(
        self,
        worker_id: str,
        connections: Dict[str, WebSocket],
        resolve_route: Callable[[str, str], Optional[str]],
        get_connection_key: Callable[[str, str], str],
        remove_connection_route: Callable[[str, str], None],
    ) -> None:
        self._worker_id = worker_id
        self._connections = connections
        self._resolve_route = resolve_route
        self._get_connection_key = get_connection_key
        self._remove_connection_route = remove_connection_route

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def listen(self) -> None:
        """Long-running loop that consumes RPC requests from Redis.

        Uses tenacity for exponential backoff (max 10 attempts) to
        prevent infinite crash loops.
        """
        if not redis_manager.is_available:
            logger.warning("Redis not available, RPC listener not started")
            return

        worker_channel = f"ws:rpc:{self._worker_id}"
        logger.info(
            f"RPC LISTENER STARTED - Listening on '{worker_channel}' "
            f"channel for direct-routed SDK invocations"
        )

        try:
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
                                result = await redis_manager.client.blpop(worker_channel, timeout=1)
                                if result:
                                    _, message = result
                                    try:
                                        request = json.loads(message)
                                        await self._handle_rpc_request(request)
                                    except Exception as e:
                                        logger.error(
                                            f"Error handling RPC request: {e}",
                                            exc_info=True,
                                        )
                            except asyncio.CancelledError:
                                logger.info("RPC listener cancelled, shutting down")
                                raise
                            except Exception as e:
                                logger.error(
                                    f"Error in RPC listener loop: {e}",
                                    exc_info=True,
                                )

                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        attempt_num = attempt.retry_state.attempt_number
                        logger.error(
                            f"RPC listener crashed (attempt {attempt_num}/10): {e}",
                            exc_info=True,
                        )
                        if attempt_num < 10:
                            logger.warning("RPC listener will retry with exponential backoff...")
                        raise

            logger.error(
                "RPC listener failed 10 times. Giving up on automatic "
                "restarts. Manual intervention required."
            )

        finally:
            logger.debug("RPC listener shutdown complete")

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    async def _handle_rpc_request(self, request: Dict[str, Any]) -> None:
        """Handle RPC request from a Celery worker.

        Supports two dispatch modes:
        - **project:env** -- test execution and project-scoped metrics
        - **connection_id** -- connection-scoped metrics (no project needed)
        """
        request_id = request.get("request_id")
        request_type = request.get("request_type", "execute_test")
        inputs = request.get("inputs", {})
        name = request.get("function_name") or request.get("metric_name", "")
        logger.debug(f"RPC request received: {request_id} - {name} (type={request_type})")

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
            await self._forward_metric_to_sdk(request_id, conn_id, conn_id, websocket, name, inputs)
            return

        project_id = request.get("project_id")
        environment = request.get("environment")
        routed_conn_id = self._resolve_route(project_id, environment)

        if not routed_conn_id or routed_conn_id not in self._connections:
            key = self._get_connection_key(project_id, environment)
            logger.error(f"Worker routing mismatch: RPC for {key} but connection not found.")
            await self._publish_error_response(
                request_id, key, f"Worker routing mismatch for {key}"
            )
            return

        key = self._get_connection_key(project_id, environment)
        websocket = self._connections[routed_conn_id]

        if request_type == "execute_metric":
            await self._forward_metric_to_sdk(
                request_id, key, routed_conn_id, websocket, name, inputs
            )
        else:
            await self._forward_to_sdk(request_id, key, routed_conn_id, websocket, name, inputs)

    # ------------------------------------------------------------------
    # Forwarding helpers
    # ------------------------------------------------------------------

    async def _forward_to_sdk(
        self,
        request_id: str,
        project_env_key: str,
        connection_id: str,
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
        await self._forward_message_to_sdk(
            request_id=request_id,
            key=project_env_key,
            connection_id=connection_id,
            websocket=websocket,
            message=message,
            call_name=function_name,
            is_metric=False,
        )

    async def _forward_metric_to_sdk(
        self,
        request_id: str,
        project_env_key: str,
        connection_id: str,
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
        await self._forward_message_to_sdk(
            request_id=request_id,
            key=project_env_key,
            connection_id=connection_id,
            websocket=websocket,
            message=message,
            call_name=metric_name,
            is_metric=True,
        )

    async def _forward_message_to_sdk(
        self,
        request_id: str,
        key: str,
        connection_id: str,
        websocket: WebSocket,
        message: BaseModel,
        call_name: str,
        is_metric: bool,
    ) -> None:
        """Forward an RPC message to SDK with shared error handling."""
        request_prefix = "metric " if is_metric else ""
        failure_details = (
            "Failed to forward metric to WebSocket"
            if is_metric
            else "Failed to forward to WebSocket"
        )

        try:
            logger.info(f"Forwarding {request_prefix}RPC request {request_id} ({call_name}) to SDK")
            await websocket.send_json(message.model_dump())
        except Exception as e:
            logger.error(f"Error forwarding {request_prefix}RPC request {request_id}: {e}")
            await self._cleanup_stale_routing(key, connection_id)
            await self._publish_error_response(
                request_id,
                key,
                f"{failure_details}: {e}",
            )

    # ------------------------------------------------------------------
    # Error / cleanup helpers
    # ------------------------------------------------------------------

    async def _publish_error_response(self, request_id: str, key: str, details: str) -> None:
        """Publish error response to RPC client via Redis."""
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

    async def _cleanup_stale_routing(self, project_env_key: str, connection_id: str) -> None:
        """Remove a stale connection from the routing pool.

        Called when a send fails, indicating the underlying connection
        is broken.  Only deletes the Redis routing key when no other
        connections remain in the pool.
        """
        logger.warning(f"Removing stale connection {connection_id} from route {project_env_key}")

        self._remove_connection_route(project_env_key, connection_id)
