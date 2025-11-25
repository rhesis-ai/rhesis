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
            self._redis = await redis.from_url(redis_url, decode_responses=True)
            logger.debug(f"RPC client connected to Redis: {redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for SDK RPC: {e}")
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
            logger.warning("🔴 RPC client Redis connection not initialized")
            return False

        try:
            key = f"ws:connection:{project_id}:{environment}"
            exists = await self._redis.exists(key)
            return exists > 0
        except Exception as e:
            logger.error(f"Error checking SDK connection status: {e}")
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
        Send RPC request to backend and await result.

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
            - {"error": "send_failed", "details": str}
        """
        if not self._redis:
            logger.error("❌ Redis not initialized for RPC call")
            return {"error": "send_failed", "details": "Redis not initialized"}

        # Subscribe to response channel first
        pubsub = self._redis.pubsub()
        response_channel = f"ws:rpc:response:{test_run_id}"

        try:
            await pubsub.subscribe(response_channel)
            logger.debug(f"Subscribed to response channel: {response_channel}")

            # Publish request
            request = {
                "request_id": test_run_id,
                "project_id": project_id,
                "environment": environment,
                "function_name": function_name,
                "inputs": inputs,
            }

            await self._redis.publish("ws:rpc:requests", json.dumps(request))
            logger.debug(f"Published RPC request: {test_run_id}")

            # Wait for response with timeout
            async def _wait_for_response():
                """Helper to wait for RPC response message."""
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        result = json.loads(message["data"])
                        await pubsub.unsubscribe(response_channel)
                        return result

            try:
                # Use wait_for for Python 3.10 compatibility
                result = await asyncio.wait_for(_wait_for_response(), timeout=timeout)
                logger.debug(f"Received RPC response: {test_run_id}")
                return result
            except asyncio.TimeoutError:
                logger.error(f"RPC request timed out after {timeout}s: {test_run_id}")
                await pubsub.unsubscribe(response_channel)
                return {"error": "timeout"}

        except Exception as e:
            logger.error(f"Error during RPC call: {e}", exc_info=True)
            return {"error": "send_failed", "details": str(e)}
        finally:
            await pubsub.close()
