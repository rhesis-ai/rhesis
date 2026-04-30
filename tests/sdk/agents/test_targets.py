"""Tests for LocalEndpointTarget."""

import pytest

from rhesis.sdk.agents.targets import LocalEndpointTarget
from rhesis.sdk.targets import TargetResponse


@pytest.mark.unit
class TestLocalEndpointTargetInit:
    """Test LocalEndpointTarget initialization and properties."""

    def test_properties(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-123",
            invoke_fn=lambda eid, data: {"output": "hi"},
            name="My Chatbot",
            endpoint_description="A helpful bot",
        )
        assert target.target_type == "endpoint"
        assert target.target_id == "ep-123"
        assert "My Chatbot" in target.description
        assert "A helpful bot" in target.description

    def test_defaults(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-456",
            invoke_fn=lambda eid, data: {"output": "ok"},
        )
        assert target.target_id == "ep-456"
        assert "ep-456" in target.description

    def test_validate_configuration_valid(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-123",
            invoke_fn=lambda eid, data: {"output": "ok"},
        )
        is_valid, error = target.validate_configuration()
        assert is_valid is True
        assert error is None

    def test_validate_configuration_missing_id(self):
        target = LocalEndpointTarget(
            endpoint_id="",
            invoke_fn=lambda eid, data: {"output": "ok"},
        )
        is_valid, error = target.validate_configuration()
        assert is_valid is False
        assert "Endpoint ID" in error

    def test_validate_configuration_bad_fn(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-123",
            invoke_fn="not callable",
        )
        is_valid, error = target.validate_configuration()
        assert is_valid is False
        assert "callable" in error

    def test_get_tool_documentation(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-123",
            invoke_fn=lambda eid, data: {"output": "ok"},
            name="File Chatbot",
        )
        doc = target.get_tool_documentation()
        assert "File Chatbot" in doc
        assert "ep-123" in doc


@pytest.mark.unit
class TestLocalEndpointTargetSendMessage:
    """Test LocalEndpointTarget.send_message()."""

    def test_success(self):
        def invoke(eid, data):
            return {
                "output": f"Response to: {data['input']}",
                "conversation_id": "conv-1",
            }

        target = LocalEndpointTarget(endpoint_id="ep-1", invoke_fn=invoke)
        resp = target.send_message("Hello")

        assert resp.success is True
        assert "Response to: Hello" in resp.content
        assert resp.conversation_id == "conv-1"

    def test_passes_conversation_id(self):
        received = {}

        def invoke(eid, data):
            received.update(data)
            return {"output": "ok"}

        target = LocalEndpointTarget(endpoint_id="ep-1", invoke_fn=invoke)
        target.send_message("Hi", conversation_id="conv-42")

        assert received["conversation_id"] == "conv-42"

    def test_empty_message_rejected(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-1",
            invoke_fn=lambda eid, data: {"output": "ok"},
        )
        resp = target.send_message("")
        assert resp.success is False
        assert "empty" in resp.error.lower()

    def test_whitespace_only_message_rejected(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-1",
            invoke_fn=lambda eid, data: {"output": "ok"},
        )
        resp = target.send_message("   ")
        assert resp.success is False

    def test_invoke_returns_none(self):
        target = LocalEndpointTarget(
            endpoint_id="ep-1",
            invoke_fn=lambda eid, data: None,
        )
        resp = target.send_message("Hello")
        assert resp.success is False
        assert "None" in resp.error

    def test_invoke_raises_exception(self):
        def bad_invoke(eid, data):
            raise ConnectionError("timeout")

        target = LocalEndpointTarget(endpoint_id="ep-1", invoke_fn=bad_invoke)
        resp = target.send_message("Hello")
        assert resp.success is False
        assert "timeout" in resp.error

    def test_passes_endpoint_id_to_invoke(self):
        received_eid = []

        def invoke(eid, data):
            received_eid.append(eid)
            return {"output": "ok"}

        target = LocalEndpointTarget(endpoint_id="ep-specific", invoke_fn=invoke)
        target.send_message("Hi")

        assert received_eid == ["ep-specific"]
