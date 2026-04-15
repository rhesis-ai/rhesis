"""Dispatch layer for sending test/metric requests to SDK WebSockets."""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from fastapi import WebSocket

from rhesis.backend.app.services.connector.result_store import ResultStore
from rhesis.backend.app.services.connector.schemas import (
    ExecuteMetricMessage,
    ExecuteTestMessage,
)

logger = logging.getLogger(__name__)


class Dispatcher:
    """Sends test and metric execution requests to SDK connections.

    Resolves WebSockets via the shared routing/connection dicts and
    uses :class:`ResultStore` for send-and-await semantics.

    Args:
        connections: Shared ``connection_id -> WebSocket`` dict (read).
        project_routing: Shared ``project:env -> connection_id`` dict (read).
        result_store: The result store for event management and cleanup.
        get_connection_key: Callable that builds a ``project:env`` key.
    """

    def __init__(
        self,
        connections: Dict[str, WebSocket],
        project_routing: Dict[str, str],
        result_store: ResultStore,
        get_connection_key: Callable[[str, str], str],
    ) -> None:
        self._connections = connections
        self._project_routing = project_routing
        self._result_store = result_store
        self._get_connection_key = get_connection_key

    # ------------------------------------------------------------------
    # WebSocket resolution
    # ------------------------------------------------------------------

    def _resolve_websocket(
        self, project_id: str, environment: str
    ) -> Optional[WebSocket]:
        """Resolve the WebSocket for a project:env via the routing table."""
        key = self._get_connection_key(project_id, environment)
        conn_id = self._project_routing.get(key)
        if not conn_id:
            return None
        return self._connections.get(conn_id)

    # ------------------------------------------------------------------
    # Test dispatch
    # ------------------------------------------------------------------

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
            key = self._get_connection_key(project_id, environment)
            logger.debug(
                f"No local WebSocket for {key} - may be on another instance"
            )
            return False

        message = ExecuteTestMessage(
            test_run_id=test_run_id,
            function_name=function_name,
            inputs=inputs,
        )

        try:
            await websocket.send_json(message.model_dump())
            key = self._get_connection_key(project_id, environment)
            logger.info(f"Sent test request to {key}: {function_name}")
            return True
        except Exception as e:
            key = self._get_connection_key(project_id, environment)
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
        """Send test request and wait for the result.

        Returns:
            Result dictionary or an error dict on timeout / send failure.
        """
        event = self._result_store.create_event(test_run_id)

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

            result = self._result_store.get_test_result(test_run_id)
            if result:
                logger.debug(f"Received SDK result for {test_run_id}")
                self._result_store.cleanup_test_result(test_run_id)
                return result

            return {
                "error": "send_failed",
                "details": "Event fired but no result stored",
            }

        except asyncio.TimeoutError:
            self._result_store.cleanup_test_result(test_run_id)
            logger.error(f"Timeout waiting for SDK result: {test_run_id}")
            return {"error": "timeout"}

        finally:
            self._result_store.remove_event(test_run_id)

    # ------------------------------------------------------------------
    # Metric dispatch
    # ------------------------------------------------------------------

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
            logger.info(
                f"Sent metric request to conn:{connection_id}: {metric_name}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error sending metric to conn:{connection_id}: {e}"
            )
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
        event = self._result_store.create_event(metric_run_id)

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
                        "Failed to send metric message to SDK "
                        f"(connection {connection_id})"
                    ),
                }

            await asyncio.wait_for(event.wait(), timeout=timeout)

            result = self._result_store.get_metric_result(metric_run_id)
            if result:
                logger.debug(f"Received metric result for {metric_run_id}")
                self._result_store.cleanup_metric_result(metric_run_id)
                return result

            return {
                "error": "send_failed",
                "details": "Event fired but no metric result stored",
            }

        except asyncio.TimeoutError:
            self._result_store.cleanup_metric_result(metric_run_id)
            logger.error(
                f"Timeout waiting for metric result: {metric_run_id}"
            )
            return {"error": "timeout"}

        finally:
            self._result_store.remove_event(metric_run_id)
