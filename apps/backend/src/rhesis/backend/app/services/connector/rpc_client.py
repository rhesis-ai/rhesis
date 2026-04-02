"""RPC client for workers to invoke SDK functions via backend's WebSocket connections."""

import asyncio
import json
import logging
import os
import threading
from typing import Any, Dict

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-local RPC client
# ---------------------------------------------------------------------------
# With the coroutine/thread Celery pool each worker thread owns its own event
# loop (see batch/__init__.py:_thread_local).  redis.asyncio clients are tied
# to the event loop they were created on, so one client per thread is both
# correct and avoids the cost of creating a new connection + PING on every
# single test invocation (the old per-call pattern).
_tls = threading.local()


async def get_rpc_client() -> "SDKRpcClient":
    """Return the thread-local SDKRpcClient, initializing it on first access."""
    client: "SDKRpcClient | None" = getattr(_tls, "rpc_client", None)
    if client is None or client._redis is None:
        client = SDKRpcClient()
        await client.initialize()
        _tls.rpc_client = client
    return client


class SDKRpcClient:
    """Client for workers to make RPC calls to SDK functions via Redis."""

    def __init__(self):
        """Initialize RPC client."""
        self._redis = None

    async def initialize(self):
        """
        Initialize Redis connection for RPC.

        Raises:
            RuntimeError: If Redis connection fails
        """
        try:
            redis_url = os.getenv("BROKER_URL", "redis://localhost:6379/0")
            logger.info("🔌 Initializing RPC client with Redis")
            self._redis = await redis.from_url(redis_url, decode_responses=True)
            logger.info("✅ RPC client connected to Redis successfully")
            # Test the connection
            await self._redis.ping()
            logger.info("✅ Redis PING successful")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis for SDK RPC: {e}", exc_info=True)
            raise RuntimeError(f"Redis connection failed: {e}")

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    async def is_connected(self, project_id: str, environment: str) -> bool:
        """
        Check if SDK client is connected.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            True if SDK client is connected, False otherwise
        """
        if not self._redis:
            logger.error("RPC client Redis connection not initialized")
            return False

        try:
            environment = environment.lower()
            key = f"ws:routing:{project_id}:{environment}"
            exists = await self._redis.exists(key)
            return exists > 0
        except Exception as e:
            logger.error(f"Exception checking SDK connection status: {e}")
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
        Send RPC request to backend with direct worker routing and await result.

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Unique test run identifier
            function_name: SDK function to invoke
            inputs: Function inputs
            timeout: Timeout in seconds (default: 30.0)

        Returns:
            Result dictionary with one of:
            - {"status": "success", "output": {...}, "duration_ms": float}
            - {"status": "error", "error": str, "duration_ms": float}
            - {"error": "timeout"}
            - {"error": "sdk_disconnected"}
            - {"error": "send_failed", "details": str}
        """
        environment = environment.lower()
        connection_id = f"{project_id}:{environment}"
        routing_key = f"ws:routing:{connection_id}"
        request = {
            "request_id": test_run_id,
            "project_id": project_id,
            "environment": environment,
            "function_name": function_name,
            "inputs": inputs,
        }
        dispatch_context = f"({function_name})"
        return await self._send_and_await(
            routing_key=routing_key,
            request=request,
            run_id=test_run_id,
            timeout=timeout,
            disconnected_details=f"No connection for {connection_id}",
            dispatch_log_context=dispatch_context,
        )

    # --- Metric dispatch ---

    async def send_and_await_metric_result(
        self,
        project_id: str,
        environment: str,
        metric_run_id: str,
        metric_name: str,
        inputs: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Send metric RPC request routed via project:env.

        The receiving worker resolves the target WebSocket locally.
        """
        environment = environment.lower()
        routing_key = f"ws:routing:{project_id}:{environment}"
        request = {
            "request_id": metric_run_id,
            "request_type": "execute_metric",
            "project_id": project_id,
            "environment": environment,
            "metric_name": metric_name,
            "inputs": inputs,
        }
        return await self._send_and_await(
            routing_key=routing_key,
            request=request,
            run_id=metric_run_id,
            timeout=timeout,
            disconnected_details=f"No connection for {project_id}:{environment}",
        )

    async def send_and_await_metric_by_connection(
        self,
        connection_id: str,
        metric_run_id: str,
        metric_name: str,
        inputs: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Send a metric RPC request routed by connection_id.

        Uses ``ws:conn:{connection_id}`` to discover which worker
        holds the connection, then dispatches the request directly.

        Returns:
            Result dictionary or error dict.
        """
        conn_key = f"ws:conn:{connection_id}"
        request = {
            "request_id": metric_run_id,
            "request_type": "execute_metric",
            "connection_id": connection_id,
            "metric_name": metric_name,
            "inputs": inputs,
        }
        dispatch_context = f"via connection {connection_id}"
        return await self._send_and_await(
            routing_key=conn_key,
            request=request,
            run_id=metric_run_id,
            timeout=timeout,
            disconnected_details=f"No worker for connection {connection_id}",
            dispatch_log_context=dispatch_context,
        )

    async def _send_and_await(
        self,
        routing_key: str,
        request: Dict[str, Any],
        run_id: str,
        timeout: float,
        disconnected_details: str,
        dispatch_log_context: str = "",
    ) -> Dict[str, Any]:
        """Shared Redis RPC dispatch + response wait flow."""
        if not self._redis:
            logger.error("Redis not initialized for RPC call")
            return {"error": "send_failed", "details": "Redis not initialized"}

        try:
            worker_id = await self._redis.get(routing_key)
        except Exception as e:
            logger.error(f"Failed to check routing for {routing_key}: {e}")
            return {"error": "send_failed", "details": f"Failed to check routing: {e}"}

        if not worker_id:
            logger.error(f"SDK connection unavailable for {routing_key}")
            return {"error": "sdk_disconnected", "details": disconnected_details}

        worker_channel = f"ws:rpc:{worker_id}"
        response_channel = f"ws:rpc:response:{run_id}"
        pubsub = self._redis.pubsub()

        try:
            await pubsub.subscribe(response_channel)
            await self._redis.rpush(worker_channel, json.dumps(request))
            logger.debug(
                f"Routed RPC request {run_id} to worker {worker_id} {dispatch_log_context}"
            )

            async def _wait_for_response() -> Dict[str, Any]:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        result = json.loads(message["data"])
                        await pubsub.unsubscribe(response_channel)
                        if not isinstance(result, dict):
                            logger.warning(f"Unexpected response payload type: {type(result)!r}")
                            return {
                                "error": "send_failed",
                                "details": "Invalid response payload format",
                            }
                        if "status" not in result and "error" not in result:
                            logger.warning(f"Unexpected response format: {result}")
                        return result
                return {"error": "send_failed", "details": "Response stream ended unexpectedly"}

            return await asyncio.wait_for(_wait_for_response(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"RPC request timed out after {timeout}s: {run_id}")
            await pubsub.unsubscribe(response_channel)
            return {"error": "timeout"}
        except Exception as e:
            logger.error(f"Error during RPC call for {run_id}: {e}")
            return {"error": "send_failed", "details": str(e)}
        finally:
            await pubsub.close()
