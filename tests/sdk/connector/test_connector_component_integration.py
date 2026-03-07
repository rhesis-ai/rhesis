"""Component-level integration tests for SDK connector over WebSocket.

These tests run in-process with a lightweight fake backend WebSocket server.
They validate real connector behavior (connect, register, execute metric)
without requiring Docker or a real backend stack.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
import websockets

from rhesis.sdk.connector.manager import ConnectorManager
from rhesis.sdk.connector.types import MessageType


@dataclass
class FakeConnectorBackend:
    """Minimal in-process backend for connector protocol testing."""

    port: int = 0
    register_event: asyncio.Event = field(default_factory=asyncio.Event)
    metric_result_event: asyncio.Event = field(default_factory=asyncio.Event)
    test_result_event: asyncio.Event = field(default_factory=asyncio.Event)
    received_messages: list[dict[str, Any]] = field(default_factory=list)
    _server: Any | None = None
    _websocket: Any = None

    async def start(self) -> None:
        """Start WebSocket server on a random available port."""

        async def handler(websocket):
            self._websocket = websocket
            await websocket.send(
                json.dumps(
                    {
                        "type": MessageType.CONNECTED.value,
                        "status": "success",
                        "connection_id": "test-connection-id",
                    }
                )
            )

            async for raw_message in websocket:
                message = json.loads(raw_message)
                self.received_messages.append(message)

                msg_type = message.get("type")
                if msg_type == MessageType.REGISTER.value:
                    self.register_event.set()
                    await websocket.send(
                        json.dumps({"type": MessageType.REGISTERED.value, "status": "success"})
                    )
                elif msg_type == MessageType.METRIC_RESULT.value:
                    self.metric_result_event.set()
                elif msg_type == MessageType.TEST_RESULT.value:
                    self.test_result_event.set()

        self._server = await websockets.serve(handler, "127.0.0.1", 0)
        socket = self._server.sockets[0]
        self.port = socket.getsockname()[1]

    async def stop(self) -> None:
        """Stop WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def send_to_sdk(self, message: dict[str, Any]) -> None:
        """Send a backend message to connected SDK client."""
        if self._websocket is None:
            raise RuntimeError("SDK is not connected to fake backend")
        await self._websocket.send(json.dumps(message))

    def latest_message(self, message_type: str) -> dict[str, Any]:
        """Return the latest message by type."""
        for message in reversed(self.received_messages):
            if message.get("type") == message_type:
                return message
        raise AssertionError(f"No message of type '{message_type}' received")


@pytest_asyncio.fixture
async def fake_connector_backend():
    """Run a fake backend server for a test."""
    backend = FakeConnectorBackend()
    await backend.start()
    try:
        yield backend
    finally:
        await backend.stop()


@pytest.mark.asyncio
async def test_metric_registration_and_remote_execution(fake_connector_backend) -> None:
    """SDK connects, registers metrics, and returns metric_result for execute_metric."""
    manager = ConnectorManager(
        api_key="test-api-key",
        base_url=f"ws://127.0.0.1:{fake_connector_backend.port}",
    )

    def relevance_metric(input: str, output: str) -> dict[str, Any]:
        score = 1.0 if input.lower() in output.lower() else 0.0
        return {"score": score, "details": {"matched": score == 1.0}}

    manager.register_metric(
        "relevance_metric",
        relevance_metric,
        {
            "accepted_params": ["input", "output"],
            "score_type": "binary",
            "description": "Checks whether input appears in output",
        },
    )

    try:
        await asyncio.wait_for(fake_connector_backend.register_event.wait(), timeout=5)

        # Connection handshake confirms the SDK established a real WS connection.
        assert manager.connection_id == "test-connection-id"

        register_message = fake_connector_backend.latest_message(MessageType.REGISTER.value)
        assert len(register_message["metrics"]) == 1
        assert register_message["metrics"][0]["name"] == "relevance_metric"
        assert register_message["metrics"][0]["parameters"] == ["input", "output"]

        await fake_connector_backend.send_to_sdk(
            {
                "type": MessageType.EXECUTE_METRIC.value,
                "metric_run_id": "metric-run-123",
                "metric_name": "relevance_metric",
                "inputs": {
                    "input": "Weather",
                    "output": "Today's weather is sunny.",
                },
            }
        )

        await asyncio.wait_for(fake_connector_backend.metric_result_event.wait(), timeout=5)

        metric_result = fake_connector_backend.latest_message(MessageType.METRIC_RESULT.value)
        assert metric_result["metric_run_id"] == "metric-run-123"
        assert metric_result["status"] == "success"
        assert metric_result["score"] == 1.0
        assert metric_result["details"]["matched"] is True
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_endpoint_registration_and_remote_execution(fake_connector_backend) -> None:
    """SDK connects, registers functions, and returns test_result for execute_test."""
    manager = ConnectorManager(
        api_key="test-api-key",
        project_id="test-project",
        environment="development",
        base_url=f"ws://127.0.0.1:{fake_connector_backend.port}",
    )

    def add_numbers(x: int, y: int) -> int:
        return x + y

    manager.register_function(
        "add_numbers",
        add_numbers,
        {"description": "Adds two integers"},
    )

    try:
        await asyncio.wait_for(fake_connector_backend.register_event.wait(), timeout=5)

        register_message = fake_connector_backend.latest_message(MessageType.REGISTER.value)
        assert register_message["project_id"] == "test-project"
        assert register_message["environment"] == "development"
        assert len(register_message["functions"]) == 1
        assert register_message["functions"][0]["name"] == "add_numbers"
        assert register_message["functions"][0]["metadata"]["description"] == "Adds two integers"

        await fake_connector_backend.send_to_sdk(
            {
                "type": MessageType.EXECUTE_TEST.value,
                "test_run_id": "test-run-456",
                "function_name": "add_numbers",
                "inputs": {"x": 7, "y": 8},
            }
        )

        await asyncio.wait_for(fake_connector_backend.test_result_event.wait(), timeout=5)

        test_result = fake_connector_backend.latest_message(MessageType.TEST_RESULT.value)
        assert test_result["test_run_id"] == "test-run-456"
        assert test_result["status"] == "success"
        assert test_result["output"] == 15
        assert test_result["error"] is None
    finally:
        await manager.shutdown()
