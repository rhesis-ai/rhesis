"""RPC client for workers to invoke SDK functions via backend's WebSocket connections."""

import asyncio
import json
import logging
import os
from typing import Any, Dict

import redis.asyncio as redis

logger = logging.getLogger(__name__)


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
        if not self._redis:
            logger.error("Redis not initialized for RPC call")
            return {"error": "send_failed", "details": "Redis not initialized"}

        # Normalize environment to lowercase for consistent key lookup
        environment = environment.lower()
        connection_id = f"{project_id}:{environment}"

        # Check if any worker has the connection (for direct routing)
        routing_key = f"ws:routing:{connection_id}"
        try:
            worker_id = await self._redis.get(routing_key)
        except Exception as e:
            logger.error(f"Failed to check worker routing for {connection_id}: {e}")
            return {"error": "send_failed", "details": f"Failed to check routing: {e}"}

        if not worker_id:
            # No worker has connection - fail immediately instead of waiting for timeout
            logger.error(f"SDK connection {connection_id} is not available (no worker registered)")
            return {"error": "sdk_disconnected", "details": f"No connection for {connection_id}"}

        # Route directly to the specific worker
        worker_channel = f"ws:rpc:{worker_id}"

        # Subscribe to response channel first
        pubsub = self._redis.pubsub()
        response_channel = f"ws:rpc:response:{test_run_id}"

        try:
            await pubsub.subscribe(response_channel)
            logger.debug(f"Subscribed to response channel: {response_channel}")

            # Publish request to worker-specific channel
            request = {
                "request_id": test_run_id,
                "project_id": project_id,
                "environment": environment,
                "function_name": function_name,
                "inputs": inputs,
            }

            await self._redis.rpush(worker_channel, json.dumps(request))
            logger.debug(
                f"Routed RPC request {test_run_id} to worker {worker_id} ({function_name})"
            )

            # Wait for response with timeout
            async def _wait_for_response():
                """Helper to wait for RPC response message."""
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        result = json.loads(message["data"])

                        # With direct routing, we expect a proper response
                        if "status" in result or "error" in result:
                            await pubsub.unsubscribe(response_channel)
                            return result
                        else:
                            # Unknown response format - log and return
                            logger.warning(f"Unexpected response format: {result}")
                            await pubsub.unsubscribe(response_channel)
                            return result

            try:
                # Use wait_for for Python 3.10 compatibility
                result = await asyncio.wait_for(_wait_for_response(), timeout=timeout)
                return result
            except asyncio.TimeoutError:
                logger.error(f"RPC request timed out after {timeout}s: {test_run_id}")
                await pubsub.unsubscribe(response_channel)
                return {"error": "timeout"}

        except Exception as e:
            logger.error(f"Error during RPC call for {test_run_id}: {e}")
            return {"error": "send_failed", "details": str(e)}
        finally:
            await pubsub.close()

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
        if not self._redis:
            return {
                "error": "send_failed",
                "details": "Redis not initialized",
            }

        environment = environment.lower()
        routing_key = f"ws:routing:{project_id}:{environment}"
        try:
            worker_id = await self._redis.get(routing_key)
        except Exception as e:
            return {
                "error": "send_failed",
                "details": f"Failed to check routing: {e}",
            }

        if not worker_id:
            return {
                "error": "sdk_disconnected",
                "details": (f"No connection for {project_id}:{environment}"),
            }

        worker_channel = f"ws:rpc:{worker_id}"
        pubsub = self._redis.pubsub()
        response_channel = f"ws:rpc:response:{metric_run_id}"

        try:
            await pubsub.subscribe(response_channel)

            request = {
                "request_id": metric_run_id,
                "request_type": "execute_metric",
                "project_id": project_id,
                "environment": environment,
                "metric_name": metric_name,
                "inputs": inputs,
            }

            await self._redis.rpush(worker_channel, json.dumps(request))

            async def _wait_for_response():
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        result = json.loads(message["data"])
                        await pubsub.unsubscribe(response_channel)
                        return result

            try:
                return await asyncio.wait_for(_wait_for_response(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"Metric RPC timed out after {timeout}s: {metric_run_id}")
                await pubsub.unsubscribe(response_channel)
                return {"error": "timeout"}

        except Exception as e:
            logger.error(f"Error during metric RPC for {metric_run_id}: {e}")
            return {"error": "send_failed", "details": str(e)}
        finally:
            await pubsub.close()

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
        if not self._redis:
            return {
                "error": "send_failed",
                "details": "Redis not initialized",
            }

        conn_key = f"ws:conn:{connection_id}"
        try:
            worker_id = await self._redis.get(conn_key)
        except Exception as e:
            logger.error(f"Failed to look up connection {connection_id}: {e}")
            return {
                "error": "send_failed",
                "details": f"Failed to check connection routing: {e}",
            }

        if not worker_id:
            return {
                "error": "sdk_disconnected",
                "details": f"No worker for connection {connection_id}",
            }

        worker_channel = f"ws:rpc:{worker_id}"
        pubsub = self._redis.pubsub()
        response_channel = f"ws:rpc:response:{metric_run_id}"

        try:
            await pubsub.subscribe(response_channel)

            request = {
                "request_id": metric_run_id,
                "request_type": "execute_metric",
                "connection_id": connection_id,
                "metric_name": metric_name,
                "inputs": inputs,
            }

            await self._redis.rpush(worker_channel, json.dumps(request))
            logger.debug(
                f"Routed metric RPC {metric_run_id} to worker "
                f"{worker_id} via connection {connection_id}"
            )

            async def _wait_for_response():
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        result = json.loads(message["data"])
                        await pubsub.unsubscribe(response_channel)
                        return result

            try:
                return await asyncio.wait_for(_wait_for_response(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"Metric RPC timed out after {timeout}s: {metric_run_id}")
                await pubsub.unsubscribe(response_channel)
                return {"error": "timeout"}

        except Exception as e:
            logger.error(f"Error during metric RPC for {metric_run_id}: {e}")
            return {"error": "send_failed", "details": str(e)}
        finally:
            await pubsub.close()
